from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "market_feature_store" / "exports"


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"missing file: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"failed to read json: {path}: {exc}"]
    if not isinstance(data, dict):
        return None, [f"json root is not an object: {path}"]
    return data, []


def normalize(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def clean(value: Any, limit: int | None = None) -> str:
    text = str(value if value is not None else "").replace("|", "／").replace("\n", " ").strip()
    if not text:
        return "-"
    if limit and len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def theme_keys(item: dict[str, Any]) -> set[str]:
    keys = {normalize(item.get("market_theme")), normalize(item.get("canonical_concept"))}
    return {key for key in keys if key}


def old_items(old_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not old_data:
        return []
    rows = []
    for section_name in ("deep_themes", "watch_themes"):
        for index, item in enumerate(as_list(old_data.get(section_name)), 1):
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row["_old_section"] = "deep" if section_name == "deep_themes" else "watch"
            row["_old_rank"] = index
            row["_old_overall_rank"] = len(rows) + 1
            rows.append(row)
    return rows


def new_items(new_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not new_data:
        return []
    rows = []
    for index, item in enumerate(as_list(new_data.get("candidates")), 1):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["_new_rank"] = index
        rows.append(row)
    return rows


def match_old_for_new(new_item: dict[str, Any], old_rows: list[dict[str, Any]], used_old: set[int]) -> tuple[int | None, dict[str, Any] | None]:
    keys = theme_keys(new_item)
    for index, old_item in enumerate(old_rows):
        if index in used_old:
            continue
        if keys & theme_keys(old_item):
            return index, old_item
    return None, None


def build_pairs(new_rows: list[dict[str, Any]], old_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    pairs = []
    used_old: set[int] = set()
    for new_item in new_rows:
        old_index, old_item = match_old_for_new(new_item, old_rows, used_old)
        if old_index is None or old_item is None:
            continue
        used_old.add(old_index)
        pairs.append({"new": new_item, "old": old_item})
    new_only = [item for item in new_rows if all(item is not pair["new"] for pair in pairs)]
    old_only = [item for index, item in enumerate(old_rows) if index not in used_old]
    return pairs, new_only, old_only


def trigger_text(item: dict[str, Any]) -> str:
    return "、".join(str(value) for value in as_list(item.get("trigger_types"))) or "-"


def evidence_count(item: dict[str, Any]) -> int:
    status = item.get("knowledge_status") if isinstance(item.get("knowledge_status"), dict) else {}
    if status.get("evidence_count") is not None:
        try:
            return int(status.get("evidence_count") or 0)
        except (TypeError, ValueError):
            return 0
    context = item.get("knowledge_context") if isinstance(item.get("knowledge_context"), dict) else {}
    return len(as_list(context.get("evidence_items")))


def concept_count(item: dict[str, Any]) -> int:
    status = item.get("knowledge_status") if isinstance(item.get("knowledge_status"), dict) else {}
    if status.get("concept_count") is not None:
        try:
            return int(status.get("concept_count") or 0)
        except (TypeError, ValueError):
            return 0
    context = item.get("knowledge_context") if isinstance(item.get("knowledge_context"), dict) else {}
    return len(as_list(context.get("matched_concepts")))


def exposure_count(item: dict[str, Any]) -> int:
    status = item.get("knowledge_status") if isinstance(item.get("knowledge_status"), dict) else {}
    if status.get("exposure_count") is not None:
        try:
            return int(status.get("exposure_count") or 0)
        except (TypeError, ValueError):
            return 0
    context = item.get("knowledge_context") if isinstance(item.get("knowledge_context"), dict) else {}
    return len(as_list(context.get("candidate_companies")))


def gaps(item: dict[str, Any]) -> list[str]:
    status = item.get("knowledge_status") if isinstance(item.get("knowledge_status"), dict) else {}
    return [str(value) for value in as_list(status.get("backfill_gaps")) if str(value).strip()]


def company_names(item: dict[str, Any], limit: int = 5) -> str:
    rows = as_list(item.get("candidate_companies"))
    if not rows:
        context = item.get("knowledge_context") if isinstance(item.get("knowledge_context"), dict) else {}
        rows = as_list(context.get("candidate_companies"))
    names = []
    for row in rows[:limit]:
        if isinstance(row, dict):
            name = row.get("company") or row.get("entity") or row.get("name")
            if name:
                names.append(str(name))
    return "、".join(names) if names else "-"


def sector_metrics(item: dict[str, Any]) -> dict[str, Any]:
    evidence = item.get("market_evidence") if isinstance(item.get("market_evidence"), dict) else {}
    metrics = evidence.get("sector_metrics") if isinstance(evidence.get("sector_metrics"), dict) else {}
    return metrics


def signal_summary(item: dict[str, Any]) -> str:
    metrics = sector_metrics(item)
    if not metrics:
        return "-"
    values = []
    if metrics.get("pct_chg") is not None:
        values.append(f"涨幅{clean(metrics.get('pct_chg'))}%")
    if metrics.get("diff_ratio") is not None:
        values.append(f"边际量{clean(metrics.get('diff_ratio'))}%")
    if metrics.get("amount") is not None:
        values.append(f"成交{clean(metrics.get('amount'))}亿")
    if metrics.get("in_capacity_top3") is not None:
        values.append("容量前三" if metrics.get("in_capacity_top3") else "非容量前三")
    return "，".join(values) if values else "-"


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        rows = [["-" for _ in headers]]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(clean(value) for value in row) + " |")
    return "\n".join(lines)


def render_report(trade_date: str, new_path: Path, old_path: Path, new_data: dict[str, Any] | None, old_data: dict[str, Any] | None, warnings: list[str], top: int) -> str:
    new_rows = new_items(new_data)
    old_rows = old_items(old_data)
    pairs, new_only, old_only = build_pairs(new_rows, old_rows)
    gap_counter = Counter(gap for item in new_rows for gap in gaps(item))
    gap_theme_rows = [[gap, count, "、".join(item.get("market_theme", "") for item in new_rows if gap in gaps(item))] for gap, count in sorted(gap_counter.items())]
    lines = [
        f"# {trade_date} theme-candidates 对照验证报告",
        "",
        "> 说明：本报告只读取本地 JSON 产物；不查询 DuckDB，不读取 wiki 正文，不写知识库，不调用大模型，不包含买卖指令。",
        "",
        "## 一、输入文件状态",
        "",
        md_table(
            ["项目", "状态", "路径/数值"],
            [
                ["新 theme-candidates JSON", "存在" if new_path.exists() else "缺失", new_path],
                ["旧 triggered-themes JSON", "存在" if old_path.exists() else "缺失", old_path],
                ["新候选数量", len(new_rows), "candidates"],
                ["Deep 候选数量", len(as_list(new_data.get("deep_candidates"))) if new_data else 0, "deep_candidates"],
                ["Watch 候选数量", len(as_list(new_data.get("watch_candidates"))) if new_data else 0, "watch_candidates"],
                ["Long Tail 候选数量", len(as_list(new_data.get("long_tail_candidates"))) if new_data else 0, "long_tail_candidates"],
                ["旧候选数量", len(old_rows), "deep_themes + watch_themes"],
                ["共同候选", len(pairs), "按 market_theme/canonical_concept 归一匹配"],
                ["仅新产物", len(new_only), "-"],
                ["仅旧产物", len(old_only), "-"],
            ],
        ),
        "",
        "## 二、新旧候选重合情况",
        "",
        md_table(
            ["类型", "题材"],
            [
                ["共同候选", "、".join(pair["new"].get("market_theme", "") for pair in pairs) or "-"],
                ["仅新产物", "、".join(item.get("market_theme", "") for item in new_only) or "-"],
                ["仅旧产物", "、".join(item.get("market_theme", "") for item in old_only) or "-"],
            ],
        ),
        "",
        "## 三、Top N 排序对照",
        "",
        md_table(
            ["新排名", "新题材", "新评分", "新触发", "旧排名", "旧题材", "旧评分", "旧触发", "匹配状态"],
            [
                [
                    item.get("_new_rank"),
                    item.get("market_theme"),
                    item.get("priority_score"),
                    trigger_text(item),
                    pair["old"].get("_old_overall_rank") if pair else "-",
                    pair["old"].get("market_theme") if pair else "-",
                    pair["old"].get("priority_score") if pair else "-",
                    trigger_text(pair["old"]) if pair else "-",
                    "matched" if pair else "new_only",
                ]
                for item in new_rows[:top]
                for pair in [next((row for row in pairs if row["new"] is item), None)]
            ],
        ),
        "",
        "## 四、知识库命中与缺口",
        "",
        md_table(
            ["题材", "标准概念", "概念数", "公司暴露数", "证据数", "缺口", "盘面信号"],
            [
                [
                    item.get("market_theme"),
                    item.get("canonical_concept"),
                    concept_count(item),
                    exposure_count(item),
                    evidence_count(item),
                    "、".join(gaps(item)) or "-",
                    signal_summary(item),
                ]
                for item in new_rows[:top]
            ],
        ),
        "",
        "## 五、候选公司覆盖抽查",
        "",
        md_table(
            ["题材", "候选公司 Top5", "证据数", "缺口"],
            [[item.get("market_theme"), company_names(item), evidence_count(item), "、".join(gaps(item)) or "-"] for item in new_rows[:top]],
        ),
        "",
        "## 六、待补库清单",
        "",
        md_table(["缺口", "次数", "涉及题材"], gap_theme_rows),
        "",
        "## 七、工程结论",
        "",
        f"- **候选重合度**：{len(pairs)} / {max(len(new_rows), 1)}（以新候选数为主口径）。",
        f"- **新产物覆盖**：共 {len(new_rows)} 个候选，旧产物共 {len(old_rows)} 个 deep/watch 候选。",
        f"- **补库缺口**：{'、'.join(f'{key}={value}' for key, value in sorted(gap_counter.items())) or '-'}。",
        "- **工作台建议**：先保留为 QA 辅助产物，不替换旧题材简报；待多日期抽样稳定后再决定展示字段。",
        "",
    ]
    if warnings:
        lines.extend(["## 八、Warnings", "", *[f"- {warning}" for warning in warnings], ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="对照新 theme-candidates 与旧 triggered-themes JSON，生成只读 QA Markdown。")
    parser.add_argument("trade_date", help="交易日 YYYY-MM-DD")
    parser.add_argument("--new-json", default=None, help="新 theme-candidates JSON 路径")
    parser.add_argument("--old-json", default=None, help="旧 triggered-themes JSON 路径")
    parser.add_argument("--out-md", default=None, help="输出 QA Markdown 路径")
    parser.add_argument("--top", type=int, default=10, help="Top N 对照数量")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    new_path = Path(args.new_json).expanduser() if args.new_json else EXPORT_DIR / f"{args.trade_date}-theme-candidates.json"
    old_path = Path(args.old_json).expanduser() if args.old_json else EXPORT_DIR / f"{args.trade_date}-triggered-themes.json"
    out_path = Path(args.out_md).expanduser() if args.out_md else EXPORT_DIR / f"{args.trade_date}-theme-candidates-qa.md"
    new_data, new_warnings = load_json(new_path)
    old_data, old_warnings = load_json(old_path)
    warnings = [*new_warnings, *old_warnings]
    report = render_report(args.trade_date, new_path, old_path, new_data, old_data, warnings, args.top)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(out_path)
    return 0 if new_data is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
