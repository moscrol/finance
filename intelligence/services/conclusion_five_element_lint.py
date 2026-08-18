"""结论段 Knevo 五元素在场 lint（KC-13）。

配方：定性 ≤40 字 / 风险=变量+方向+信号 / 下一步分层 / 未验证变量+时点 /
替代路径。只做关键词+结构匹配，缺项进核验 warning，不阻断、不触发修订。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

ELEMENT_IDS: tuple[str, ...] = (
    "qualitative",
    "risk_signal",
    "next_layered",
    "unverified_timed",
    "alternative",
)
ELEMENT_LABELS = {
    "qualitative": "定性≤40字",
    "risk_signal": "风险=变量+方向+信号",
    "next_layered": "下一步分层",
    "unverified_timed": "未验证变量+时点",
    "alternative": "替代路径",
}

_HEADING_RE = re.compile(r"^## .+", re.M)
_QUAL_LINE_RE = re.compile(
    r"(?:直接定性|核心判断|定性)[*：:]*\s*(.+)",
)
_RISK_VAR_RE = re.compile(
    r"(毛利率|净利|订单|价格|股价|成交|换手|价量|需求|供给|客户|"
    r"收入|渗透|盘面|量价|拥挤|估值|库存|产能)"
)
_RISK_DIR_RE = re.compile(r"(升|降|回落|走弱|走强|上行|下行|扩大|收窄|改善|恶化|上涨|下跌|缩量|放量)")
_RISK_SIG_RE = re.compile(r"(若|当|跌破|突破|低于|高于|连续|一旦)")
_NEXT_PAIR_RE = re.compile(
    r"(?:T\s*\+\s*1).{0,40}(?:T\s*\+\s*[35])|(?:近(?:期|端).{0,16}中(?:期|端))"
)
_NEXT_NUMBERED_RE = re.compile(
    r"(?:下一步|如何验证).{0,400}(?:^|\n)\s*1[\.、)].{0,200}(?:^|\n)\s*2[\.、)]",
    re.S,
)
_UNVERIFIED_TIMED_RE = re.compile(
    r"(?:未验证|待验证|尚未验证).{0,40}"
    r"(?:T\s*\+|Q[1-4]|本周|本月|\d{1,2}月|20\d{2}-\d{2}-\d{2}|\d+\s*天)",
    re.S,
)
_ALTERNATIVE_RE = re.compile(
    r"(?:替代路径|否则(?:改看|看|切到)|另一条路径|若(?:被)?证伪则|备选路径|证伪后切)"
)


@dataclass(frozen=True)
class FiveElementLint:
    present_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]

    @property
    def present_count(self) -> int:
        return len(self.present_ids)


def extract_conclusion_section(text: str) -> str:
    raw = str(text or "")
    if "## 结论" in raw:
        return _slice_heading(raw, "## 结论")
    parts: list[str] = []
    for heading in ("## 核心判断", "## 反证与缺口", "## 下一步如何验证"):
        if heading in raw:
            parts.append(_slice_heading(raw, heading))
    return "\n".join(parts) if parts else raw


def lint_conclusion_five_elements(text: str) -> FiveElementLint:
    section = extract_conclusion_section(text)
    present: list[str] = []
    missing: list[str] = []
    detectors = {
        "qualitative": _has_short_qualitative,
        "risk_signal": _has_risk_signal,
        "next_layered": _has_layered_next,
        "unverified_timed": _has_unverified_timed,
        "alternative": _has_alternative,
    }
    for element_id in ELEMENT_IDS:
        if detectors[element_id](section):
            present.append(element_id)
        else:
            missing.append(element_id)
    return FiveElementLint(
        present_ids=tuple(present),
        missing_ids=tuple(missing),
    )


def render_presence_baseline(
    corpus: Mapping[str, str],
    *,
    as_of: str,
) -> str:
    rows = {key: lint_conclusion_five_elements(text) for key, text in corpus.items()}
    total = len(rows) or 1
    lines = [
        f"# 结论五元素在场率 {as_of}",
        "",
        "确定性 lint，不阻断输出。缺项只进核验 warning，先攒在场率再决定是否进修订轮。",
        "",
        f"样本 {len(rows)} 篇",
        "",
        "| 元素 | 在场 | 在场率 |",
        "| --- | ---: | ---: |",
    ]
    for element_id in ELEMENT_IDS:
        hit = sum(1 for report in rows.values() if element_id in report.present_ids)
        lines.append(
            f"| {element_id}（{ELEMENT_LABELS[element_id]}） | {hit}/{len(rows)} "
            f"| {hit / total:.0%} |"
        )
    lines.extend(("", "## 分篇", ""))
    for name, report in rows.items():
        missing = "、".join(report.missing_ids) if report.missing_ids else "无"
        lines.append(
            f"- {name}：{report.present_count}/{len(ELEMENT_IDS)} 在场；缺 {missing}"
        )
    lines.append("")
    return "\n".join(lines)


def _slice_heading(text: str, heading: str) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    rest = text[start + len(heading) :]
    nxt = _HEADING_RE.search(rest)
    return heading + (rest[: nxt.start()] if nxt else rest)


def _compact_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _has_short_qualitative(text: str) -> bool:
    for match in _QUAL_LINE_RE.finditer(text):
        body = re.sub(r"[*#>`]+", "", match.group(1)).strip()
        if 1 <= _compact_len(body) <= 40:
            return True
    return False


def _has_risk_signal(text: str) -> bool:
    riskish = "\n".join(
        line
        for line in text.splitlines()
        if any(token in line for token in ("风险", "反证", "若"))
    ) or text
    return bool(
        _RISK_VAR_RE.search(riskish)
        and _RISK_DIR_RE.search(riskish)
        and _RISK_SIG_RE.search(riskish)
    )


def _has_layered_next(text: str) -> bool:
    return bool(_NEXT_PAIR_RE.search(text) or _NEXT_NUMBERED_RE.search(text))


def _has_unverified_timed(text: str) -> bool:
    return bool(_UNVERIFIED_TIMED_RE.search(text))


def _has_alternative(text: str) -> bool:
    return bool(_ALTERNATIVE_RE.search(text))
