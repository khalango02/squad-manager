import asyncio
import json
import logging
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


def _db_get_run_chain(run_id: str):
    """
    Returns (user_input, agent_chain) where agent_chain is an ordered list of
    agent dicts following the first outgoing connection at each step.
    """
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not run:
            return None, []

        chain = []
        visited: set[str] = set()
        current_id: str | None = str(run.agent_id)

        while current_id and current_id not in visited:
            visited.add(current_id)
            agent = db.query(Agent).filter(Agent.id == current_id).first()
            if not agent:
                break

            chain.append({
                "id": str(agent.id),
                "name": agent.name,
                "system_prompt": _build_system_prompt(agent) or "You are a helpful assistant.",
            })

            # Follow the first outgoing connection (linear chain)
            outgoing = sorted(agent.outgoing, key=lambda c: c.created_at)
            current_id = str(outgoing[0].target_id) if outgoing else None

        return (run.input, chain)
    finally:
        db.close()


# ── LLM helpers ───────────────────────────────────────────────────────────────

async def _openai_stream(
    system_prompt: str,
    user_input: str,
    output_parts: list[str],
    run_id: str,
    step_idx: int,
) -> None:
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    stream = await client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=8096,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        stream=True,
    )
    async for chunk in stream:
        text = chunk.choices[0].delta.content or ""
        if text:
            output_parts.append(text)
            await publish(run_id, {"type": "token", "content": text, "index": step_idx})


async def _call_agent_full(system_prompt: str, user_input: str) -> str:
    """Calls an agent without streaming (for non-first agents in the chain)."""
    try:
        response = await _claude.messages.create(
            model=settings.claude_model,
            max_tokens=8096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_input}],
        )
        return next(
            (block.text for block in response.content if hasattr(block, "text")),
            "",
        )
    except Exception as exc:
        if _is_billing_error(exc) and settings.openai_api_key:
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            resp = await client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=8096,
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
        user_input, agent_chain = await asyncio.to_thread(_db_get_run_chain, run_id)
        if not agent_chain:
            return

        # ── Step 0: Loading context ───────────────────────────────────────
        step_load = {
            "name": "Carregando contexto",
            "status": "running",
            "started_at": _now_iso(),
            "finished_at": None,
        }
        steps = [step_load]
        await asyncio.to_thread(_db_update, run_id, status="running", steps=steps)
        await publish(run_id, {"type": "step_update", "step": step_load, "index": 0})
        await asyncio.sleep(0.3)

        step_load = {**step_load, "status": "done", "finished_at": _now_iso()}
        steps = [step_load]
        await asyncio.to_thread(_db_update, run_id, steps=steps)
        await publish(run_id, {"type": "step_update", "step": step_load, "index": 0})

        # ── Pipeline: run each agent in chain ─────────────────────────────
        current_input = user_input
        final_output = ""

        try:
            for i, agent_info in enumerate(agent_chain):
                step_name = "Processando" if i == 0 else f"Chamando: {agent_info['name']}"
                step = {
                    "name": step_name,
                    "agent_id": agent_info["id"],
                    "status": "running",
                    "started_at": _now_iso(),
                    "finished_at": None,
                }
                step_idx = i + 1
                steps = steps[:step_idx] + [step]
                await asyncio.to_thread(_db_update, run_id, steps=steps)
                await publish(run_id, {"type": "step_update", "step": step, "index": step_idx})

                if i == 0:
                    # First agent: stream tokens live
                    output_parts: list[str] = []
                    try:
                        async with _claude.messages.stream(
                            model=settings.claude_model,
                            max_tokens=8096,
                            system=agent_info["system_prompt"],
                            messages=[{"role": "user", "content": current_input}],
                        ) as stream:
                            async for text in stream.text_stream:
                                output_parts.append(text)
                                await publish(run_id, {
                                    "type": "token",
                                    "content": text,
                                    "index": step_idx,
                                })
                    except Exception as exc:
                        if not _is_billing_error(exc) or not settings.openai_api_key:
                            raise
                        output_parts.clear()
                        await publish(run_id, {"type": "fallback", "provider": "openai"})
                        await _openai_stream(
                            agent_info["system_prompt"], current_input,
                            output_parts, run_id, step_idx,
                        )

                    agent_output = "".join(output_parts)

                else:
                    # Subsequent agents: run fully (output becomes next input)
                    agent_output = await _call_agent_full(
                        agent_info["system_prompt"], current_input
                    )

                # Publish this agent's completed output
                await publish(run_id, {
                    "type": "agent_output",
                    "agent_id": agent_info["id"],
                    "agent_name": agent_info["name"],
                    "content": agent_output,
                })

                step = {**step, "status": "done", "finished_at": _now_iso()}
                steps[step_idx] = step
                await asyncio.to_thread(_db_update, run_id, steps=steps)
                await publish(run_id, {"type": "step_update", "step": step, "index": step_idx})

                current_input = agent_output  # chain: this agent's output → next agent's input
                final_output = agent_output

            # ── Finalize ──────────────────────────────────────────────────
            await asyncio.to_thread(
                _db_update, run_id,
                steps=steps,
                output=final_output,
                status="done",
                finished_at=datetime.now(timezone.utc),
            )
            await publish(run_id, {"type": "done", "output": final_output})

        except Exception as exc:
            logger.exception("Run %s failed: %s", run_id, exc)
            failed_step = steps[-1] if steps else step_load
            failed_step = {**failed_step, "status": "failed", "finished_at": _now_iso()}
            steps[-1] = failed_step
            await asyncio.to_thread(
                _db_update, run_id,
                steps=steps,
                status="failed",
                finished_at=datetime.now(timezone.utc),
            )
            await publish(run_id, {"type": "step_update", "step": failed_step, "index": len(steps) - 1})
            await publish(run_id, {"type": "error", "message": str(exc)})

    except Exception as exc:
        logger.exception("Unexpected error in run %s: %s", run_id, exc)
        await publish(run_id, {"type": "error", "message": "Internal error"})
