from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class AgentConnection(Base):
    __tablename__ = "agent_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    target_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    label = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("Agent", foreign_keys=[source_id], back_populates="outgoing")
    target = relationship("Agent", foreign_keys=[target_id], back_populates="incoming")
