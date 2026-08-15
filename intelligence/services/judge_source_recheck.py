"""Optional numeric-claim recheck for the semantic judge (bookgap S2).

Default off.  When ``ASK_JUDGE_RECHECK`` is on, extract high-precision
numeric claims (one number + a date token) and compare them to a
read-only ``finance_query`` lookup.  Failures are ``recheck_unavailable``
and must not fail the judge.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from intelligence.services.finance_query import FinanceQuery, FinanceQuerySpec
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline

Verdict = Literal["match", "mismatch", "recheck_unavailable"]

_SENTENCE_SPLIT = re.compile(r"[。！？\n]+")
_NUMBER = re.compile(r"(-?\d+(?:\.\d+)?)")
_DATEISH = re.compile(
    r"今日|昨天|本周|本月|今年|\d{4}-\d{2}-\d{2}|\d{1,2}月\d{1,2}日"
)
_ABS_TOLERANCE = 0.05
PER_CLAIM_SECONDS = 3.0
TOTAL_RECHECK_SECONDS = 8.0


@dataclass(frozen=True)
class NumericClaim:
    text: str
    number: float


def recheck_enabled() -> bool:
    raw = os.environ.get("ASK_JUDGE_RECHECK", "off").strip().lower()
    return raw in {"on", "true", "1", "yes"}


def extract_numeric_claims(text: str) -> tuple[NumericClaim, ...]:
    """Precision-first: one number and a date token, or skip the sentence."""

    claims: list[NumericClaim] = []
    for raw in _SENTENCE_SPLIT.split(str(text or "")):
        sentence = raw.strip()
        if not sentence or _DATEISH.search(sentence) is None:
            continue
        numbers = _NUMBER.findall(sentence)
        if len(numbers) != 1:
            continue
        claims.append(NumericClaim(text=sentence, number=float(numbers[0])))
    return tuple(claims)


def compare_claim(claim: NumericClaim, source_value: float) -> Verdict:
    if abs(claim.number - source_value) <= _ABS_TOLERANCE:
        return "match"
    return "mismatch"


def recheck_draft(
    text: str,
    *,
    lookup: Callable[[NumericClaim], float | None] | None = None,
    per_claim_seconds: float = PER_CLAIM_SECONDS,
    total_seconds: float = TOTAL_RECHECK_SECONDS,
) -> list[dict[str, object]]:
    """Return ``{claim, source_value, verdict}`` rows.  Fail-open on errors."""

    deadline = time.monotonic() + max(0.0, float(total_seconds))
    reports: list[dict[str, object]] = []
    for claim in extract_numeric_claims(text):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            reports.append(_unavailable(claim, None))
            continue
        try:
            if lookup is not None:
                source = lookup(claim)
            else:
                source = _default_lookup(
                    claim,
                    timeout=min(float(per_claim_seconds), remaining),
                )
        except Exception:
            reports.append(_unavailable(claim, None))
            continue
        if source is None:
            reports.append(_unavailable(claim, None))
            continue
        reports.append(
            {
                "claim": claim.text,
                "source_value": source,
                "verdict": compare_claim(claim, source),
            }
        )
    return reports


def _unavailable(claim: NumericClaim, source: float | None) -> dict[str, object]:
    return {
        "claim": claim.text,
        "source_value": source,
        "verdict": "recheck_unavailable",
    }


def _default_lookup(claim: NumericClaim, *, timeout: float = PER_CLAIM_SECONDS) -> float | None:
    """Map a narrow claim shape onto read-only ``market_daily`` index return.

    Unparseable claims return ``None`` (unavailable), never invent a number.
    """

    if "涨幅" not in claim.text and "跌幅" not in claim.text:
        return None
    root = os.environ.get("FINANCE_WS", "").strip()
    if not root:
        return None
    from datetime import date as date_cls
    from pathlib import Path

    db_path = Path(root).expanduser() / "db" / "market_feature_store.duckdb"
    if not db_path.is_file():
        return None
    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "market_daily",
            "metrics": ["index_return_pct"],
            "dimensions": ["trade_date"],
            "filters": [],
            "group_by": [],
            "order_by": [{"field": "trade_date", "direction": "desc"}],
            "limit": 1,
        }
    )
    result = FinanceQuery(db_path).run(
        spec,
        information_cutoff=InformationCutoff(date_cls.today(), "requested"),
        deadline=ResearchDeadline.from_timeout(max(0.05, float(timeout))),
    )
    rows = list(result.rows or [])
    if not rows:
        return None
    raw = rows[0].get("index_return_pct")
    if raw is None:
        return None
    return float(raw)
