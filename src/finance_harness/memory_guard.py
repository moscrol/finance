from __future__ import annotations
import time, uuid
from typing import Dict, List, Optional
from finance_harness.contracts import ClaimCategory, MemoryLifecycleState, MemoryRecord, MemoryValidationState

class MemoryGuardError(Exception): pass

class MemoryStore:
    def __init__(self, allow_candidate_registration: bool = True):
        self._store: Dict[str, MemoryRecord] = {}
        self.allow_candidate_registration = allow_candidate_registration

    def register_candidate(self, content: str, category: ClaimCategory, source_baseline_id: Optional[str] = None) -> MemoryRecord:
        if not self.allow_candidate_registration:
            raise MemoryGuardError("Memory candidate registration is disabled by active policy.")
        mem_id = "mem_" + uuid.uuid4().hex[:10]
        rec = MemoryRecord(memory_id=mem_id, content=content, category=category, lifecycle_state=MemoryLifecycleState.CANDIDATE, validation_state=MemoryValidationState.UNVERIFIED, source_baseline_id=source_baseline_id)
        self._store[mem_id] = rec
        return rec

    def confirm_candidate(self, memory_id: str) -> MemoryRecord:
        rec = self._store.get(memory_id)
        if not rec: raise KeyError(f"Memory {memory_id} not found")
        if rec.lifecycle_state != MemoryLifecycleState.CANDIDATE:
            raise MemoryGuardError(f"Cannot confirm memory in state {rec.lifecycle_state}")
        rec.lifecycle_state = MemoryLifecycleState.CONFIRMED
        rec.confirmed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return rec

    def query_active_context(self, category: Optional[ClaimCategory] = None) -> List[MemoryRecord]:
        return [rec for rec in self._store.values() if rec.lifecycle_state == MemoryLifecycleState.CONFIRMED and (category is None or rec.category == category)]

    def list_pending_candidates(self) -> List[MemoryRecord]:
        return [rec for rec in self._store.values() if rec.lifecycle_state == MemoryLifecycleState.CANDIDATE]
