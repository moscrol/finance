"""Finite market contradictions and total-only evidence scope, never a market oracle.

Only same-task raw finance_query cards can supply measurements. With no owned
sentence→output coordinate, comparisons use required-binding intersection;
total-only scope requires every eligible support card to be a raw total.
Explicit citations narrow inputs. Ambiguous dates, conflicting
values and other sources are not guessed. A finding requests revision; it does
not invent a corrected phase, weights, fund flows or a risk-clearing mechanism.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re

from intelligence.services.agent_research import AgentEvidence, evidence_content_hash
from intelligence.services.episode_protocol import cited_evidence_ordinals, evidence_ordinal_table
from intelligence.services.episode_verifier import VerifiedEpisodeOutcome
from intelligence.services.material_grounding import historical_claim_texts

AMOUNT_DIRECTION = "market_amount_direction"
EVIDENCE_SCOPE = "market_evidence_scope"
PATH_SCOPE = "market_path_scope"
RISK_THRESHOLD = "market_risk_threshold"
MARKET_REASONS = frozenset({AMOUNT_DIRECTION, EVIDENCE_SCOPE, PATH_SCOPE, RISK_THRESHOLD})
_TOTAL_FIELDS = {
    "market_daily": frozenset({"total_amount", "amount_change_pct", "amount_ma20", "volume_ratio",
                               "index_close", "index_return_pct", "advancers", "limit_up", "limit_down"}),
    "market_breadth_daily": frozenset({"advancers", "decliners", "unchanged", "observed_stocks",
                                      "valid_returns", "missing_returns"}),
    "theme_limit_heat_daily": frozenset({"limit_up_count", "limit_up_ratio", "market_share", "rank",
                                         "total_count", "market_limit_up_count"}),
}
_TOTAL_DIMENSIONS = {
    "market_daily": frozenset({"trade_date"}),
    "market_breadth_daily": frozenset({"trade_date", "source"}),
    "theme_limit_heat_daily": frozenset({"trade_date", "sector_code", "sector_name", "dimension", "scope"}),
}
_TOTAL_DATASETS = frozenset(_TOTAL_FIELDS)
_IDENTITY = ("tool", "title", "detail", "source", "source_date", "independent_key", "evidence_tier")
_DATE = re.compile(r"(?<!\d)(?:(?P<year>20\d{2})-)?(?P<month>\d{1,2})[-/](?P<day>\d{1,2})(?!\d)")
_CLAUSE = re.compile(r"[，,。；;！？!?]|但是|然而|不过|而是|但|却|——")
_NONASSERTED_PREFIX = re.compile(r"不能|无法|不足以|不等于|未能|并非|不是|尚未|并未|未做|没有|并无|未见|缺少|可能|假设|待验证|仍需|需要|是否|若|如果")
_REPORTED_QUOTE = re.compile(
    r'(?:旧稿|原文|作者|评论员|他人)(?:中)?(?:称|说|写道|认为)\s*(?:“[^”]*”|「[^」]*」|"[^"]*")'
)
_NONASSERTED_SUFFIX = re.compile(r"不成立|错误(?:写法|说法)?|(?:只是|仅是)?(?:待验证)?假设|仍待核对|吗$|么$")
_DIRECTION = re.compile(r"放量|缩量")
_OTHER_BASE = re.compile(r"均额|均量|均线|量比|前周|上周|前月|上月|同比|成交股数|成交手数")
_AMOUNT_SUBJECT = re.compile(r"(?:全市场|两市|大盘|市场)成交额")
_AMOUNT_BRIDGE = re.compile(r"\s*(?:(?:环比|较前一交易日|小幅|明显|继续|呈现|已经|已|仍|的|是|为)\s*)*$")
_WEIGHT = re.compile(r"(?:指数|反弹).{0,14}(?:靠|由).{0,10}权重.{0,8}(?:拉动|推动)|权重(?:股)?.{0,8}(?:拉动|推动)(?:了)?指数")
_CLEARING = re.compile(r"风险(?:已经|已|得到|完成|充分|正在|逐步|的)?(?:出清|释放)|情绪宣泄式出清|出清得到验证")
_FLOW = re.compile(r"(?:资金.{0,12}(?:入场|迁移|回流)|集中回流)")
_RISK_HEADING = re.compile(r"^(?:#{1,6}\s*|\*\*|__)?(?:风险信号与观察条件|风险信号|风险观察|风险与观察条件)(?:\*\*|__)?[：:]?$")
_DURATION_TOKEN = r"\d+(?:\s*[-~～至到—]\s*\d+)?\s*(?:个交易日|交易日|天|日)"
_USER_DURATION = re.compile(r"(?<![\d./-])" + _DURATION_TOKEN + r"(?!均|移动平均)")
_RISK_WINDOW = re.compile(
    r"(?:若|如果)[^。；;，,]{0,40}?(?:延续|持续|观察)\s*"
    r"(?P<window>" + _DURATION_TOKEN + r")"
)


@dataclass(frozen=True)
class MarketClaimFinding:
    sentence_index: int
    reason: str
    output_ids: tuple[str, ...]
    repair_instruction: str


def risk_sentence_indexes(sentences: Sequence[Mapping[str, object]]) -> frozenset[int]:
    """A recognized risk heading narrows numeric checks; it never grants authority."""
    active = False
    indexes = set()
    for row in sentences:
        text = str(row.get("text") or "").strip()
        label, sep, _ = text.partition("：")
        if _RISK_HEADING.fullmatch(text):
            active = True
            continue
        if text.startswith(("#", "**", "__")) or (sep and len(label) <= 12):
            active = bool(_RISK_HEADING.fullmatch(label))
        if active and isinstance(row.get("index"), int):
            indexes.add(row["index"])
    return frozenset(indexes)


def _normalize_duration(window: str) -> str:
    # Range separators and the optional counter do not change the duration;
    # trading days and calendar days remain different units.
    return re.sub(r"[-~～到—]", "至", "".join(window.split())).replace("个交易日", "交易日")


def user_risk_window_tokens(date_masked_question: str) -> frozenset[str]:
    """Match complete durations after the caller masks explicit calendar dates.

    No dimensionless fallback: counts, numeric substrings and MA lookbacks
    cannot suppress an unsupported prospective-window finding.
    """
    return frozenset(_normalize_duration(m[0]) for m in _USER_DURATION.finditer(date_masked_question))


def risk_window_tokens(text: str) -> frozenset[str]:
    """Prospective windows, not dates, formula lookbacks or raw observation counts.

    This is only used after the evidence schema proves that the risk slot has
    no duration/forecast field. User-supplied windows cause abstention, not an
    entailment certificate. All other numeric shapes keep the default policy.
    """
    text = _REPORTED_QUOTE.sub("", text)
    if text.rstrip().endswith(("?", "？")):
        return frozenset()
    windows = set()
    for clause in _CLAUSE.split(text):
        for match in _RISK_WINDOW.finditer(clause):
            if (_NONASSERTED_PREFIX.search(clause[:match.start()])
                    or _NONASSERTED_SUFFIX.search(clause[match.end():])):
                continue
            windows.add(_normalize_duration(match["window"]))
    return frozenset(windows)


def _bound_pool(verified: VerifiedEpisodeOutcome, preferred: str) -> tuple[tuple[str, ...], frozenset[str]]:
    contract = verified.contract
    if contract is None:
        return (), frozenset()
    eligible = tuple(o.output_id for o in contract.required_outputs if o.required and o.grounding_mode == "evidence")
    targets = (preferred,) if preferred in eligible else ()
    bindings = [b for b in verified.outcome.bindings if b.output_id in targets]
    if len(bindings) != 1 or bindings[0].gap or bindings[0].basis != "evidence":
        return targets, frozenset()
    return targets, frozenset(bindings[0].evidence_hashes)


def _sentence_pools(verified: VerifiedEpisodeOutcome) -> tuple[frozenset[str], frozenset[str]]:
    """No heading heuristic may assign a sentence another slot's authority.

    Intersection can establish a contradiction regardless of which required
    evidence output owns it. Conversely, absence of mechanism support is known
    only if *all* legal bound sources (including optional ones) are raw totals.
    These are rejection checks, never positive entailment certificates.
    """
    contract = verified.contract
    if contract is None:
        return frozenset(), frozenset()
    pools = []
    all_bound = set()
    for spec in contract.required_outputs:
        bindings = [b for b in verified.outcome.bindings if b.output_id == spec.output_id]
        valid = (len(bindings) == 1 and not bindings[0].gap
                 and bindings[0].basis == spec.grounding_mode)
        pool = set(bindings[0].evidence_hashes) if valid else set()
        all_bound.update(pool)
        if spec.required and spec.grounding_mode == "evidence":
            pools.append(pool)
    common = set.intersection(*pools) if pools else set()
    return frozenset(common), frozenset(all_bound)


def _raw_total_cards(verified: VerifiedEpisodeOutcome) -> dict[str, tuple[AgentEvidence, str, frozenset[str]]]:
    outcome = verified.outcome
    if verified.contract is None or verified.contract.task_frame_hash != outcome.task_frame_hash:
        return {}
    counts = Counter(row.content_hash for row in outcome.evidence if isinstance(row.content_hash, str))
    cards = {row.content_hash: row for row in outcome.evidence
             if isinstance(row.content_hash, str) and counts[row.content_hash] == 1
             and row.tool == "finance_query" and row.evidence_tier == "L4_structured"
             and all(isinstance(getattr(row, key), str) for key in _IDENTITY)
             and row.content_hash == evidence_content_hash(row)}
    trusted = {}
    for event in outcome.events:
        payload = event.payload
        basis = payload.get("query_basis")
        if not (event.kind == "tool_result" and payload.get("ok") is True
                and payload.get("tool") == "finance_query"
                and payload.get("task_frame_hash") == outcome.task_frame_hash
                and isinstance(basis, Mapping) and isinstance(basis.get("dataset"), str)
                and basis["dataset"] in _TOTAL_DATASETS and basis.get("group_by") in ([], ())):
            continue
        metrics, emitted, hashes = basis.get("metrics"), payload.get("evidence"), payload.get("evidence_hashes")
        if not (isinstance(metrics, (list, tuple)) and all(isinstance(m, str) for m in metrics)
                and metrics and set(metrics) <= _TOTAL_FIELDS[basis["dataset"]]
                and isinstance(basis.get("dimensions", []), (list, tuple))
                and all(isinstance(d, str) and d in _TOTAL_DIMENSIONS[basis["dataset"]]
                        for d in basis.get("dimensions", []))
                and isinstance(emitted, (list, tuple)) and isinstance(hashes, (list, tuple))):
            continue
        for item in emitted:
            if not isinstance(item, Mapping):
                continue
            digest = item.get("content_hash")
            if not isinstance(digest, str) or digest not in hashes:
                continue
            card = cards.get(digest)
            if (card is not None and card.independent_key.startswith(f"duckdb:{basis['dataset']}:")
                    and all(item.get(key) == getattr(card, key) for key in _IDENTITY)):
                trusted[digest] = (card, basis["dataset"], frozenset(metrics))
    return trusted


def has_bound_market_totals(verified: VerifiedEpisodeOutcome, output_id: str) -> bool:
    targets, pool = _bound_pool(verified, output_id)
    return targets == (output_id,) and bool(pool) and pool <= _raw_total_cards(verified).keys()


def _amount_changes(cards) -> dict[date, Decimal]:
    values: dict[date, set[Decimal | None]] = {}
    for card, dataset, metrics in cards:
        if dataset != "market_daily" or "amount_change_pct" not in metrics:
            continue
        pairs = [part.split("=", 1) for part in card.detail.split("；") if "=" in part]
        keys = Counter(key for key, _ in pairs)
        fields = dict(pairs)
        if keys["交易日"] != 1:
            continue
        try:
            day = date.fromisoformat(fields["交易日"])
        except (ValueError, TypeError):
            continue
        if card.source_date != day.isoformat() or card.independent_key != f"duckdb:market_daily:{day}":
            continue
        try:
            value = Decimal(fields.get("成交额环比%", "NaN"))
            if not value.is_finite() or keys["成交额环比%"] != 1:
                value = None
        except InvalidOperation:
            value = None
        values.setdefault(day, set()).add(value)
    return {day: next(iter(group)) for day, group in values.items() if len(group) == 1 and None not in group}


def _asserted(clause: str, match: re.Match[str]) -> bool:
    return not (_NONASSERTED_PREFIX.search(clause[:match.end()])
                or _NONASSERTED_SUFFIX.search(clause[match.end():]))


def market_claim_findings(
    sentences: Sequence[Mapping[str, object]], verified: VerifiedEpisodeOutcome,
) -> tuple[MarketClaimFinding, ...]:
    contract = verified.contract
    if contract is None:
        return ()
    trusted = _raw_total_cards(verified)
    if not trusted:
        return ()
    historical = historical_claim_texts(contract, verified.outcome.bindings, verified.outcome.draft)
    by_ordinal = {ordinal: digest for digest, ordinal in evidence_ordinal_table(verified.outcome.evidence).items()}
    direction_targets, _ = _bound_pool(verified, "change_summary")
    scope_targets, _ = _bound_pool(verified, "direct_assessment")
    direction_pool, scope_pool = _sentence_pools(verified)
    findings = []
    for row in sentences:
        index, original = row.get("index"), str(row.get("text") or "")
        if (not isinstance(index, int) or original in historical
                or original.rstrip().endswith(("?", "？"))):
            continue
        cited = cited_evidence_ordinals(original)
        if any(token not in by_ordinal for token in cited):
            continue
        cited_hashes = frozenset(by_ordinal[token] for token in cited)
        text = _REPORTED_QUOTE.sub("", original.replace("**", "").replace("__", ""))
        # A different slot or a table-out-of-range E cannot lend measurement authority.
        direction_allowed = direction_pool if not cited else direction_pool & cited_hashes
        changes = _amount_changes(trusted[h] for h in direction_allowed if h in trusted)
        directions = tuple(_DIRECTION.finditer(text))
        if direction_targets and changes and directions and not _OTHER_BASE.search(text):
            dates = []
            for token in _DATE.finditer(text):
                matches = {day for day in changes if day.month == int(token["month"]) and day.day == int(token["day"])
                           and (not token["year"] or day.year == int(token["year"]))}
                dates.append(next(iter(matches)) if len(matches) == 1 else None)
            # No implicit carry from a neighboring sentence, citation or phase label.
            if len(dates) == 1 and dates[0] is not None:
                for clause in _CLAUSE.split(text):
                    for match in _DIRECTION.finditer(clause):
                        subjects = tuple(_AMOUNT_SUBJECT.finditer(clause[:match.start()]))
                        bridge = clause[subjects[-1].end():match.start()] if subjects else ""
                        explicit_basis = "环比" in bridge or "较前一交易日" in bridge
                        local_date = bool(subjects and _DATE.search(clause[:subjects[-1].start()]))
                        if local_date and explicit_basis and _AMOUNT_BRIDGE.fullmatch(bridge) and _asserted(clause, match) and (
                            (match[0] == "缩量" and changes[dates[0]] > 0)
                            or (match[0] == "放量" and changes[dates[0]] < 0)
                        ):
                            findings.append(MarketClaimFinding(index, AMOUNT_DIRECTION, direction_targets,
                                f"{dates[0]}已绑定成交额环比为{changes[dates[0]]}%，与该方向词矛盾；"
                                "核对日期及前一交易日比较基准后重写，保留逐日读数，不用20日均额替代环比。"))
            elif ("→" in text and len(directions) > len(dates)
                  and any(token in text for token in ("整体", "全市场", "市场", "两市", "大盘"))
                  and not _NONASSERTED_PREFIX.search(text)):
                findings.append(MarketClaimFinding(index, PATH_SCOPE, direction_targets,
                    "分阶段量能路径没有逐段对应的日期和比较基准；请对齐已绑定逐日成交额及环比后重写。"
                    "这不是已证明方向相反，不按恐慌等描述猜阶段日期。"))
        scope_allowed = scope_pool if not cited else scope_pool & cited_hashes
        # This narrow gate speaks only when ALL eligible support is raw totals.
        # Other evidence is left to entailment review, not certified by this absence check.
        if not scope_targets or not scope_allowed or not scope_allowed <= trusted.keys():
            continue
        for clause in _CLAUSE.split(text):
            patterns = (_WEIGHT, _CLEARING, _FLOW) if "资金" in text else (_WEIGHT, _CLEARING)
            if any(_asserted(clause, match) for pattern in patterns for match in pattern.finditer(clause)):
                findings.append(MarketClaimFinding(index, EVIDENCE_SCOPE, scope_targets,
                    "本句可用绑定仅有成交额、涨跌/涨停统计或题材热度；它们不能证明权重贡献、资金来源/回流"
                    "或情绪出清机制。保留观测与阶段比较，补相应证据或明确写成待验证假设及验证方法；"
                    "不能靠邻句免责声明把事实断言放行，不扩大读取权限。"))
                break
    return tuple(dict.fromkeys(findings))
