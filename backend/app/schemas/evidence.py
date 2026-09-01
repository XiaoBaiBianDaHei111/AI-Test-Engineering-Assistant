"""Evidence / TraceParse request/response schemas (Phase 6)."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class EvidenceKind(StrEnum):
    screenshot = "screenshot"
    trace = "trace"
    console = "console"
    network = "network"
    log = "log"


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    run_case_id: int | None
    kind: str
    file_path: str
    meta: dict
    created_at: datetime


class TraceParseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: int
    actions: list
    network: list
    console: list
    snapshots: list
    created_at: datetime
