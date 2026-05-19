from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.auth.encryption import EncryptedText
from app.database import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    input = Column(EncryptedText, nullable=False)
    output = Column(EncryptedText, default="")
    status = Column(String(20), default="queued")   # queued | running | done | failed
    steps = Column(JSON, default=list)              # [{name, status, started_at, finished_at}]
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    agent = relationship("Agent", back_populates="runs")
