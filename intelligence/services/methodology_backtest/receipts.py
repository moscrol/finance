"""收据：一次回测的读数 + 它成立的条件，JSON 为真本源，md 是渲染物。

落点 ``methodology/receipts/<rule_id>@v<version>/<date>.json``（gitignore，可重建），台账地图有登记。
成立条件块照 ``scripts/check_test_receipt.py`` 的思路：源库 ``max(trade_date)``、``label_version``、
``rule_id@version``、N、data_gap 日数、树 / 解释器 / revision / dirty——下一个读者比对条件即可
决定采信还是重跑，不用重跑一遍来验证。

证伪库（设计稿 §6 BP v0.4 产品约束第二条）：结论为 ``refuted`` 的收据另落一条精简条目到
``methodology/refuted/<rule_id>@v<version>/<date>.json``（**进 git**——证伪是资产不是副产物，收据目录
是本机可重建物，条目要跨机器、跨旁路库重建留下来），字段含 rule_id / rule_version / sharing / owner /
N / p / p0 / ci / 按大盘阶段拆分 / refuted_at / 收据路径。``report --refuted`` 按大盘阶段汇总它。
scan 模式以 BH 校正后的结论为准：单次 refuted、BH 降级的不落库。

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
REFUTED_SCHEMA = "methodology-backtest-refuted/v0"
REFUTED_VERDICT = "refuted"
# 预声明的检验角色（工单 #42 / 补强 spec OPT-04）。跑之前就说清这份收据是发现、验证还是 Holdout；
# 没声明的收据是探索或历史观察，lifecycle 不拿它当晋升证据（证伪不需要声明，refuted 照旧生效）。
DECLARED_STAGES: tuple[str, ...] = ("discovery", "validation", "holdout")

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
    declared_stage: str | None = None,
) -> dict[str, Any]:
    if test_mode not in ("single", "scan"):
        raise ValueError(f"test_mode 必须是 single / scan，得到 {test_mode!r}")
    if declared_stage is not None and declared_stage not in DECLARED_STAGES:
        raise ValueError(f"declared_stage 必须是 {'/'.join(DECLARED_STAGES)} 或 None，得到 {declared_stage!r}")
    rule = result.rule
    rd = result.readout
    verdict = (bh or {}).get("verdict_bh", rd.verdict) if test_mode == "scan" else rd.verdict
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "generated_at": _now_iso(now),
        "test_mode": test_mode,
        "exploratory": test_mode == "scan",
        "declared_stage": declared_stage,
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
            "sharing": rule.sharing,
            "owner": rule.owner,
            "source_perspective": rule.raw.get("source_perspective"),
            "notes": rule.raw.get("notes"),
            "provenance": rule.raw.get("provenance"),
        },
        # 顶层再放一份：渲染层合规硬门按顶层字段判「缺任一即不渲染」，不用钻进 rule 块
        "sharing": rule.sharing,
        "owner": rule.owner,
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
        "baseline_kind": rule.baseline_kind,
        "baseline_alt": result.baseline_alt.to_dict() if result.baseline_alt else None,
        # 第三列对照：按事件阶段分布加权的阶段基准率；同 baseline_alt 一样只对照、不定结论
        "baseline_stage_matched": result.baseline_stage_matched.to_dict() if result.baseline_stage_matched else None,
        "verdict": verdict,
        "verdict_single": rd.verdict,
        "verdict_label": _VERDICT_CN.get(verdict, verdict),
        "bh": bh,
        "horizons": [h.to_dict() for h in result.horizons],
        "by_market_stage": [b.to_dict() for b in result.stage_breakdown],
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
    lines.append(
        f"> 归属 `{receipt.get('sharing')}` / owner `{receipt.get('owner')}`"
        + (f"，来源 {r['source_perspective']}" if r.get("source_perspective") else "")
        + "。"
    )
    if receipt["test_mode"] == "scan" and receipt.get("verdict_single") != receipt["verdict"]:
        lines.append(f"> 单次检验结论为 `{receipt['verdict_single']}`，经 BH 校正降级为 `{receipt['verdict']}`。")
    stage = receipt.get("declared_stage")
    lines.append(
        f"> 声明阶段 `{stage}`：计入该规则本轮次的晋升证据。"
        if stage
        else "> 未声明阶段：探索 / 历史观察，不作晋升证据（要计入请 `run --stage discovery|validation|holdout`）。"
    )
    lines.append("")
    lines.append("## 读数")
    lines.append("")
    lines.append("| 项 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| N（已到期事件） | {s['n']}（匹配 {ev['n_matched']}，pending {ev['n_pending']}，missing {ev['n_missing']}） |")
    lines.append(f"| 命中 k / 命中率 p | {s['k']} / {_pct(s['p'])} |")
    bw = receipt.get("baseline_window") or {}
    lines.append(
        f"| 同期基准率 p0（`{receipt.get('baseline_kind', 'same_universe_all_days')}`） | {_pct(s['p0'])}（{s['baseline_k']}/{s['baseline_n']}，"
        f"{bw.get('start', '—')} → {bw.get('end', '—')}） |"
    )
    lines.append(f"| 提升 lift | {_pct(s['lift'])} |")
    alt = receipt.get("baseline_alt")
    if alt:
        lines.append(
            f"| 对照基准率（`{alt['kind']}`） | {_pct(alt['p0'])}（{alt['k']}/{alt['n']}），lift {_pct(alt['lift'])}，"
            f"若以此定结论 → `{alt['verdict_if_used']}` |"
        )
    sm = receipt.get("baseline_stage_matched")
    if sm:
        lines.append(
            f"| 对照基准率（`{sm['kind']}`，按事件阶段分布加权） | {_pct(sm['p0'])}，lift {_pct(sm['lift'])}，"
            f"若以此定结论 → `{sm['verdict_if_used']}` |"
        )
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
    stages = receipt.get("by_market_stage") or []
    if stages:
        lines.append("")
        lines.append(
            "## 按大盘阶段拆分（事件日当日 `market_stage`；p0 为该阶段自己的基准率，"
            f"阶段级结论在规则内按 BH 校正，n < min_n={s['min_n']} 记 insufficient_n）"
        )
        lines.append("")
        lines.append("| 大盘阶段 | n | k | p | p0（阶段） | lift | Wilson 95% | adj p | 结论 |")
        lines.append("|---|---:|---:|---:|---:|---:|---|---:|---|")
        for b in stages:
            lines.append(
                f"| {b['stage']} | {b['n']} | {b['k']} | {_pct(b.get('p'))} | {_pct(b.get('p0'))} | {_pct(b.get('lift'))} | "
                f"[{_pct(b.get('wilson_lo'))}, {_pct(b.get('wilson_hi'))}] | {_num(b.get('adjusted_p'), 4)} | "
                f"`{b.get('verdict', '—')}` |"
            )
    lines.append("")
    lines.append("## 规则")
    lines.append("")
    lines.append("```json")
    lines.append(
        json.dumps(
            {k: r[k] for k in ("scope", "condition", "outcome", "baseline", "min_n", "sharing", "owner")},
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


def latest_receipt(root: str | Path, rule_id: str) -> dict[str, Any] | None:
    """某条规则（任意版本）最近一次收据；没有则 None。

    「最近」按收据自述的 ``generated_at`` 取，跨版本比较——规则升到 v2 但还没跑过，
    P1 统计门看的仍是 v1 那份读数，并在 ``rule.ref`` 里说明是哪个版本。返回值多带 ``_path``。
    """
    base = Path(root).expanduser()
    if not base.is_dir():
        return None
    best: dict[str, Any] | None = None
    best_key: tuple[str, str] | None = None
    for folder in sorted(base.glob(f"{rule_id}@v*")):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(doc, dict) or doc.get("schema_version") != RECEIPT_SCHEMA:
                continue
            if str(doc.get("rule", {}).get("rule_id")) != rule_id:
                continue
            key = (str(doc.get("generated_at") or ""), str(path))
            if best_key is None or key > best_key:
                best_key = key
                best = dict(doc, _path=str(path))
    return best


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
# 证伪库
# --------------------------------------------------------------------------- #
def build_refuted_entry(receipt: dict[str, Any], *, receipt_path: str | None) -> dict[str, Any]:
    """从一张 ``refuted`` 收据抽精简条目。结论不是 refuted 抛 ValueError——证伪库只收证伪。"""
    if receipt.get("verdict") != REFUTED_VERDICT:
        raise ValueError(f"证伪库只收 verdict=refuted 的收据，得到 {receipt.get('verdict')!r}")
    r = receipt["rule"]
    s = receipt["stats"]
    cond = receipt.get("conditions", {})
    return {
        "schema_version": REFUTED_SCHEMA,
        "rule_id": r["rule_id"],
        "rule_version": r["version"],
        "rule_ref": r["ref"],
        "title": r.get("title"),
        "sharing": receipt.get("sharing"),
        "owner": receipt.get("owner"),
        "entity_type": (r.get("scope") or {}).get("entity_type"),
        "universe": (r.get("scope") or {}).get("universe"),
        "success": (r.get("outcome") or {}).get("success"),
        "n": s["n"],
        "k": s["k"],
        "p": s["p"],
        "p0": s["p0"],
        "baseline_kind": receipt.get("baseline_kind"),
        "lift": s["lift"],
        "ci": {"lo": s["wilson_lo"], "hi": s["wilson_hi"], "level": 0.95, "method": "wilson"},
        "first_half": s.get("first_half"),
        "second_half": s.get("second_half"),
        "by_market_stage": receipt.get("by_market_stage") or [],
        "baseline_stage_matched": receipt.get("baseline_stage_matched"),
        "test_mode": receipt.get("test_mode"),
        "exploratory": receipt.get("exploratory"),
        "bh": receipt.get("bh"),
        "refuted_at": receipt.get("generated_at"),
        "window": receipt.get("window"),
        "baseline_window": receipt.get("baseline_window"),
        "source_max_trade_date": cond.get("source_max_trade_date"),
        "label_version": cond.get("label_version"),
        "revision": (cond.get("environment") or {}).get("revision"),
        "receipt_path": receipt_path,
    }


def write_refuted(root: str | Path, receipt: dict[str, Any], *, date_str: str, receipt_path: str | None) -> Path:
    """落 ``<root>/<rule_id>@v<version>/<date>.json``。同日重跑覆盖（与收据同规矩）。"""
    entry = build_refuted_entry(receipt, receipt_path=receipt_path)
    folder = Path(root).expanduser() / receipt["rule"]["ref"]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{date_str}.json"
    path.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_refuted(root: str | Path) -> list[dict[str, Any]]:
    """读整个证伪库（schema 不对或坏文件跳过），按 refuted_at 倒序。"""
    base = Path(root).expanduser()
    if not base.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(base.glob("*@v*/*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or doc.get("schema_version") != REFUTED_SCHEMA:
            continue
        out.append(dict(doc, _path=str(path)))
    out.sort(key=lambda d: (str(d.get("refuted_at") or ""), d["_path"]), reverse=True)
    return out


def summarize_refuted_by_stage(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """「这个阶段这招不灵」：每条证伪规则的事件按大盘阶段展开成行，同一规则多张条目只取最近一张。

    ``p0_stage`` / ``verdict_stage`` 来自阶段自己的基准率（第五刀起才有；老条目没有这两个键，显示为空）。
    """
    latest: dict[str, dict[str, Any]] = {}
    for e in entries:  # entries 已按 refuted_at 倒序
        latest.setdefault(e["rule_ref"], e)
    rows: list[dict[str, Any]] = []
    for e in latest.values():
        for b in e.get("by_market_stage") or []:
            rows.append(
                {
                    "stage": b["stage"],
                    "rule_ref": e["rule_ref"],
                    "title": e.get("title"),
                    "n": b["n"],
                    "k": b["k"],
                    "p": b.get("p"),
                    "p0": e.get("p0"),
                    "p0_stage": b.get("p0"),
                    "lift_stage": b.get("lift"),
                    "verdict_stage": b.get("verdict"),
                    "ci": e.get("ci"),
                    "refuted_at": e.get("refuted_at"),
                }
            )
    rows.sort(key=lambda r: (r["stage"], -r["n"], r["rule_ref"]))
    return rows


def render_refuted_markdown(entries: list[dict[str, Any]]) -> str:
    rows = summarize_refuted_by_stage(entries)
    lines = [f"# 证伪库 · {len({e['rule_ref'] for e in entries})} 条规则 / {len(entries)} 张条目"]
    lines.append("")
    if not entries:
        lines.append("证伪库为空：目前没有任何规则在统计门下被证伪（不可区分 ≠ 证伪）。")
        return "\n".join(lines) + "\n"
    lines.append(
        "> 每条证伪规则按事件日当日大盘阶段展开；p0 是该规则整体 universe 的基准率，p0（阶段）是该阶段自己的基准率，"
        "阶段级结论已在规则内按 BH 校正（老条目无此两列）。"
    )
    lines.append("")
    lines.append("| 大盘阶段 | 规则 | n | k | p | p0 | p0（阶段） | 阶段结论 | Wilson 95%（整体） | 证伪于 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|---|---|")
    for r in rows:
        ci = r.get("ci") or {}
        vs = r.get("verdict_stage")
        lines.append(
            f"| {r['stage']} | `{r['rule_ref']}` | {r['n']} | {r['k']} | {_pct(r.get('p'))} | {_pct(r.get('p0'))} | "
            f"{_pct(r.get('p0_stage'))} | {f'`{vs}`' if vs else '—'} | "
            f"[{_pct(ci.get('lo'))}, {_pct(ci.get('hi'))}] | {r.get('refuted_at')} |"
        )
    return "\n".join(lines) + "\n"


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
