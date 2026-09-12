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

import hashlib
import json
import sys
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
# 文件名里摘要取多少位。128 bit：即便每天写一万份、连写一万年也撞不上一次，而全长 64 位
# 会让文件名到 77 字符。**唯一性不靠它兜底**——写入前还有一道内容比对闸（同名必比内容，
# 不同即抛 ``ReceiptCollision``），所以这里是「够长到不用担心」而不是「赌它不撞」。
# 4 位那版就是赌输的：实测两份结论相反的收据拿到同一个后缀，refuted 被静默抹掉。
STEM_DIGEST_CHARS = 32

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


def _parse_ts(raw: Any) -> datetime:
    """ISO 时间戳 → 带时区的 datetime；解析不了按最早处理（不让它冒充最新）。"""
    try:
        ts = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)
    return (ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _now_iso(now: datetime | None) -> str:
    """收据的 ``generated_at``，**微秒精度**。

    原来截到秒：同一秒内跑完两次检验（合成库上很常见）两份收据时间戳逐字相同，
    读取端 ``load_steps`` 的排序键退化到文件名，而文件名后缀是内容 hash——于是
    「哪次更晚」由 hash 随机决定。实测：先 supported、同秒稍后 not_distinguishable，
    读取端选回 supported，生命周期停在 personal_method（09-12 复核）。
    顺序是这条链的判据之一，不能丢精度、更不能让 hash 替它排序。
    """
    ts = now or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat(timespec="microseconds")


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
            # OPT-05 purge：outcome 跨出窗末的事件不计入统计（跨窗标签泄漏），如实报数
            "n_purged_cross_window": result.n_purged,
            "purge_cut_date": result.purge_cut_date,
            "first_date": result.first_event_date,
            "last_date": result.last_event_date,
            "sample": result.events_sample,
        },
        "stats": rd.to_dict(),
        # OPT-05 依赖感知读数：方法 / 块长 / 种子 / CI 全入账；顶层 verdict 已是
        # 「独立假设 × 依赖感知」的保守合成，stats 里的 Wilson 读数降为描述性。
        "dependence": result.dependence.to_dict() if result.dependence else None,
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
    if result.discovery is not None:
        # 双窗（设计稿 §10.2 第二条）：顶层 verdict 已是 validation 窗的；这里把两窗读数并排放出来。
        # 没声明 windows 的规则不进这个分支——收据键集与之前逐键一致。
        disc = result.discovery
        receipt["rule"]["windows"] = rule.raw.get("windows")
        receipt["windows"] = {
            "discovery": _window_block(disc),
            "validation": _window_block(result),
        }
        receipt["verdict_discovery"] = disc.readout.verdict
        receipt["verdict_validation"] = rd.verdict
        receipt["windows_note"] = "结论只认 validation 窗（verdict == verdict_validation）；discovery 窗只作对照，supported 不能从它来"
    return receipt


def _window_block(result: RunResult) -> dict[str, Any]:
    rd = result.readout
    return {
        "window": {"start": result.window[0], "end": result.window[1]},
        "baseline_window": (
            {"start": result.baseline_window[0], "end": result.baseline_window[1]} if result.baseline_window else None
        ),
        "events": {
            "n_matched": result.n_matched,
            "n_ok": rd.n,
            "n_pending": result.n_pending,
            "n_missing": result.n_missing,
            "first_date": result.first_event_date,
            "last_date": result.last_event_date,
        },
        "stats": rd.to_dict(),
        "verdict": rd.verdict,
        "verdict_label": _VERDICT_CN.get(rd.verdict, rd.verdict),
    }


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
    windows = receipt.get("windows")
    if windows:
        lines.append("")
        lines.append("## 发现窗 / 验证窗（结论只认验证窗；发现窗只作对照）")
        lines.append("")
        lines.append("| 窗 | 起止 | N | k | p | p0 | Wilson 95% | 结论 |")
        lines.append("|---|---|---:|---:|---:|---:|---|---|")
        for name in ("discovery", "validation"):
            w = windows[name]
            ws = w["stats"]
            lines.append(
                f"| {name} | {w['window']['start']} → {w['window']['end']} | {ws['n']} | {ws['k']} | {_pct(ws['p'])} | "
                f"{_pct(ws['p0'])} | [{_pct(ws['wilson_lo'])}, {_pct(ws['wilson_hi'])}] | `{w['verdict']}` |"
            )
        lines.append("")
        lines.append(f"> {receipt.get('windows_note', '')}")
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
    best_key: tuple[datetime, str] | None = None
    for folder in sorted(base.glob(f"{rule_id}@v*")):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                _warn_corrupt(path, exc)
                continue
            if not isinstance(doc, dict) or doc.get("schema_version") != RECEIPT_SCHEMA:
                continue
            if str(doc.get("rule", {}).get("rule_id")) != rule_id:
                continue
            # 与 lifecycle 同一口径：按**解析后的时刻**比，不用裸字符串（精度不同的
            # 时间戳字典序不可靠），文件名只作同刻 tiebreak。
            key = (_parse_ts(doc.get("generated_at")), str(path))
            if best_key is None or key > best_key:
                best_key = key
                best = dict(doc, _path=str(path))
    return best


def _content_digest(payload: dict[str, Any]) -> str:
    """内容的完整 sha256。**不截短**：4 位 = 16 bit，几百份就撞得上——实测两份结论相反的
    收据拿到同一个 `120000-c62b`，后写的把 refuted 抹掉，状态从 contradicted 变回
    personal_method（09-12 复核）。截短的 hash 不构成「内容不同必不同名」。"""
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _run_suffix(receipt: dict[str, Any]) -> str:
    """``<HHMMSSffffff>-<完整 sha256>``：时刻定**先后**，摘要定**身份**。

    两件事分开：微秒时刻让「哪次更晚」可比（读取端不必靠文件名排序）；完整摘要让
    「是不是同一份」可判（同一份原样重写落同名 → 幂等；内容不同必不同名 → 都留档）。
    ``generated_at`` 解析不了时只用摘要。
    """
    digest = _content_digest(receipt)[:STEM_DIGEST_CHARS]
    raw = str(receipt.get("generated_at") or "")
    try:
        stamp = datetime.fromisoformat(raw).astimezone(timezone.utc).strftime("%H%M%S%f")
    except ValueError:
        return digest
    return f"{stamp}-{digest}"


def receipt_stem(receipt: dict[str, Any], date_str: str) -> str:
    """收据文件名主干 ``<date>[-<stage>]-<HHMMSS>``：**每次运行一份，永不互相覆盖**。

    两个缺口一起堵（09-12 走三段闭环时暴露）：

    1. ``declared_stage`` 让「同一天跑 discovery / validation / holdout 三段」成为合法且
       常见的场景（历史回填时三段窗口都在过去），但原来文件名只有日期粒度，三段互相
       覆盖只剩最后一份，``lifecycle._stage_ladder`` 永远凑不齐三级。
    2. 更要命的是**同段重跑会物理删掉上一次的结果**。「取最新那次」是**读取层**的事
       （``_stage_ladder`` 已经按 ``generated_at`` 取同窗最新一份），写入层照做就变成了
       「删除失败记录」：留出窗判 refuted 之后当天换个窗口重跑判 supported，失败那份
       被覆盖，``_stage_ladder`` 的「同阶段两个不同窗口 = 事后挑窗」检测**没有证据可查**，
       于是直接晋升 personal_method。采用最新 ≠ 删除旧的。

    所以文件名带上运行时刻：每次运行各留一份，由 ``load_steps`` + ``derive_state`` 决定
    采用哪次、以及这些运行合起来说明了什么。``date_str`` 仍是落盘日期（目录内可排序）。
    """
    stage = receipt.get("declared_stage")
    head = f"{date_str}-{stage}" if stage in DECLARED_STAGES else date_str
    return f"{head}-{_run_suffix(receipt)}"


def _warn_corrupt(path: Path, exc: BaseException) -> None:
    """读到坏收据要**出声**。

    静默 `continue` 的后果在 09-12 质检里现形过：正式目录留下 0 字节 JSON，读取端
    跳过它、派生状态若无其事地停在旧值，没有任何人知道有一份证据读不出来。
    这里不修不删（可能是真证据），只保证它不会无声无息。
    """
    print(f"[receipts] 跳过读不出的收据 {path}: {type(exc).__name__}: {exc}",
          file=sys.stderr, flush=True)


def _fsync_dir(directory: Path) -> None:
    """把目录项刷到存储。发布正式名之后、以及任何「已存在即成功」的分支都要做——
    否则上一次在 `link` 与 `fsync` 之间中断的发布，重试时会被「文件已存在」短路掉，
    目录同步永远补不上。"""
    import os

    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class ReceiptCollision(RuntimeError):
    """目标文件已存在且内容不同。**绝不静默覆盖**——覆盖会抹掉一次真实运行的证据。"""


def _compare_existing(path: Path, text: str, payload: dict[str, Any]) -> bool:
    """目标已存在时比内容：相同 → 幂等（False），不同/读不出 → 抛 `ReceiptCollision`。"""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError 不是 OSError 的子类：只捕 OSError 会让它裸奔出去，
        # 调用方拿到一个不带文件路径的 UnicodeDecodeError，不知道是哪份收据坏了。
        raise ReceiptCollision(f"{path} 已存在且读不出来，拒绝覆盖：{type(exc).__name__}: {exc}") from exc
    if path.suffix == ".json":
        try:
            existing = json.loads(raw)
        except ValueError as exc:
            # 旧版本留下的损坏对象（如中断造成的 0 字节）：**不自动覆盖、不自动删除**。
            # 它可能是真证据也可能是残留，分不清就不能替人处置；报清楚让人来定。
            hint = "（0 字节，疑为旧版写入中断残留）" if not raw.strip() else ""
            raise ReceiptCollision(
                f"{path} 已存在但不是可读 JSON{hint}，拒绝覆盖：{exc}。"
                f"请人工确认后移走或归档该文件，不要凭文件名推断其结论"
            ) from exc
        if _content_digest(existing) == _content_digest(payload):
            return False
        raise ReceiptCollision(
            f"{path} 已存在且内容不同，拒绝静默覆盖："
            f"既有摘要 {_content_digest(existing)[:12]}…，本次 {_content_digest(payload)[:12]}…"
        )
    if raw == text:
        return False
    raise ReceiptCollision(
        f"{path} 已存在且内容不同，拒绝静默覆盖（非 JSON 产物，按字节比对不同）"
    )


def _write_exclusive(path: Path, text: str, payload: dict[str, Any]) -> bool:
    """**先写满再发布**；目标已存在则比内容——相同 → 幂等（False），不同 → 抛错。

    **原子占名 ≠ 完整发布**。旧实现用 ``O_CREAT | O_EXCL`` 直接开正式文件，名字立即
    可见、内容随后才写：进程在这个窗口被杀（``os._exit`` 这类真实终止，不是可捕获异常，
    ``except BaseException`` 的清理根本不会执行），正式目录就留下 0 字节 JSON——读取端
    静默跳过它、派生状态停在旧值，而**原内容重试反而被当成撞名拒绝**，人工不介入就
    恢复不了（09-12 质检实测）。

    改成：同目录临时文件写满 → ``flush`` + ``fsync`` → ``os.link`` 无覆盖地发布正式名
    → fsync 目录。正式名只在内容已落盘后才出现，中断最多留下一个 ``.pending-*``
    临时文件（不带 ``.json`` 后缀，任何 ``glob("*.json")`` 都读不到它）。

    不用 ``os.replace``：它会覆盖已有目标，恰好破掉「失败证据不可覆盖」这条合同——
    被覆盖的可能正是一次失败记录，而「事后挑窗 / 改判痕迹」检测都靠它在场。
    """
    import os
    import tempfile

    data = text.encode("utf-8")
    if path.exists():                      # 已发布则直接比内容，不白写临时文件
        idempotent = _compare_existing(path, text, payload)
        # 幂等分支也要补目录同步：上一次发布可能在 link 成功、fsync 目录失败时中断，
        # 那时目录项还没落盘，重试却因为「文件已存在」直接判成功，同步就永远补不上了
        # （09-12 第五轮质检实测；仓内 `_publish` 在同一探针下会补做）。
        _fsync_dir(path.parent)
        return idempotent
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".pending-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        try:
            os.link(temporary, path)       # 目标存在即失败，永不覆盖
        except FileExistsError:
            idempotent = _compare_existing(path, text, payload)
            _fsync_dir(path.parent)        # 同上：竞态输家也要保证目录项已落盘
            return idempotent
        _fsync_dir(path.parent)            # 目录项落盘，崩溃后正式名不会丢
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def _guard_no_silent_overwrite(path: Path, payload: dict[str, Any]) -> bool:
    """保留给调用方做「同名是否冲突」的只读判定；真正的写入走 ``_write_exclusive``。"""
    if not path.exists():
        return True
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReceiptCollision(f"{path} 已存在且读不出来，拒绝覆盖：{exc}") from exc
    if _content_digest(existing) == _content_digest(payload):
        return False
    raise ReceiptCollision(
        f"{path} 已存在且内容不同，拒绝静默覆盖："
        f"既有摘要 {_content_digest(existing)[:12]}…，本次 {_content_digest(payload)[:12]}…"
    )


def write_receipt(root: str | Path, receipt: dict[str, Any], *, date_str: str) -> tuple[Path, Path]:
    """写 ``<root>/<rule_id>@v<version>/<date>[-<stage>]-<HHMMSSffffff>-<sha256>.json`` 与同名 md。

    **不覆盖任何既有运行记录**：同一份收据原样重写落同名且内容相同（幂等）；内容不同却
    撞名 → 抛 ``ReceiptCollision``。两个文件**各自**判幂等——只有 json 落盘、md 写失败时，
    原样重试必须把 md 补上，不能因为 json 在就整体当成功返回（09-12 复核故障注入实测）。
    """
    folder = receipt_dir(root, receipt["rule"]["ref"])
    folder.mkdir(parents=True, exist_ok=True)
    stem = receipt_stem(receipt, date_str)
    json_path = folder / f"{stem}.json"
    md_path = folder / f"{stem}.md"
    json_text = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    md_text = render_receipt_markdown(receipt)
    _write_exclusive(json_path, json_text, receipt)
    _write_exclusive(md_path, md_text, receipt)
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
    """落 ``<root>/<rule_id>@v<version>/<date>-<HHMMSS>.json``。**每次证伪各留一条**。

    与收据同规矩：证伪是资产，同日再跑一次不该把上一条证伪从库里抹掉。
    """
    entry = build_refuted_entry(receipt, receipt_path=receipt_path)
    folder = Path(root).expanduser() / receipt["rule"]["ref"]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{date_str}-{_run_suffix(receipt)}.json"
    _write_exclusive(path, json.dumps(entry, ensure_ascii=False, indent=2) + "\n", entry)
    return path


def load_refuted(root: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    """读整个证伪库，按 refuted_at 倒序。返回 ``(条目, 读不出的文件路径)``。

    坏文件**不能只是跳过**：证伪库里一份 0 字节的反证被静默略过，`report --refuted`
    就会照常打印「目前没有任何规则被证伪」——「证据损坏」伪装成「证据不存在」，
    恰好是证伪库最不能出的错（09-12 第五轮质检实测）。`load_steps` 那侧已经这样修过，
    这个入口当时漏了；两处现在都走 `_warn_corrupt` 并把坏文件名交回给调用方渲染。
    """
    base = Path(root).expanduser()
    if not base.is_dir():
        return [], []
    out: list[dict[str, Any]] = []
    unreadable: list[str] = []
    for path in sorted(base.glob("*@v*/*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            _warn_corrupt(path, exc)
            unreadable.append(str(path))
            continue
        if not isinstance(doc, dict) or doc.get("schema_version") != REFUTED_SCHEMA:
            continue
        out.append(dict(doc, _path=str(path)))
    # 与 load_steps / latest_receipt / report 同一口径：**解析成时刻**再比。
    # `refuted_at` 抄自收据的 generated_at，同样可能混着 `12:00:00Z` 与
    # `12:00:00.500000+00:00` 两种合法 ISO UTC——字符串序与时间序相反，
    # `report --refuted` 会选中较早那份（09-12 质检实测）。
    out.sort(key=lambda d: (_parse_ts(d.get("refuted_at")), d["_path"]), reverse=True)
    return out, unreadable


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
    """落 ``<root>/scan/<date>-<HHMMSS>.{json,md}``。**每次扫描各留一份**——同一天跑
    三段（discovery / validation / holdout）时前两段的汇总不该被最后一段覆盖。"""
    folder = Path(root).expanduser() / "scan"
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{date_str}-{_run_suffix(summary)}"
    json_path = folder / f"{stem}.json"
    md_path = folder / f"{stem}.md"
    # 与收据同一道闸：原子创建 + 同名比内容。原本这里完全没接，强制同名即可覆盖旧汇总。
    _write_exclusive(json_path, json.dumps(summary, ensure_ascii=False, indent=2) + "\n", summary)
    _write_exclusive(md_path, render_scan_markdown(summary), summary)
    return json_path, md_path
