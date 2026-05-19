import asyncio
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

import anthropic
import openai

from app.config import settings
from app.database import SessionLocal
from app.models import Agent, AgentRun

logger = logging.getLogger(__name__)

_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
_claude = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def _is_billing_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "credit balance" in msg or "insufficient_quota" in msg or "billing" in msg


def _sanitize_tool_name(name: str, agent_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:48]
    return f"agent_{safe}_{agent_id[-6:]}"


# ── Pub/sub ───────────────────────────────────────────────────────────────────

async def publish(run_id: str, event: dict) -> None:
    for q in list(_subscribers.get(run_id, [])):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


def subscribe(run_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=1000)
    _subscribers[run_id].append(q)
    return q


def unsubscribe(run_id: str, q: asyncio.Queue) -> None:
    subs = _subscribers.get(run_id, [])
    if q in subs:
        subs.remove(q)
    if not subs:
        _subscribers.pop(run_id, None)


# ── SSE stream ────────────────────────────────────────────────────────────────

async def sse_stream(
    run_id: str,
    initial_steps: list,
    initial_status: str,
    initial_output: str,
):
    for i, step in enumerate(initial_steps):
        yield f"data: {json.dumps({'type': 'step_update', 'step': step, 'index': i})}\n\n"

    if initial_status in ("done", "failed"):
        event_type = "done" if initial_status == "done" else "error"
        yield f"data: {json.dumps({'type': event_type, 'output': initial_output})}\n\n"
        return

    q = subscribe(run_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield 'data: {"type":"ping"}\n\n'
    finally:
        unsubscribe(run_id, q)


# ── DB helpers ────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_update(run_id: str, **fields) -> None:
    db = SessionLocal()
    try:
        db.query(AgentRun).filter(AgentRun.id == run_id).update(fields)
        db.commit()
    finally:
        db.close()


def _build_system_prompt(agent: Agent) -> str:
    parts = [agent.md_content or ""]
    for skill in agent.skills:
        if skill.content:
            parts.append(f"## Skill: {skill.name}\n{skill.content}")
    return "\n\n---\n\n".join(p for p in parts if p)


def _db_get_run_and_agent(run_id: str):
    """Returns (user_input, system_prompt, connected_agents) or (None, None, [])."""
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not run:
            return None, None, []

        agent = db.query(Agent).filter(Agent.id == run.agent_id).first()
        if not agent:
            return (run.input, "", [])

        system_prompt = _build_system_prompt(agent) or "You are a helpful assistant."

        connected = []
        for conn in agent.outgoing:
            target = conn.target
            if not target:
                continue
            connected.append({
                "id": str(target.id),
                "tool_name": _sanitize_tool_name(target.name, str(target.id)),
                "name": target.name,
                "description": target.description or "",
                "system_prompt": _build_system_prompt(target) or "You are a helpful assistant.",
            })

        return (run.input, system_prompt, connected)
    finally:
        db.close()


# ── LLM helpers ───────────────────────────────────────────────────────────────

async def _openai_stream(system_prompt: str, messages: list, output_parts: list, run_id: str, step_index: int) -> None:
    """Stream OpenAI response tokens into output_parts and publish to SSE."""
    _openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    oai_messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if isinstance(m.get("content"), str)
    ]
    stream = await _openai_client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=8096,
        messages=oai_messages,
        stream=True,
    )
    async for chunk in stream:
        text = chunk.choices[0].delta.content or ""
        if text:
            output_parts.append(text)
            await publish(run_id, {"type": "token", "content": text, "index": step_index})


async def _call_sub_agent(system_prompt: str, user_input: str) -> str:
    """Calls a connected agent and returns its full text response (no streaming)."""
    try:
        response = await _claude.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_input}],
        )
        return next(
            (block.text for block in response.content if hasattr(block, "text")),
            "",
        )
    except Exception as exc:
        if _is_billing_error(exc) and settings.openai_api_key:
            _openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            resp = await _openai_client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
            )
            return resp.choices[0].message.content or ""
        raise


# ── Agent execution ───────────────────────────────────────────────────────────

async def execute_run(run_id: str) -> None:
    try:
        user_input, system_prompt, connected_agents = await asyncio.to_thread(
            _db_get_run_and_agent, run_id
        )
        if user_input is None:
            return

        # ── Step 1: Loading context ───────────────────────────────────────
        step_load = {"name": "Carregando contexto", "status": "running",
                     "started_at": _now_iso(), "finished_at": None}
        steps = [step_load]
        await asyncio.to_thread(_db_update, run_id, status="running", steps=steps)
        await publish(run_id, {"type": "step_update", "step": step_load, "index": 0})
        await asyncio.sleep(0.3)

        step_load = {**step_load, "status": "done", "finished_at": _now_iso()}
        steps = [step_load]
        await asyncio.to_thread(_db_update, run_id, steps=steps)
        await publish(run_id, {"type": "step_update", "step": step_load, "index": 0})

        # ── Step 2: Processing ────────────────────────────────────────────
        step_proc = {"name": "Processando", "status": "running",
                     "started_at": _now_iso(), "finished_at": None}
        steps = [step_load, step_proc]
        await asyncio.to_thread(_db_update, run_id, steps=steps)
        await publish(run_id, {"type": "step_update", "step": step_proc, "index": 1})

        output_parts: list[str] = []

        # Build tool definitions from connected agents
        tool_defs = [
            {
                "name": ca["tool_name"],
                "description": (
                    f"Call agent '{ca['name']}'"
                    + (f": {ca['description']}" if ca["description"] else "")
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": "The task or question to send to this agent",
                        }
                    },
                    "required": ["input"],
                },
            }
            for ca in connected_agents
        ]
        tool_map = {ca["tool_name"]: ca for ca in connected_agents}

        try:
            used_fallback = False
            messages: list = [{"role": "user", "content": user_input}]
            call_steps: list[dict] = []  # steps added by agent-to-agent calls

            # ── Agentic loop (handles tool calls) ────────────────────────
            for iteration in range(10):  # max 10 tool-call rounds
                try:
                    async with _claude.messages.stream(
                        model=settings.claude_model,
                        max_tokens=8096,
                        system=system_prompt,
                        tools=tool_defs if tool_defs else anthropic.NOT_GIVEN,
                        messages=messages,
                    ) as stream:
                        async for text in stream.text_stream:
                            output_parts.append(text)
                            await publish(run_id, {"type": "token", "content": text, "index": 1})

                        final_msg = await stream.get_final_message()

                except Exception as exc:
                    if not _is_billing_error(exc) or not settings.openai_api_key:
                        raise
                    # Fallback to OpenAI (no tool use support in fallback)
                    logger.warning("Run %s: Anthropic billing error, falling back to OpenAI", run_id)
                    output_parts.clear()
                    used_fallback = True
                    await publish(run_id, {"type": "fallback", "provider": "openai"})
                    await _openai_stream(system_prompt, messages, output_parts, run_id, 1)
                    break  # OpenAI path done, no tool loop

                if final_msg.stop_reason != "tool_use":
                    break  # Claude finished naturally

                # ── Handle tool calls ─────────────────────────────────────
                tool_results = []
                for block in final_msg.content:
                    if block.type != "tool_use":
                        continue
                    ca = tool_map.get(block.name)
                    if not ca:
                        continue

                    step_call_idx = 2 + len(call_steps)
                    step_call = {
                        "name": f"Chamando: {ca['name']}",
                        "status": "running",
                        "started_at": _now_iso(),
                        "finished_at": None,
                    }
                    call_steps.append(step_call)
                    all_steps = [step_load, step_proc] + call_steps
                    await asyncio.to_thread(_db_update, run_id, steps=all_steps)
                    await publish(run_id, {
                        "type": "step_update", "step": step_call, "index": step_call_idx,
                    })

                    sub_input = block.input.get("input", "") if isinstance(block.input, dict) else ""
                    logger.info("Run %s: calling sub-agent '%s'", run_id, ca["name"])
                    sub_result = await _call_sub_agent(ca["system_prompt"], sub_input)

                    step_call = {**step_call, "status": "done", "finished_at": _now_iso()}
                    call_steps[-1] = step_call
                    all_steps = [step_load, step_proc] + call_steps
                    await asyncio.to_thread(_db_update, run_id, steps=all_steps)
                    await publish(run_id, {
                        "type": "step_update", "step": step_call, "index": step_call_idx,
                    })
                    await publish(run_id, {
                        "type": "agent_output",
                        "agent_id": ca["id"],
                        "agent_name": ca["name"],
                        "content": sub_result,
                    })

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": sub_result,
                    })

                messages.append({"role": "assistant", "content": final_msg.content})
                messages.append({"role": "user", "content": tool_results})

            # ── Finalize ──────────────────────────────────────────────────
            step_proc = {**step_proc, "status": "done", "finished_at": _now_iso()}
            full_output = "".join(output_parts)
            final_steps = [step_load, step_proc] + call_steps
            await asyncio.to_thread(
                _db_update, run_id,
                steps=final_steps,
                output=full_output,
                status="done",
                finished_at=datetime.now(timezone.utc),
            )
            await publish(run_id, {"type": "step_update", "step": step_proc, "index": 1})
            await publish(run_id, {"type": "done", "output": full_output})

        except Exception as exc:
            logger.exception("Run %s failed during LLM call: %s", run_id, exc)
            step_proc = {**step_proc, "status": "failed", "finished_at": _now_iso()}
            final_steps = [step_load, step_proc] + call_steps
            await asyncio.to_thread(
                _db_update, run_id,
                steps=final_steps,
                status="failed",
                finished_at=datetime.now(timezone.utc),
            )
            await publish(run_id, {"type": "step_update", "step": step_proc, "index": 1})
            await publish(run_id, {"type": "error", "message": str(exc)})

    except Exception as exc:
        logger.exception("Unexpected error in run %s: %s", run_id, exc)
        await publish(run_id, {"type": "error", "message": "Internal error"})
