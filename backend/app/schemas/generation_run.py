"""GenerationRun request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GenerationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    status: str
    total_items: int
    processed_items: int
    created_count: int
    warnings: list[str]
    failed_items: list[dict]
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime
