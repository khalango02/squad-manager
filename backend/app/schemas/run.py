from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    input: str = Field(min_length=1, max_length=10_000)


class RunOut(BaseModel):
    id: UUID
    agent_id: UUID
    status: str
    steps: list[dict]
    output: str
    created_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}
