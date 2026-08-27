from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from intelligence.services import l3_evidence


NOISE_KEYWORDS = (
    "可转债",
    "转债",
    "赎回",
    "摘牌",
    "提示性公告",
    "股东大会",
    "董事会",
    "监事会",
    "权益分派",
    "分红",
    "独立董事",
    "章程",
    "法律意见书",
)

RISK_KEYWORDS = ("问询函", "监管", "澄清", "风险提示", "异动", "异常波动", "减持", "立案", "处罚")
ORDER_KEYWORDS = ("订单", "合同", "中标", "定点", "采购协议", "长协", "框架协议")
CUSTOMER_KEYWORDS = ("客户", "供应商", "导入", "认证", "验证", "送样", "供货", "供应")
CAPACITY_KEYWORDS = ("量产", "投产", "扩产", "产能", "产线", "募投项目", "项目进展", "结项")
FINANCIAL_KEYWORDS = ("收入", "营收", "毛利", "毛利率", "出货", "销量", "净利润", "产能利用率")


@dataclass(frozen=True)
class L3RawItem:
    source_type: str
    title: str
    summary: str
    citation: str = ""
    raw: str = ""


@dataclass(frozen=True)
class L3FactCandidate:
    company: str
    source_type: str
    title: str
    summary: str
    citation: str
    fact_type: str
    evidence_layer: str
    hardness: str
    disposition: str
    reason: str
    raw_excerpt: str = ""


@dataclass
class L3IngestResult:
    company: str
    sources: tuple[str, ...]
    days: int
    raw_items: list[L3RawItem] = field(default_factory=list)
    candidates: list[L3FactCandidate] = field(default_factory=list)
    rejected: list[L3FactCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"

    def write_json(self, path: str | Path) -> Path:
        out = Path(path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.to_json(), encoding="utf-8")
        return out


@dataclass
class L3ApplyResult:
    company: str
    kb_wiki: str
    payload_path: str
    apply: bool
    reviewed: bool
    selected_count: int = 0
    source_note_path: str = ""
    entity_path: str = ""
    created_sources: list[str] = field(default_factory=list)
    updated_entities: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    landing: str = "wiki_page"
    relations_updated: bool = False
    next_gate: str = "disclosure-archive reviewed apply"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"


def ingest_l3_company(
    company: str,
    *,
    sources: tuple[str, ...] = ("cninfo",),
    days: int = 30,
    limit: int = 20,
    lookup_config: l3_evidence.L3LookupConfig | None = None,
) -> L3IngestResult:
    cfg = lookup_config or l3_evidence.L3LookupConfig.from_env(enabled=True, limit=limit)
    cfg = l3_evidence.L3LookupConfig(
        enabled=cfg.enabled,
        company_cmd=cfg.company_cmd,
        cninfo_cmd=cfg.cninfo_cmd,
        sse_einteract_cmd=cfg.sse_einteract_cmd,
        timeout=cfg.timeout,
        limit=limit,
        days=days,
        python=cfg.python,
        pythonpath=cfg.pythonpath,
        cwd=cfg.cwd,
        cache_dir=cfg.cache_dir,
        cache_ttl_seconds=cfg.cache_ttl_seconds,
    )
    normalized_sources = tuple(s.strip() for s in sources if s.strip()) or ("cninfo",)
    bundle = l3_evidence.lookup_l3_company(company, sources=normalized_sources, config=cfg)
    result = L3IngestResult(
        company=company,
        sources=normalized_sources,
        days=days,
        warnings=list(bundle.warnings),
        commands=list(bundle.commands),
    )
    for item in bundle.items:
        raw = L3RawItem(
            source_type=item.source_type,
            title=item.title,
            summary=item.summary,
            citation=item.citation,
            raw=item.raw,
        )
        result.raw_items.append(raw)
        candidate = classify_l3_item(company, raw)
        if candidate.disposition in {"candidate", "official", "risk_boundary"}:
            result.candidates.append(candidate)
        else:
            result.rejected.append(candidate)
    return result


def classify_l3_item(company: str, item: L3RawItem) -> L3FactCandidate:
    text = _normalize(f"{item.title}\n{item.summary}\n{item.raw}")
    raw_excerpt = _squash(item.raw or item.summary, 300)

    if _has_any(text, RISK_KEYWORDS):
        return L3FactCandidate(
            company=company,
            source_type=item.source_type,
            title=item.title,
            summary=item.summary,
            citation=item.citation,
            fact_type="risk_or_regulatory_boundary",
            evidence_layer="L3_official",
            hardness="high",
            disposition="risk_boundary",
            reason="公告/互动内容涉及监管问询、澄清、异动、减持或风险边界，能约束预期交易。",
            raw_excerpt=raw_excerpt,
        )

    if _has_any(text, ORDER_KEYWORDS):
        return _candidate(company, item, "order_or_contract", "high", "订单/合同/中标/定点等关键词命中。", raw_excerpt)

    if _has_any(text, CUSTOMER_KEYWORDS):
        return _candidate(company, item, "customer_validation", "high", "客户、认证、验证、送样、供货等关键词命中。", raw_excerpt)

    if _has_any(text, CAPACITY_KEYWORDS):
        return _candidate(company, item, "capacity_or_project_progress", "medium", "量产、投产、扩产、产能或募投项目进展关键词命中。", raw_excerpt)

    if _has_any(text, FINANCIAL_KEYWORDS):
        return _candidate(company, item, "financial_or_shipment_metric", "high", "收入、毛利、出货、销量或产能利用率等财务/经营口径命中。", raw_excerpt)

    if _has_any(text, NOISE_KEYWORDS):
        return _rejected(company, item, "capital_market_or_governance_noise", "例行治理、可转债、权益分派或提示性公告，默认不沉淀为 L3 硬事实。", raw_excerpt)

    return _rejected(company, item, "low_signal", "未命中订单、客户、产能、财务、监管边界等 L3 高价值事实关键词。", raw_excerpt)


def render_l3_ingest_report(result: L3IngestResult) -> str:
    lines = [
        f"# L3 ingest：{result.company}",
        f"> sources={','.join(result.sources)} | days={result.days} | raw={len(result.raw_items)} | candidates={len(result.candidates)} | rejected={len(result.rejected)}",
        "",
        "## 候选事实",
    ]
    if result.candidates:
        for idx, item in enumerate(result.candidates, start=1):
            lines.append(
                f"- [C{idx}] {item.fact_type} / {item.hardness} / {item.evidence_layer}：{item.title}；理由：{item.reason}；来源：{item.citation or '-'}"
            )
    else:
        lines.append("- 无候选 L3 硬事实。")
    lines.extend(["", "## 过滤项"])
    if result.rejected:
        for idx, item in enumerate(result.rejected[:20], start=1):
            lines.append(f"- [R{idx}] {item.fact_type}：{item.title}；原因：{item.reason}")
    else:
        lines.append("- 无过滤项。")
    if result.warnings:
        lines.extend(["", "## 警告"])
        lines.extend(f"- {warning}" for warning in result.warnings)
    return "\n".join(lines) + "\n"


def _entity_path_for_ticker(entities: Path, code: str) -> Path | None:
    """Find the named entity page whose frontmatter tickers include this 6-digit code.

    Skip ``entities/<code>.md`` stubs so a leftover code-named page cannot win
    over the consumed Chinese-name page.
    """
    if not entities.is_dir():
        return None
    needle = f'"{code}"'
    hits: list[Path] = []
    for path in entities.glob("*.md"):
        if path.stem == code:
            continue
        try:
            head = path.read_text(encoding="utf-8")[:1200]
        except OSError:
            continue
        if "tickers:" in head and needle in head:
            hits.append(path)
    if not hits:
        return None
    hits.sort(key=lambda item: item.name)
    return hits[0]


def _resolve_entity_path(wiki: Path, company: str) -> Path:
    entities = wiki / "entities"
    direct = entities / f"{company}.md"
    if re.fullmatch(r"\d{6}", company):
        matched = _entity_path_for_ticker(entities, company)
        if matched is not None:
            return matched
    return direct


def apply_l3_payload(
    payload_path: str | Path,
    *,
    kb_wiki: str | Path,
    apply: bool = False,
    reviewed: bool = False,
    today: date | None = None,
) -> L3ApplyResult:
    """Turn reviewed runtime L3 candidates into durable wiki evidence notes.

    P1 intentionally writes only wiki source notes and entity-page summaries.
    It does not mutate relations/evidence_index; that remains a higher-risk
    reviewed-apply step in the knowledge-base disclosure archive workflow.
    """
    payload_file = Path(payload_path).expanduser()
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    company = str(payload.get("company") or "").strip()
    if not company:
        raise ValueError("payload missing company")

    wiki = Path(kb_wiki).expanduser()
    run_date = today or date.today()
    candidates = [_coerce_candidate(item) for item in payload.get("candidates", [])]
    selected = [
        item
        for item in candidates
        if item.get("disposition") in {"candidate", "official", "risk_boundary"}
        and str(item.get("evidence_layer") or "").startswith("L3")
    ]
    entity_path = _resolve_entity_path(wiki, company)
    source_title = f"{entity_path.stem}_L3官方证据_{run_date.strftime('%Y%m%d')}"
    source_path = wiki / "sources" / f"{_safe_filename(source_title)}.md"
    result = L3ApplyResult(
        company=company,
        kb_wiki=str(wiki),
        payload_path=str(payload_file),
        apply=apply,
        reviewed=reviewed,
        selected_count=len(selected),
        source_note_path=str(source_path),
        entity_path=str(entity_path),
    )
    if not selected:
        result.warnings.append("payload 中没有可写入的 L3 候选；未生成 wiki 写入计划。")
        return result

    if not apply:
        result.skipped.append("dry-run：未写 wiki。添加 --apply 后才会创建 source note 并更新 entity。")
        return result

    source_path.parent.mkdir(parents=True, exist_ok=True)
    entity_path.parent.mkdir(parents=True, exist_ok=True)
    source_note = _render_source_note(
        company=company,
        source_title=source_title,
        selected=selected,
        payload=payload,
        run_date=run_date,
        reviewed=reviewed,
    )
    source_path.write_text(source_note, encoding="utf-8")
    result.created_sources.append(str(source_path))

    changed, warning = _append_entity_l3_section(
        entity_path,
        company=company,
        source_title=source_title,
        selected=selected,
        run_date=run_date,
    )
    if changed:
        result.updated_entities.append(str(entity_path))
    if warning:
        result.warnings.append(warning)
    return result


def render_l3_apply_report(result: L3ApplyResult) -> str:
    mode = "apply" if result.apply else "dry-run"
    lines = [
        f"# L3 apply：{result.company}",
        f"> mode={mode} | reviewed={str(result.reviewed).lower()} | selected={result.selected_count}",
        "",
        "## 写入计划",
        f"- source note：{result.source_note_path or '-'}",
        f"- entity page：{result.entity_path or '-'}",
    ]
    if result.created_sources or result.updated_entities:
        lines.extend(["", "## 已写入"])
        lines.extend(f"- source：{path}" for path in result.created_sources)
        lines.extend(f"- entity：{path}" for path in result.updated_entities)
    if result.skipped:
        lines.extend(["", "## 跳过"])
        lines.extend(f"- {item}" for item in result.skipped)
    if result.warnings:
        lines.extend(["", "## 警告"])
        lines.extend(f"- {item}" for item in result.warnings)
    lines.extend(
        [
            "",
            "## 边界",
            f"- landing={result.landing} | relations_updated={str(result.relations_updated).lower()}",
            f"- next_gate：{result.next_gate}",
            "- 本命令只把候选沉淀为 wiki source/entity L3 证据资产；暂不改 relations/evidence_index。",
            "- 结构化读侧可扫这些 source note（landing=wiki_page）；要进图谱排序必须走 next_gate。",
        ]
    )
    return "\n".join(lines) + "\n"


def _candidate(
    company: str,
    item: L3RawItem,
    fact_type: str,
    hardness: str,
    reason: str,
    raw_excerpt: str,
) -> L3FactCandidate:
    return L3FactCandidate(
        company=company,
        source_type=item.source_type,
        title=item.title,
        summary=item.summary,
        citation=item.citation,
        fact_type=fact_type,
        evidence_layer="L3_candidate",
        hardness=hardness,
        disposition="candidate",
        reason=reason,
        raw_excerpt=raw_excerpt,
    )


def _rejected(
    company: str,
    item: L3RawItem,
    fact_type: str,
    reason: str,
    raw_excerpt: str,
) -> L3FactCandidate:
    return L3FactCandidate(
        company=company,
        source_type=item.source_type,
        title=item.title,
        summary=item.summary,
        citation=item.citation,
        fact_type=fact_type,
        evidence_layer="not_l3",
        hardness="low",
        disposition="reject",
        reason=reason,
        raw_excerpt=raw_excerpt,
    )


def _coerce_candidate(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        return {}
    return {str(key): "" if value is None else str(value) for key, value in item.items()}


def _render_source_note(
    *,
    company: str,
    source_title: str,
    selected: list[dict[str, str]],
    payload: dict[str, Any],
    run_date: date,
    reviewed: bool,
) -> str:
    sources = ", ".join(str(item) for item in payload.get("sources", []) if item) or "-"
    commands = payload.get("commands", []) or []
    lines = [
        "---",
        f"title: {source_title}",
        "type: official_l3_evidence",
        f"company: {company}",
        "evidence_layer: L3",
        "source_quality: official_disclosure_or_exchange_interaction",
        "fact_hardness: hard_fact_candidate",
        "update_type: delta",
        f"review_required: {str(not reviewed).lower()}",
        f"created: {run_date.isoformat()}",
        f"updated: {run_date.isoformat()}",
        f"publish_time: {run_date.isoformat()}",
        f"available_time: {run_date.isoformat()}",
        "log: []",
        "---",
        "",
        f"# {company} L3 官方证据候选（{run_date.isoformat()}）",
        "",
        "> 由 finance `l3-ingest apply` 从公告/互动易运行时查询结果沉淀。"
        "本页保存可复核候选，不等同于公告全文；进入 relations/evidence_index 前仍需复核原文。",
        "",
        f"- 查询窗口：近 {payload.get('days', '-')} 天",
        f"- 数据源：{sources}",
        f"- 候选数量：{len(selected)}",
        "",
        "## 候选事实表",
        "",
        "| 序号 | 来源 | 类型 | 硬度 | 标题 | 摘要/摘录 | 链接/引用 | 入库理由 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for idx, item in enumerate(selected, start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    f"C{idx}",
                    _md_cell(item.get("source_type")),
                    _md_cell(item.get("fact_type")),
                    _md_cell(item.get("hardness")),
                    _md_cell(item.get("title")),
                    _md_cell(item.get("raw_excerpt") or item.get("summary")),
                    _md_cell(item.get("citation")),
                    _md_cell(item.get("reason")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## 调用痕迹"])
    if commands:
        lines.extend(f"- `{cmd}`" for cmd in commands)
    else:
        lines.append("- 无命令痕迹。")
    lines.extend(
        [
            "",
            "## 资产化边界",
            "",
            "- 适合进入问答 RAG/全文检索：是。",
            "- 适合直接进入题材图谱评分：否，需人工复核后再升级。",
            "- 适合直接作为买卖结论：否，只能作为事实证据或反证边界。",
        ]
    )
    return "\n".join(lines) + "\n"


def _append_entity_l3_section(
    entity_path: Path,
    *,
    company: str,
    source_title: str,
    selected: list[dict[str, str]],
    run_date: date,
) -> tuple[bool, str]:
    source_link = f"[[{source_title}]]"
    if entity_path.exists():
        text = entity_path.read_text(encoding="utf-8")
    else:
        text = (
            "---\n"
            f"title: {company}\n"
            'tags: ["entity", "company"]\n'
            f"created: {run_date.isoformat()}\n"
            f"updated: {run_date.isoformat()}\n"
            "revision: 1\n"
            "sources: []\n"
            "log: []\n"
            "---\n\n"
            f"# {company}\n"
        )
    if source_link in text:
        return False, f"{entity_path} 已包含 {source_link}，跳过重复追加。"

    text = _touch_entity_frontmatter(text, run_date, source_link)
    if "## L3 官方证据" not in text:
        text = text.rstrip() + "\n\n## L3 官方证据\n"
    entry = [
        "",
        f"### {run_date.isoformat()}｜{source_link}",
        "",
    ]
    for item in selected:
        entry.append(
            "- "
            f"{item.get('title') or '未命名事实'}："
            f"{item.get('fact_type') or '-'} / {item.get('evidence_layer') or '-'} / {item.get('hardness') or '-'}；"
            f"{item.get('reason') or '无理由'}"
        )
    text = text.rstrip() + "\n" + "\n".join(entry) + "\n"
    entity_path.write_text(text, encoding="utf-8")
    return True, ""


def _touch_entity_frontmatter(text: str, run_date: date, source_link: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end < 0:
        return text
    fm = text[4:end].splitlines()
    body = text[end + 4 :]
    seen_updated = False
    seen_revision = False
    seen_sources = False
    out: list[str] = []
    for line in fm:
        if line.startswith("updated:"):
            out.append(f"updated: {run_date.isoformat()}")
            seen_updated = True
        elif line.startswith("revision:"):
            out.append(f"revision: {_increment_revision(line)}")
            seen_revision = True
        elif line.startswith("sources:"):
            out.append(_append_source_inline(line, source_link))
            seen_sources = True
        else:
            out.append(line)
    if not seen_updated:
        out.append(f"updated: {run_date.isoformat()}")
    if not seen_revision:
        out.append("revision: 1")
    if not seen_sources:
        out.append(f'sources: ["{source_link}"]')
    return "---\n" + "\n".join(out) + "\n---" + body


def _increment_revision(line: str) -> int:
    match = re.search(r"(\d+)", line)
    return int(match.group(1)) + 1 if match else 1


def _append_source_inline(line: str, source_link: str) -> str:
    if source_link in line:
        return line
    if "[" in line and "]" in line:
        prefix, rest = line.split("[", 1)
        inner, suffix = rest.rsplit("]", 1)
        inner = inner.strip()
        appended = f'{inner}, "{source_link}"' if inner else f'"{source_link}"'
        return f"{prefix}[{appended}]{suffix}"
    return f'sources: ["{source_link}"]'


@dataclass(frozen=True)
class AppliedL3Note:
    company: str
    path: str
    note_date: str
    titles: tuple[str, ...]
    landing: str = "wiki_page"


def iter_applied_l3_notes(
    kb_wiki: str | Path,
    companies: list[str] | tuple[str, ...],
    *,
    limit_per_company: int = 2,
) -> list[AppliedL3Note]:
    """读 ``l3-ingest apply`` 写下的 source note。不读 evidence_index。"""
    sources = Path(kb_wiki).expanduser() / "sources"
    if not sources.is_dir():
        return []
    notes: list[AppliedL3Note] = []
    for company in dict.fromkeys(str(name).strip() for name in companies if str(name).strip()):
        matches = sorted(sources.glob(f"{_safe_filename(company)}_L3官方证据_*.md"), reverse=True)
        for path in matches[: max(1, limit_per_company)]:
            notes.append(_parse_applied_l3_note(path, company))
    return notes


def format_applied_l3_lines(notes: list[AppliedL3Note]) -> list[str]:
    lines: list[str] = []
    for note in notes:
        titles = "；".join(note.titles[:3]) or "（无候选标题）"
        locator = Path(note.path).name
        lines.append(
            f"[R-wiki] {note.company} L3页 {note.note_date} "
            f"landing={note.landing} relations=false "
            f"next=disclosure-archive reviewed apply | {locator} | {titles}"
        )
    return lines


def _parse_applied_l3_note(path: Path, company: str) -> AppliedL3Note:
    text = path.read_text(encoding="utf-8")
    date_match = re.search(r"(\d{8})", path.stem)
    note_date = date_match.group(1) if date_match else ""
    if len(note_date) == 8:
        note_date = f"{note_date[:4]}-{note_date[4:6]}-{note_date[6:]}"
    titles: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| 序号"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 5 and (cells[0].isdigit() or re.fullmatch(r"C\d+", cells[0])):
            title = cells[4]
            if title and title != "-":
                titles.append(title)
    return AppliedL3Note(
        company=company,
        path=str(path),
        note_date=note_date,
        titles=tuple(titles),
    )


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "l3_evidence"


def _md_cell(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "-")).replace("|", "\\|").strip()


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _squash(text: str, limit: int) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return clean if len(clean) <= limit else clean[: limit - 1] + "…"
