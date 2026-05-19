from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ConnectionCreate(BaseModel):
    source_id: UUID
    target_id: UUID
    label: str = ""


class ConnectionOut(BaseModel):
    id: UUID
    source_id: UUID
    target_id: UUID
    label: str
    created_at: datetime

    model_config = {"from_attributes": True}
