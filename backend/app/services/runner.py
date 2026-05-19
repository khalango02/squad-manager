import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone

import anthropic

from app.config import settings
from app.database import SessionLocal
from app.models import Agent, AgentRun

logger = logging.getLogger(__name__)

# In-memory pub/sub: run_id -> list of subscriber queues
_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

_claude = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


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


# ── SSE stream generator ──────────────────────────────────────────────────────

async def sse_stream(
    run_id: str,
    initial_steps: list,
    initial_status: str,
    initial_output: str,
):
    # Replay existing state for clients that connect mid-run or after completion
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


# ── Agent execution ───────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def execute_run(run_id: str) -> None:
    db = SessionLocal()
    try:
        run: AgentRun = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not run:
            return
        agent: Agent = db.query(Agent).filter(Agent.id == run.agent_id).first()

        # ── Step 1: Loading context ───────────────────────────────────────
        step_load = {"name": "Carregando contexto", "status": "running", "started_at": _now_iso(), "finished_at": None}
        run.steps = [step_load]
        run.status = "running"
        db.commit()
        await publish(run_id, {"type": "step_update", "step": step_load, "index": 0})

        await asyncio.sleep(0.3)

        step_load = {**step_load, "status": "done", "finished_at": _now_iso()}
        run.steps = [step_load]
        db.commit()
        await publish(run_id, {"type": "step_update", "step": step_load, "index": 0})

        # ── Step 2: Processing ────────────────────────────────────────────
        step_proc = {"name": "Processando", "status": "running", "started_at": _now_iso(), "finished_at": None}
        run.steps = [step_load, step_proc]
        db.commit()
        await publish(run_id, {"type": "step_update", "step": step_proc, "index": 1})

        system_prompt = (agent.md_content or "").strip() or "You are a helpful assistant."
        user_input = run.input

        output_parts: list[str] = []
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

            step_proc = {**step_proc, "status": "done", "finished_at": _now_iso()}
            run.steps = [step_load, step_proc]
            run.output = "".join(output_parts)
            run.status = "done"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()

            await publish(run_id, {"type": "step_update", "step": step_proc, "index": 1})
            await publish(run_id, {"type": "done", "output": run.output})

        except Exception as exc:
            logger.exception("Run %s failed during Claude call: %s", run_id, exc)
            step_proc = {**step_proc, "status": "failed", "finished_at": _now_iso()}
            run.steps = [step_load, step_proc]
            run.status = "failed"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()

            await publish(run_id, {"type": "step_update", "step": step_proc, "index": 1})
            await publish(run_id, {"type": "error", "message": str(exc)})

    except Exception as exc:
        logger.exception("Unexpected error in run %s: %s", run_id, exc)
        await publish(run_id, {"type": "error", "message": "Internal error"})
    finally:
        db.close()
