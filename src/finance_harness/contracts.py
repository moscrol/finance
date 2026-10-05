from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ToolStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    NODATA = "NODATA"
    BAD_PARAM = "BAD_PARAM"
    TIMEOUT = "TIMEOUT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    ERROR = "ERROR"

class ToolMetadata(BaseModel):
    as_of: str
    published_at: Optional[str] = None
    fetched_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    source: str
    coverage: Optional[str] = None
    evidence_id: str

class ToolResultEnvelope(BaseModel):
    status: ToolStatus
    data: Optional[Dict[str, Any]] = None
    metadata: ToolMetadata
    error_message: Optional[str] = None
    @property
    def is_usable(self) -> bool:
        return self.status in (ToolStatus.SUCCESS, ToolStatus.PARTIAL) and self.data is not None

class ClaimCategory(str, Enum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    ASSUMPTION = "ASSUMPTION"

class ClaimItem(BaseModel):
    claim_id: str
    statement: str
    category: ClaimCategory
    evidence_ids: List[str] = Field(default_factory=list)
    falsification_conditions: List[str] = Field(default_factory=list)
    observable_signals: List[str] = Field(default_factory=list)
    next_check_date: Optional[str] = None

class ResearchBaseline(BaseModel):
    baseline_id: str
    subject: str
    as_of_date: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    claims: List[ClaimItem] = Field(default_factory=list)
    open_gaps: List[str] = Field(default_factory=list)

class DeltaStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    WEAKENED = "WEAKENED"
    UNCHANGED = "UNCHANGED"
    INCONCLUSIVE = "INCONCLUSIVE"

class ClaimDelta(BaseModel):
    claim_id: str
    status: DeltaStatus
    delta_evidence_ids: List[str] = Field(default_factory=list)
    reasoning: str
    revised_statement: Optional[str] = None

class TrackingDelta(BaseModel):
    tracking_id: str
    baseline_ref: str
    as_of_date: str
    deltas: List[ClaimDelta] = Field(default_factory=list)
    new_open_gaps: List[str] = Field(default_factory=list)

class MemoryLifecycleState(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"

class MemoryValidationState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VALIDATED = "VALIDATED"
    FALSIFIED = "FALSIFIED"
    INCONCLUSIVE = "INCONCLUSIVE"

class MemoryRecord(BaseModel):
    memory_id: str
    content: str
    category: ClaimCategory
    lifecycle_state: MemoryLifecycleState = MemoryLifecycleState.CANDIDATE
    validation_state: MemoryValidationState = MemoryValidationState.UNVERIFIED
    source_baseline_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    confirmed_at: Optional[str] = None
    falsification_notes: Optional[str] = None
