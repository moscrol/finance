"""A frozen research protocol for one system candidate, not a rule language."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from intelligence.services.methodology_backtest.labels import LABEL_SPEC, LABEL_VERSION

SHANGHAI = ZoneInfo("Asia/Shanghai")
EVALUATOR_VERSION = "date-equal-return-v1"
RULE_NAME = "dual_red_streak3_continuation.v1.json"
ARMS = ("universe", "dual_red", "streak3")
BOUNDARY = {
    "research_only": True,
    "decision_eligible": False,
    "promotion_eligible": False,
}


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def iso_date(value: str) -> str:
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("date must be YYYY-MM-DD")
    return value


def clock_now(now: datetime | None = None) -> datetime:
    result = now or datetime.now(timezone.utc)
    if result.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return result.astimezone(SHANGHAI)


def _check_seed(text: str) -> None:
    seed = json.loads(text)
    expected = {
        "rule_id": "dual_red_streak3_continuation",
        "version": 1,
        "scope": {"entity_type": "sector", "universe": "published_snapshot"},
        "condition": {
            "all": [
                {"label": "dual_red_strict", "op": "==", "value": True, "lag": 0},
                {"label": "dual_red_streak", "op": ">=", "value": 3, "lag": 0},
                {
                    "entity": "market",
                    "label": "market_stage",
                    "op": "in",
                    "value": ["主升", "反弹"],
                    "lag": 0,
                },
            ]
        },
        "outcome": {
            "target": "pct_chg",
            "horizons": [3, 5, 7, 10],
            "metrics": [
                "fwd_return",
                "max_return",
                "days_to_peak",
                "drawdown_after_peak",
            ],
            "success": {"metric": "fwd_return", "horizon": 5, "op": ">", "value": 0},
        },
        "baseline": {"kind": "same_universe_all_days"},
        "min_n": 20,
        "sharing": "shared",
        "owner": "system",
        "source_perspective": "系统内置：strategy1-matrix 严格双红口径",
    }
    if not isinstance(seed, dict) or set(seed) != set(expected) | {"title", "notes"}:
        raise ValueError("unsupported seed shape")
    if any(
        canonical_bytes(seed.get(k)) != canonical_bytes(v) for k, v in expected.items()
    ):
        raise ValueError(
            "only the fixed dual_red_streak3_continuation v1 candidate is supported"
        )
    if not all(isinstance(seed.get(k), str) for k in ("title", "notes")):
        raise ValueError("seed title and notes must be strings")


def _fixed_fields() -> dict:
    return {
        "schema_version": 1,
        "evaluator_version": EVALUATOR_VERSION,
        "label_version": LABEL_VERSION,
        "label_spec": json.loads(canonical_bytes(LABEL_SPEC)),
        "entity_type": "sector",
        "market_stages": ["主升", "反弹"],
        "required_inputs": [
            "sector_labels",
            "market_stage",
            "trading_calendar",
            "horizon5_outcomes_at_recheck",
        ],
        "pending_inputs": {
            "l2": "pending_sync",
            "evening_sellside": "pending_sync",
            "morning_briefing": "pending_sync",
        },
        "arms": {
            "universe": "all sectors on same date and market stage",
            "dual_red": "dual_red_strict == 1",
            "streak3": "dual_red_strict == 1 AND dual_red_streak >= 3",
        },
        "metric": {
            "name": "fwd_return",
            "horizon": 5,
            "window": "D+1..D+5",
            "unit": "percent",
            "calculation": "100 * (product(1 + pct_chg / 100) - 1)",
        },
        "secondary_metric": {
            "name": "drawdown_after_peak",
            "meaning": "peak-to-end drawdown, not maximum drawdown",
        },
        "aggregation": "equal dates; same-date means; all three arms nonempty; complete universe outcomes",
        "method_card": {
            "hypothesis": "主升/反弹期连续至少三日严格双红板块的后五日收益高于当日双红和全体板块",
            "observation_order": [
                "market_stage",
                "dual_red_strict",
                "dual_red_streak",
                "freeze_membership",
                "wait_D+5",
                "compare_date_means",
            ],
            "invalidation_conditions": [
                "共同日期收益差不为正时不支持该假设",
                "未知标签或结果不齐时暂停该日主对照",
                "样本重叠与重建标签不能支持推广或严格时点有效声明",
            ],
            "source": "system_candidate_not_personally_validated_knowhow",
        },
        **BOUNDARY,
    }


def _validate_content(content: dict, *, require_current: bool) -> None:
    fixed = _fixed_fields()
    if set(content) != set(fixed) | {"seed", "history", "forward_start"}:
        raise ValueError("invalid protocol fields")
    archived_versions = {"label_version", "label_spec", "evaluator_version"}
    for key, expected in fixed.items():
        if not require_current and key in archived_versions:
            continue
        if canonical_bytes(content[key]) != canonical_bytes(expected):
            raise ValueError("unsupported protocol contract or label version/spec")
    if (
        not all(
            isinstance(content[key], str) and content[key]
            for key in ("label_version", "evaluator_version")
        )
        or not isinstance(content["label_spec"], dict)
        or content["label_spec"].get("label_version") != content["label_version"]
    ):
        raise ValueError("invalid archived version/spec structure")
    if set(content["seed"]) != {"text", "sha256"} or set(content["history"]) != {
        "start",
        "end",
    }:
        raise ValueError("invalid seed/history fields")
    _check_seed(content["seed"]["text"])
    if (
        hashlib.sha256(content["seed"]["text"].encode("utf-8")).hexdigest()
        != content["seed"]["sha256"]
    ):
        raise ValueError("seed digest mismatch")
    start, end = (iso_date(content["history"][key]) for key in ("start", "end"))
    if not start <= end < iso_date(content["forward_start"]):
        raise ValueError("history must precede forward_start")
    canonical_bytes(content)


def _protocol_content(rule_path, *, history_start, history_end, forward_start) -> dict:
    if Path(rule_path).name != RULE_NAME:
        raise ValueError("unsupported rule filename")
    seed_text = Path(rule_path).read_text(encoding="utf-8")
    content = {
        **_fixed_fields(),
        "seed": {
            "text": seed_text,
            "sha256": hashlib.sha256(seed_text.encode("utf-8")).hexdigest(),
        },
        "history": {"start": iso_date(history_start), "end": iso_date(history_end)},
        "forward_start": iso_date(forward_start),
    }
    _validate_content(content, require_current=True)
    return content


def protocol_id_for(rule_path, *, history_start, history_end, forward_start) -> str:
    """Identify static semantics so an existing registration can be found at any date.

    This does not register a study or assert any creation time. A new registration
    must still pass ``build_protocol`` and its real-time registration gate.
    """
    return digest(
        _protocol_content(
            rule_path,
            history_start=history_start,
            history_end=history_end,
            forward_start=forward_start,
        )
    )


def build_protocol(
    rule_path, *, history_start, history_end, forward_start, now=None
) -> dict:
    current = clock_now(now)
    content = _protocol_content(
        rule_path,
        history_start=history_start,
        history_end=history_end,
        forward_start=forward_start,
    )
    protocol = {
        **content,
        "protocol_id": digest(content),
        "created_at": current.astimezone(timezone.utc).isoformat(timespec="seconds"),
    }
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol, *, require_current=True) -> None:
    """Verify immutable semantics/hash; archive readers may retain old versions.

    Computation callers keep the default current-version requirement. Disabling
    it permits reading historical evidence, never running a new evaluation.
    """
    try:
        if "protocol_id" not in protocol or "created_at" not in protocol:
            raise ValueError("invalid protocol fields")
        content = {
            k: v for k, v in protocol.items() if k not in ("protocol_id", "created_at")
        }
        _validate_content(content, require_current=require_current)
        created = clock_now(datetime.fromisoformat(protocol["created_at"]))
        if (
            not protocol["history"]["end"]
            <= created.date().isoformat()
            < protocol["forward_start"]
        ):
            raise ValueError(
                "history must end by registration day; forward_start must be after registration day"
            )
        if protocol["protocol_id"] != digest(content):
            raise ValueError("protocol digest mismatch")
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("invalid protocol") from exc
