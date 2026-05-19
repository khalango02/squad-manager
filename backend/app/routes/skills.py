from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.jwt import get_current_user
from app.database import get_db
from app.models import Agent, Skill, User
from app.schemas import SkillCreate, SkillOut, SkillUpdate

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/", response_model=list[SkillOut])
def list_skills(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Skill).filter(Skill.owner_id == current_user.id).order_by(Skill.created_at.desc()).all()


@router.post("/", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
def create_skill(
    payload: SkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skill = Skill(**payload.model_dump(), owner_id=current_user.id)
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


@router.get("/{skill_id}", response_model=SkillOut)
def get_skill(
    skill_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.owner_id == current_user.id).first()
    if not skill:
        raise HTTPException(404, "Skill not found")
    return skill


@router.patch("/{skill_id}", response_model=SkillOut)
def update_skill(
    skill_id: UUID,
    payload: SkillUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.owner_id == current_user.id).first()
    if not skill:
        raise HTTPException(404, "Skill not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(skill, field, value)
    db.commit()
    db.refresh(skill)
    return skill


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(
    skill_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.owner_id == current_user.id).first()
    if not skill:
        raise HTTPException(404, "Skill not found")
    db.delete(skill)
    db.commit()
