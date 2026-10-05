from __future__ import annotations
import hashlib, json, time
from typing import Any, Callable, Dict, Optional
from finance_harness.contracts import ToolMetadata, ToolResultEnvelope, ToolStatus

def compute_evidence_hash(source: str, as_of: str, data: Any) -> str:
    raw = f"{source}:{as_of}:{json.dumps(data, sort_keys=True, default=str)}"
    return "ev_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

def wrap_tool_execution(source: str, as_of: str, func: Callable[..., Dict[str, Any]], *args: Any, published_at: Optional[str] = None, coverage: Optional[str] = None, **kwargs: Any) -> ToolResultEnvelope:
    fetch_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        raw_result = func(*args, **kwargs)
        if raw_result is None or (isinstance(raw_result, dict) and not raw_result):
            return ToolResultEnvelope(status=ToolStatus.NODATA, data=None, metadata=ToolMetadata(as_of=as_of, published_at=published_at, fetched_at=fetch_time, source=source, coverage=coverage, evidence_id=compute_evidence_hash(source, as_of, {})), error_message="No data returned")
        ev_id = compute_evidence_hash(source, as_of, raw_result)
        return ToolResultEnvelope(status=ToolStatus.SUCCESS, data=raw_result, metadata=ToolMetadata(as_of=as_of, published_at=published_at, fetched_at=fetch_time, source=source, coverage=coverage, evidence_id=ev_id))
    except ValueError as e:
        return ToolResultEnvelope(status=ToolStatus.BAD_PARAM, data=None, metadata=ToolMetadata(as_of=as_of, fetched_at=fetch_time, source=source, evidence_id=compute_evidence_hash(source, as_of, {"error": str(e)})), error_message=str(e))
    except Exception as e:
        return ToolResultEnvelope(status=ToolStatus.ERROR, data=None, metadata=ToolMetadata(as_of=as_of, fetched_at=fetch_time, source=source, evidence_id=compute_evidence_hash(source, as_of, {"error": str(e)})), error_message=str(e))

def compute_derived_metric(metric_name: str, numerator: float, denominator: float, as_of: str) -> ToolResultEnvelope:
    fetch_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if denominator == 0:
        return ToolResultEnvelope(status=ToolStatus.BAD_PARAM, data=None, metadata=ToolMetadata(as_of=as_of, fetched_at=fetch_time, source="derived_calculation", evidence_id=compute_evidence_hash("derived_calc", as_of, {"err": "div_zero"})), error_message="denominator is zero")
    val = numerator / denominator
    payload = {"metric": metric_name, "value": round(val, 6), "percentage": round(val * 100, 4)}
    return ToolResultEnvelope(status=ToolStatus.SUCCESS, data=payload, metadata=ToolMetadata(as_of=as_of, fetched_at=fetch_time, source="derived_calculation", coverage="arithmetic", evidence_id=compute_evidence_hash("derived_calc", as_of, payload)))
