"""历史 LLM 演练适配器：只读可验证的 replay 原件，保留 pit_grade / memory_bucket / arm / model。

原件 = 一份 JSON / JSONL 文件 + 它的 sha256。每条记录进入 ``ProbabilityForecast`` 时
``origin=historical_llm``、``mode=historical_llm``，**永不**改成 forward——历史演练与前向不混，
协议的 mode 不是 historical_llm 时直接拒绝整批。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from intelligence.services.research_validation.contracts import (
    ContractError,
    digest,
    is_probability,
    iso_date,
    market_close,
    utc_iso,
)

REQUIRED_FIELDS = ("as_of", "entity_id", "arm", "confidence_probability", "pit_grade", "memory_bucket", "model")


def load_replay_records(path: str | Path) -> tuple[list[dict[str, Any]], str]:
    """读 JSON 数组或 JSONL；返回 (records, 文件 sha256)。不解释、不修补。"""
    p = Path(path).expanduser()
    if p.is_symlink():
        raise ContractError("replay 原件不能是软链")
    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    records: list[dict[str, Any]]
    stripped = text.strip()
    if stripped.startswith("["):
        loaded = json.loads(stripped)
        if not isinstance(loaded, list):
            raise ContractError("replay 原件不是记录列表")
        records = [r for r in loaded if isinstance(r, dict)]
    else:
        records = [json.loads(line) for line in stripped.splitlines() if line.strip()]
        if any(not isinstance(r, dict) for r in records):
            raise ContractError("replay JSONL 含非对象行")
    return records, sha


def forecasts_from_replay(
    records: Iterable[Mapping[str, Any]],
    *,
    protocol: Mapping[str, Any],
    replay_source_hash: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """replay 记录 → ``register_forecasts`` 输入；返回 (inputs, skipped)。"""
    if protocol.get("mode") != "historical_llm":
        raise ContractError(f"协议 mode={protocol.get('mode')!r}：历史 LLM 概率只能进入 historical_llm study，不与前向混合")
    arm_ids = {a["arm_id"] for a in protocol["arms"]}
    inputs: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        missing = [k for k in REQUIRED_FIELDS if k not in record]
        if missing:
            skipped.append({"index": index, "reason": "missing_fields", "fields": missing})
            continue
        arm = str(record["arm"])
        if arm not in arm_ids:
            skipped.append({"index": index, "reason": "arm_unknown", "arm": arm})
            continue
        p = record["confidence_probability"]
        if not is_probability(p):
            skipped.append({"index": index, "reason": "invalid_probability", "p": repr(p)})
            continue
        try:
            as_of = iso_date(str(record["as_of"]), field_name="as_of")
        except ContractError:
            skipped.append({"index": index, "reason": "invalid_as_of", "as_of": record["as_of"]})
            continue
        inputs.append(
            {
                "entity_type": str(record.get("entity_type") or "sector"),
                "entity_id": str(record["entity_id"]),
                "as_of": as_of,
                "arm_id": arm,
                "p": float(p),
                "forecast_at": utc_iso(market_close(as_of)),
                "origin": "historical_llm",
                "pit_grade": str(record["pit_grade"]),
                "memory_bucket": str(record["memory_bucket"]),
                "model_id": str(record["model"]),
                "model_version": (str(record["model_version"]) if record.get("model_version") else None),
                "prompt_hash": (str(record["prompt_hash"]) if record.get("prompt_hash") else None),
                "input_refs": {
                    "replay_source_hash": replay_source_hash,
                    "record_hash": digest(dict(record)),
                    "replay_id": str(record.get("id") or index),
                },
                "capture_receipt_ref": (str(record["capture_receipt_ref"]) if record.get("capture_receipt_ref") else None),
            }
        )
    return inputs, skipped


__all__ = ["REQUIRED_FIELDS", "forecasts_from_replay", "load_replay_records"]
