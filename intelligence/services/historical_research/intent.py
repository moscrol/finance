"""User-owned historical research semantics; tool arguments cannot grant scope."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
import re

_DISCOVERY = re.compile(
    r"事后(?:复盘|分析|发现)|(?:这一波|这波|那一波|上一波|行情|强势股|板块|题材).{0,32}"
    r"(?:怎么走出来|如何走出来|诞生|回溯|演变|复盘)|"
    r"(?:回溯|重建).{0,20}(?:行情|板块|题材|走势)|历史.{0,12}(?:规律|特征|行情)"
)
_COMPARISON = re.compile(
    r"(?:历史|多样本).{0,24}(?:类似|相似|验证|回测|反例|失败|共性)|"
    r"(?:之前|过去|其他).{0,24}(?:行情|走势|板块|强势股|样本|题材).{0,24}(?:类似|相似|验证|回测|反例|失败|共性)|"
    r"(?:找|看看|查|比较).{0,15}(?:失败案例|历史样本|反例)|条件全集"
)
_DATE = re.compile(r"(?<!\d)(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})日?(?!\d)")
_SHORT_RANGE_END = re.compile(
    r"\s*(?:到|至|~|～|—|-)\s*"
    r"(?:(?P<month>\d{1,2})[月/-](?P<day>\d{1,2})日?|(?P<same_month_day>\d{1,2})日)"
    r"(?!\d)"
)


@dataclass(frozen=True)
class HistoryIntent:
    purpose: str
    requested_start: str | None = None
    requested_end: str | None = None
    scope: str = "historical_research"
    strict_window: bool = False
    window_error: str | None = None

    def __post_init__(self):
        if self.purpose not in {"retrospective_discovery", "historical_comparison"}:
            raise ValueError("invalid history purpose")
        if self.scope != "historical_research":
            raise ValueError("invalid historical scope")
        if type(self.strict_window) is not bool:
            raise ValueError("invalid strict window flag")
        for value in (self.requested_start, self.requested_end):
            if value is not None:
                date.fromisoformat(value)
        if (
            self.requested_start
            and self.requested_end
            and self.requested_start > self.requested_end
        ):
            raise ValueError("reversed historical window")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if value is None:
            return None
        if not isinstance(value, dict) or set(value) - {
            "purpose",
            "requested_start",
            "requested_end",
            "scope",
            "strict_window",
            "window_error",
        }:
            raise ValueError("invalid history intent")
        return cls(**value)


def infer_history_intent(question: str) -> HistoryIntent | None:
    if history_research_cancelled(question):
        return None
    purpose = (
        "historical_comparison"
        if _COMPARISON.search(question)
        else "retrospective_discovery"
        if _DISCOVERY.search(question)
        else None
    )
    if purpose is None:
        return None
    dates = []
    invalid_date = False
    matches = []
    for match in _DATE.finditer(question):
        try:
            dates.append(date(*(int(v) for v in match.groups())).isoformat())
            matches.append(match)
        except ValueError:
            invalid_date = True
            continue
    # Multiple anchors are not necessarily a range: September compared with August.
    strict = bool(
        re.search(r"只(?:研究|看|查|分析)|仅(?:研究|限|看)|限定|范围限制", question)
    )
    if invalid_date:
        return HistoryIntent(
            purpose,
            strict_window=strict,
            window_error="历史日期无效，请明确有效的研究日期",
        )
    # Chinese ranges commonly omit the repeated year/month. Only inherit from
    # a directly connected full anchor; never infer a year rollover or turn
    # separate comparison dates into a single authorized range.
    if matches:
        short_end = _SHORT_RANGE_END.match(question, matches[0].end())
        if short_end is not None:
            start = date.fromisoformat(dates[0])
            try:
                end = date(
                    start.year,
                    int(short_end["month"]) if short_end["month"] else start.month,
                    int(short_end["day"] or short_end["same_month_day"]),
                )
            except ValueError:
                return HistoryIntent(
                    purpose, strict_window=strict,
                    window_error="历史日期无效，请明确有效的研究日期",
                )
            if end < start:
                return HistoryIntent(
                    purpose, strict_window=strict,
                    window_error="历史起止日期顺序相反或跨年不明，请明确完整研究窗口",
                )
            return HistoryIntent(purpose, start.isoformat(), end.isoformat(), strict_window=strict)
    if len(matches) >= 2 and re.fullmatch(
        r"\s*(?:到|至|~|～|—|-)\s*", question[matches[0].end() : matches[1].start()]
    ):
        if dates[0] > dates[1]:
            return HistoryIntent(
                purpose,
                strict_window=strict,
                window_error="历史起止日期顺序相反，请明确研究窗口",
            )
        return HistoryIntent(purpose, dates[0], dates[1], strict_window=strict)
    if strict and matches:
        return HistoryIntent(
            purpose, strict_window=True,
            window_error="限定的历史窗口终点不明确，请给出完整起止日期",
        )
    return HistoryIntent(purpose, strict_window=strict)


def named_wave_subject(question: str) -> str | None:
    match = re.search(
        r"(?:这一波|这波|那一波|上一波)(?:的)?([\u4e00-\u9fffA-Za-z0-9]{2,20}?)(?:是?怎么|如何|的)",
        question,
    )
    if match is None:
        match = re.search(
            r"(?:这一波|这波|那一波|上一波)(?:的)?([\u4e00-\u9fffA-Za-z0-9]{2,20}?)"
            r"(?:行情|走势)(?=[，,。；;！？!?\s]|$)",
            question,
        )
    if match:
        subject = re.sub(r"(?:行情|走势|板块|题材)$", "", match[1])
        if subject and subject not in {
            "行情",
            "题材",
            "板块",
            "强势股",
            "上涨",
            "下跌",
        }:
            return subject
    for cue in re.finditer(r"(?:这一段|这段|这一波|这波)(?:行情|走势)", question):
        prefix = re.split(r"[，,。；;！？!?]", question[:cue.start()])[-1].strip()
        prefix = re.sub(r"^(?:请|帮我|事后|复盘|回溯|研究|分析|\s)+", "", prefix)
        prefix = re.sub(r"^[\d年月日./至到~～—\-\s]+", "", prefix)
        if re.fullmatch(r"[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9.]{1,19}", prefix):
            return prefix
    return None


def inherit_history_followup(
    question: str, previous: HistoryIntent | None
) -> HistoryIntent | None:
    """Only explicit continuations of a known history task inherit its permission."""
    if previous is None or history_research_cancelled(question):
        return None
    text = question.strip()
    if re.search(
        r"(?:以前|之前|过去|历史).{0,12}(?:类似|相似|呢|情况)|(?:失败案例|反例)", text
    ):
        return HistoryIntent("historical_comparison")
    if re.search(r"(?:继续|接着)(?:做)?(?:复盘|研究|比较)", text):
        return previous
    if re.match(
        r"(?:那|再|继续|把|将|只看|仅看|范围改|阈值|条件|窗口|样本|去掉|加入)", text
    ) and re.search(
        r"(?:阈值|条件|窗口|样本|范围|20\d{2}[-年]|改成|改为|去掉|加入|继续比较)", text
    ):
        parsed = infer_history_intent("历史行情复盘，" + text)
        if parsed and parsed.requested_start:
            return HistoryIntent(
                previous.purpose,
                parsed.requested_start,
                parsed.requested_end,
                strict_window=parsed.strict_window,
                window_error=parsed.window_error,
            )
        return previous
    return None


def history_research_cancelled(question: str) -> bool:
    return bool(
        re.search(
            r"(?:不要|不用|不做|停止|不再|别)(?:再|继续|做|进行)?"
            r"(?:历史|复盘|找反例|查反例)",
            question,
        )
    )


def assert_history_window(intent, start, end, *, cutoff=None):
    """One domain boundary for new queries and stored query projections."""
    if intent and intent.window_error:
        raise ValueError("historical_window_unresolved: " + intent.window_error)
    start = str(start) if start is not None else None
    end = str(end) if end is not None else None
    if cutoff is not None and end is not None and end > str(cutoff):
        raise ValueError("historical_artifact_after_information_cutoff")
    if (
        intent
        and intent.strict_window
        and intent.requested_start
        and intent.requested_end
    ):
        if (
            start is None
            or end is None
            or start < intent.requested_start
            or end > intent.requested_end
        ):
            raise ValueError(
                "historical_window_outside_authorized_scope: 用户明确限定了研究日期"
            )
