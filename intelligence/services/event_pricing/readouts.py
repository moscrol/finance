"""读数与收据：形状 × 非事件日基准 → 四态；按阶段分桶（caveat）；三代理 × 形状计数；横截面频次；``latest_known`` 自测。

全部经 ``methodology_backtest.stats.readout / stage_readouts`` 出四态，不建第二套统计口径。
收据里不出现「概率」「可能性」「利好出尽」这类结论词——``assert_no_forbidden_words`` 是测试用的门。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from market_feature_store.db import DB_PATH as CANONICAL_DB_PATH

from intelligence.services.methodology_backtest.stats import (
    apply_bh_downgrade,
    benjamini_hochberg,
    readout,
    stage_readouts,
)
from intelligence.services.methodology_backtest.store import (
    attach_source,
    default_labels_db_path,
    detach_source,
    open_labels_db,
    read_meta,
    utc_now,
)

from .event_calendar import latest_known
from .params import EventParams, load_params
from .reaction import SEMANTICS_EXPECTATION, SEMANTICS_STATE_ONLY, SHAPES, build_feature_pool, quantile

FORBIDDEN_PATTERNS = (
    re.compile(r"概率"),
    re.compile(r"可能性"),
    re.compile(r"利好出尽"),
    re.compile(r"\d+(\.\d+)?%\s*会"),
)
STOCK_CODE_RE = re.compile(r"\b\d{6}\.(SZ|SH|BJ)\b")


def assert_no_forbidden_words(text: str) -> None:
    for pat in FORBIDDEN_PATTERNS:
        m = pat.search(text)
        if m:
            raise AssertionError(f"收据出现禁词/禁形: {m.group(0)!r}")


def _dist(values: list[float | None]) -> dict[str, Any]:
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "p25": round(quantile(vals, 0.25), 3),
        "p50": round(quantile(vals, 0.5), 3),
        "p75": round(quantile(vals, 0.75), 3),
        "share_positive": round(sum(1 for v in vals if v > 0) / len(vals), 3),
    }


def _fetch_records(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    cols = [
        "event_class", "reaction_day", "entity_type", "entity_id", "pre_window_semantics", "source_grade",
        "pre_return_m", "d0_return", "fwd_return_3", "fwd_return_5", "fwd_return_10", "excess_pre_m", "excess_d0",
        "excess_fwd_5", "shape_tag", "crowding_pct_dm1", "consensus_stage_dm1", "consensus_stage_gap",
        "market_stage_dm1", "status", "d0_amount_ratio", "d0_limit_up_delta", "dispersion_d0_iqr",
    ]
    rows = con.execute(f"SELECT {', '.join(cols)} FROM history_event_reaction ORDER BY reaction_day, event_class, entity_type, entity_id").fetchall()
    return [dict(zip(cols, r)) for r in rows]


def _baseline(con: duckdb.DuckDBPyConnection, event_class: str, entity_type: str) -> tuple[dict[str, int], int, dict[str, tuple[int, int]], dict[str, dict[str, int]]]:
    """同实体集合、全部非锚点交易日的形状计数。返回 (k_by_shape, n, by_stage {stage: (n, k)} 需按形状 → 见第四项)。"""
    rows = con.execute(
        """
        WITH ents AS (
            SELECT DISTINCT entity_type, entity_id FROM history_event_anchors WHERE label = ? AND entity_type = ?
        ),
        anchor_days AS (
            SELECT entity_type, entity_id, trade_date FROM history_event_anchors WHERE label = ?
        )
        SELECT f.shape_tag, COALESCE(f.market_stage_dm1, '(无阶段)'), COUNT(*)
        FROM _feat f
        JOIN ents e ON e.entity_type = f.entity_type AND e.entity_id = f.entity_id
        LEFT JOIN anchor_days a ON a.entity_type = f.entity_type AND a.entity_id = f.entity_id AND a.trade_date = f.trade_date
        WHERE a.trade_date IS NULL AND f.shape_tag IS NOT NULL
        GROUP BY 1, 2
        """,
        [f"ev.{event_class}", entity_type, f"ev.{event_class}"],
    ).fetchall()
    k_by_shape: dict[str, int] = {s: 0 for s in SHAPES}
    n = 0
    stage_n: dict[str, int] = {}
    stage_k: dict[str, dict[str, int]] = {}
    for shape, stage, cnt in rows:
        k_by_shape[shape] = k_by_shape.get(shape, 0) + int(cnt)
        n += int(cnt)
        stage_n[stage] = stage_n.get(stage, 0) + int(cnt)
        stage_k.setdefault(stage, {})
        stage_k[stage][shape] = stage_k[stage].get(shape, 0) + int(cnt)
    by_stage = {s: (stage_n[s], 0) for s in stage_n}
    return k_by_shape, n, by_stage, stage_k


def class_readouts(con: duckdb.DuckDBPyConnection, params: EventParams, records: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    classes = sorted({r["event_class"] for r in records})
    for cls in classes:
        recs = [r for r in records if r["event_class"] == cls]
        etype = params.classes[cls].scope if cls in params.classes else recs[0]["entity_type"]
        ok = [r for r in recs if r["status"] == "ok"]
        k_by_shape, base_n, base_stage_n, base_stage_k = _baseline(con, cls, etype)
        entry: dict[str, Any] = {
            "entity_type": etype,
            "anchor_days": len({r["reaction_day"] for r in recs}),
            "records_by_status": _count(recs, "status"),
            "records_by_semantics": _count(ok, "pre_window_semantics"),
            "records_by_source_grade": _count(recs, "source_grade"),
            "baseline": {"n": base_n, "k_by_shape": k_by_shape, "note": "同实体集合、全部非锚点交易日；形状同定义"},
            "by_semantics": {},
        }
        for sem in (SEMANTICS_EXPECTATION, SEMANTICS_STATE_ONLY):
            sub = [r for r in ok if r["pre_window_semantics"] == sem]
            if not sub:
                continue
            sem_entry: dict[str, Any] = {
                "n": len(sub),
                "distributions": {
                    "pre_return_m": _dist([r["pre_return_m"] for r in sub]),
                    "d0_return": _dist([r["d0_return"] for r in sub]),
                    "fwd_return_3": _dist([r["fwd_return_3"] for r in sub]),
                    "fwd_return_5": _dist([r["fwd_return_5"] for r in sub]),
                    "fwd_return_10": _dist([r["fwd_return_10"] for r in sub]),
                    "d0_amount_ratio": _dist([r["d0_amount_ratio"] for r in sub]),
                    "d0_limit_up_delta": _dist([r["d0_limit_up_delta"] for r in sub]),
                },
                "shape_counts": _count(sub, "shape_tag"),
                "shapes": {},
                "by_stage": {},
            }
            if etype == "sector":
                sem_entry["distributions"]["excess_d0"] = _dist([r["excess_d0"] for r in sub])
                sem_entry["distributions"]["excess_fwd_5"] = _dist([r["excess_fwd_5"] for r in sub])
            ordered = sorted(sub, key=lambda r: (r["reaction_day"], r["entity_id"]))
            shape_rds = {}
            for shape in SHAPES:
                successes = [r["shape_tag"] == shape for r in ordered]
                rd = readout(successes, baseline_n=base_n, baseline_k=k_by_shape.get(shape, 0), min_n=params.min_n)
                shape_rds[shape] = rd
                sem_entry["shapes"][shape] = rd.to_dict()
            # 六个形状是一族六次检验：族内 BH，没拒绝 H0 的 supported / refuted 降级
            testable = [s for s in SHAPES if shape_rds[s].p_value is not None and shape_rds[s].verdict != "insufficient_n"]
            rejected: dict[str, bool] = {s: False for s in SHAPES}
            adjusted: dict[str, float | None] = {s: None for s in SHAPES}
            if testable:
                rej, adj = benjamini_hochberg([shape_rds[s].p_value for s in testable], q=params.bh_q)
                for s, r_, a_ in zip(testable, rej, adj):
                    rejected[s], adjusted[s] = r_, a_
            verdicts_bh = apply_bh_downgrade([shape_rds[s].verdict for s in SHAPES], [rejected[s] for s in SHAPES])
            for s, v in zip(SHAPES, verdicts_bh):
                d = sem_entry["shapes"][s]
                d["verdict_single"] = d.pop("verdict")
                d["verdict"] = v
                d["bh"] = {"q": params.bh_q, "family": list(SHAPES), "adjusted_p": adjusted[s], "rejected": rejected[s]}
            for shape in SHAPES:
                by_stage_succ: dict[str, list[bool]] = {}
                for r in ordered:
                    st = r["market_stage_dm1"] or "(无阶段)"
                    by_stage_succ.setdefault(st, []).append(r["shape_tag"] == shape)
                baseline_by_stage = {
                    st: (base_stage_n.get(st, (0, 0))[0], base_stage_k.get(st, {}).get(shape, 0)) for st in by_stage_succ
                }
                buckets = stage_readouts(by_stage_succ, baseline_by_stage, min_n=params.min_n, q=params.bh_q)
                sem_entry["by_stage"][shape] = {
                    "caveat": "market_stage 是旁路库 history_labels 里的供应商阶段标签（是否归一取决于 labels 版本，见 build_meta.labels；G-05）；分桶读数只作对照，不作结论",
                    "buckets": [b.to_dict() for b in buckets],
                }
            sem_entry["proxies_by_shape"] = _proxies_by_shape(sub)
            entry["by_semantics"][sem] = sem_entry
        if etype == "market":
            entry["cross_section"] = _cross_section_summary(con, cls, params)
            entry["dispersion_d0_iqr"] = _dist([r["dispersion_d0_iqr"] for r in ok])
        out[cls] = entry
    return out


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = str(r.get(key))
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def _proxies_by_shape(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for shape in SHAPES:
        sub = [r for r in rows if r["shape_tag"] == shape]
        if not sub:
            continue
        pre_key = "excess_pre_m" if sub[0]["entity_type"] == "sector" else "pre_return_m"
        out[shape] = {
            "n": len(sub),
            "pre_excess_m": _dist([r[pre_key] for r in sub]),
            "crowding_pct_dm1": _dist([r["crowding_pct_dm1"] for r in sub]),
            "consensus_stage_dm1": {"n_with_value": sum(1 for r in sub if r["consensus_stage_dm1"]), "gap": _count(sub, "consensus_stage_gap")},
        }
    return out


def _cross_section_summary(con: duckdb.DuckDBPyConnection, cls: str, params: EventParams) -> dict[str, Any]:
    sh = int(params.shape_horizon)
    rows = con.execute(
        """
        SELECT metric, entity_id, ANY_VALUE(entity_name), COUNT(*)
        FROM history_event_cross_section
        WHERE event_class = ? AND entity_kind = 'sector'
        GROUP BY 1, 2 ORDER BY 1, 4 DESC, 2
        """,
        [cls],
    ).fetchall()
    n_events = con.execute(
        "SELECT COUNT(DISTINCT reaction_day) FROM history_event_cross_section WHERE event_class = ?", [cls]
    ).fetchone()[0]
    freq: dict[str, list[dict[str, Any]]] = {}
    for metric, eid, name, cnt in rows:
        freq.setdefault(metric, [])
        if len(freq[metric]) < 10:
            freq[metric].append({"sector": name or eid, "code": eid, "times_in_top_k": int(cnt)})
    sw = con.execute(
        f"""
        SELECT entity_id, AVG(value), COUNT(*)
        FROM history_event_cross_section
        WHERE event_class = ? AND entity_kind = 'sw_l1' AND metric = 'sw_l1_excess_fwd{sh}'
        GROUP BY 1 ORDER BY 2 DESC
        """,
        [cls],
    ).fetchall()
    return {
        "events_with_cross_section": int(n_events or 0),
        "top_k": params.cross_section_top_k,
        "frequency_in_top_k": freq,
        "sw_l1_mean_excess_fwd": [{"sw_l1": r[0], "mean_excess": round(float(r[1]), 3), "n": int(r[2])} for r in sw],
        "note": "只报出现次数与均值，不登记规则",
    }


def build_receipt(
    source_db: str | Path | None,
    labels_db: str | Path | None,
    *,
    params: EventParams | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    params = params or load_params()
    source = Path(source_db).expanduser() if source_db else CANONICAL_DB_PATH
    labels_path = Path(labels_db).expanduser() if labels_db else default_labels_db_path(source)
    con = open_labels_db(labels_path, read_only=True)
    try:
        meta = read_meta(con)
        if "event_reaction" not in meta:
            raise RuntimeError("旁路库没有 event_reaction 构建记录，先跑 build-reaction")
        attach_source(con, source)
        try:
            build_feature_pool(con, params)
            records = _fetch_records(con)
            classes = class_readouts(con, params, records)
            coverage = [
                {"series": str(k), "entities": int(n), "first_day": str(lo), "last_day": str(hi), "entity_days": int(rows)}
                for k, n, lo, hi, rows in con.execute(
                    """
                    SELECT CASE WHEN entity_type = 'market' THEN 'market' ELSE 'sector.' || right(entity_id, 2) END AS series,
                           COUNT(DISTINCT entity_id), MIN(c.trade_date), MAX(c.trade_date), COUNT(*)
                    FROM _series s JOIN history_calendar c ON c.idx = s.idx
                    GROUP BY 1 ORDER BY 1
                    """
                ).fetchall()
            ]
        finally:
            detach_source(con)
        cal_by_class = dict(con.execute("SELECT event_class, COUNT(*) FROM history_event_calendar GROUP BY 1 ORDER BY 1").fetchall())
        cal_by_grade = dict(con.execute("SELECT source_grade, COUNT(*) FROM history_event_calendar GROUP BY 1 ORDER BY 1").fetchall())
        gaps = dict(
            con.execute("SELECT gap_kind || '/' || reason, COUNT(*) FROM history_event_gaps GROUP BY 1 ORDER BY 1").fetchall()
        )
        cal_end = con.execute("SELECT MAX(trade_date) FROM history_calendar").fetchone()[0]
        lk: dict[str, Any] = {}
        for ind in sorted(params.indicator_to_class()):
            lk[ind] = latest_known(con, ind, cal_end)
    finally:
        con.close()
    computed = (now or utc_now()).isoformat(timespec="seconds")
    return {
        "kind": "event_pricing_receipt",
        "ev_version": params.ev_version,
        "computed_at": computed,
        "labels_db": str(labels_path),
        "source_db": str(source),
        "build_meta": {k: v for k, v in meta.items() if k in ("labels", "outcomes", "event_calendar", "event_anchors", "event_reaction")},
        "params": params.to_dict(),
        "calendar": {
            "by_class": {str(k): int(v) for k, v in cal_by_class.items()},
            "by_source_grade": {str(k): int(v) for k, v in cal_by_grade.items()},
            "gaps": {str(k): int(v) for k, v in gaps.items()},
        },
        "latest_known_at_calendar_end": {"as_of": str(cal_end), "by_indicator": lk},
        "price_series_coverage": coverage,
        "classes": classes,
        "discipline": [
            "读数不是结论：形状标签是描述词，四态来自 stats.readout，N < min_n 一律 insufficient_n",
            "expectation 与 state_only 分表：只有官方日程事前已公开的事件，事前窗才读作预期",
            "日历知道何时不知道多少：latest_known 不返回数值",
            "横截面只到板块 / 申万一级，不到个股",
        ],
    }


def _fmt(x: Any) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.2f}"
    return str(x)


def render_markdown(receipt: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# 事件定价读数 · {receipt['ev_version']} · {receipt['computed_at']}")
    lines.append("")
    lines.append("> 读数不是结论。形状标签是描述词；四态来自统计门；N < min_n 一律 insufficient_n；日历只答何时。")
    lines.append("")
    cal = receipt["calendar"]
    lines.append("## 日历")
    lines.append("")
    lines.append("| 事件类 | 行数 |\n|---|---:|")
    for k, v in cal["by_class"].items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("来源等级：" + ", ".join(f"{k}={v}" for k, v in cal["by_source_grade"].items()))
    lines.append("缺口：" + (", ".join(f"{k}={v}" for k, v in cal["gaps"].items()) or "无"))
    lines.append("")
    lines.append("价格序列覆盖（板块锚点只在序列覆盖的日子里才有反应记录）：")
    for c in receipt.get("price_series_coverage", []):
        lines.append(f"- {c['series']}: {c['entities']} 个实体，{c['first_day']} → {c['last_day']}，{c['entity_days']} 实体日")
    lines.append("")
    lk = receipt["latest_known_at_calendar_end"]
    lines.append(f"## latest_known @ {lk['as_of']}")
    lines.append("")
    lines.append("| 指标 | 状态 | 最新一期 | 发布日 | 下一期发布日 | 来源等级 |\n|---|---|---|---|---|---|")
    for ind, d in lk["by_indicator"].items():
        lines.append(
            f"| {ind} | {d.get('status')} | {_fmt(d.get('period'))} | {_fmt(d.get('release_date'))} | {_fmt(d.get('next_release_date'))} | {_fmt(d.get('source_grade'))} |"
        )
    lines.append("")
    for cls, e in receipt["classes"].items():
        lines.append(f"## {cls}（{e['entity_type']}）")
        lines.append("")
        lines.append(
            f"锚点日 {e['anchor_days']}；记录 " + ", ".join(f"{k}={v}" for k, v in e["records_by_status"].items())
            + "；来源 " + ", ".join(f"{k}={v}" for k, v in e["records_by_source_grade"].items())
            + f"；基准 N={e['baseline']['n']}"
        )
        lines.append("")
        for sem, s in e["by_semantics"].items():
            lines.append(f"### {sem}（n={s['n']}）")
            lines.append("")
            lines.append("| 窗口 | n | p25 | p50 | p75 | 为正占比 |\n|---|---:|---:|---:|---:|---:|")
            for w, d in s["distributions"].items():
                if d.get("n"):
                    lines.append(f"| {w} | {d['n']} | {_fmt(d['p25'])} | {_fmt(d['p50'])} | {_fmt(d['p75'])} | {_fmt(d['share_positive'])} |")
                else:
                    lines.append(f"| {w} | 0 | — | — | — | — |")
            lines.append("")
            lines.append("| 形状 | k/N | 基准 k0/N0 | Wilson | 前/后半段 | 四态（族内 BH 后） |\n|---|---|---|---|---|---|")
            for shape, rd in s["shapes"].items():
                verdict = rd["verdict"]
                if rd.get("verdict_single") and rd["verdict_single"] != verdict:
                    verdict = f"{verdict}（单次 {rd['verdict_single']}）"
                lines.append(
                    f"| {shape} | {rd['k']}/{rd['n']} | {rd['baseline_k']}/{rd['baseline_n']} | "
                    f"[{_fmt(rd['wilson_lo'])}, {_fmt(rd['wilson_hi'])}] | {_fmt(rd['first_half']['p'])}/{_fmt(rd['second_half']['p'])} | {verdict} |"
                )
            lines.append("")
            decided = []
            for shape, bs in s["by_stage"].items():
                for b in bs["buckets"]:
                    if b["verdict"] in ("supported", "refuted"):
                        decided.append(f"{shape} × {b['stage']} n={b['n']} → {b['verdict']}")
            lines.append("按阶段（供应商 market_stage 标签，只作对照）：" + ("; ".join(decided) if decided else "无任一桶过门（insufficient_n 或 not_distinguishable）"))
            lines.append("")
            lines.append("| 形状 | n | 事前超额 p50 | 拥挤度分位 p50 | 舆论阶段有值 |\n|---|---:|---:|---:|---:|")
            for shape, p in s["proxies_by_shape"].items():
                lines.append(
                    f"| {shape} | {p['n']} | {_fmt(p['pre_excess_m'].get('p50'))} | {_fmt(p['crowding_pct_dm1'].get('p50'))} | {p['consensus_stage_dm1']['n_with_value']} |"
                )
            lines.append("")
        if "cross_section" in e:
            cs = e["cross_section"]
            lines.append(f"横截面：{cs['events_with_cross_section']} 个锚点日；进前 {cs['top_k']} 次数最多的板块：")
            for metric, items in cs["frequency_in_top_k"].items():
                lines.append(f"- {metric}: " + ", ".join(f"{i['sector']}×{i['times_in_top_k']}" for i in items[:5]))
            lines.append("")
    lines.append("## 纪律")
    for d in receipt["discipline"]:
        lines.append(f"- {d}")
    lines.append("")
    return "\n".join(lines)


def write_receipt(receipts_dir: str | Path, receipt: dict[str, Any], *, date_str: str) -> tuple[Path, Path]:
    d = Path(receipts_dir).expanduser() / "event_pricing"
    d.mkdir(parents=True, exist_ok=True)
    stem = f"{date_str}-{receipt['ev_version'].replace('+', '_')}"
    jp = d / f"{stem}.json"
    mp = d / f"{stem}.md"
    jp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    md = render_markdown(receipt)
    assert_no_forbidden_words(md)
    mp.write_text(md, encoding="utf-8")
    return jp, mp
