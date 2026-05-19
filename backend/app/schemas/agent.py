from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AgentCreate(BaseModel):
    name: str
    description: str | None = None
    md_content: str = ""


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    md_content: str | None = None


class AgentOut(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    md_content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
