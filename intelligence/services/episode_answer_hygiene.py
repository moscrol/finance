"""Deterministic public-draft hygiene: unattempted claims and stub repair.

This module is the small stable side of the 2026-08-20 quality spec (INV-5 /
INV-7). It reads draft text and ``ProviderTrace`` receipts; it does not call
tools or an LLM. The semantic verifier invokes it around the judge. Q2 补枪 is
intentionally absent — coverage is classified here, the extra query is not.

Why a new module: ``episode_semantic_verifier`` is already a 3500-line judge
loop. The truth table below must stay reviewable without that loop. Same
shape as ``FallbackAttemptedDisclosureTests``: a claim about a source is
legal only when that source was actually attempted.

Capability names are the receipt field. ``news_search`` is a tool name;
traces record ``directional_news``. Matching the tool name would rewrite an
honest cutoff gap into a lie.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.task_frame import has_explicit_date, last_explicit_iso_date

# Live TaskFrame.question_type strings. Spec §6.2 used stock_analysis /
# market_review / causal_review / fermentation_trace; those are not in the
# current enum. Map to what ``_POLICY_BY_QUESTION_TYPE`` actually carries.
ASKED_DATE_COVERAGE_TYPES = frozenset(
    {
        "theme_analysis",
        "stock_deep_dive",
        "dated_market_review",
        "market_forecast",
        "market_cause",
        "news_impact",
        "theme_track",
        "market_watch",
    }
)

_SENTENCE_RE = re.compile(r"(?<=[。！？!?；;])|\n+")
_NEWS_GAP_RE = re.compile(
    r"(?:news|资讯).{0,48}(?:未返回|未检索|无检索)"
    r"|(?:未返回|未检索|无检索).{0,48}(?:news|资讯)",
    re.IGNORECASE,
)
_MISSING_DATA_RE = re.compile(r"(?:数据未取到|未取到)")
_DAY_ANCHOR_RE = re.compile(r"(?:当日|当天|这天)")
_NO_RETRIEVAL_RE = re.compile(
    r"本次未提供任何检索|retrieved_material\s*为空",
    re.IGNORECASE,
)
_CONFIGURE_CAPABILITIES = frozenset({"", "configure"})
_MIN_ROLLBACK_SENTENCES = 2
_MIN_ROLLBACK_CHARS = 80
_STUB_CHAR_RATIO = 0.2
# V2：本轮是否调过 KB 看 provider，不看 capability（成功路 capability=agent_loop）。
_KB_QUERY_PROVIDERS = frozenset({"agent:kb_search", "agent:evidence_search"})
_KB_ABSENCE_GAP_RE = re.compile(
    r"(?:缺公告级证据|知识库暂无|知识库无|库无|暂无公告级)"
)
_UNVERIFIED_QUALIFIER = "（本轮未查证知识库）"


@dataclass(frozen=True)
class UnattemptedClaim:
    capability: str
    asked_date: str | None
    snippet: str


def sentence_count(text: str) -> int:
    return sum(1 for raw in _SENTENCE_RE.split(str(text or "")) if raw.strip())


def iter_sentences(text: str) -> tuple[str, ...]:
    return tuple(
        raw.strip()
        for raw in _SENTENCE_RE.split(str(text or ""))
        if raw.strip()
    )


def date_aliases(iso_date: str | None) -> tuple[str, ...]:
    if not iso_date:
        return ()
    year, month, day = iso_date.split("-")
    month_i = int(month)
    day_i = int(day)
    return (
        iso_date,
        f"{year}年{month_i}月{day_i}日",
        f"{month_i}/{day_i}",
        f"{month_i:02d}/{day_i:02d}",
        f"{month_i}-{day_i}",
        f"{month_i:02d}-{day_i:02d}",
        f"{month_i}月{day_i}",
        f"{month_i}月{day_i}日",
    )


def _attempted(trace: ProviderTrace) -> bool:
    status = str(trace.status or "")
    if status and status != "not_attempted":
        return True
    blob = f"{trace.detail or ''} {trace.provider or ''}"
    return "tool_budget_exhausted" in blob


def _is_research_trace(trace: ProviderTrace) -> bool:
    capability = str(trace.capability or "").strip()
    if capability.lower() in _CONFIGURE_CAPABILITIES:
        return False
    if "configure" in str(trace.provider or "").lower():
        return False
    return _attempted(trace)


def _window_covers(trace: ProviderTrace, asked_date: str) -> bool:
    rng = trace.requested_time_range
    if rng is None:
        return False
    start, end = rng
    low = start or "0000-01-01"
    high = end or "9999-12-31"
    return low <= asked_date <= high


def _is_truncated(trace: ProviderTrace) -> bool:
    detail = str(trace.detail or "").lower()
    return "truncat" in detail or "截断" in detail


def has_directional_news_attempt(traces: tuple[ProviderTrace, ...]) -> bool:
    return any(
        trace.capability == "directional_news" and _attempted(trace)
        for trace in traces
    )


def covering_finance_query_traces(
    traces: tuple[ProviderTrace, ...],
    asked_date: str,
) -> tuple[ProviderTrace, ...]:
    return tuple(
        trace
        for trace in traces
        if trace.capability == "finance_query"
        and _attempted(trace)
        and _window_covers(trace, asked_date)
    )


def classify_asked_date_coverage(
    question: str,
    question_type: str,
    traces: tuple[ProviderTrace, ...],
) -> str:
    """INV-6 classifier. Does not fire a follow-up query (Q2 is deferred)."""

    if question_type not in ASKED_DATE_COVERAGE_TYPES or not has_explicit_date(
        question
    ):
        return "not_applicable"
    asked_date = last_explicit_iso_date(question)
    if asked_date is None:
        return "not_applicable"
    covering = covering_finance_query_traces(traces, asked_date)
    if not covering:
        return "missing"
    if any(_is_truncated(trace) for trace in covering):
        return "truncated"
    return "covered"


def find_unattempted_claims(
    text: str,
    traces: tuple[ProviderTrace, ...],
    *,
    asked_date: str | None,
) -> tuple[UnattemptedClaim, ...]:
    """Return gap claims that have no matching attempt receipt.

    Four states, not two: not called / empty / filtered by our own gate /
    truncated. Only the first is an unattempted claim. ``future_of_cutoff``
    and truncation count as attempted.
    """

    traces = tuple(traces or ())
    claims: list[UnattemptedClaim] = []
    news_ok = has_directional_news_attempt(traces)
    finance_ok = bool(
        asked_date and covering_finance_query_traces(traces, asked_date)
    )
    any_research = any(_is_research_trace(trace) for trace in traces)
    aliases = date_aliases(asked_date)

    for sentence in iter_sentences(text):
        if _NEWS_GAP_RE.search(sentence) and not news_ok:
            claims.append(
                UnattemptedClaim(
                    capability="directional_news",
                    asked_date=asked_date,
                    snippet=sentence,
                )
            )
            continue
        if _MISSING_DATA_RE.search(sentence) and (
            _DAY_ANCHOR_RE.search(sentence)
            or any(alias in sentence for alias in aliases)
        ):
            if asked_date and not finance_ok:
                claims.append(
                    UnattemptedClaim(
                        capability="finance_query",
                        asked_date=asked_date,
                        snippet=sentence,
                    )
                )
                continue
        if _NO_RETRIEVAL_RE.search(sentence) and not any_research:
            claims.append(
                UnattemptedClaim(
                    capability="research",
                    asked_date=asked_date,
                    snippet=sentence,
                )
            )
    return tuple(claims)


def rewrite_unattempted_claim(claim: UnattemptedClaim) -> str:
    date_part = f" {claim.asked_date}" if claim.asked_date else ""
    return f"本次未查询 {claim.capability}{date_part}。"


def rewrite_unattempted_claims(
    text: str,
    claims: tuple[UnattemptedClaim, ...],
) -> str:
    """Replace each claimed sentence. No LLM."""

    rewritten = str(text or "")
    for claim in claims:
        snippet = claim.snippet
        if snippet and snippet in rewritten:
            rewritten = rewritten.replace(snippet, rewrite_unattempted_claim(claim), 1)
    return rewritten


def traces_include_kb_query(traces: tuple[ProviderTrace, ...]) -> bool:
    """本轮是否调过 KB。与 V7 ``test_shape_i_called_uses_provider_not_capability`` 同口径。"""

    return any(
        str(trace.provider or "") in _KB_QUERY_PROVIDERS and _attempted(trace)
        for trace in traces or ()
    )


def kb_gap_claim_kind(traces: tuple[ProviderTrace, ...]) -> str:
    """缺口声明二分：库无 vs 未查证。变异闸——恒返回「库无」必须让零调用钉红。"""

    if traces_include_kb_query(traces):
        return "库无"
    return "未查证"


def find_unverified_kb_gap_claims(
    text: str,
    traces: tuple[ProviderTrace, ...],
) -> tuple[str, ...]:
    """零 KB 查证下的断言性缺口句。已带「未查证」限定的不算。"""

    if kb_gap_claim_kind(traces) != "未查证":
        return ()
    found: list[str] = []
    for sentence in iter_sentences(text):
        if "未查证" in sentence:
            continue
        if _KB_ABSENCE_GAP_RE.search(sentence):
            found.append(sentence)
    return tuple(found)


def _qualify_unverified_gap_sentence(sentence: str) -> str:
    """去掉断言性「库无/暂无」，并带上「未查证」限定。"""

    text = sentence
    text = text.replace("知识库暂无", "本轮未查证知识库是否有")
    text = text.replace("知识库无", "本轮未查证知识库是否有")
    text = text.replace("库无", "本轮未查证是否存在")
    text = text.replace("暂无公告级", "本轮未查证公告级")
    if "未查证" not in text:
        text = text.rstrip("。！？!?") + f"{_UNVERIFIED_QUALIFIER}。"
    return text


def rewrite_unverified_kb_gap_claims(
    text: str,
    traces: tuple[ProviderTrace, ...],
) -> str:
    """零查证的断言性缺口改为「未查证」；有查证未命中则原样保留「库无」。"""

    rewritten = str(text or "")
    for snippet in find_unverified_kb_gap_claims(rewritten, traces):
        if snippet in rewritten:
            rewritten = rewritten.replace(
                snippet, _qualify_unverified_gap_sentence(snippet), 1
            )
    return rewritten


def repair_collapsed_to_stub(
    before: str,
    after: str,
    question_type: str,
) -> bool:
    """True only when both shortness tests fire on a 盘面 research type."""

    if question_type == "quick_fact":
        return False
    if question_type not in ASKED_DATE_COVERAGE_TYPES:
        return False
    before_text = str(before or "").strip()
    after_text = str(after or "").strip()
    if len(before_text) < _MIN_ROLLBACK_CHARS:
        return False
    threshold = max(_MIN_ROLLBACK_CHARS, _STUB_CHAR_RATIO * len(before_text))
    return sentence_count(after_text) < _MIN_ROLLBACK_SENTENCES and len(
        after_text
    ) < threshold


def choose_repair_rollback(before: str, minus_flagged: str) -> tuple[str, str]:
    """Pick public source after a withhold. Not ``view(before)`` by default.

    Rolling back to the previous version in a pipeline that already named
    defects would republish those defects. Subtract the flagged sentences
    first; only if that remainder is still a stub do we keep the whole
    pre-repair draft and say so in issues.
    """

    remainder = str(minus_flagged or "").strip()
    if (
        sentence_count(remainder) >= _MIN_ROLLBACK_SENTENCES
        and len(remainder) >= _MIN_ROLLBACK_CHARS
    ):
        return remainder, "minus_flagged_sentences"
    return str(before or ""), "whole_pre_repair"
