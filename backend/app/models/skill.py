from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID

from app.auth.encryption import EncryptedText
from app.database import Base

agent_skills = Table(
    "agent_skills",
    Base.metadata,
    Column("agent_id", UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


class Skill(Base):
    __tablename__ = "skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    content = Column(EncryptedText, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
