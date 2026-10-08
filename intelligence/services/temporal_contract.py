"""Immutable user time authority, independent of routing and provider freshness.

The lexical primitives are shared by legacy readers. Compilation lazily imports
the provenance partitioner so importing the value types cannot create cycles.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
import hashlib
import re
from typing import Literal


CutoffOrigin = Literal[
    "none", "explicit_user", "relative_target", "runtime_relative", "inherited_user", "legacy_user",
]
_ORIGINS = frozenset({
    "none", "explicit_user", "relative_target", "runtime_relative", "inherited_user", "legacy_user",
})
_FULL_DATE_RE = re.compile(
    r"(?<!\d)(20\d{2})(?:年|[-/.])(\d{1,2})(?:月|[-/.])(\d{1,2})日?(?!\d)"
)
_YEARLESS_DATE_RE = re.compile(
    r"(?<!\d)(\d{1,2})(?:月|[./])(\d{1,2})日?(?!\d)"
)
# Quantity dimensions already used by financial calculation/delivery checks:
# currency/price, money/shares, ratios/multiples and counted physical units.
# A unit must end as a token; a date followed by a company/theme name does not
# become a quantity merely because that name starts with 元/亿/倍/股.
_FINANCIAL_QUANTITY_UNIT_RE = re.compile(
    r"\s*(?:[%％]|(?:人民币(?:元)?|亿美元|美元|港元|欧元|万亿元|百万元|亿元|万元|千元|万亿|亿股|万股|"
    r"元\s*(?:[/／]\s*(?:股|元)|每股)?|个百分点|百分点|百分比|基点|bps?|[%％]|倍|亿|万|千|"
    r"股|手|只|家|个月|个|笔|万吨|吨|台|套|片|颗|条|GWh|MWh)"
    r"(?=$|[\s，,。；;？！?!、）)\]】]|的|(?:收入|利润|订单|股本|成交额|成交量)))", re.I,
)
_YEARLESS_QUANTITY_PREFIX_RE = re.compile(
    r"(?:每股(?:价格|价)?|股价|价格|单价|收盘价|发行价|目标价|市盈率|市净率|估值倍数|"
    r"营业收入|经营现金流|净利润|收入|利润|总股本|股本|持股|成交额|成交量|金额|"
    r"订单(?:金额)?|涨跌幅|涨幅|跌幅|换手率|毛利率|净利率|利率|增长率|收益率|占比|比例|比率|倍数|PE|PB)"
    r"(?:[=：:]|为|是|在|约|大约|达到|由|从|至|到|涨至|跌至)*$"
    r"|[涨跌幅率价值为达到约是了升降]$|\d$|[.．]$", re.I,
)
_SHORT_RANGE_END = re.compile(
    r"\s*(?:到|至|~|～|—|-)\s*"
    r"(?:(?P<month>\d{1,2})[月/.-](?P<day>\d{1,2})日?|(?P<same_month_day>\d{1,2})日)"
    r"(?!\d)"
)
_RANGE_JOIN = re.compile(r"\s*(?:到|至|~|～|—|–|-)\s*")
_CUTOFF_DATE = rf"(?:{_FULL_DATE_RE.pattern}|{_YEARLESS_DATE_RE.pattern})"
_EXPLICIT_CUTOFF_RE = re.compile(
    rf"(?:截至|截止(?:到)?)\s*(?P<until>{_CUTOFF_DATE})"
    rf"|(?:以|将)\s*(?P<asof>{_CUTOFF_DATE})\s*(?:为|作为)\s*信息截止(?:点|日|时间)"
    rf"|信息截止(?:点|日|时间)\s*(?:为|是|[:：=])?\s*(?P<label>{_CUTOFF_DATE})"
    rf"|(?P<history>{_CUTOFF_DATE})\s*(?:为|作为)?\s*信息截止日"
)
_RELATIVE_CUTOFF_RE = re.compile(
    r"(?:截至|截止(?:到)?)\s*(?P<relative>今天|当日|该日|该区间结束日|区间结束日)"
)
_NEGATION = re.compile(r"(?:不要|不得|不应|并非|不是|不能|无需|别).*$")
_DATE_ROLE = re.compile(
    r"(?:报告期|会计期|统计期|披露日|发布日期|复查日|复核日|有效期|到期日|期限)[\s:：=为是]*$"
)


# Numeric punctuation is not date authority on its own. Short dates need a
# local calendar role; financial quantities and slash-separated period lists
# take precedence even when they occur next to a general review instruction.
_DATE_PREFIX = re.compile(
    r"(?:复盘|回看|回顾|日期|交易日|截至|截止|比较|对比)"
    r"(?:一下|到|为|是|[:：]|\s)*$"
)
_DATE_SUFFIX = re.compile(r"\s*(?:的\s*)?(?:A股|市场|行情|盘面|主线|复盘|收盘|连板|龙虎榜|成交额|成交量|涨家数|跌家数|涨停|跌停|当天|当日|那天|这天)")
_NUMERIC_ROLE_PREFIX = re.compile(
    r"(?:仓位|持仓|仓|分位|历史|比例|占比|分数|概率|胜率|均线|MA)"
    r"(?:\s|为|是|在|从|由|至|到|约|提高到|降低到|[:：=])*$", re.I,
)
_NUMERIC_ROLE_SUFFIX = re.compile(
    r"\s*(?:仓位|仓|分位|概率|比例|日均线|天均线|日线|天线|日周期|日窗口)", re.I,
)


def _yearless_quantity(text: str, start: int, end: int, raw: str, *, permission: bool = False, linked_date: bool = False) -> bool:
    prefix, suffix = text[:start], text[end:]
    if _NUMERIC_ROLE_SUFFIX.match(suffix):
        return True
    # Do not extract 5/10 from 5/10/20, or the middle of another numeric token.
    if "月" not in raw and (re.search(r"[\d][/.]\s*$", prefix) or re.match(r"\s*[/．.]\d", suffix)):
        return True
    if "月" in raw or raw.endswith("日"):
        # 5/10日均线: the trailing 日 is a period unit, not a date marker.
        return raw.endswith("日") and bool(re.match(r"\s*(?:均线|线|周期|窗口)", suffix))
    if (raw.startswith("0.") or _FINANCIAL_QUANTITY_UNIT_RE.match(suffix)
            or (not permission and (_YEARLESS_QUANTITY_PREFIX_RE.search(re.sub(r"\s+", "", prefix))
                                    or _NUMERIC_ROLE_PREFIX.search(prefix)))):
        return True
    if re.fullmatch(r"\s*(?:那|那么)\s*", prefix) and re.fullmatch(r"\s*呢[？?。\s]*", suffix):
        return False  # Existing explicit short-date follow-up syntax.
    if permission or linked_date or _DATE_PREFIX.search(prefix) or _DATE_SUFFIX.match(suffix):
        return False
    if not text[:start].strip() and not text[end:].strip(" 。，？！?!\n"):
        return False  # A standalone date reply keeps legacy short-date support.
    return True


def yearless_date_matches(text: str) -> tuple[re.Match[str], ...]:
    """One source-aware numeric-role filter for every yearless date reader.

    Propagate directly connected date roles iteratively: long date lists must
    not recurse through every preceding token or authorize unrelated fractions.
    """
    accepted = []
    full_dates = list(_FULL_DATE_RE.finditer(text))
    connector = re.compile(r"\s*(?:和|与|及|、|到|至|~|～|—|–|-)\s*")
    for match in _YEARLESS_DATE_RE.finditer(text):
        prior = accepted[-1:] + [full for full in full_dates if full.end() <= match.start()]
        linked = any(connector.fullmatch(text[item.end():match.start()]) for item in prior)
        if not _yearless_quantity(text, match.start(), match.end(), match.group(), linked_date=linked):
            accepted.append(match)
    return tuple(accepted)


def _iso(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("temporal date must be canonical ISO")
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("invalid temporal date")
    return value


def message_digest(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("temporal source must be a complete user string")
    return hashlib.sha256(text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TemporalSource:
    message_id: str | None
    message_sha256: str
    excerpt: str

    def __post_init__(self) -> None:
        if self.message_id is not None and not isinstance(self.message_id, str):
            raise ValueError("invalid temporal message identity")
        if not isinstance(self.message_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.message_sha256):
            raise ValueError("invalid temporal message digest")
        if not isinstance(self.excerpt, str) or message_digest(self.excerpt) != self.message_sha256:
            raise ValueError("temporal source digest does not match complete user text")

    def to_dict(self) -> dict[str, object]:
        return {"message_id": self.message_id, "message_sha256": self.message_sha256, "excerpt": self.excerpt}

    @classmethod
    def from_dict(cls, value: object) -> TemporalSource:
        if not isinstance(value, dict) or set(value) != {"message_id", "message_sha256", "excerpt"}:
            raise ValueError("invalid temporal source schema")
        return cls(**value)


@dataclass(frozen=True)
class ResearchDateWindow:
    start: str
    end: str
    source: TemporalSource

    def __post_init__(self) -> None:
        _iso(self.start)
        _iso(self.end)
        if self.start > self.end or not isinstance(self.source, TemporalSource):
            raise ValueError("invalid research date window")

    def to_dict(self) -> dict[str, object]:
        return {"start": self.start, "end": self.end, "source": self.source.to_dict()}

    @property
    def timeframe(self) -> str:
        return self.end if self.start == self.end else f"{self.start}至{self.end}"

    @classmethod
    def from_dict(cls, value: object) -> ResearchDateWindow:
        if not isinstance(value, dict) or set(value) != {"start", "end", "source"}:
            raise ValueError("invalid research date window schema")
        return cls(value["start"], value["end"], TemporalSource.from_dict(value["source"]))


@dataclass(frozen=True)
class TemporalContract:
    market_target: ResearchDateWindow | None = None
    information_cutoff: str | None = None
    cutoff_origin: CutoffOrigin = "none"
    cutoff_source: TemporalSource | None = None
    relative_anchor_sha256: str | None = None
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.cutoff_origin, str) or self.cutoff_origin not in _ORIGINS:
            raise ValueError("invalid temporal cutoff origin")
        if self.market_target is not None and not isinstance(self.market_target, ResearchDateWindow):
            raise ValueError("invalid temporal target")
        if not isinstance(self.errors, tuple) or any(not isinstance(e, str) or not e for e in self.errors):
            raise ValueError("invalid temporal errors")
        if self.cutoff_origin == "none":
            if any(v is not None for v in (self.information_cutoff, self.cutoff_source, self.relative_anchor_sha256)):
                raise ValueError("unspecified temporal permission cannot carry a bound")
        else:
            _iso(self.information_cutoff)
            if not isinstance(self.cutoff_source, TemporalSource):
                raise ValueError("temporal permission requires a user source")
        if self.relative_anchor_sha256 is not None:
            # An inherited permit keeps its original target anchor even when
            # the current goal changes. Recovery verifies it against the
            # prior user chain, rather than rebinding it to the new goal/source.
            if (not isinstance(self.relative_anchor_sha256, str)
                    or self.cutoff_origin not in {"relative_target", "inherited_user", "legacy_user"}
                    or not re.fullmatch(r"[0-9a-f]{64}", self.relative_anchor_sha256)
                    or self.cutoff_source is None):
                raise ValueError("invalid relative temporal anchor")
        if self.cutoff_origin == "relative_target" and (
            self.market_target is None or self.cutoff_source is None
            or self.relative_anchor_sha256 != self.market_target.source.message_sha256
            or self.information_cutoff != self.market_target.end
        ):
            raise ValueError("relative permission must bind its target source and end")

    def to_dict(self) -> dict[str, object]:
        return {
            "market_target": self.market_target.to_dict() if self.market_target else None,
            "information_cutoff": self.information_cutoff, "cutoff_origin": self.cutoff_origin,
            "cutoff_source": self.cutoff_source.to_dict() if self.cutoff_source else None,
            "relative_anchor_sha256": self.relative_anchor_sha256, "errors": list(self.errors),
        }

    def to_model_dict(self) -> dict[str, object]:
        """Dates and scope only; source identities/full text belong to private audit."""
        return {
            "market_target": {"start": self.market_target.start, "end": self.market_target.end} if self.market_target else None,
            "information_cutoff": self.information_cutoff, "cutoff_origin": self.cutoff_origin,
            "scope": "known_date_upper_bound", "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, value: object) -> TemporalContract:
        if not isinstance(value, dict) or set(value) != {
            "market_target", "information_cutoff", "cutoff_origin", "cutoff_source", "relative_anchor_sha256", "errors",
        }:
            raise ValueError("invalid temporal contract schema")
        if not isinstance(value["errors"], (list, tuple)):
            raise ValueError("invalid temporal error schema")
        return cls(
            ResearchDateWindow.from_dict(value["market_target"]) if value["market_target"] is not None else None,
            value["information_cutoff"], value["cutoff_origin"],
            TemporalSource.from_dict(value["cutoff_source"]) if value["cutoff_source"] is not None else None,
            value["relative_anchor_sha256"], tuple(value["errors"]),
        )


def cutoff_instruction_clauses(text: str) -> tuple[tuple[int, int, str, str], ...]:
    """Permission spans in already provenance-partitioned text.

    Negation, date role and range-start rules are shared by absolute and
    relative readers. Offsets permit equal-length masking without dropping a
    market target elsewhere in the same clause.
    """
    spans = []
    for clause_match in re.finditer(r"[^，,。；;\n]+", text):
        clause = clause_match.group()
        for regex, kind in ((_EXPLICIT_CUTOFF_RE, "explicit"), (_RELATIVE_CUTOFF_RE, "relative")):
            for match in regex.finditer(clause):
                prefix = clause[:match.start()].strip()
                if _NEGATION.search(prefix):
                    continue
                until = match.groupdict().get("until") or match.groupdict().get("relative")
                if until and _DATE_ROLE.search(prefix):
                    continue
                if re.match(r"\s*[-~—–～至到]+\s*\d", clause[match.end():]):
                    continue
                raw = next(v for v in match.groupdict().values() if v is not None)
                matched_kind = kind
                if kind == "explicit" and _YEARLESS_DATE_RE.fullmatch(raw):
                    group = next(name for name, value in match.groupdict().items() if value is not None)
                    start, end = match.span(group)
                    if _yearless_quantity(clause, start, end, raw, permission=True):
                        matched_kind = "quantity"
                spans.append((clause_match.start() + match.start(), clause_match.start() + match.end(), matched_kind, raw))
    return tuple(sorted(spans))


def _explicit_cutoff_candidates(text: str) -> list[str]:
    return [raw for _start, _end, kind, raw in cutoff_instruction_clauses(text) if kind == "explicit"]


def lexical_date(raw: str, *, today: date) -> date | None:
    full = _FULL_DATE_RE.fullmatch(raw)
    if full:
        try:
            return date(*(int(part) for part in full.groups()))
        except ValueError:
            return None
    short = _YEARLESS_DATE_RE.fullmatch(raw)
    if short:
        for year in (today.year, today.year - 1):
            try:
                candidate = date(year, *(int(part) for part in short.groups()))
            except ValueError:
                continue
            if candidate <= today:
                return candidate
    return None


def _comparison_error(text: str, *, today: date) -> tuple[str, ...]:
    # A single target/window cannot faithfully represent two discrete dates.
    # Clarify before routing instead of silently dropping 今天 or one endpoint.
    token = rf"(?:今天|{_FULL_DATE_RE.pattern}|{_YEARLESS_DATE_RE.pattern})"
    pattern = re.compile(rf"(?P<left>{token})\s*(?:和|与|跟|对比|相比)\s*(?P<right>{token})")
    for match in pattern.finditer(text):
        prefix = re.sub(r"\s+", "", text[:match.start()])
        if _NUMERIC_ROLE_PREFIX.search(prefix) or _YEARLESS_QUANTITY_PREFIX_RE.search(prefix):
            continue
        raw_dates = (match['left'], match['right'])
        dates = [today if raw == "今天" else lexical_date(raw, today=today) for raw in raw_dates]
        if any(value is None for value in dates):
            return ("对比日期无效，请明确两个有效日期",)
        if dates[0] != dates[1]:
            return (f"已识别对比日期 {dates[0].isoformat()} 与 {dates[1].isoformat()}；"
                    "当前单日/连续窗口合同不支持离散多日对比，请分别查询，或明确是否研究两日之间的连续区间",)
    return ()


def market_review_requested_date(query: str, *, today: date | None = None) -> str | None:
    """Legacy single-date projection with the same legal/recent-year lexicon."""
    anchor = today or date.today()
    if _comparison_error(query, today=anchor):
        return None
    full = _FULL_DATE_RE.search(query)
    if full is not None:
        parsed = lexical_date(full.group(), today=anchor)
        return parsed.isoformat() if parsed else None
    short = next(iter(yearless_date_matches(query)), None)
    if short is None:
        return None
    parsed = lexical_date(short.group(), today=anchor)
    return parsed.isoformat() if parsed else None


def _target_window(
    text: str, *, today: date, source: TemporalSource,
    inherited: ResearchDateWindow | None = None,
) -> tuple[ResearchDateWindow | None, tuple[str, ...]]:
    comparison_errors = _comparison_error(text, today=today)
    if comparison_errors:
        return None, comparison_errors
    full = list(_FULL_DATE_RE.finditer(text))
    matches = full + [m for m in yearless_date_matches(text) if not any(
        f.start() <= m.start() < f.end() for f in full
    )]
    matches.sort(key=lambda m: m.start())
    matches = [m for m in matches if not _NEGATION.search(re.split(r"[，,。；;\n]", text[:m.start()])[-1])]
    dates = [lexical_date(m.group(), today=today) for m in matches]
    if any(d is None for d in dates):
        return None, ("时间日期无效，请明确有效的目标日期或窗口",)
    if not matches:
        return inherited, ()
    start = dates[0]
    short_end = _SHORT_RANGE_END.match(text, matches[0].end())
    if short_end is not None:
        try:
            end = date(start.year, int(short_end["month"]) if short_end["month"] else start.month,
                       int(short_end["day"] or short_end["same_month_day"]))
        except ValueError:
            return None, ("时间日期无效，请明确有效的目标窗口",)
        if end < start:
            return None, ("目标起止日期顺序相反或跨年不明，请明确完整窗口",)
        if any(m.start() >= short_end.end() for m in matches[1:]):
            return None, ()
        return ResearchDateWindow(start.isoformat(), end.isoformat(), source), ()
    if len(matches) == 2 and _RANGE_JOIN.fullmatch(text[matches[0].end():matches[1].start()]):
        if start > dates[1]:
            return None, ("目标起止日期顺序相反，请明确研究窗口",)
        return ResearchDateWindow(start.isoformat(), dates[1].isoformat(), source), ()
    if len(set(dates)) == 1:
        return ResearchDateWindow(start.isoformat(), start.isoformat(), source), ()
    return None, ()


def _temporal_user_text(query: str) -> tuple[str, tuple[str, ...], str]:
    from intelligence.services.user_task import split_user_message, top_level_message_text

    parts = split_user_message(query)
    regions = parts.regions
    visible, uncertain = top_level_message_text(query)
    control = regions.control_text if regions else visible
    if not uncertain and parts.materials:
        instructions = [span.visible_text for span in regions.instructions if span.scope == "message"] if regions else []
        visible, _ = top_level_message_text("\n".join([*instructions, parts.question]))
    return visible, uncertain, control


def compile_temporal_contract(
    query: str, *, today: date, message_id: str | None = None,
    previous: TemporalContract | None = None, continuing: bool = False,
) -> TemporalContract:
    """Freeze full current user input before any resolver/model sees it."""
    from intelligence.services.honesty_gates import _standing_information_date

    if type(today) is not date or not isinstance(query, str):
        raise ValueError("temporal compiler requires a trusted date and user string")
    if previous is not None and not isinstance(previous, TemporalContract):
        raise ValueError("invalid previous temporal contract")
    source = TemporalSource(message_id, message_digest(query), query)
    visible, uncertain, control = _temporal_user_text(query)
    instructions = cutoff_instruction_clauses(visible)
    goal_text = list(visible)
    for start, end, _kind, _raw in instructions:
        goal_text[start:end] = " " * (end - start)
    target, target_errors = _target_window(
        "".join(goal_text), today=today, source=source,
        inherited=previous.market_target if continuing and previous else None,
    )
    errors = list(target_errors)
    if uncertain and (cutoff_instruction_clauses(control) or _standing_information_date(control)):
        errors.append("时间指令与材料边界不明确，请将授权和材料分开提供")
    candidates: list[tuple[str, CutoffOrigin, str | None]] = []
    for _start, _end, kind, raw in instructions:
        if kind == "quantity":
            errors.append("资料截止需要有效日期，价格、数量或比例不能作为日期")
        elif kind == "explicit":
            parsed = lexical_date(raw, today=today)
            if parsed is None:
                errors.append("资料截止日期无效，请明确有效日期")
            else:
                candidates.append((min(parsed, today).isoformat(), "explicit_user", None))
        elif raw == "今天":
            candidates.append((today.isoformat(), "runtime_relative", None))
        elif target is None or (raw in {"当日", "该日"} and target.start != target.end):
            errors.append("相对资料截止缺少唯一目标日期或明确区间，请明确资料截止日")
        elif target.end > today.isoformat():
            errors.append("目标截止日尚未到来，请明确截至今天或已知日期的资料范围")
        else:
            candidates.append((target.end, "relative_target", target.source.message_sha256))
    if not instructions:
        standing = _standing_information_date(visible)
        if standing:
            parsed = lexical_date(standing, today=today)
            if parsed is None:
                errors.append("站立日期无效，请明确有效日期")
            else:
                candidates.append((min(parsed, today).isoformat(), "explicit_user", None))
    if len({v[0] for v in candidates}) > 1:
        errors.append("存在冲突的资料截止授权，请明确唯一截止日")
    if errors:
        if continuing and previous is not None and previous.information_cutoff:
            return replace(previous, cutoff_origin="inherited_user", errors=tuple(dict.fromkeys(errors)))
        return TemporalContract(target, errors=tuple(dict.fromkeys(errors)))
    if candidates:
        chosen = next((v for v in candidates if v[1] == "explicit_user"), candidates[0])
        return TemporalContract(target, chosen[0], chosen[1], source, chosen[2])
    if continuing:
        if previous is None:
            return TemporalContract(target, errors=("无法恢复上一轮的完整用户时间授权，请明确本轮资料截止日",))
        return TemporalContract(
            target, previous.information_cutoff,
            "inherited_user" if previous.information_cutoff else "none", previous.cutoff_source,
            previous.relative_anchor_sha256, previous.errors,
        )
    return TemporalContract(target)


def compile_static_temporal_contract(
    query: str, *, message_id: str | None = None,
    previous: TemporalContract | None = None, continuing: bool = False,
) -> TemporalContract | None:
    """Recover only user semantics that provably never consult an execution day.

    Every permission has a runtime upper clamp, and yearless goals consult the
    runtime year. Neither can be reconstructed without a trusted audit anchor.
    Full-year goals and ordinary follow-ups can retain an already verified
    permit without inventing an original execution date.
    """
    from intelligence.services.honesty_gates import _standing_information_date

    visible, uncertain, control = _temporal_user_text(query)
    if uncertain and (cutoff_instruction_clauses(control) or _standing_information_date(control)):
        return None
    if cutoff_instruction_clauses(visible) or _standing_information_date(visible):
        return None
    full = list(_FULL_DATE_RE.finditer(visible))
    compressed = [_SHORT_RANGE_END.match(visible, match.end()) for match in full]
    for match in yearless_date_matches(visible):
        if any(start.start() <= match.start() < start.end() for start in full):
            continue
        if any(end is not None and end.start() <= match.start() < end.end() for end in compressed):
            continue
        prefix = visible[:match.start()]
        if _NEGATION.search(re.split(r"[，,。；;\n]", prefix)[-1]):
            continue
        return None
    # The guards prove that this compiler path does not read its day. This
    # constant is not an inferred execution date and grants no new permission.
    return compile_temporal_contract(query, today=date.min, message_id=message_id,
                                     previous=previous, continuing=continuing)
