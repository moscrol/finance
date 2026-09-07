"""授课框架 → 时间长河：把旁路库里已算好的教学标签，作为盘面轨的 ``teaching_*`` 对象读给切片。

roadmap G-01 (b)「复盘 run 新增 teaching 模式，可关，关掉后输出与当前逐字节一致」的前置：这里只负责
**读**（旁路库 → ``RiverObject``），不算任何新东西、不解释、不下结论。三个对象，全部挂在盘面轨的
``__market__`` 实体上：

- ``teaching_stage``      当日的 ``tf.*`` 阶段读数：粗 / 细阶段、置信档（几条视角命中 / 缺哪几条 / 领先几分）、
                          来源状态、量能三档、偏离度带、周均线上下与下方周期、亏钱效应日、承接 5 日均值、量能比。
- ``teaching_dynasty``    王朝链截至当日的状态。**只暴露当日已知的东西**（第十三段「站在当时那个节点是看不出谁
                          会是新王朝」是这条对象的契约）：最近一个已见顶的王朝（其覆灭窗已开始 = 当日或更早
                          的平台阶段已离开顶部块）、它的前 N 成员（波内涨幅在见顶日已锁定）、覆灭窗至今的天数与
                          亏钱日数；下一波的成员只在下一波**也见顶之后**（其覆灭窗开始 ≤ 当日）才出现——
                          那时整节衔接才算「走出来」。当日之后才定下来的边界（覆灭窗终点、下一波起点）不写。
- ``teaching_range_leaders`` 当日各窗口的区间涨幅前 N 组（名次、涨幅、在位第几天、申万一级）——当日的事实。

``recorded_at`` 一律取旁路库行的 ``computed_at``（构建时刻）：标签是事后重算的，回放 / 校准用 ``require_strict``
时这些对象会被无前视门滤掉，这是对的——它们在历史那天并不存在。当日带读（cutoff = as_of）能看到。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from intelligence.services.methodology_backtest.store import open_labels_db
from intelligence.services.river import RiverObject, _hash, _ts

STAGE_LABELS = (
    "tf.stage_coarse", "tf.stage_fine", "tf.stage_evidence", "tf.volume_band", "tf.deviation_band",
    "tf.above_week_ma", "tf.cross_below_kind", "tf.below_ma_cycle_day", "tf.money_losing_day", "tf.money_losing_streak",
    "tf.limit_premium_ma5_pct", "tf.amount_vs_ma20_pct", "tf.new_high_1y_count", "tf.turn_up", "tf.turn_top", "tf.turn_down",
)
EVIDENCE_KEYS = ("confidence", "from", "entered", "eligible", "resolution", "tied")


def _date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _rows(con: Any, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    cur = con.execute(sql, params)
    names = [str(c[0]) for c in cur.description]
    return [dict(zip(names, row, strict=True)) for row in cur.fetchall()]


def _has_table(con: Any, table: str) -> bool:
    return bool(con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", [table]).fetchone()[0])


def teaching_objects(labels_db: str | Path, as_of: str, *, top: int = 10) -> list[RiverObject]:
    """Read the teaching sidecar for ``as_of`` and return the ``teaching_*`` river objects (possibly empty)."""
    path = Path(labels_db).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"教学框架旁路库不存在: {path}（先跑 scripts/teaching_framework.py build-labels）")
    day = _date(as_of)
    con = open_labels_db(path, read_only=True)
    try:
        out: list[RiverObject] = []
        stage = _stage_object(con, day, as_of)
        if stage is not None:
            out.append(stage)
        dynasty = _dynasty_object(con, day, as_of, top=top)
        if dynasty is not None:
            out.append(dynasty)
        leaders = _range_leaders_object(con, day, as_of, top=top)
        if leaders is not None:
            out.append(leaders)
        return out
    finally:
        con.close()


def _stage_object(con: Any, day: date, as_of: str) -> RiverObject | None:
    if not _has_table(con, "history_teaching_labels"):
        return None
    rows = _rows(
        con,
        f"""SELECT label, value_num, value_text, framework_version, computed_at FROM history_teaching_labels
            WHERE entity_type = 'market' AND entity_id = 'market' AND status = 'ok' AND trade_date = ?
              AND label IN ({", ".join("?" for _ in STAGE_LABELS)})
            ORDER BY label""",
        [day, *STAGE_LABELS],
    )
    if not rows:
        return None
    payload: dict[str, Any] = {}
    versions: set[str] = set()
    computed: list[Any] = []
    for r in rows:
        label = str(r["label"]).removeprefix("tf.")
        value = r["value_text"] if r["value_text"] is not None else r["value_num"]
        if label == "stage_evidence":
            try:
                evidence = json.loads(str(value)) if value is not None else {}
            except ValueError:
                evidence = {}
            payload["evidence"] = {k: evidence.get(k) for k in EVIDENCE_KEYS if k in evidence}
            payload["evidence_hits"] = [f"{h.get('stage')}:{h.get('predicate')}" for h in (evidence.get("hits") or [])]
        else:
            payload[label] = value
        versions.add(str(r["framework_version"]))
        computed.append(r["computed_at"])
    payload["framework_version"] = sorted(versions)[0] if len(versions) == 1 else sorted(versions)
    hashed = {k: v for k, v in payload.items()}
    return RiverObject(
        track="market", entity_id="__market__", object_type="teaching_stage",
        ref=f"history_teaching_labels:{as_of}:market", source_hash=_hash(hashed),
        valid_from=as_of, recorded_at=_ts(max(computed)) if computed else None, payload=payload,
    )


def _dynasty_object(con: Any, day: date, as_of: str, *, top: int) -> RiverObject | None:
    if not _has_table(con, "history_dynasties"):
        return None
    waves = _rows(
        con,
        """SELECT DISTINCT wave_idx, wave_start, peak_end, collapse_start, collapse_end, wave_status, framework_version
           FROM history_dynasties ORDER BY wave_idx""",
        [],
    )
    # The latest wave whose collapse has started by ``day``: its peak is known (the platform's stage on
    # collapse_start already left the peak block).  Waves still inside their peak block on ``day`` are unknown.
    known = [w for w in waves if w["collapse_start"] is not None and _date(w["collapse_start"]) <= day]
    if not known:
        return None
    w = known[-1]
    wi = int(w["wave_idx"])
    members = _rows(
        con,
        """SELECT rank, stock_ts_code, stock_name, wave_gain_pct, sw_l1, form, computed_at FROM history_dynasties
           WHERE wave_idx = ? AND rank <= ? ORDER BY rank""",
        [wi, top],
    )
    counted = _rows(
        con,
        """SELECT COUNT(*) AS days, COALESCE(SUM(CASE WHEN value_num = 1 THEN 1 ELSE 0 END), 0) AS losing
           FROM history_teaching_labels
           WHERE entity_type = 'market' AND label = 'tf.money_losing_day' AND status = 'ok' AND trade_date BETWEEN ? AND ?""",
        [w["collapse_start"], day],
    )
    payload: dict[str, Any] = {
        "wave_idx": wi, "wave_status": w["wave_status"], "wave_start": str(w["wave_start"]), "peak_end": str(w["peak_end"]),
        "collapse_start": str(w["collapse_start"]),
        "labelled_days_since_collapse_start": int(counted[0]["days"]) if counted else None,
        "money_losing_days_since_collapse_start": int(counted[0]["losing"]) if counted else None,
        "dynasty_top": [
            {"rank": int(m["rank"]), "stock_ts_code": m["stock_ts_code"], "stock_name": m["stock_name"],
             "wave_gain_pct": m["wave_gain_pct"], "sw_l1": m["sw_l1"], "form": m["form"]}
            for m in members
        ],
        "framework_version": w["framework_version"],
        "note": "只写当日已知的东西：这一波已见顶（覆灭窗已开始），成员在见顶日锁定；覆灭窗终点与下一波要等下一波也见顶才知道，"
                "所以这里没有它们，也永远没有「候选新王朝」名单",
    }
    # The handoff *into* this wave is fully known once this wave has peaked: how its members behaved in the
    # previous dynasty's collapse (分离确认) is a retrospective fact by ``day``.
    prev = next((x for x in waves if int(x["wave_idx"]) == wi - 1), None)
    if prev is not None:
        new_members = _rows(
            con,
            """SELECT new_rank, stock_ts_code, stock_name, old_wave_rank, collapse_ret_percentile, separation_relative,
                      separation_new_high, separation_on_losing_days, separation_on_other_days
               FROM history_dynasty_handoffs WHERE old_wave_idx = ? AND new_wave_idx = ? AND new_rank <= ? ORDER BY new_rank""",
            [int(prev["wave_idx"]), wi, top],
        )
        payload["last_completed_handoff"] = {
            "old_wave_idx": int(prev["wave_idx"]), "old_peak_end": str(prev["peak_end"]),
            "old_collapse": [str(prev["collapse_start"]), None if prev["collapse_end"] is None else str(prev["collapse_end"])],
            "new_members_in_old_collapse": [
                {"rank": int(m["new_rank"]), "stock_ts_code": m["stock_ts_code"], "stock_name": m["stock_name"],
                 "old_wave_rank": m["old_wave_rank"], "collapse_ret_percentile": m["collapse_ret_percentile"],
                 "separation_relative": m["separation_relative"], "separation_new_high": m["separation_new_high"],
                 "separation_on_losing_days": m["separation_on_losing_days"], "separation_on_other_days": m["separation_on_other_days"]}
                for m in new_members
            ],
        }
    computed = [m["computed_at"] for m in members if m.get("computed_at") is not None]
    return RiverObject(
        track="market", entity_id="__market__", object_type="teaching_dynasty",
        ref=f"history_dynasties:{wi}", source_hash=_hash(payload), valid_from=as_of,
        recorded_at=_ts(max(computed)) if computed else None, payload=payload,
    )


def _range_leaders_object(con: Any, day: date, as_of: str, *, top: int) -> RiverObject | None:
    if not _has_table(con, "history_range_leaders"):
        return None
    rows = _rows(
        con,
        """SELECT window_days, rank, stock_ts_code, stock_name, gain_pct, sw_l1, limit_times, tenure_day, framework_version, computed_at
           FROM history_range_leaders WHERE trade_date = ? AND rank <= ? ORDER BY window_days, rank""",
        [day, top],
    )
    if not rows:
        return None
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault(str(int(r["window_days"])), []).append({
            "rank": int(r["rank"]), "stock_ts_code": r["stock_ts_code"], "stock_name": r["stock_name"], "gain_pct": r["gain_pct"],
            "sw_l1": r["sw_l1"], "limit_times": r["limit_times"], "tenure_day": r["tenure_day"],
        })
    payload = {"windows": groups, "framework_version": sorted({str(r["framework_version"]) for r in rows})[0]}
    return RiverObject(
        track="market", entity_id="__market__", object_type="teaching_range_leaders",
        ref=f"history_range_leaders:{as_of}", source_hash=_hash(payload), valid_from=as_of,
        recorded_at=_ts(max(r["computed_at"] for r in rows)), payload=payload,
    )
