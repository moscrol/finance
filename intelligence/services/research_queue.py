from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from typing import Any

from intelligence.services import catalyst_attribution


QUEUE_DO_IMA = "today_do_ima"
QUEUE_FIND_OFFICIAL = "today_find_official_evidence"
QUEUE_WAIT_MARKET = "today_wait_market_validation"
QUEUE_DOWNGRADE = "today_downgrade_or_watch"

SCHEMA_VERSION = "research-queue/v1"
QUEUE_JSON_SUFFIX = "-research-queue.json"
QUEUE_MD_SUFFIX = "-research-queue.md"
QUEUE_HTML_SUFFIX = "-research-queue.html"
AGENT_JSON_SUFFIX = "-daily-agent.json"

ACTION_LABELS = {
    QUEUE_DO_IMA: "今日该做 IMA",
    QUEUE_FIND_OFFICIAL: "今日该找公告/调研/订单",
    QUEUE_WAIT_MARKET: "今日等盘面验证",
    QUEUE_DOWNGRADE: "今日降级/观察",
}

QUEUE_SECTIONS = (
    (QUEUE_DO_IMA, "今日该做 IMA", "info"),
    (QUEUE_FIND_OFFICIAL, "今日该找公告/调研/订单", "watch"),
    (QUEUE_WAIT_MARKET, "今日等盘面验证", "good"),
    (QUEUE_DOWNGRADE, "今日降级/观察", "gap"),
)

BLOCKING_GAPS = {
    "placeholder_market_theme",
    "missing_concept",
    "missing_entity_exposure",
    "missing_evidence",
    "missing_source_trace",
}

WEAK_STAGES = {"高位分歧", "衰退观察", "证伪退出"}
RESEARCHABLE_STAGES = {"新出现", "旧逻辑唤醒", "升温验证", "加速定价"}

_DATE_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EXACT_AGENT_TO_QUEUE = {
    "daily-agent.json": "research-queue.json",
    "daily-agent.md": "research-queue.md",
    "daily-agent.html": "research-queue.html",
}
_AGENT_SUFFIX_TO_QUEUE = (
    ("-daily-agent.json", QUEUE_JSON_SUFFIX),
    ("-daily-agent.md", QUEUE_MD_SUFFIX),
    ("-daily-agent.html", QUEUE_HTML_SUFFIX),
)


def build_research_queue(decision: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    queue: dict[str, Any] = {
        QUEUE_DO_IMA: [],
        QUEUE_FIND_OFFICIAL: [],
        QUEUE_WAIT_MARKET: [],
        QUEUE_DOWNGRADE: [],
        "skipped": {
            "data_gap_or_unconfirmed": [],
            "no_clear_action": [],
        },
    }
    for row in _iter_rows(decision):
        bucket, reason = _classify_row(row)
        item = _queue_item(row, bucket, reason)
        if bucket in ACTION_LABELS:
            queue[bucket].append(item)
        elif bucket == "data_gap_or_unconfirmed":
            queue["skipped"]["data_gap_or_unconfirmed"].append(item)
        else:
            queue["skipped"]["no_clear_action"].append(item)

    for key in (QUEUE_DO_IMA, QUEUE_FIND_OFFICIAL, QUEUE_WAIT_MARKET, QUEUE_DOWNGRADE):
        queue[key].sort(key=lambda item: float(item.get("优先级") or 0), reverse=True)
    queue["summary"] = {
        QUEUE_DO_IMA: len(queue[QUEUE_DO_IMA]),
        QUEUE_FIND_OFFICIAL: len(queue[QUEUE_FIND_OFFICIAL]),
        QUEUE_WAIT_MARKET: len(queue[QUEUE_WAIT_MARKET]),
        QUEUE_DOWNGRADE: len(queue[QUEUE_DOWNGRADE]),
        "total": sum(len(queue[key]) for key in (QUEUE_DO_IMA, QUEUE_FIND_OFFICIAL, QUEUE_WAIT_MARKET, QUEUE_DOWNGRADE)),
        "skipped": sum(len(items) for items in queue["skipped"].values()),
    }
    return queue


def extract_queue(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Accept a wrapped artifact, a full daily-agent report, or a bare queue."""
    if not isinstance(payload, dict):
        return None
    nested = payload.get("research_queue")
    if isinstance(nested, dict):
        return nested
    if any(key in payload for key in ACTION_LABELS):
        return payload
    return None


def wrap_research_queue_artifact(
    queue: dict[str, Any],
    *,
    date: str,
    generated_at: str | None = None,
    source: str = "daily_agent",
) -> dict[str, Any]:
    summary = queue.get("summary") if isinstance(queue.get("summary"), dict) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "date": date,
        "generated_at": generated_at,
        "source": source,
        "human_summary": human_summary(summary),
        "research_queue": queue,
    }


def human_summary(summary: dict[str, Any] | None) -> str:
    summary = summary or {}
    total = int(summary.get("total") or 0)
    ima = int(summary.get(QUEUE_DO_IMA) or 0)
    official = int(summary.get(QUEUE_FIND_OFFICIAL) or 0)
    wait = int(summary.get(QUEUE_WAIT_MARKET) or 0)
    down = int(summary.get(QUEUE_DOWNGRADE) or 0)
    return (
        f"今日研究队列 {total} 项：IMA {ima} / 找公告 {official} / 等盘面 {wait} / 降级 {down}"
    )


def sibling_queue_path(path: str | Path) -> Path:
    """Map a daily-agent output path to the canonical research-queue sibling."""
    target = Path(path)
    name = target.name
    exact = _EXACT_AGENT_TO_QUEUE.get(name)
    if exact:
        return target.with_name(exact)
    for old, new in _AGENT_SUFFIX_TO_QUEUE:
        if name.endswith(old):
            return target.with_name(name[: -len(old)] + new)
    return target.with_name(f"{target.stem}-research-queue{target.suffix}")


def default_queue_paths(finance_root: str | Path, date: str) -> tuple[Path, Path, Path]:
    root = Path(finance_root)
    exports = root / "market_feature_store" / "exports"
    daily = root / "复盘" / "daily" / date
    return (
        exports / f"{date}{QUEUE_JSON_SUFFIX}",
        exports / f"{date}{QUEUE_MD_SUFFIX}",
        daily / f"{date}{QUEUE_HTML_SUFFIX}",
    )


def find_research_queue_path(
    exports: str | Path,
    date: str | None = None,
    *,
    as_of: str | None = None,
) -> Path | None:
    """Prefer ``{date}-research-queue.json``, then nested daily-agent JSON."""
    ranked = _ranked_queue_paths(Path(exports))
    if date:
        matches = [path for item_date, _rank, path in ranked if item_date == date]
        return matches[0] if matches else None
    if as_of:
        ranked = [item for item in ranked if item[0] <= as_of]
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    return ranked[0][2]


def load_research_queue(
    exports: str | Path,
    date: str | None = None,
    *,
    as_of: str | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    path = find_research_queue_path(exports, date, as_of=as_of)
    if path is None:
        return None, {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return path, {}
    if not isinstance(payload, dict):
        return path, {}
    return path, payload


def write_research_queue_outputs(
    report_or_queue: dict[str, Any],
    *,
    json_path: str | Path,
    md_path: str | Path | None = None,
    html_path: str | Path | None = None,
    kb_queue_path: str | Path | None = None,
) -> dict[str, Path]:
    """Write the canonical research-queue artifact. No fidelity 1.2 gate."""
    payload = report_or_queue if isinstance(report_or_queue, dict) else {}
    queue = extract_queue(payload) or _empty_queue()
    date = str(payload.get("date") or "")
    artifact = wrap_research_queue_artifact(
        queue,
        date=date,
        generated_at=str(payload.get("generated_at") or "") or None,
        source="daily_agent",
    )
    written: dict[str, Path] = {}
    json_file = Path(json_path).expanduser()
    json_file.parent.mkdir(parents=True, exist_ok=True)
    json_file.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    written["json"] = json_file
    if md_path:
        md_file = Path(md_path).expanduser()
        md_file.parent.mkdir(parents=True, exist_ok=True)
        md_file.write_text(render_research_queue_markdown(artifact), encoding="utf-8")
        written["md"] = md_file
    if html_path:
        html_file = Path(html_path).expanduser()
        html_file.parent.mkdir(parents=True, exist_ok=True)
        html_file.write_text(render_research_queue_html(artifact), encoding="utf-8")
        written["html"] = html_file
    kb_queue = payload.get("kb_ingest_queue")
    if isinstance(kb_queue, dict):
        kb_name = f"{date}-kb-ingest-queue.json" if date else "kb-ingest-queue.json"
        kb_file = Path(kb_queue_path).expanduser() if kb_queue_path else json_file.with_name(kb_name)
        kb_file.parent.mkdir(parents=True, exist_ok=True)
        kb_file.write_text(json.dumps(kb_queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written["kb_ingest"] = kb_file
    return written


def render_queue_grid_html(queue: dict[str, Any], *, limit: int = 6) -> str:
    columns = []
    for key, title, kind in QUEUE_SECTIONS:
        items = list(queue.get(key) or [])
        body = []
        if not items:
            body.append('<p class="empty small">暂无</p>')
        for item in items[:limit]:
            stocks = "、".join(item.get("强势股") or []) or "-"
            missing = "、".join(item.get("缺失证据层") or []) or "-"
            body.append(
                '<li>'
                f'<strong>{escape(str(item.get("目标") or "-"))}</strong>'
                f'<span>{escape(str(item.get("理由") or "-"))}</span>'
                f'<small>priority={escape(str(item.get("优先级") or "-"))}｜生命周期={escape(str(item.get("生命周期阶段") or "-"))}｜裁判={escape(str(item.get("证据状态") or "-"))}</small>'
                f'<small>缺：{escape(missing)}｜强势股：{escape(stocks)}</small>'
                f'<small>催化：{escape(catalyst_attribution.catalyst_brief(item.get("催化归因")))}</small>'
                '</li>'
            )
        columns.append(
            '<div class="task-col">'
            f'<h3>{_html_badge(title, kind)}</h3>'
            '<ul>'
            + "".join(body)
            + '</ul></div>'
        )
    return '<div class="task-grid">' + "".join(columns) + "</div>"


def render_research_queue_markdown(artifact: dict[str, Any], *, limit: int = 12) -> str:
    queue = extract_queue(artifact) or _empty_queue()
    summary = queue.get("summary") if isinstance(queue.get("summary"), dict) else {}
    date = str(artifact.get("date") or "-")
    lines = [
        f"# 研究队列 · {date}",
        "",
        f"- schema：{artifact.get('schema_version') or SCHEMA_VERSION}",
        f"- 来源：{artifact.get('source') or 'daily_agent'}",
        f"- 生成：{artifact.get('generated_at') or '-'}",
        f"- {artifact.get('human_summary') or human_summary(summary)}",
        "",
    ]
    for key, title, _kind in QUEUE_SECTIONS:
        items = list(queue.get(key) or [])
        lines.append(f"## {title}")
        lines.append("")
        if not items:
            lines.append("- 无")
            lines.append("")
            continue
        for item in items[:limit]:
            stocks = "、".join(item.get("强势股") or []) or "-"
            missing = "、".join(item.get("缺失证据层") or []) or "-"
            catalyst = catalyst_attribution.catalyst_brief(item.get("催化归因"))
            lines.append(
                f"- {item.get('目标', '-')}｜priority={item.get('优先级', '-')}｜"
                f"生命周期={item.get('生命周期阶段', '-')}｜裁判={item.get('证据状态', '-')}｜"
                f"缺={missing}｜催化={catalyst}｜强势股={stocks}｜理由={item.get('理由', '-')}"
            )
        lines.append("")
    skipped = (queue.get("skipped") or {}).get("data_gap_or_unconfirmed") or []
    if skipped:
        lines.append("## 未进队列（数据缺口 / 待确认）")
        lines.append("")
        for item in skipped[:limit]:
            lines.append(f"- {item.get('目标', '-')}｜{item.get('理由', '-')}")
        lines.append("")
    return "\n".join(lines)


def render_research_queue_html(artifact: dict[str, Any], *, limit: int = 8) -> str:
    queue = extract_queue(artifact) or _empty_queue()
    title = f"研究队列 - {artifact.get('date') or '-'}"
    summary_text = escape(str(artifact.get("human_summary") or human_summary(queue.get("summary"))))
    generated = escape(str(artifact.get("generated_at") or "-"))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>
:root{{--paper:#fffaf1;--ink:#17140f;--muted:#746b5d;--line:#d8cbbb;--accent:#0057ff;--card:#fffdf8;--good:#0f7b43;--watch:#a35b00;--gap:#b3261e;--soft:#f3eadb}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:'Avenir Next','PingFang SC','Hiragino Sans GB',sans-serif;line-height:1.65}}
main{{max-width:1280px;margin:0 auto;padding:24px}}
.hero{{border:1px solid var(--ink);background:var(--card);padding:22px 24px;margin-bottom:18px}}
.kicker{{font-size:12px;letter-spacing:.18em;color:var(--accent);font-weight:900}}
h1{{margin:4px 0 0;font-size:32px;line-height:1.15}}
h2{{font-size:20px;margin:0 0 12px}}
h3{{font-size:16px;margin:0}}
.hero p{{margin:8px 0 0;color:var(--muted)}}
.section{{border:1px solid var(--line);background:var(--card);padding:18px;margin:14px 0}}
.badge{{display:inline-flex;align-items:center;border:1px solid var(--line);border-radius:999px;padding:2px 9px;font-size:12px;font-weight:800;background:#fff;margin:2px 4px 2px 0;white-space:nowrap}}
.badge.good{{color:var(--good);border-color:#91c7aa;background:#eef8f2}}
.badge.watch{{color:var(--watch);border-color:#e2b36f;background:#fff7e8}}
.badge.gap{{color:var(--gap);border-color:#e7aaa5;background:#fff0ee}}
.badge.info{{color:var(--accent);border-color:#9bbcff;background:#eef4ff}}
.empty{{color:var(--muted);margin:0}}
.empty.small{{font-size:13px}}
.task-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}}
.task-col{{border:1px solid var(--line);background:#fff;padding:12px}}
.task-col h3{{margin-bottom:8px}}
.task-col ul{{list-style:none;margin:0;padding:0;display:grid;gap:10px}}
.task-col li{{border-top:1px solid var(--line);padding-top:8px;display:grid;gap:4px}}
.task-col li:first-child{{border-top:0;padding-top:0}}
.task-col span,.task-col small{{color:var(--muted);font-size:12px}}
@media (max-width:1100px){{.task-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media (max-width:680px){{main{{padding:14px}}.task-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<main>
  <section class="hero">
    <div class="kicker">RESEARCH QUEUE</div>
    <h1>{escape(title)}</h1>
    <p>{summary_text}。这是 intelligence 的当日研究入口，不是第二份市场复盘。</p>
    <p>生成时间 {generated}</p>
  </section>
  <section class="section">
    <h2>今日研究任务</h2>
    {render_queue_grid_html(queue, limit=limit)}
  </section>
</main>
</body>
</html>
"""


def _ranked_queue_paths(exports: Path) -> list[tuple[str, int, Path]]:
    ranked: list[tuple[str, int, Path]] = []
    if not exports.is_dir():
        return ranked
    for path in exports.glob(f"*{QUEUE_JSON_SUFFIX}"):
        date = _date_from_suffix(path.name, QUEUE_JSON_SUFFIX)
        if date:
            ranked.append((date, 0, path))
    for path in exports.glob(f"*{AGENT_JSON_SUFFIX}"):
        date = _date_from_suffix(path.name, AGENT_JSON_SUFFIX)
        if date:
            ranked.append((date, 1, path))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return ranked


def _date_from_suffix(name: str, suffix: str) -> str | None:
    if not name.endswith(suffix):
        return None
    date = name[: -len(suffix)]
    return date if _DATE_NAME_RE.fullmatch(date) else None


def _empty_queue() -> dict[str, Any]:
    return {
        QUEUE_DO_IMA: [],
        QUEUE_FIND_OFFICIAL: [],
        QUEUE_WAIT_MARKET: [],
        QUEUE_DOWNGRADE: [],
        "skipped": {"data_gap_or_unconfirmed": [], "no_clear_action": []},
        "summary": {
            QUEUE_DO_IMA: 0,
            QUEUE_FIND_OFFICIAL: 0,
            QUEUE_WAIT_MARKET: 0,
            QUEUE_DOWNGRADE: 0,
            "total": 0,
            "skipped": 0,
        },
    }


def _html_badge(text: Any, kind: str = "muted") -> str:
    return f'<span class="badge {escape(kind)}">{escape(str(text))}</span>'


def _iter_rows(decision: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in ("old_logic_wakeup", "new_logic_candidate", "data_gap", "noise_or_unconfirmed"):
        rows.extend(row for row in decision.get(bucket, []) if isinstance(row, dict))
    return rows


def _classify_row(row: dict[str, Any]) -> tuple[str, str]:
    gaps = set(row.get("data_gaps") or [])
    if gaps & BLOCKING_GAPS or row.get("classification") in {"data_gap", "noise_or_unconfirmed"}:
        return "data_gap_or_unconfirmed", "仍有概念、公司、证据、来源或占位缺口，先留在回补/待确认区。"

    stage = _stage(row)
    layers = set(_judgment(row).get("已有证据层") or [])
    missing = set(_judgment(row).get("缺失证据层") or [])
    status = str(_judgment(row).get("证据状态") or "-")
    has_l1 = "L1 叙事线索" in layers
    has_l2 = bool({"L2 基线", "L2 官方基线"} & layers)
    has_l3_candidate = "L3 候选硬事实" in layers
    has_l3_official = "L3 官方验证" in layers
    has_l4 = "L4 盘面验证" in layers

    if stage in WEAK_STAGES:
        return QUEUE_DOWNGRADE, f"生命周期转弱为{stage}，先降级观察，等待新事实或盘面重新扩散。"

    if has_l2 and (has_l3_candidate or has_l3_official) and ("L4 盘面验证" in missing or not has_l4):
        return QUEUE_WAIT_MARKET, "已有 L2/L3，但缺 L4 盘面验证，先等市场重新定价或扩散。"

    if has_l1 and (not has_l2 or "L2 基线" in missing or "L2 官方基线" in missing or "L3 官方验证" in missing):
        return QUEUE_FIND_OFFICIAL, "已有 L1 旧逻辑材料，下一步补 L2 基线或 L3 官方验证，不重复做同一题材 IMA。"

    if ("L3 官方验证" in missing or not has_l3_official) and (has_l2 or has_l3_candidate or status in {"能力栈候选", "重点验证"}):
        return QUEUE_FIND_OFFICIAL, "已有 L2 或 L3 候选，但缺 L3 官方验证，优先找公告、调研、订单、客户验证。"

    if stage in RESEARCHABLE_STAGES and not has_l1 and not has_l2:
        return QUEUE_DO_IMA, "盘面触发但缺 L1/L2 叙事或基线材料，优先做 IMA/题材地图补边界。"

    if status == "已有事实验证" and has_l4:
        return QUEUE_WAIT_MARKET, "事实验证已较完整，今天重点观察盘面持续性和扩散。"

    return "no_clear_action", "证据和生命周期暂未触发明确研究动作，保留人工复核。"


def _queue_item(row: dict[str, Any], bucket: str, reason: str) -> dict[str, Any]:
    judgment = _judgment(row)
    lifecycle = row.get("logic_lifecycle") or row.get("生命周期") or {}
    return {
        "目标": row.get("query") or row.get("matched_theme") or "-",
        "动作": ACTION_LABELS.get(bucket, "暂不进入研究任务"),
        "理由": reason,
        "优先级": row.get("priority_score"),
        "生命周期阶段": lifecycle.get("生命周期阶段") or "-",
        "阶段变化": lifecycle.get("阶段变化") or "-",
        "证据状态": judgment.get("证据状态") or "-",
        "已有证据层": list(judgment.get("已有证据层") or []),
        "缺失证据层": list(judgment.get("缺失证据层") or []),
        "数据缺口": list(row.get("data_gaps") or []),
        "强势股": list(row.get("strong_stocks") or [])[:5],
        "建议动作": _suggest_action(bucket, judgment, lifecycle),
    }


def _suggest_action(bucket: str, judgment: dict[str, Any], lifecycle: dict[str, Any]) -> str:
    if bucket == QUEUE_DO_IMA:
        return "补 IMA/题材地图，目标是补清题材边界、产业链位置、核心公司和 L1/L2 材料。"
    if bucket == QUEUE_FIND_OFFICIAL:
        return (
            "查公告、互动易、调研纪要、订单/合同、客户验证，把候选事实升级为 L3 官方验证。"
            "口径：L3 测公司端兑现度，驱动看催化归因；查无公告读作「尚未兑现」，不降级。"
        )
    if bucket == QUEUE_WAIT_MARKET:
        return "不急着补材料，观察强势股扩散、成交边际和后续是否继续进候选。"
    if bucket == QUEUE_DOWNGRADE:
        return "降级观察；除非新增 L3 事实或盘面重新扩散，否则减少研究投入。"
    if judgment.get("建议动作"):
        return str(judgment["建议动作"])
    if lifecycle.get("下一步"):
        return str(lifecycle["下一步"])
    return "人工复核。"


def _judgment(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("research_judgment") or {}


def _stage(row: dict[str, Any]) -> str:
    lifecycle = row.get("logic_lifecycle") or row.get("生命周期") or {}
    return str(lifecycle.get("生命周期阶段") or "-")
