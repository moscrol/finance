"""用户价值测量（05 轨）：ProductValueEvent → MeasurementReceipt → PilotSummary。

三件纯函数（``validate_event`` / ``measure_pair`` / ``summarize``）加两个只读
证据解析器。不落盘、不读环境变量、不调模型；生产存储与身份判定归 06。
"""

from intelligence.services.product_value.evidence import (
    EvidenceReader,
    InMemoryEvidenceReader,
    RunStoreEvidenceReader,
)
from intelligence.services.product_value.events import (
    PreparedEvents,
    ValidationResult,
    load_events_jsonl,
    prepare_events,
    validate_event,
)
from intelligence.services.product_value.measure import measure_pair
from intelligence.services.product_value.protocol import (
    ProtocolError,
    freeze_protocol,
    load_protocol,
    protocol_hash,
    validate_protocol,
)
from intelligence.services.product_value.summarize import summarize

__all__ = [
    "EvidenceReader",
    "InMemoryEvidenceReader",
    "PreparedEvents",
    "ProtocolError",
    "RunStoreEvidenceReader",
    "ValidationResult",
    "freeze_protocol",
    "load_events_jsonl",
    "load_protocol",
    "measure_pair",
    "prepare_events",
    "protocol_hash",
    "summarize",
    "validate_event",
    "validate_protocol",
]
