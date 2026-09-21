"""After daily-full: list theme DeepDive gaps and stock-card gaps. Does not ask IMA."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from intelligence.services.concept_page_gate import (
    STUB_BODY_MARKERS,
    STUB_TAG_RE,
    find_concept_path,
    is_stub_concept,
    parse_frontmatter_tags,
)
from intelligence.services.research_queue import QUEUE_DO_IMA, QUEUE_FIND_OFFICIAL, extract_queue

MEGA_UMBRELLA = frozenset(
    {
        "碳中和",
        "新能源车",
        "一带一路",
        "新型工业化",
        "高端装备",
        "化工",
        "医药",
        "医疗",
        "医疗服务",
        "光伏概念",
        "芯片概念",
        "机器人概念",
        "石油",
        "非银金融",
        "信创",
        "半导体",
    }
)
DENY_STOCKS = frozenset(
    {
        "*ST威领",
        "中关村",
        "中国石油",
        "宇树科技",
        "德源药业",
        "汉森制药",
        "湘财股份",
        "锦龙股份",
    }
)
NEED_CARD = ("type: stock_research", "Entity Baseline", "后续跟踪", "原始资料", "预期差")
DEEPDIVE_HINT = re.compile(r"DeepDive_ThemeRadar|ima_deep_dive|题材DeepDive|_DeepDive_")
L1_MARKERS = ("## 核心机制", "## 产业链", "## 产业链位置", "## 关键公司", "## 定义")


def _norm_queue(payload: dict[str, Any]) -> dict[str, Any]:
    return extract_queue(payload) or payload


def _theme_name(item: dict[str, Any]) -> str:
    return str(item.get("目标") or item.get("theme") or "").strip()


def _stocks(item: dict[str, Any]) -> list[str]:
    raw = item.get("强势股") or item.get("stocks") or []
    return [str(x).strip() for x in raw if str(x).strip() and str(x).strip() != "-"]


def _read_concept(wiki: Path, theme: str) -> tuple[Path | None, str]:
    path = find_concept_path(wiki / "concepts", theme)
    if path is None:
        return None, ""
    return path, path.read_text(encoding="utf-8", errors="replace")


def classify_page(text: str) -> str:
    """stub | thin_card | l1 | has_deepdive"""
    if not text.strip():
        return "missing"
    if DEEPDIVE_HINT.search(text) or "ima_deep_dive" in parse_frontmatter_tags(text):
        return "has_deepdive"
    if (
        "别名卡" in text
        or "不必再跑 DeepDive" in text
        or "不新跑 IMA" in text
        or "不伪造 15 章" in text
    ):
        return "l1"
    if is_stub_concept(text) or any(m in text for m in STUB_BODY_MARKERS) or any(
        STUB_TAG_RE.search(tag) for tag in parse_frontmatter_tags(text)
    ):
        return "stub"
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    headings = {ln for ln in lines if ln.startswith("## ")}
    marker_hits = sum(1 for marker in L1_MARKERS if marker in headings)
    if marker_hits >= 2 and len(lines) >= 20:
        return "l1"
    return "thin_card"


def best_page_class(theme: str, wikis: list[Path]) -> dict[str, Any]:
    best = "missing"
    rank = {"missing": 0, "stub": 1, "thin_card": 2, "l1": 3, "has_deepdive": 4}
    chosen = ""
    wiki_hit = ""
    for wiki in wikis:
        _path, text = _read_concept(wiki, theme)
        if not text:
            continue
        kind = classify_page(text)
        if rank[kind] >= rank[best]:
            best = kind
            chosen = text
            wiki_hit = str(wiki)
    return {"page_class": best, "wiki": wiki_hit, "chars": len(chosen)}


def has_full_stock_card(name: str, wikis: list[Path]) -> bool:
    for wiki in wikis:
        sources = wiki / "sources"
        if not sources.is_dir():
            continue
        for path in sources.glob(f"*{name}*"):
            if path.suffix != ".md" or "逻辑" not in path.name:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if all(token in text for token in NEED_CARD) and len(text) >= 8000:
                return True
    return False


def entity_exists(name: str, wikis: list[Path]) -> bool:
    for wiki in wikis:
        if (wiki / "entities" / f"{name}.md").is_file():
            return True
    return False


def classify_theme(theme: str, page_class: str, bucket: str) -> dict[str, str]:
    if bucket == QUEUE_FIND_OFFICIAL:
        return {"action": "route_disclosure", "reason": "复盘已标找公告，不重复做题材 DeepDive"}
    if theme in MEGA_UMBRELLA:
        return {"action": "skip_mega", "reason": "过宽伞页，15 章会写成行业综述"}
    if page_class == "has_deepdive":
        return {"action": "skip_have_deepdive", "reason": "已有 ThemeRadar / ima_deep_dive 15 章材料"}
    if page_class == "l1":
        return {"action": "skip_have_l1", "reason": "已有 L1（核心机制/产业链），不重复 IMA"}
    if page_class == "stub":
        return {"action": "run_deepdive", "reason": "占位页，走 15 章升 L1"}
    if page_class == "thin_card":
        return {"action": "run_deepdive", "reason": "概念卡偏薄，缺 15 章边界/分篮"}
    if page_class == "missing":
        return {"action": "skip_missing", "reason": "无概念页，fail closed 不空建"}
    return {"action": "skip_other", "reason": page_class}


def build_ima_gap_report(
    payload: dict[str, Any],
    *,
    wikis: list[Path],
    date: str = "",
) -> dict[str, Any]:
    queue = _norm_queue(payload)
    wikis = [Path(w) for w in wikis]
    theme_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for bucket in (QUEUE_DO_IMA, QUEUE_FIND_OFFICIAL):
        for item in queue.get(bucket) or []:
            theme = _theme_name(item)
            if not theme or theme in seen:
                continue
            seen.add(theme)
            page = best_page_class(theme, wikis)
            decision = classify_theme(theme, page["page_class"], bucket)
            theme_rows.append(
                {
                    "theme": theme,
                    "bucket": bucket,
                    "priority": item.get("优先级") or item.get("priority"),
                    "stocks": _stocks(item),
                    **page,
                    **decision,
                }
            )

    stock_rows: list[dict[str, Any]] = []
    stock_seen: set[str] = set()
    for item in queue.get(QUEUE_DO_IMA) or []:
        for name in _stocks(item):
            if name in stock_seen:
                continue
            stock_seen.add(name)
            if name in DENY_STOCKS:
                action, reason = "skip_deny", "deny：不建卡"
            elif not entity_exists(name, wikis):
                action, reason = "skip_no_entity", "无实体页，不空建"
            elif has_full_stock_card(name, wikis):
                action, reason = "skip_have_card", "已有 12 章逻辑卡"
            else:
                action, reason = "run_stock_card", "有实体、无完整 12 章卡"
            stock_rows.append({"company": name, "theme": _theme_name(item), "action": action, "reason": reason})

    run_themes = [r["theme"] for r in theme_rows if r["action"] == "run_deepdive"]
    run_stocks = [r["company"] for r in stock_rows if r["action"] == "run_stock_card"]
    return {
        "schema_version": "ima-gap/v1",
        "date": date or str(payload.get("date") or ""),
        "auto_fetch": False,
        "note": "只出清单。daily-full 不自动问 IMA；补卡/DeepDive 另开一轮。",
        "theme_run": run_themes,
        "stock_run": run_stocks,
        "themes": theme_rows,
        "stocks": stock_rows,
        "counts": {
            "theme_run": len(run_themes),
            "stock_run": len(run_stocks),
            "themes": len(theme_rows),
            "stocks": len(stock_rows),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# IMA 缺口 · {report.get('date') or '-'}",
        "",
        f"- 该跑题材 DeepDive：**{report['counts']['theme_run']}**",
        f"- 该补个股逻辑卡：**{report['counts']['stock_run']}**",
        f"- 不自动问 IMA（{report.get('note')}）",
        "",
        "## 题材",
        "",
        "| 题材 | 动作 | 页 | 理由 |",
        "|---|---|---|---|",
    ]
    for row in report.get("themes") or []:
        lines.append(f"| {row['theme']} | {row['action']} | {row['page_class']} | {row['reason']} |")
    lines += ["", "## 个股", "", "| 公司 | 动作 | 题材 | 理由 |", "|---|---|---|---|"]
    for row in report.get("stocks") or []:
        lines.append(f"| {row['company']} | {row['action']} | {row['theme']} | {row['reason']} |")
    return "\n".join(lines) + "\n"


def write_ima_gap_report(report: dict[str, Any], json_path: Path, md_path: Path | None = None) -> dict[str, Path]:
    json_path = Path(json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    written = {"json": json_path}
    if md_path:
        md_path = Path(md_path)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(report), encoding="utf-8")
        written["md"] = md_path
    return written
