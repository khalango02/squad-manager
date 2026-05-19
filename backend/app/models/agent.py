from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.auth.encryption import EncryptedText
from app.database import Base
from app.models.skill import agent_skills


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    md_content = Column(EncryptedText, default="")   # AES-128 encrypted at rest
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="agents")
    runs = relationship("AgentRun", back_populates="agent", cascade="all, delete-orphan")
    skills = relationship("Skill", secondary=agent_skills, lazy="select")
    outgoing = relationship(
        "AgentConnection",
        foreign_keys="AgentConnection.source_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    incoming = relationship(
        "AgentConnection",
        foreign_keys="AgentConnection.target_id",
        back_populates="target",
        cascade="all, delete-orphan",
    )
