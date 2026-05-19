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


# ── DB helpers (sync, called via asyncio.to_thread) ──────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_update(run_id: str, **fields) -> None:
    db = SessionLocal()
    try:
        db.query(AgentRun).filter(AgentRun.id == run_id).update(fields)
        db.commit()
    finally:
        db.close()


def _db_get_run_and_agent(run_id: str):
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not run:
            return None, None
        agent = db.query(Agent).filter(Agent.id == run.agent_id).first()
        if not agent:
            return (run.input, "")
        parts = [agent.md_content or ""]
        for skill in agent.skills:
            if skill.content:
                parts.append(f"## Skill: {skill.name}\n{skill.content}")
        return (run.input, "\n\n---\n\n".join(p for p in parts if p))
    finally:
        db.close()


# ── Agent execution ───────────────────────────────────────────────────────────

async def execute_run(run_id: str) -> None:
    try:
        # Fetch data from DB in a thread (sync SQLAlchemy)
        user_input, agent_md = await asyncio.to_thread(_db_get_run_and_agent, run_id)
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

        system_prompt = (agent_md or "").strip() or "You are a helpful assistant."
        output_parts: list[str] = []

        try:
            try:
                async with _claude.messages.stream(
                    model=settings.claude_model,
                    max_tokens=8096,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_input}],
                ) as stream:
                    async for text in stream.text_stream:
                        output_parts.append(text)
                        await publish(run_id, {"type": "token", "content": text, "index": 1})

            except Exception as exc:
                if not _is_billing_error(exc) or not settings.openai_api_key:
                    raise

                logger.warning("Run %s: Anthropic billing error, falling back to OpenAI", run_id)
                output_parts.clear()
                await publish(run_id, {"type": "fallback", "provider": "openai"})

                _openai = openai.AsyncOpenAI(api_key=settings.openai_api_key)
                stream = await _openai.chat.completions.create(
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
                        await publish(run_id, {"type": "token", "content": text, "index": 1})

            step_proc = {**step_proc, "status": "done", "finished_at": _now_iso()}
            full_output = "".join(output_parts)
            await asyncio.to_thread(
                _db_update, run_id,
                steps=[step_load, step_proc],
                output=full_output,
                status="done",
                finished_at=datetime.now(timezone.utc),
            )
            await publish(run_id, {"type": "step_update", "step": step_proc, "index": 1})
            await publish(run_id, {"type": "done", "output": full_output})

        except Exception as exc:
            logger.exception("Run %s failed during LLM call: %s", run_id, exc)
            step_proc = {**step_proc, "status": "failed", "finished_at": _now_iso()}
            await asyncio.to_thread(
                _db_update, run_id,
                steps=[step_load, step_proc],
                status="failed",
                finished_at=datetime.now(timezone.utc),
            )
            await publish(run_id, {"type": "step_update", "step": step_proc, "index": 1})
            await publish(run_id, {"type": "error", "message": str(exc)})

    except Exception as exc:
        logger.exception("Unexpected error in run %s: %s", run_id, exc)
        await publish(run_id, {"type": "error", "message": "Internal error"})
