from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from html.parser import HTMLParser

from market_feature_store.signals import DOUBLE_RED_DESCRIPTION


MAX_SUMMARY_ITEMS = 3
MAX_CANDIDATE_ITEMS = 6
MAX_ACTION_ITEMS = 8


@dataclass(frozen=True)
class ReportMetric:
    label: str
    value: str
    tone: str | None = None
    context: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"label": self.label, "value": self.value}
        if self.tone:
            result["tone"] = self.tone
        if self.context:
            result["context"] = self.context
        return result


@dataclass(frozen=True)
class ReportItem:
    title: str
    summary: str
    badges: tuple[str, ...] = ()
    meta: tuple[tuple[str, str], ...] = ()
    next_action: str | None = None
    details: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "title": self.title,
            "summary": self.summary,
            "badges": list(self.badges),
        }
        if self.meta:
            result["meta"] = [
                {"label": label, "value": value} for label, value in self.meta
            ]
        if self.next_action:
            result["next_action"] = self.next_action
        if self.details:
            result["details"] = list(self.details)
        return result


@dataclass(frozen=True)
class ReportSection:
    title: str
    items: tuple[ReportItem, ...]

    def to_dict(self) -> dict[str, object]:
        return {"title": self.title, "items": [item.to_dict() for item in self.items]}


@dataclass(frozen=True)
class ReportProvenance:
    canonical_path: str | None
    rendered_path: str | None
    warnings: tuple[str, ...]
    original_report_available: bool
    generated_at: str | None = None
    original_artifact_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "canonical_path": self.canonical_path,
            "rendered_path": self.rendered_path,
            "warnings": list(self.warnings),
            "original_report_available": self.original_report_available,
        }
        if self.generated_at:
            result["generated_at"] = self.generated_at
        if self.original_artifact_id:
            result["original_artifact_id"] = self.original_artifact_id
        return result


@dataclass(frozen=True)
class DailyReportProjection:
    report_type: str
    title: str
    date: str | None
    source_mode: str
    plain_summary: tuple[str, ...]
    metrics: tuple[ReportMetric, ...]
    sections: tuple[ReportSection, ...]
    glossary: tuple[tuple[str, str], ...]
    provenance: ReportProvenance

    def to_dict(self) -> dict[str, object]:
        return {
            "report_type": self.report_type,
            "title": self.title,
            "date": self.date,
            "source_mode": self.source_mode,
            "plain_summary": list(self.plain_summary[:MAX_SUMMARY_ITEMS]),
            "metrics": [metric.to_dict() for metric in self.metrics],
            "sections": [section.to_dict() for section in self.sections],
            "glossary": [
                {"term": term, "definition": definition}
                for term, definition in self.glossary
            ],
            "provenance": self.provenance.to_dict(),
        }


_AGENT_GLOSSARY = (
    ("IMA", "快速建立题材边界、产业链位置与核心公司的研究卡。"),
    ("L1", "叙事线索：用于发现方向，尚不能单独确认事实。"),
    ("L2", "基线资料：主营、财务与行业位置等稳定背景。"),
    ("L3", "官方验证：公告、订单、调研或客户验证等硬事实。"),
    ("L4", "盘面验证：价格、成交、新高与涨停等市场反馈。"),
)

_REVIEW_GLOSSARY = (
    ("双红", DOUBLE_RED_DESCRIPTION),
    ("边际量", "相对近期基准的成交变化，用于观察资金增减。"),
    ("市场阶段", "根据指数、量能和广度归纳的当前市场位置。"),
)

_CLASSIFICATION_LABELS = {
    "old_logic_wakeup": "旧逻辑重新活跃",
    "new_logic_candidate": "新逻辑候选",
    "data_gap": "数据待补",
    "noise_or_unconfirmed": "待确认信号",
}

_QUEUE_LABELS = {
    "today_do_ima": "补题材研究",
    "today_find_official_evidence": "补官方证据",
    "today_wait_market_validation": "等待市场验证",
    "today_downgrade_or_watch": "降级观察",
}


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _mappings(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strings(value: object, *, limit: int | None = None) -> list[str]:
    if not isinstance(value, list):
        return []
    result = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return result if limit is None else result[:limit]


def _text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return str(value)
    return ""


def _number(value: object) -> float:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return float(value)
    return 0


def _count(mapping: Mapping[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return len(_mappings(value))


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _date_from_path(source_path: str) -> str | None:
    match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", source_path)
    return match.group(1) if match else None


def _candidate_item(
    candidate: Mapping[str, object], classification: str
) -> ReportItem | None:
    title = _text(candidate.get("matched_theme")) or _text(candidate.get("query"))
    if not title:
        return None
    lifecycle = _mapping(
        candidate.get("logic_lifecycle") or candidate.get("生命周期")
    )
    judgment = _mapping(candidate.get("research_judgment"))
    validation = _mapping(
        candidate.get("market_validation") or candidate.get("盘面验证")
    )
    lifecycle_stage = _text(lifecycle.get("生命周期阶段"))
    evidence_status = _text(judgment.get("证据状态")) or _text(
        lifecycle.get("证据状态")
    )
    summary = (
        _text(validation.get("验证结论"))
        or _text(judgment.get("判断理由"))
        or "已进入今日优先观察范围，仍需按证据边界复核。"
    )
    missing_layers = _strings(judgment.get("缺失证据层"), limit=4)
    stocks = _strings(candidate.get("strong_stocks"), limit=5)
    meta: list[tuple[str, str]] = []
    priority = _text(candidate.get("priority_score"))
    if priority:
        meta.append(("优先级", priority))
    if stocks:
        meta.append(("代表股票", "、".join(stocks)))
    fallback_actions = _strings(candidate.get("next_actions"), limit=1)
    return ReportItem(
        title=title,
        summary=summary,
        badges=_unique(
            [
                _CLASSIFICATION_LABELS.get(classification, ""),
                lifecycle_stage,
                evidence_status,
            ]
        ),
        meta=tuple(meta),
        next_action=_text(judgment.get("建议动作"))
        or (fallback_actions[0] if fallback_actions else None),
        details=tuple(f"缺失：{layer}" for layer in missing_layers),
    )


def _action_item(value: Mapping[str, object], queue_key: str) -> ReportItem | None:
    title = _text(value.get("目标"))
    if not title:
        return None
    stocks = _strings(value.get("强势股"), limit=5)
    meta: list[tuple[str, str]] = []
    priority = _text(value.get("优先级"))
    if priority:
        meta.append(("优先级", priority))
    if stocks:
        meta.append(("代表股票", "、".join(stocks)))
    return ReportItem(
        title=title,
        summary=_text(value.get("理由")) or "按今日研究优先级继续验证。",
        badges=_unique(
            [
                _QUEUE_LABELS[queue_key],
                _text(value.get("生命周期阶段")),
                _text(value.get("证据状态")),
            ]
        ),
        meta=tuple(meta),
        next_action=_text(value.get("建议动作")),
    )


def project_daily_agent(
    payload: dict[str, object], *, source_path: str
) -> dict[str, object]:
    decision = _mapping(payload.get("decision"))
    queue = _mapping(payload.get("research_queue"))
    if not decision and not queue:
        raise ValueError("Daily Agent payload does not contain report data")

    decision_groups = {
        key: _mappings(decision.get(key)) for key in _CLASSIFICATION_LABELS
    }
    queue_summary = _mapping(queue.get("summary"))
    queue_counts = {
        key: _count(queue_summary, key)
        if key in queue_summary
        else len(_mappings(queue.get(key)))
        for key in _QUEUE_LABELS
    }
    queue_total = _count(queue_summary, "total")
    if "total" not in queue_summary:
        queue_total = sum(queue_counts.values())

    candidate_values: list[tuple[float, ReportItem]] = []
    for classification, candidates in decision_groups.items():
        for candidate in candidates:
            item = _candidate_item(candidate, classification)
            if item:
                candidate_values.append(
                    (_number(candidate.get("priority_score")), item)
                )
    candidate_values.sort(key=lambda value: value[0], reverse=True)
    candidate_items = tuple(
        item for _, item in candidate_values[:MAX_CANDIDATE_ITEMS]
    )

    action_values: list[tuple[float, ReportItem]] = []
    for queue_key in _QUEUE_LABELS:
        for value in _mappings(queue.get(queue_key)):
            item = _action_item(value, queue_key)
            if item:
                action_values.append((_number(value.get("优先级")), item))
    action_values.sort(key=lambda value: value[0], reverse=True)
    action_items = tuple(item for _, item in action_values[:MAX_ACTION_ITEMS])

    old_count = len(decision_groups["old_logic_wakeup"])
    new_count = len(decision_groups["new_logic_candidate"])
    plain_summary = [
        f"{old_count} 个旧逻辑重新活跃，{new_count} 个新方向进入候选。",
        (
            f"今日研究队列共 {queue_total} 项：补题材研究 "
            f"{queue_counts['today_do_ima']} 项，补官方证据 "
            f"{queue_counts['today_find_official_evidence']} 项。"
        ),
    ]
    if candidate_items:
        plain_summary.append(
            f"优先关注 {candidate_items[0].title}，结论仍需结合证据层级验证。"
        )

    missing_layers = sorted(
        {
            detail.removeprefix("缺失：")
            for item in candidate_items
            for detail in item.details
        }
    )
    evidence_items = (
        ReportItem(
            title="当前证据边界",
            summary=(
                "仍需补齐 " + "、".join(missing_layers) + "。"
                if missing_layers
                else "当前优先项未声明额外证据缺口。"
            ),
            badges=("结论需验证",),
            meta=(
                ("生成时间", _text(payload.get("generated_at"))),
            )
            if _text(payload.get("generated_at"))
            else (),
        ),
    )
    sections = (
        ReportSection("值得关注", candidate_items),
        ReportSection("今天要做什么", action_items),
        ReportSection("证据边界", evidence_items),
    )
    warnings = tuple(_strings(payload.get("notes"), limit=3))
    projection = DailyReportProjection(
        report_type="daily_agent",
        title="日常研究雷达",
        date=_text(payload.get("date")) or _date_from_path(source_path),
        source_mode="canonical_json",
        plain_summary=tuple(plain_summary),
        metrics=(
            ReportMetric("旧逻辑重新活跃", str(old_count), "attention"),
            ReportMetric("需要补题材研究", str(queue_counts["today_do_ima"])),
            ReportMetric(
                "需要补官方证据",
                str(queue_counts["today_find_official_evidence"]),
                "attention",
            ),
            ReportMetric(
                "等待市场验证", str(queue_counts["today_wait_market_validation"])
            ),
            ReportMetric(
                "降级或观察", str(queue_counts["today_downgrade_or_watch"]), "muted"
            ),
        ),
        sections=sections,
        glossary=_AGENT_GLOSSARY,
        provenance=ReportProvenance(
            canonical_path=source_path,
            rendered_path=None,
            warnings=warnings,
            original_report_available=False,
            generated_at=_text(payload.get("generated_at")) or None,
        ),
    )
    return projection.to_dict()


def _normalise_heading(heading: str) -> str:
    return re.sub(r"^\s*\d+\s*[.、-]?\s*", "", heading).strip()


def _clean_markdown_text(value: str) -> str:
    value = value.strip().lstrip(">").strip()
    value = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = value.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", value).strip()


def _parse_markdown_sections(source: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in source.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", raw_line)
        if heading:
            current = _normalise_heading(heading.group(1))
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(raw_line)
    return sections


def _markdown_table(lines: list[str]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [_clean_markdown_text(cell) for cell in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if cells[:2] in (["维度", "结论"], ["项目", "数值"], ["表", "状态"]):
            continue
        rows.append((cells[0], cells[-1]))
    return rows


def _assessment_text(lines: list[str]) -> str:
    candidates = [
        _clean_markdown_text(line)
        for line in lines
        if line.strip().startswith(">") and _clean_markdown_text(line)
    ]
    return " ".join(candidates[:2])


def _markdown_warnings(source: str) -> tuple[str, ...]:
    warnings = []
    for line in source.splitlines():
        text = _clean_markdown_text(line)
        if line.strip().startswith(">") and "数据降级" in text:
            warnings.append(text)
    return tuple(warnings[:3])


def _project_daily_review(
    core_rows: list[tuple[str, str]],
    assessment: str,
    coverage_rows: list[tuple[str, str]],
    *,
    source_path: str,
    date: str | None,
    source_mode: str,
    warnings: tuple[str, ...] = (),
) -> dict[str, object]:
    if not core_rows and not assessment:
        raise ValueError("Daily Review source does not contain supported sections")
    core = dict(core_rows)
    summary = [
        core[label]
        for label in ("市场性质", "涨停方向", "强度状态")
        if core.get(label)
    ]
    if assessment and assessment not in summary:
        summary.append(assessment)

    metrics = tuple(
        ReportMetric(label, core[label])
        for label in ("指数表现", "量能状态", "情绪状态", "成交集中", "强度状态")
        if core.get(label)
    )
    direction_items = tuple(
        ReportItem(label, core[label])
        for label in ("题材量能", "新高方向", "涨停方向", "加权强股")
        if core.get(label)
    )
    risk_items: list[ReportItem] = []
    if assessment:
        risk_items.append(ReportItem("市场环境判断", assessment, ("待后续验证",)))
    missing_coverage = [
        f"{name}：{status}"
        for name, status in coverage_rows
        if status and status.upper() != "OK"
    ]
    if missing_coverage:
        risk_items.append(
            ReportItem(
                "数据覆盖提醒",
                "；".join(missing_coverage[:5]),
                ("数据不完整",),
            )
        )
    professional_items = tuple(
        ReportItem(label, value)
        for label, value in core_rows
        if label in {"市场性质", "指数表现", "量能状态", "情绪状态", "成交集中", "强度状态"}
    )
    canonical_path: str | None = source_path
    rendered_path: str | None = None
    original_report_available = False
    if source_mode == "legacy_html_projection":
        warnings = warnings + (
            "当前内容来自历史 HTML 的兼容投影，仅提取核心看板和市场环境判断；请对照原始报告核验。",
        )
        canonical_path = None
        rendered_path = source_path
        original_report_available = True
    projection = DailyReportProjection(
        report_type="daily_review",
        title=f"{date} 每日市场复盘" if date else "每日市场复盘",
        date=date or _date_from_path(source_path),
        source_mode=source_mode,
        plain_summary=tuple(summary[:MAX_SUMMARY_ITEMS]),
        metrics=metrics,
        sections=(
            ReportSection("主要方向", direction_items),
            ReportSection("风险与验证", tuple(risk_items)),
            ReportSection("专业数据", professional_items),
        ),
        glossary=_REVIEW_GLOSSARY,
        provenance=ReportProvenance(
            canonical_path=canonical_path,
            rendered_path=rendered_path,
            warnings=warnings,
            original_report_available=original_report_available,
        ),
    )
    return projection.to_dict()


def project_daily_review_markdown(
    source: str, *, source_path: str, date: str | None
) -> dict[str, object]:
    sections = _parse_markdown_sections(source)
    core_rows = _markdown_table(sections.get("核心看板", []))
    assessment_lines = sections.get("市场环境总评", []) or sections.get(
        "市场环境判断", []
    )
    coverage_rows = _markdown_table(sections.get("数据覆盖检查", []))
    return _project_daily_review(
        core_rows,
        _assessment_text(assessment_lines),
        coverage_rows,
        source_path=source_path,
        date=date,
        source_mode="canonical_markdown",
        warnings=_markdown_warnings(source),
    )


class _DailyReviewHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current_section: str | None = None
        self.heading_parts: list[str] | None = None
        self.row: list[str] | None = None
        self.cell_parts: list[str] | None = None
        self.core_rows: list[tuple[str, str]] = []
        self.assessment_parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del attrs
        if tag in {"script", "style"}:
            self.ignored_depth += 1
            return
        if self.ignored_depth:
            return
        if tag == "h2":
            self.heading_parts = []
        elif tag == "tr" and self.current_section == "core":
            self.row = []
        elif tag in {"th", "td"} and self.row is not None:
            self.cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.ignored_depth:
            self.ignored_depth -= 1
            return
        if self.ignored_depth:
            return
        if tag == "h2" and self.heading_parts is not None:
            heading = _normalise_heading(" ".join(self.heading_parts))
            if heading == "核心看板":
                self.current_section = "core"
            elif heading in {"市场环境总评", "市场环境判断"}:
                self.current_section = "assessment"
            else:
                self.current_section = None
            self.heading_parts = None
        elif tag in {"th", "td"} and self.cell_parts is not None:
            if self.row is not None:
                self.row.append(" ".join(self.cell_parts).strip())
            self.cell_parts = None
        elif tag == "tr" and self.row is not None:
            if (
                len(self.row) >= 2
                and self.row[:2] != ["维度", "结论"]
                and self.row[0]
                and self.row[1]
            ):
                self.core_rows.append((self.row[0], self.row[1]))
            self.row = None

    def handle_data(self, data: str) -> None:
        if self.ignored_depth:
            return
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self.heading_parts is not None:
            self.heading_parts.append(text)
        elif self.cell_parts is not None:
            self.cell_parts.append(text)
        elif self.current_section == "assessment":
            self.assessment_parts.append(text)


def project_daily_review_html(
    source: str, *, source_path: str, date: str | None
) -> dict[str, object]:
    parser = _DailyReviewHTMLParser()
    parser.feed(source)
    assessment = re.sub(r"\s+", " ", " ".join(parser.assessment_parts)).strip()
    return _project_daily_review(
        parser.core_rows,
        assessment,
        [],
        source_path=source_path,
        date=date,
        source_mode="legacy_html_projection",
    )
