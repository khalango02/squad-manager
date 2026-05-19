from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.jwt import get_current_user
from app.database import get_db
from app.models import Agent, Skill, User
from app.schemas import AgentCreate, AgentOut, AgentUpdate, SkillOut

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Agent).filter(Agent.owner_id == current_user.id).all()


@router.post("/", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = Agent(**payload.model_dump(), owner_id=current_user.id)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.owner_id == current_user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.owner_id == current_user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.owner_id == current_user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(agent)
    db.commit()


@router.get("/{agent_id}/skills", response_model=list[SkillOut])
def list_agent_skills(
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.owner_id == current_user.id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent.skills


@router.post("/{agent_id}/skills/{skill_id}", response_model=list[SkillOut], status_code=status.HTTP_200_OK)
def attach_skill(
    agent_id: UUID,
    skill_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.owner_id == current_user.id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.owner_id == current_user.id).first()
    if not skill:
        raise HTTPException(404, "Skill not found")
    if skill not in agent.skills:
        agent.skills.append(skill)
        db.commit()
    return agent.skills


@router.delete("/{agent_id}/skills/{skill_id}", response_model=list[SkillOut])
def detach_skill(
    agent_id: UUID,
    skill_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.owner_id == current_user.id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if skill and skill in agent.skills:
        agent.skills.remove(skill)
        db.commit()
    return agent.skills
