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
- ``teaching_breadth``   广度（第二十五段）：个股周均线上方占比、20 日新高 / 新低家数、一年新低、上涨比例、涨幅中位、偏离度中位、背离广度。
- ``teaching_capital`` / ``teaching_narrative`` / ``teaching_briefing`` 资金面与消息面（卖方观点事件、晨汇 Tier 投影）的
                          市场级当日读数，各一个对象；某个源没有读数的日子，原因（未接知识库 / 断更 / 当日无晨汇）挂在阶段对象上。

标签对象的 ``recorded_at`` 取成分行最晚的 ``first_known_at``；任一成分缺戳则整体未知。
王朝与区间高标等尚无逐行可知性证据的对象继续用 ``computed_at``。河的 PIT 闸仍过滤晚于
cutoff 的对象，不能仅凭 trade_date 声称历史那天就可见。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from intelligence.services.methodology_backtest.store import open_labels_db
from intelligence.services.river import RiverObject, _hash, _ts

STAGE_LABELS = (
    "tf.stage_coarse", "tf.stage_fine", "tf.stage_evidence", "tf.volume_band", "tf.deviation_band",
    "tf.above_week_ma", "tf.cross_below_kind", "tf.below_ma_cycle_day", "tf.money_losing_day", "tf.money_losing_streak",
    "tf.limit_premium_ma5_pct", "tf.amount_vs_ma20_pct", "tf.new_high_1y_count", "tf.turn_up", "tf.turn_top", "tf.turn_down",
)
EVIDENCE_KEYS = ("confidence", "from", "entered", "eligible", "resolution", "tied")
# 资金面（第十五段）：单独一个对象，免得阶段对象超过「payload ≤ 20 键」的索引层约束。全部是市场级当日读数。
CAPITAL_LABELS = (
    "tf.dragon_count", "tf.dragon_net_amount", "tf.dragon_net_amount_ratio_pm", "tf.dragon_net_amount_ratio_pm_ma5",
    "tf.dragon_buy_sell_ratio", "tf.dragon_buy_sell_ratio_ma5", "tf.limit_seal_amount_median_wan", "tf.limit_seal_mv_ratio_median",
    "tf.limit_thick_seal_share_pct", "tf.auction_zt_pct_median", "tf.auction_zt_positive_share_pct", "tf.auction_zt_amount",
    "tf.top100_amount_share", "tf.mainline_share_expanding.volume_top3",
)
# 消息面（第十六段）：知识库卖方观点事件聚成的市场级叙事读数（隔夜可知的那部分），只搬不解释。
NARRATIVE_LABELS = tuple(f"tf.{name}" for name in (
    "narrative_events", "narrative_events_ratio_ma20_pct", "narrative_concepts", "narrative_new_concepts",
    "narrative_new_concept_share_pct", "narrative_hard_share_pct", "narrative_bull_share_pct", "narrative_top3_share_pct",
    "narrative_cover_rps5_pct",
))
# 消息面第二个源：晨汇 Tier 投影。两个源各自一个对象、各自的缺口原因（卖方断更时晨汇可能还在，反之亦然）。
BRIEFING_LABELS = tuple(f"tf.{name}" for name in (
    "briefing_tier1_items", "briefing_tier2_items", "briefing_tier3_items", "briefing_market_confirmed",
    "briefing_dimensions", "briefing_hit_rps5_pct", "briefing_lag_days",
))
# 周期位置：转点、周均线穿越、量能日型、主线容量趋势。
# 从旁路库搬运已有标签，不在判定路径重新计算。
# （转点缺口、站上周均确认、缩量、双量日、量板块、主线成交占比趋势、连板高度、偏离度收敛）。
# 不并进 STAGE_LABELS 的原因与 CAPITAL/BREADTH 相同：阶段对象已接近 payload ≤ 20 键的索引层约束。
# 这里只负责**搬**，不新增任何计算、阈值或口径。
CYCLE_LABELS = tuple(f"tf.{name}" for name in (
    "gap_down_open", "cross_above_week_ma", "deviation_narrowing",
    "shrink_day", "volume_shrink_streak", "double_volume_day",
    "mainline_volume_top3", "mainline_share_trend_up", "max_boards",
))
# 广度（第二十五段）：全市场个股层的市场级读数，单独一个对象——阶段对象已接近 payload ≤ 20 键的上限。
BREADTH_LABELS = tuple(f"tf.{name}" for name in (
    "stock_above_ma5_share_pct", "new_high_20d_count", "new_low_20d_count", "new_low_1y_count",
    "stock_up_ratio_pct", "stock_pct_chg_median", "stock_ma5_deviation_median", "stock_ma10_deviation_median",
    "stock_div_bottom_observe_share_pct", "stock_div_top_share_pct",
))
# 没有某个叙事对象的日子，要说清为什么（未接知识库 / 源断更 / 当日无晨汇），不能让读者以为「今天没消息」；挂在阶段对象上。
_SOURCE_GAPS = (("narrative_gap", "tf.narrative_events"), ("briefing_gap", "tf.briefing_tier1_items"))


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


class StaleTeachingSidecarError(RuntimeError):
    """教学旁路库的表比当前 DDL 旧，读不出 PIT 身份。"""


def _require_pit_column(con: Any) -> None:
    """``history_teaching_labels`` 必须有 ``first_known_at``，否则给出可操作的中止。

    为什么需要这个：加 ``first_known_at`` 那一刀只改了 DDL，而 ``ensure_schema`` 全是
    ``CREATE TABLE IF NOT EXISTS``——**已存在的旧表不会被加列**。写路径有
    ``_open_sidecar_for_write`` → ``check_teaching_schema`` 挡着，读路径只有
    ``_has_table``（查表在不在），没查列。于是旧库上这里会抛一个裸的
    ``Binder Error: Referenced column "first_known_at" not found``——
    对着那条信息没人猜得到该做什么。

    不选「列不在就当 NULL 继续」：那会静默产出一批没有 PIT 身份的对象，
    正是「有库无河」那一类病（管子通着、水是假的）。教学表**可丢弃**
    （内容全部能由 ``build-*`` 从主库重算），所以这里直接要求重建。
    """
    if not _has_table(con, "history_teaching_labels"):
        return
    cols = {
        str(r[0])
        for r in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'history_teaching_labels'"
        ).fetchall()
    }
    if "first_known_at" not in cols:
        raise StaleTeachingSidecarError(
            "history_teaching_labels 缺列 first_known_at：这张表建于加 PIT 身份之前。"
            "ensure_schema 的 CREATE TABLE IF NOT EXISTS 不会给已存在的表加列。"
            "跑 `teaching_framework.py reset-teaching` 重建 10 张教学表后再 build-*"
            "（教学表可重算；legacy 的 history_calendar / history_labels 不会被动）。"
        )


def teaching_objects(
    labels_db: str | Path, as_of: str, *, top: int = 10,
    entity_type: str | None = None, entity_id: str | None = None,
) -> list[RiverObject]:
    """Read the teaching sidecar for ``as_of`` and return the ``teaching_*`` river objects (possibly empty).

    ``entity_type`` / ``entity_id`` 给定时额外带出该实体的结构事件对象（``teaching_structure``）。
    不给 = 只要市场级那批，与改动前逐字节一致。
    """
    path = Path(labels_db).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"教学框架旁路库不存在: {path}（先跑 scripts/teaching_framework.py build-labels）")
    day = _date(as_of)
    con = open_labels_db(path, read_only=True)
    try:
        _require_pit_column(con)
        out: list[RiverObject] = []
        narrative = _labels_object(con, day, as_of, labels=NARRATIVE_LABELS, object_type="teaching_narrative", suffix="narrative")
        briefing = _labels_object(con, day, as_of, labels=BRIEFING_LABELS, object_type="teaching_briefing", suffix="briefing")
        extra: dict[str, Any] = {}
        for (gap_key, gap_kind), obj in zip(_SOURCE_GAPS, (narrative, briefing), strict=True):
            if obj is None:
                reason = _gap_reason(con, day, gap_kind)
                if reason:
                    extra[gap_key] = reason
        stage = _stage_object(con, day, as_of, extra=extra)
        if stage is not None:
            out.append(stage)
        capital = _capital_object(con, day, as_of)
        if capital is not None:
            out.append(capital)
        breadth = _labels_object(con, day, as_of, labels=BREADTH_LABELS, object_type="teaching_breadth", suffix="breadth")
        if breadth is not None:
            out.append(breadth)
        cycle = _labels_object(con, day, as_of, labels=CYCLE_LABELS, object_type="teaching_cycle", suffix="cycle")
        if cycle is not None:
            out.append(cycle)
        if narrative is not None:
            out.append(narrative)
        if briefing is not None:
            out.append(briefing)
        dynasty = _dynasty_object(con, day, as_of, top=top)
        if dynasty is not None:
            out.append(dynasty)
        leaders = _range_leaders_object(con, day, as_of, top=top)
        if leaders is not None:
            out.append(leaders)
        if entity_type is not None and entity_id is not None:
            structure = _structure_object(con, day, as_of, entity_type=entity_type, entity_id=entity_id)
            if structure is not None:
                out.append(structure)
            if entity_type == "sector":
                role = _sector_role_object(con, day, as_of, entity_id=entity_id)
                if role is not None:
                    out.append(role)
        return out
    finally:
        con.close()



def _earliest_known_values(stamps: list[Any]) -> Any:
    """一组 ``first_known_at`` → 这个对象最早可知的时刻。

    **取 max 而不是 min**:对象是多条标签打包成的一个整体,要到**最晚的那条**也可知之后,
    整个对象才算可知。取 min 会让对象声称自己比其中某条成分更早可知。

    任何一条是 NULL ⇒ 整个对象返回 ``None`` ⇒ 河的 PIT 闸 fail-closed 把它滤掉。
    「这条读数没有可知时间证据」和「它那天已知」是两回事,不能混。
    """

    if not stamps:
        return None
    if any(x is None for x in stamps):
        return None
    return max(stamps)


def _earliest_known(rows: list[Mapping[str, Any]]) -> Any:
    return _earliest_known_values([r["first_known_at"] for r in rows])


def _stage_object(con: Any, day: date, as_of: str, extra: Mapping[str, Any] | None = None) -> RiverObject | None:
    if not _has_table(con, "history_teaching_labels"):
        return None
    rows = _rows(
        con,
        f"""SELECT label, value_num, value_text, framework_version, first_known_at FROM history_teaching_labels
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
        computed.append(r["first_known_at"])
    payload["framework_version"] = sorted(versions)[0] if len(versions) == 1 else sorted(versions)
    payload.update(dict(extra or {}))
    hashed = {k: v for k, v in payload.items()}
    return RiverObject(
        track="market", entity_id="__market__", object_type="teaching_stage",
        ref=f"history_teaching_labels:{as_of}:market", source_hash=_hash(hashed),
        valid_from=as_of, recorded_at=_ts(_earliest_known_values(computed)), payload=payload,
    )


def _labels_object(con: Any, day: date, as_of: str, *, labels: tuple[str, ...], object_type: str, suffix: str) -> RiverObject | None:
    """一组市场级数值标签 → 一个对象，只搬不解释；全 NULL 的日子没有这个对象。"""
    if not _has_table(con, "history_teaching_labels"):
        return None
    rows = _rows(
        con,
        f"""SELECT label, value_num, framework_version, first_known_at FROM history_teaching_labels
            WHERE entity_type = 'market' AND entity_id = 'market' AND status = 'ok' AND trade_date = ?
              AND label IN ({", ".join("?" for _ in labels)}) AND value_num IS NOT NULL
            ORDER BY label""",
        [day, *labels],
    )
    if not rows:
        return None
    payload: dict[str, Any] = {str(r["label"]).removeprefix("tf."): r["value_num"] for r in rows}
    payload["framework_version"] = sorted({str(r["framework_version"]) for r in rows})[0]
    return RiverObject(
        track="market", entity_id="__market__", object_type=object_type,
        ref=f"history_teaching_labels:{as_of}:market:{suffix}", source_hash=_hash(payload),
        valid_from=as_of, recorded_at=_ts(_earliest_known(rows)), payload=payload,
    )


# 实体级结构事件：板块 / 个股层的 MACD 背离。
# 与上面所有标签组不同——这组**不是市场级**，每行挂在一个具体 entity_id 上，
# 所以它进的是切片自己那个实体的轨（板块 → theme），不是 ``__market__``。
# scripts/teaching_framework.py:1309 STRUCTURE_ENTITY_LABELS 是同一份名单的 SSOT 对侧。
_SECTOR_LABELS_SSOT: tuple[str, ...]
from intelligence.services.teaching_framework.sector_roles import SECTOR_LABELS as _SECTOR_LABELS_SSOT  # noqa: E402

STRUCTURE_LABELS = (
    "tf.macd_bottom_div_observe", "tf.macd_bottom_div_confirm",
    "tf.macd_bottom_div_failed", "tf.macd_top_div",
)


# 板块角色（C 类，sector_roles.SECTOR_LABELS）：量板块 / 价板块 / 锐度 / RPS / 双红 /
# 赚钱效应五种口径并列保留。
# 名单从 sector_roles 推导而不是手抄——手抄一份四元组导致「两处同名不同物」是本仓踩过的坑。
#
# 刻意剔除 ``mainline_volume_top3``：它在 sector_roles:265 就是 ``role_volume_top3`` 的别名，
# 而这个名字在**市场级**已经被 CYCLE_LABELS 占了（含义不同）。同名不同物正是上面那个坑，
# 搬别名零收益、却要付命名空间碰撞的代价，所以搬 role_volume_top3 就够了。
SECTOR_ROLE_LABELS: tuple[str, ...] = tuple(
    f"tf.{name}" for name in _SECTOR_LABELS_SSOT if name != "mainline_volume_top3"
)


def _entity_labels_object(
    con: Any, day: date, as_of: str, *, entity_type: str, entity_id: str,
    labels: tuple[str, ...], object_type: str, suffix: str, with_text: bool = False,
) -> RiverObject | None:
    """一组**实体级**标签 → 一个对象。与 ``_labels_object`` 的区别只在实体不是 ``market``。"""
    if not _has_table(con, "history_teaching_labels"):
        return None
    rows = _rows(
        con,
        f"""SELECT label, value_num, value_text, framework_version, first_known_at FROM history_teaching_labels
            WHERE entity_type = ? AND entity_id = ? AND status = 'ok' AND trade_date = ?
              AND label IN ({", ".join("?" for _ in labels)}) AND value_num IS NOT NULL
            ORDER BY label""",
        [entity_type, entity_id, day, *labels],
    )
    if not rows:
        return None
    payload: dict[str, Any] = {str(r["label"]).removeprefix("tf."): r["value_num"] for r in rows}
    if with_text:
        anchors = {
            str(r["label"]).removeprefix("tf."): str(r["value_text"]) for r in rows if r["value_text"] is not None
        }
        if anchors:
            payload["anchor_days"] = anchors
    payload["framework_version"] = sorted({str(r["framework_version"]) for r in rows})[0]
    return RiverObject(
        track="theme" if entity_type == "sector" else "stock", entity_id=entity_id,
        object_type=object_type,
        ref=f"history_teaching_labels:{as_of}:{entity_type}:{entity_id}:{suffix}",
        source_hash=_hash(payload), valid_from=as_of,
        recorded_at=_ts(_earliest_known(rows)), payload=payload,
    )


def _structure_object(con: Any, day: date, as_of: str, *, entity_type: str, entity_id: str) -> RiverObject | None:
    """某个板块 / 个股当日的 MACD 背离事件 → 一个对象，只搬不解释。

    **只落事件日**（``scripts/teaching_framework.py:1316``）：``value_num`` 恒为 1.0，
    ``value_text`` 是锚点日（事件指向的极值日）。没事件的日子根本没有行，
    所以这里返回 None —— 判定路径会当 unknown，不当「没背离」。
    这两件事在读数上长得一样，混起来就是 ``rules.text_domain_error`` 那句
    「『从未成立』与『今天没成立』在读数上长得一样」的同一个坑。
    """
    return _entity_labels_object(
        con, day, as_of, entity_type=entity_type, entity_id=entity_id,
        labels=STRUCTURE_LABELS, object_type="teaching_structure", suffix="structure", with_text=True,
    )


def _sector_role_object(con: Any, day: date, as_of: str, *, entity_id: str) -> RiverObject | None:
    """某个板块当日的角色标签（量板块 / 价板块 / 锐度 / RPS / 双红 / 赚钱效应）。

    与结构事件不同，角色标签是**逐日全量**的：板块在就有行，不在就是真的没算出来
    （``sector_roles`` 全程 fail-closed，窗口不全或输入 NULL 一律给 NULL，不补零）。
    """
    return _entity_labels_object(
        con, day, as_of, entity_type="sector", entity_id=entity_id,
        labels=SECTOR_ROLE_LABELS, object_type="teaching_sector_role", suffix="sector_role",
    )


def _gap_reason(con: Any, day: date, gap_kind: str) -> str | None:
    if not _has_table(con, "history_teaching_gaps"):
        return None
    row = con.execute(
        "SELECT status_reason FROM history_teaching_gaps WHERE trade_date = ? AND gap_kind = ? LIMIT 1", [day, gap_kind]
    ).fetchone()
    return None if row is None or row[0] is None else str(row[0])


def _capital_object(con: Any, day: date, as_of: str) -> RiverObject | None:
    """资金面当日读数（龙虎榜 / 封单 / 竞价 / 成交占比）。"""
    return _labels_object(con, day, as_of, labels=CAPITAL_LABELS, object_type="teaching_capital", suffix="capital")


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
    # 局限：history_dynasties 还没有 first_known_at 列，这里仍是 computed_at，
    # 也就是「最后一次重算是什么时候」。王朝本来就是**事后对象**（要两波都走完才能回溯
    # 衔接），它在历史切片上不可见是正确的，所以没有顺手给它加列。真要让它有 PIT 身份，
    # 得先定义「王朝在哪一天才算可知」——那是口径问题，不是字段问题。
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
        # 局限：history_range_leaders 同样还没有 first_known_at 列。区间高标是当日横截面排名，
        # 机制上应当前缀稳定，但补证包的前缀检查没覆盖它 —— 没有证据就不声称，保持 computed_at。
        recorded_at=_ts(max(r["computed_at"] for r in rows)), payload=payload,
    )
