from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.jwt import get_current_user
from app.database import get_db
from app.models import Agent, AgentConnection, User
from app.schemas import ConnectionCreate, ConnectionOut

router = APIRouter(prefix="/connections", tags=["connections"])


def _assert_owns(agent_id: UUID, user_id: UUID, db: Session):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.owner_id == user_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return agent


@router.get("/", response_model=list[ConnectionOut])
def list_connections(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    owned_ids = [a.id for a in db.query(Agent.id).filter(Agent.owner_id == current_user.id)]
    return db.query(AgentConnection).filter(AgentConnection.source_id.in_(owned_ids)).all()


@router.post("/", response_model=ConnectionOut, status_code=status.HTTP_201_CREATED)
def create_connection(
    payload: ConnectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_owns(payload.source_id, current_user.id, db)
    _assert_owns(payload.target_id, current_user.id, db)
    conn = AgentConnection(**payload.model_dump())
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    owned_ids = [a.id for a in db.query(Agent.id).filter(Agent.owner_id == current_user.id)]
    conn = db.query(AgentConnection).filter(
        AgentConnection.id == connection_id,
        AgentConnection.source_id.in_(owned_ids),
    ).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    db.delete(conn)
    db.commit()
