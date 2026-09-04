"""收据：一次回测的读数 + 它成立的条件，JSON 为真本源，md 是渲染物。

落点 ``methodology/receipts/<rule_id>@v<version>/<date>.json``（gitignore，可重建），台账地图有登记。
成立条件块照 ``scripts/check_test_receipt.py`` 的思路：源库 ``max(trade_date)``、``label_version``、
``rule_id@version``、N、data_gap 日数、树 / 解释器 / revision / dirty——下一个读者比对条件即可
决定采信还是重跑，不用重跑一遍来验证。

收据**不是**预注册假设：要立案走 ``docs/prediction-ledger.md`` 的 R-号流程，本模块不写那张表。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runner import RunResult, ScanResult

RECEIPT_SCHEMA = "methodology-backtest-receipt/v0"
SCAN_SCHEMA = "methodology-backtest-scan/v0"

_VERDICT_CN = {
    "insufficient_n": "样本不足",
    "not_distinguishable": "与基准不可区分",
    "supported": "支持",
    "refuted": "证伪",
}


def _pct(x: float | None, digits: int = 1) -> str:
    return "—" if x is None else f"{x * 100:.{digits}f}%"


def _num(x: float | None, digits: int = 2) -> str:
    return "—" if x is None else f"{x:.{digits}f}"


def _now_iso(now: datetime | None) -> str:
    ts = now or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat(timespec="seconds")


def build_receipt(
    result: RunResult,
    *,
    rule_path: str | None,
    rule_sha256: str | None,
    environment: dict[str, Any],
    test_mode: str = "single",
    bh: dict[str, Any] | None = None,
    appendix: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if test_mode not in ("single", "scan"):
        raise ValueError(f"test_mode 必须是 single / scan，得到 {test_mode!r}")
    rule = result.rule
    rd = result.readout
    verdict = (bh or {}).get("verdict_bh", rd.verdict) if test_mode == "scan" else rd.verdict
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "generated_at": _now_iso(now),
        "test_mode": test_mode,
        "exploratory": test_mode == "scan",
        "multiple_testing_note": (
            f"scan 模式：{len((bh or {}).get('family', []))} 条规则同族，Benjamini–Hochberg q={(bh or {}).get('q')}"
            if test_mode == "scan"
            else "单次检验，未做多重校正；同一批规则请用 scan"
        ),
        "rule": {
            "rule_id": rule.rule_id,
            "version": rule.version,
            "ref": rule.ref,
            "title": rule.title,
            "path": rule_path,
            "sha256": rule_sha256,
            "scope": rule.raw.get("scope"),
            "condition": rule.raw.get("condition"),
            "outcome": rule.raw.get("outcome"),
            "baseline": {"kind": rule.baseline_kind},
            "min_n": rule.min_n,
            "notes": rule.raw.get("notes"),
        },
        "window": {"start": result.window[0], "end": result.window[1]},
        "baseline_window": (
            {"start": result.baseline_window[0], "end": result.baseline_window[1]}
            if result.baseline_window
            else None
        ),
        "events": {
            "n_matched": result.n_matched,
            "n_ok": rd.n,
            "n_pending": result.n_pending,
            "n_missing": result.n_missing,
            "first_date": result.first_event_date,
            "last_date": result.last_event_date,
            "sample": result.events_sample,
        },
        "stats": rd.to_dict(),
        "verdict": verdict,
        "verdict_single": rd.verdict,
        "verdict_label": _VERDICT_CN.get(verdict, verdict),
        "bh": bh,
        "horizons": [h.to_dict() for h in result.horizons],
        "conditions": {
            "source_db": result.conditions.get("source_db"),
            "source_max_trade_date": result.conditions.get("source_max_trade_date"),
            "label_version": result.conditions.get("label_version"),
            "labels_computed_at": result.conditions.get("labels_computed_at"),
            "outcomes_computed_at": result.conditions.get("outcomes_computed_at"),
            "outcomes_horizons": result.conditions.get("outcomes_horizons"),
            "rule_ref": rule.ref,
            "n": rd.n,
            "min_n": rule.min_n,
            "data_gap_days": result.conditions.get("data_gap_days", []),
            "data_gap_count": result.conditions.get("data_gap_count", 0),
            "calendar": result.conditions.get("calendar"),
            "source_row_counts": result.conditions.get("source_row_counts"),
            "environment": dict(environment),
        },
        "appendix": appendix or {},
        "sql": result.sql,
    }
    return receipt


def render_receipt_markdown(receipt: dict[str, Any]) -> str:
    r = receipt["rule"]
    s = receipt["stats"]
    ev = receipt["events"]
    cond = receipt["conditions"]
    env = cond.get("environment", {})
    lines: list[str] = []
    lines.append(f"# {r['ref']} · {receipt['verdict_label']}（{receipt['verdict']}）")
    lines.append("")
    lines.append(f"> {r.get('title') or ''}")
    lines.append(">")
    lines.append(
        f"> 窗口 {receipt['window']['start']} → {receipt['window']['end']}；"
        f"{receipt['multiple_testing_note']}；生成于 {receipt['generated_at']}。"
    )
    if receipt["test_mode"] == "scan" and receipt.get("verdict_single") != receipt["verdict"]:
        lines.append(f"> 单次检验结论为 `{receipt['verdict_single']}`，经 BH 校正降级为 `{receipt['verdict']}`。")
    lines.append("")
    lines.append("## 读数")
    lines.append("")
    lines.append("| 项 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| N（已到期事件） | {s['n']}（匹配 {ev['n_matched']}，pending {ev['n_pending']}，missing {ev['n_missing']}） |")
    lines.append(f"| 命中 k / 命中率 p | {s['k']} / {_pct(s['p'])} |")
    bw = receipt.get("baseline_window") or {}
    lines.append(
        f"| 同期基准率 p0 | {_pct(s['p0'])}（{s['baseline_k']}/{s['baseline_n']}，"
        f"{bw.get('start', '—')} → {bw.get('end', '—')}） |"
    )
    lines.append(f"| 提升 lift | {_pct(s['lift'])} |")
    lines.append(f"| Wilson 95% | [{_pct(s['wilson_lo'])}, {_pct(s['wilson_hi'])}] |")
    fh, sh = s["first_half"], s["second_half"]
    lines.append(f"| 前半段 / 后半段 | {_pct(fh['p'])}（{fh['k']}/{fh['n']}） / {_pct(sh['p'])}（{sh['k']}/{sh['n']}） |")
    lines.append(f"| 双侧 p 值（H0: p = p0） | {_num(s['p_value'], 4)} |")
    lines.append(f"| min_n | {s['min_n']} |")
    lines.append(f"| **结论** | **{receipt['verdict_label']}** `{receipt['verdict']}` |")
    if receipt.get("bh"):
        bh = receipt["bh"]
        lines.append(
            f"| BH 校正 | adjusted p {_num(bh.get('adjusted_p'), 4)}，"
            f"{'拒绝 H0' if bh.get('rejected') else '未拒绝 H0'}（q={bh.get('q')}，同族 {len(bh.get('family', []))} 条） |"
        )
    for note in s.get("notes", []):
        lines.append(f"| 备注 | {note} |")
    lines.append("")
    lines.append("## 多窗口（仅已到期事件）")
    lines.append("")
    lines.append("| 窗口 | n | 胜率 | 均值收益% | 均值最高收益% | 均值峰值天数 | 均值峰后回撤% |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for h in receipt["horizons"]:
        lines.append(
            f"| T+{h['horizon']} | {h['n']} | {_pct(h['win_rate'])} | {_num(h['mean_fwd_return'])} | "
            f"{_num(h['mean_max_return'])} | {_num(h['mean_days_to_peak'], 1)} | {_num(h['mean_drawdown_after_peak'])} |"
        )
    lines.append("")
    lines.append("## 规则")
    lines.append("")
    lines.append("```json")
    lines.append(
        json.dumps(
            {k: r[k] for k in ("scope", "condition", "outcome", "baseline", "min_n")},
            ensure_ascii=False,
            indent=2,
        )
    )
    lines.append("```")
    lines.append("")
    lines.append("## 成立条件")
    lines.append("")
    lines.append(f"- 源库：`{cond.get('source_db')}` max(trade_date) = **{cond.get('source_max_trade_date')}**")
    lines.append(f"- label_version：`{cond.get('label_version')}`；labels 构建 {cond.get('labels_computed_at')}，outcomes 构建 {cond.get('outcomes_computed_at')}")
    lines.append(f"- 规则：`{cond.get('rule_ref')}`" + (f"（sha256 `{r.get('sha256')}`）" if r.get("sha256") else ""))
    lines.append(f"- N = {cond.get('n')}，min_n = {cond.get('min_n')}")
    gaps = cond.get("data_gap_days") or []
    lines.append(
        f"- data_gap 日数 = {cond.get('data_gap_count', 0)}"
        + (f"：{', '.join(gaps)}" if gaps else "（本窗口无全零日）")
    )
    cal = cond.get("calendar") or {}
    lines.append(f"- 日历：{cal.get('start')} → {cal.get('end')}，{cal.get('days')} 个交易日")
    lines.append(
        f"- 树 `{env.get('tree')}` 分支 `{env.get('branch')}` revision `{env.get('revision')}`"
        + ("（工作区有未提交代码改动）" if env.get("dirty") else "（代码路径干净）")
    )
    lines.append(f"- 解释器 `{env.get('interpreter')}` python {env.get('python_version')} duckdb {env.get('duckdb_version')}")
    if ev.get("sample"):
        lines.append("")
        lines.append(f"## 事件样例（前 {len(ev['sample'])} 条，共 {ev['n_ok']} 条已到期）")
        lines.append("")
        lines.append("| 实体 | 日期 | 命中 | 指标 |")
        lines.append("|---|---|---|---:|")
        metric_key = receipt["rule"]["outcome"]["success"]["metric"]
        for e in ev["sample"]:
            lines.append(f"| {e['entity_id']} | {e['trade_date']} | {'✓' if e['success'] else '✗'} | {_num(e.get(metric_key))} |")
    appendix = receipt.get("appendix") or {}
    if appendix:
        lines.append("")
        lines.append("## 附录")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(appendix, ensure_ascii=False, indent=2))
        lines.append("```")
    lines.append("")
    return "\n".join(lines)


def receipt_dir(root: str | Path, rule_ref: str) -> Path:
    return Path(root).expanduser() / rule_ref


def write_receipt(root: str | Path, receipt: dict[str, Any], *, date_str: str) -> tuple[Path, Path]:
    """写 ``<root>/<rule_id>@v<version>/<date>.json`` 与同名 md。同日重跑覆盖。"""
    folder = receipt_dir(root, receipt["rule"]["ref"])
    folder.mkdir(parents=True, exist_ok=True)
    json_path = folder / f"{date_str}.json"
    md_path = folder / f"{date_str}.md"
    json_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_receipt_markdown(receipt), encoding="utf-8")
    return json_path, md_path


# --------------------------------------------------------------------------- #
# scan 汇总
# --------------------------------------------------------------------------- #
def build_scan_summary(
    scan: ScanResult,
    *,
    receipt_paths: list[str | None],
    environment: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    rows = []
    for i, res in enumerate(scan.results):
        rd = res.readout
        rows.append(
            {
                "rule_ref": res.rule.ref,
                "title": res.rule.title,
                "n": rd.n,
                "k": rd.k,
                "p": rd.p,
                "p0": rd.p0,
                "lift": rd.lift,
                "wilson_lo": rd.lo,
                "wilson_hi": rd.hi,
                "p_value": scan.p_values[i],
                "adjusted_p": scan.adjusted_p[i],
                "bh_rejected": scan.rejected[i],
                "verdict_single": rd.verdict,
                "verdict_bh": scan.verdicts_bh[i],
                "exploratory": True,
                "receipt": receipt_paths[i],
            }
        )
    first = scan.results[0].conditions if scan.results else {}
    return {
        "schema_version": SCAN_SCHEMA,
        "generated_at": _now_iso(now),
        "q": scan.q,
        "family_size": len(rows),
        "rules": rows,
        "conditions": {
            "source_max_trade_date": first.get("source_max_trade_date"),
            "label_version": first.get("label_version"),
            "data_gap_days": first.get("data_gap_days", []),
            "environment": dict(environment),
        },
    }


def render_scan_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# 规则扫描 · {summary['family_size']} 条 · BH q={summary['q']} · exploratory",
        "",
        f"> 生成于 {summary['generated_at']}；源库 max(trade_date) {summary['conditions'].get('source_max_trade_date')}；"
        f"label_version `{summary['conditions'].get('label_version')}`。"
        " 一次跑多条规则总会有一条在 95% 下「显著」，所以这里的支持 / 证伪都过了 BH 校正才算。",
        "",
        "| 规则 | N | p | p0 | lift | Wilson 95% | p 值 | BH adj p | 单次 | BH 后 |",
        "|---|---:|---:|---:|---:|---|---:|---:|---|---|",
    ]
    for row in summary["rules"]:
        lines.append(
            f"| `{row['rule_ref']}` | {row['n']} | {_pct(row['p'])} | {_pct(row['p0'])} | {_pct(row['lift'])} | "
            f"[{_pct(row['wilson_lo'])}, {_pct(row['wilson_hi'])}] | {_num(row['p_value'], 4)} | "
            f"{_num(row['adjusted_p'], 4)} | {row['verdict_single']} | **{row['verdict_bh']}** |"
        )
    lines.append("")
    return "\n".join(lines)


def write_scan_summary(root: str | Path, summary: dict[str, Any], *, date_str: str) -> tuple[Path, Path]:
    folder = Path(root).expanduser() / "scan"
    folder.mkdir(parents=True, exist_ok=True)
    json_path = folder / f"{date_str}.json"
    md_path = folder / f"{date_str}.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_scan_markdown(summary), encoding="utf-8")
    return json_path, md_path
