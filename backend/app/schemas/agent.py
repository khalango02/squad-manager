from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    md_content: str = Field(default="", max_length=500_000)


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    md_content: str | None = Field(default=None, max_length=500_000)


class AgentOut(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    md_content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
