from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.jwt import get_current_user
from app.database import get_db
from app.models import Agent, AgentRun, User
from app.schemas import RunCreate, RunOut
from app.services.runner import execute_run, sse_stream

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("/agents/{agent_id}", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_run(
    agent_id: UUID,
    payload: RunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.owner_id == current_user.id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")

    run = AgentRun(
        agent_id=agent_id,
        owner_id=current_user.id,
        input=payload.input,
        steps=[],
        status="queued",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Pass the async coroutine directly — FastAPI/Starlette will await it
    # in the running event loop, allowing pub/sub queues to work correctly
    background_tasks.add_task(execute_run, str(run.id))
    return run


@router.get("/agents/{agent_id}", response_model=list[RunOut])
def list_runs(
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.owner_id == current_user.id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return (
        db.query(AgentRun)
        .filter(AgentRun.agent_id == agent_id)
        .order_by(AgentRun.created_at.desc())
        .limit(20)
        .all()
    )


@router.get("/{run_id}", response_model=RunOut)
def get_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.query(AgentRun).filter(
        AgentRun.id == run_id, AgentRun.owner_id == current_user.id
    ).first()
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.query(AgentRun).filter(
        AgentRun.id == run_id, AgentRun.owner_id == current_user.id
    ).first()
    if not run:
        raise HTTPException(404, "Run not found")

    initial_steps = list(run.steps or [])
    initial_status = run.status
    initial_output = run.output or ""

    return StreamingResponse(
        sse_stream(str(run_id), initial_steps, initial_status, initial_output),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
