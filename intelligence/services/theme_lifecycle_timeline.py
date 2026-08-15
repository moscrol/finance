"""题材生命周期时间线回放：从盘面逐日行派生「酝酿→首发→发酵→主升→分歧→退潮→回流」。

⚠️ 与既有 `theme_lifecycle.py`（P1 题材生命周期**诊断**，八阶段）的分工——两者互补不重复：
    - `theme_lifecycle.py`：答「市场**现在**把这个题材交易到哪一段」。输入是证据侧信号 +
      market_structure 状态机，输出交易叙事段（新出现/旧逻辑唤醒/升温验证/…/证伪退出）
      + 市场奖励谁/抛弃谁，已接进 ask/agent 运行时。
    - 本模块：答「这个题材**历史上**怎么走过来的」。输入是 DuckDB 盘面逐日行（+可选
      消息面日期），输出可回放的**盘面结构段**时间线（严格双红口径），每段带触发条件。
      两套阶段词表口径不同（交易叙事 vs 盘面结构），引用时须标明来源模块，不得混用。

背景（为什么要这个模块）：
    theme-radar 给当前快照、fermentation-tracer 给发酵链路回溯、theme_lifecycle 给当前
    阶段诊断，但没有模块把「历史上阶段怎么切换的」作为可回放时间线取出来。本模块补上
    这块（2026-08-13 memory-analog-lifecycle 设计稿 §5，slice 3）。

设计（事件日志 + 派生阶段，不落库状态机）：
    - **阶段是派生态不是落库态**：只依赖库内逐日行 + 可选消息面事件日期，同一套
      规则可对任何历史区间重放；规则演进时历史阶段自动跟着修正，不会漂。
    - **确定性规则**（全部参数化，非 LLM 判定）：
        酝酿  消息面已有证据/认知跃迁，盘面无首板无双红（无消息面数据则显式缺口）
        首发  题材首次出现涨停/首板
        发酵  题材板块双红（pct>0 & diff_ratio>10 & amount>500，严格口径）
        主升  连续双红 ≥3 且连板高度较本轮发酵起点抬升（高度数据缺失则放宽并声明）
        分歧  发酵/主升中放量（本轮成交额新高）但边际转负（diff_ratio ≤ 0）
        退潮  双红消失连续 ≥5 日（起点回溯到断红首日）
        回流  退潮后再现双红（跑马策略关注的「回流后再分歧」窗口入口）
    - 允许多轮循环（退潮→回流→主升→…），每段带触发条件说明，可审计。
    - 缺数（库不可用/题材无行/消息面缺失/连板数据缺失）显式声明，禁止臆补。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from intelligence.paths import default_market_db_path
from intelligence.services import retrieval_cache

DEFAULT_MARKET_DB_PATH = default_market_db_path()

# 严格双红口径（与 strategy1-matrix / D8 一致）
DOUBLE_RED_PCT = 0.0
DOUBLE_RED_DIFF = 10.0
DOUBLE_RED_AMOUNT = 500.0

MAINUP_CONSECUTIVE = 3   # 主升：连续双红天数下限
EBB_BREAK_DAYS = 5       # 退潮：连续无双红天数下限
# 回流滞回（slice 3.1）：退潮中出现双红须连续 ≥N 日才确认回流，孤立单日双红不切段。
# live 实测（2026-08-13，固态电池 53 段/信创 65 段）：无滞回时真实双红闪烁把时间线切成锯齿。
REFLOW_CONFIRM_DAYS = 2
# 最短阶段时长（Q8，bookgap S8）：滞回只消回流抖动，<N 日切段仍把时间线切碎。
# 与滞回正交——派生完成后再合并，不改状态机。设 1 即关闭合并。
MIN_PHASE_DAYS = 3

STAGE_INCUBATION = "酝酿"
STAGE_FIRST_MOVE = "首发"
STAGE_FERMENT = "发酵"
STAGE_MAIN_UP = "主升"
STAGE_DIVERGENCE = "分歧"
STAGE_EBB = "退潮"
STAGE_REFLOW = "回流"


def is_double_red(row: dict[str, Any]) -> bool:
    pct, diff, amount = row.get("pct_chg"), row.get("diff_ratio"), row.get("amount")
    if pct is None or diff is None or amount is None:
        return False
    return (
        float(pct) > DOUBLE_RED_PCT
        and float(diff) > DOUBLE_RED_DIFF
        and float(amount) > DOUBLE_RED_AMOUNT
    )


@dataclass
class StageSegment:
    stage: str
    start_date: str
    end_date: str
    trigger: str

    def to_payload(self) -> dict[str, str]:
        return {
            "stage": self.stage,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "trigger": self.trigger,
        }


@dataclass(frozen=True)
class ThemeTimelineArtifact:
    theme: str
    segments: tuple[StageSegment, ...]
    gaps: tuple[str, ...]
    params: dict[str, Any] = field(default_factory=dict)
    degrade_reason: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.segments)

    @property
    def current_stage(self) -> str | None:
        return self.segments[-1].stage if self.segments else None

    def to_payload(self) -> dict[str, object]:
        return {
            "theme": self.theme,
            "available": self.available,
            "current_stage": self.current_stage,
            "segments": [s.to_payload() for s in self.segments],
            "gaps": list(self.gaps),
            "params": dict(self.params),
            "degrade_reason": self.degrade_reason,
        }


def segment_calendar_days(seg: StageSegment) -> int:
    """段时长：起止日含首尾的日历天数。同日段 = 1。"""
    start = date.fromisoformat(str(seg.start_date)[:10])
    end = date.fromisoformat(str(seg.end_date)[:10])
    return (end - start).days + 1


def merge_short_phases(
    segments: list[StageSegment],
    min_phase_days: int = MIN_PHASE_DAYS,
) -> tuple[list[StageSegment], list[StageSegment]]:
    """把短于 ``min_phase_days`` 的切段并入邻段（Q8）。

    与滞回正交：只做派生后的后处理。规则：
    - ``min_phase_days <= 1`` 关闭合并（与 ``reflow_confirm_days=1`` 同形）；
    - 短段优先并入前一段（保留前段阶段名）；首段过短则并入后一段；
    - 合并后相邻同名段再粘合，避免「退潮-短回流-退潮」拆成两段退潮；
    - 整条时间线短于阈值时无法再并，短段保留（数据跨度限制，不臆造天数）。
    返回 ``(合并后段落, 被吸收的原短段清单)``。
    """
    if min_phase_days <= 1 or len(segments) <= 1:
        return list(segments), []

    absorbed: list[StageSegment] = []
    segs = list(segments)

    def _coalesce(items: list[StageSegment]) -> list[StageSegment]:
        if not items:
            return []
        out = [items[0]]
        for item in items[1:]:
            prev = out[-1]
            if item.stage == prev.stage:
                out[-1] = StageSegment(
                    prev.stage,
                    prev.start_date,
                    item.end_date if item.end_date > prev.end_date else prev.end_date,
                    prev.trigger,
                )
            else:
                out.append(item)
        return out

    changed = True
    while changed:
        changed = False
        segs = _coalesce(segs)
        i = 0
        while i < len(segs):
            if segment_calendar_days(segs[i]) >= min_phase_days:
                i += 1
                continue
            short = segs[i]
            if i > 0:
                prev = segs[i - 1]
                segs[i - 1] = StageSegment(
                    prev.stage,
                    prev.start_date,
                    short.end_date if short.end_date > prev.end_date else prev.end_date,
                    f"{prev.trigger}；合并短于{min_phase_days}日的「{short.stage}」"
                    f"{short.start_date}~{short.end_date}",
                )
                del segs[i]
                absorbed.append(short)
                changed = True
                segs = _coalesce(segs)
                i = max(i - 1, 0)
            elif i + 1 < len(segs):
                nxt = segs[i + 1]
                segs[i + 1] = StageSegment(
                    nxt.stage,
                    short.start_date if short.start_date < nxt.start_date else nxt.start_date,
                    nxt.end_date,
                    f"{nxt.trigger}；合并短于{min_phase_days}日的「{short.stage}」"
                    f"{short.start_date}~{short.end_date}",
                )
                del segs[i]
                absorbed.append(short)
                changed = True
                segs = _coalesce(segs)
            else:
                i += 1
    return segs, absorbed


def derive_stages(
    rows: list[dict[str, Any]],
    message_dates: tuple[str, ...] = (),
    mainup_consecutive: int = MAINUP_CONSECUTIVE,
    ebb_break_days: int = EBB_BREAK_DAYS,
    reflow_confirm_days: int = REFLOW_CONFIRM_DAYS,
    min_phase_days: int = MIN_PHASE_DAYS,
) -> tuple[list[StageSegment], list[str]]:
    """从升序逐日行派生阶段段落。rows 每行至少含：

        trade_date, pct_chg, diff_ratio, amount,
        limit_up_count（题材涨停数，可空）, first_board_count（首板数，可空）,
        max_boards（题材连板最高度，可空）

    message_dates：消息面事件日（证据/认知跃迁），仅用于酝酿段；为空则声明缺口。
    reflow_confirm_days：回流滞回——退潮中须连续 ≥N 日双红才确认回流（起点回溯
    确认串首日）；设 1 即关闭滞回。
    min_phase_days：最短阶段时长，派生后再合并短于 N 日的切段（与滞回正交；
    设 1 关闭）。返回（阶段段落列表, 缺口声明列表）。
    全程确定性规则，可对任意区间重放。
    """
    gaps: list[str] = []
    if not rows:
        return [], ["题材无盘面逐日行，无法判定生命周期"]

    has_boards = any(r.get("max_boards") is not None for r in rows)
    if not has_boards:
        gaps.append("连板高度数据缺失：主升判定放宽为仅「连续双红 ≥%d」" % mainup_consecutive)
    if not message_dates:
        gaps.append("消息面事件缺失：酝酿段无法判定（需知识库 evidence/认知跃迁日期）")

    # 首个盘面信号日：首板/涨停/双红任一
    first_signal_idx: int | None = None
    for i, r in enumerate(rows):
        limit_up = r.get("limit_up_count")
        first_board = r.get("first_board_count")
        if (
            (limit_up is not None and float(limit_up) > 0)
            or (first_board is not None and float(first_board) > 0)
            or is_double_red(r)
        ):
            first_signal_idx = i
            break
    if first_signal_idx is None:
        return [], gaps + ["区间内无首板/涨停/双红信号，题材未进入盘面生命周期"]

    segments: list[StageSegment] = []
    first_signal_date = str(rows[first_signal_idx]["trade_date"])

    # 酝酿段：消息面事件早于首个盘面信号
    pre_dates = sorted(d for d in message_dates if d < first_signal_date)
    if pre_dates:
        segments.append(
            StageSegment(
                STAGE_INCUBATION,
                pre_dates[0],
                pre_dates[-1],
                f"消息面事件 {len(pre_dates)} 起早于首个盘面信号（{first_signal_date}）",
            )
        )

    stage: str | None = None
    stage_start: str | None = None
    stage_trigger = ""
    consecutive_dr = 0
    break_run = 0
    break_start: str | None = None
    dr_run_start: str | None = None       # 当前双红连串的首日（回流起点回溯用）
    dr_run_prev_date: str | None = None   # 双红连串首日的前一交易日（关闭上一段用）
    cycle_amount_max: float | None = None
    boards_at_ferment: float | None = None

    def close_segment(end_date: str) -> None:
        nonlocal stage, stage_start
        if stage is not None and stage_start is not None:
            segments.append(StageSegment(stage, stage_start, end_date, stage_trigger))

    def open_segment(new_stage: str, start: str, trigger: str, prev_end: str) -> None:
        nonlocal stage, stage_start, stage_trigger
        if stage == new_stage:
            return
        close_segment(prev_end)
        stage, stage_start, stage_trigger = new_stage, start, trigger

    prev_date = first_signal_date
    for r in rows[first_signal_idx:]:
        day = str(r["trade_date"])
        dr = is_double_red(r)
        amount = r.get("amount")
        boards = r.get("max_boards")

        if stage is None:
            limit_up = r.get("limit_up_count")
            first_board = r.get("first_board_count")
            if (limit_up is not None and float(limit_up) > 0) or (
                first_board is not None and float(first_board) > 0
            ):
                open_segment(STAGE_FIRST_MOVE, day, "题材首次出现涨停/首板", prev_date)

        if dr:
            consecutive_dr += 1
            if consecutive_dr == 1:
                dr_run_start = day
                dr_run_prev_date = prev_date
            break_run = 0
            break_start = None
            if amount is not None:
                cycle_amount_max = (
                    float(amount)
                    if cycle_amount_max is None
                    else max(cycle_amount_max, float(amount))
                )
            if stage in (None, STAGE_FIRST_MOVE):
                boards_at_ferment = float(boards) if boards is not None else None
                cycle_amount_max = float(amount) if amount is not None else None
                open_segment(
                    STAGE_FERMENT, day,
                    f"板块双红（pct>{DOUBLE_RED_PCT:g} & diff>{DOUBLE_RED_DIFF:g} & amount>{DOUBLE_RED_AMOUNT:g}）",
                    prev_date,
                )
            elif stage == STAGE_EBB and consecutive_dr >= reflow_confirm_days:
                # 滞回：孤立单日双红不切段；确认后起点回溯到连串首日
                open_segment(
                    STAGE_REFLOW,
                    dr_run_start or day,
                    f"退潮后连续 {reflow_confirm_days} 日双红确认回流（起点回溯确认串首日）"
                    if reflow_confirm_days > 1
                    else "退潮后再现双红",
                    dr_run_prev_date or prev_date,
                )
            elif stage == STAGE_DIVERGENCE:
                open_segment(STAGE_FERMENT, day, "分歧后双红修复", prev_date)
            if stage in (STAGE_FERMENT, STAGE_REFLOW) and consecutive_dr >= mainup_consecutive:
                boards_lift = (
                    True
                    if (boards is None or boards_at_ferment is None)
                    else float(boards) > boards_at_ferment
                )
                if boards_lift:
                    lift_note = (
                        "（连板高度数据缺失，抬升条件放宽）"
                        if boards is None or boards_at_ferment is None
                        else f"（连板高度 {boards_at_ferment:g}→{float(boards):g}）"
                    )
                    open_segment(
                        STAGE_MAIN_UP, day,
                        f"连续双红 ≥{mainup_consecutive} 且高度抬升{lift_note}",
                        prev_date,
                    )
        else:
            consecutive_dr = 0
            if stage in (STAGE_FERMENT, STAGE_MAIN_UP, STAGE_DIVERGENCE, STAGE_REFLOW):
                if break_run == 0:
                    break_start = day
                break_run += 1
                diff = r.get("diff_ratio")
                if (
                    stage in (STAGE_FERMENT, STAGE_MAIN_UP)
                    and amount is not None
                    and cycle_amount_max is not None
                    and float(amount) >= cycle_amount_max
                    and diff is not None
                    and float(diff) <= 0
                ):
                    open_segment(
                        STAGE_DIVERGENCE, day,
                        "放量（本轮成交额新高）但边际转负（diff_ratio ≤ 0）",
                        prev_date,
                    )
                    cycle_amount_max = max(cycle_amount_max, float(amount))
                if break_run >= ebb_break_days and stage != STAGE_EBB:
                    open_segment(
                        STAGE_EBB, break_start or day,
                        f"连续 {ebb_break_days} 日无双红（起点回溯断红首日）",
                        break_start or day,
                    )
                    cycle_amount_max = None
                    boards_at_ferment = None
        prev_date = day

    close_segment(prev_date)
    segments, absorbed = merge_short_phases(segments, min_phase_days)
    if absorbed:
        merged = "、".join(
            f"{item.stage}{item.start_date}~{item.end_date}" for item in absorbed
        )
        gaps.append(
            f"最短阶段合并：吸收 {len(absorbed)} 段短于 {min_phase_days} 日的切段（{merged}）"
        )
    return segments, gaps


# ---------------------------------------------------------------------------
# 取数层：从主库拼题材逐日行；消息面事件从知识库 theme_signals.json 取（可选）。
# ---------------------------------------------------------------------------


def load_theme_daily_rows(con: Any, theme: str) -> list[dict[str, Any]]:
    """题材逐日行：fact_sector_daily 为主轴，涨停热度/连板高度左连（缺表→维度为空）。"""
    base = con.execute(
        """
        select trade_date, pct_chg, diff_ratio, amount
        from fact_sector_daily
        where sector_name = ?
        order by trade_date asc
        """,
        [theme],
    ).fetchall()
    if not base:
        return []
    heat: dict[str, tuple[float | None, float | None]] = {}
    try:
        for r in con.execute(
            "select trade_date, max(limit_up_count), max(market_share) "
            "from fact_theme_limit_heat_daily where sector_name = ? group by trade_date",
            [theme],
        ).fetchall():
            heat[str(r[0])] = (r[1], r[2])
    except Exception:
        heat = {}
    boards: dict[str, tuple[float | None, float | None]] = {}
    try:
        for r in con.execute(
            "select trade_date, max(boards), "
            "sum(case when boards = 1 then 1 else 0 end) "
            "from fact_limit_advance_daily where theme like ? group by trade_date",
            [f"%{theme}%"],
        ).fetchall():
            boards[str(r[0])] = (r[1], r[2])
    except Exception:
        boards = {}
    rows: list[dict[str, Any]] = []
    for r in base:
        day = str(r[0])
        h = heat.get(day, (None, None))
        b = boards.get(day, (None, None))
        rows.append(
            {
                "trade_date": day,
                "pct_chg": r[1],
                "diff_ratio": r[2],
                "amount": r[3],
                "limit_up_count": h[0],
                "market_share": h[1],
                "max_boards": b[0],
                "first_board_count": b[1],
            }
        )
    return rows


def resolve_theme_alias(con: Any, theme: str) -> str | None:
    """板块口语名 → ``fact_sector_daily.sector_name``（Q7，bookgap S8）。

    08-13 live 实测：「液冷 / AI概念」这类口语名对不上库内 sector_name，
    时间线只能显式降级。别名解析**复用**既有 ``resolve_query_themes``
    （子串 + 锚定宽松匹配，收敛到板块表已存在的口径），不另建硬编码别名表。
    解析不到返回 None——调用方保持显式降级，禁止臆配。
    """
    from intelligence.services.market_midterm import resolve_query_themes

    candidates = resolve_query_themes(con, theme, limit=1)
    if candidates and candidates[0] != theme:
        return candidates[0]
    return None


def load_message_dates(kb_vault: str | Path | None, theme: str) -> tuple[str, ...]:
    """从知识库 theme_signals.json 取该题材认知跃迁日期（缺库/缺字段→空元组）。"""
    if not kb_vault:
        return ()
    path = Path(kb_vault).expanduser() / "wiki" / "relations" / "theme_signals.json"
    if not path.exists():
        return ()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ()
    theme_obj = (data.get("themes") or {}).get(theme) or {}
    dates = []
    for rec in theme_obj.get("recognition_timeline") or []:
        d = str(rec.get("date") or "").strip()
        if d:
            dates.append(d)
    return tuple(sorted(set(dates)))


def load_theme_timeline_artifact(
    theme: str,
    market_db_path: str | Path | None = None,
    kb_vault: str | Path | None = None,
    mainup_consecutive: int = MAINUP_CONSECUTIVE,
    ebb_break_days: int = EBB_BREAK_DAYS,
    reflow_confirm_days: int = REFLOW_CONFIRM_DAYS,
    min_phase_days: int = MIN_PHASE_DAYS,
) -> ThemeTimelineArtifact:
    params = {
        "mainup_consecutive": mainup_consecutive,
        "ebb_break_days": ebb_break_days,
        "reflow_confirm_days": reflow_confirm_days,
        "min_phase_days": min_phase_days,
        "double_red": f"pct>{DOUBLE_RED_PCT:g} & diff>{DOUBLE_RED_DIFF:g} & amount>{DOUBLE_RED_AMOUNT:g}",
    }
    db_path = (
        Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    )
    if not db_path.exists():
        return ThemeTimelineArtifact(
            theme, (), (), params, degrade_reason="生命周期判定库不存在"
        )
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return ThemeTimelineArtifact(
            theme, (), (), params, degrade_reason="生命周期判定库不可读"
        )
    con = db_result.connection
    try:
        rows = load_theme_daily_rows(con, theme)
        if not rows:
            # Q7：口语名对不上 sector_name 时先走别名解析（resolve_query_themes），
            # 解析不到仍显式降级——只收敛盘面取数入口，阶段算法与 KB 消息面
            # 查询口径（按用户原名）都不动。
            resolved = resolve_theme_alias(con, theme)
            if resolved is not None:
                rows = load_theme_daily_rows(con, resolved)
                if rows:
                    params["resolved_sector_name"] = resolved
        if not rows:
            return ThemeTimelineArtifact(
                theme, (), (), params,
                degrade_reason=(
                    f"fact_sector_daily 无「{theme}」逐日行"
                    "（别名解析 resolve_query_themes 也未命中）"
                ),
            )
        message_dates = load_message_dates(kb_vault, theme)
        segments, gaps = derive_stages(
            rows,
            message_dates=message_dates,
            mainup_consecutive=mainup_consecutive,
            ebb_break_days=ebb_break_days,
            reflow_confirm_days=reflow_confirm_days,
            min_phase_days=min_phase_days,
        )
        if not segments:
            return ThemeTimelineArtifact(
                theme, (), tuple(gaps), params,
                degrade_reason="区间内无盘面生命周期信号",
            )
        return ThemeTimelineArtifact(theme, tuple(segments), tuple(gaps), params)
    except Exception:
        return ThemeTimelineArtifact(
            theme, (), (), params, degrade_reason="生命周期判定查询失败"
        )
    finally:
        try:
            con.close()
        except Exception:
            pass


def lifecycle_markdown(artifact: ThemeTimelineArtifact) -> str:
    """渲染成 markdown 时间线（确定性判定，可回放；空串=未取到）。"""
    if not artifact.available:
        return ""
    lines = [f"## 题材生命周期：{artifact.theme}（确定性判定，可回放）"]
    lines.append(
        f"- 口径：{artifact.params.get('double_red')}；主升=连续双红 ≥"
        f"{artifact.params.get('mainup_consecutive')} 且高度抬升；退潮=连续 "
        f"{artifact.params.get('ebb_break_days')} 日无双红；回流=退潮后连续 "
        f"{artifact.params.get('reflow_confirm_days')} 日双红确认（滞回，孤立单日不切段）；"
        f"短于 {artifact.params.get('min_phase_days')} 日的切段并入邻段（与滞回正交）。"
        "阶段由库内逐日行按规则派生，非 LLM 生成；规则版本变更时历史阶段自动重算。"
    )
    resolved = artifact.params.get("resolved_sector_name")
    if resolved:
        lines.append(
            f"- 板块别名：「{artifact.theme}」按 sector_name「{resolved}」取数"
            "（resolve_query_themes 解析）。"
        )
    for gap in artifact.gaps:
        lines.append(f"- 数据缺口：{gap}。")
    lines.append(f"- **当前阶段：{artifact.current_stage}**")
    lines.append("")
    lines.append("| 阶段 | 起止 | 触发条件 |")
    lines.append("|---|---|---|")
    for seg in artifact.segments:
        span = seg.start_date if seg.start_date == seg.end_date else f"{seg.start_date}~{seg.end_date}"
        lines.append(f"| {seg.stage} | {span} | {seg.trigger} |")
    lines.append("")
    lines.append(
        "- 使用要求：阶段是**盘面结构的派生标签，不是预测**；「回流」不承诺再分歧前"
        "有退出机会，须结合当时消息面与容量核对。消息面维度缺失时酝酿段缺席，禁止臆补。"
    )
    return "\n".join(lines)


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="题材生命周期时间线回放（只读）")
    parser.add_argument(
        "--theme", required=True,
        help="题材名（fact_sector_daily.sector_name；口语别名会经 resolve_query_themes 解析）",
    )
    parser.add_argument("--db", default=None, help="DuckDB 路径（默认主库）")
    parser.add_argument("--kb-vault", default=None, help="知识库 vault 路径（可选，供酝酿段）")
    parser.add_argument(
        "--reflow-confirm", type=int, default=REFLOW_CONFIRM_DAYS,
        help="回流滞回确认天数（默认 %(default)s；设 1 关闭滞回）",
    )
    parser.add_argument(
        "--min-phase-days", type=int, default=MIN_PHASE_DAYS,
        help="最短阶段时长（默认 %(default)s；设 1 关闭短段合并）",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON payload")
    args = parser.parse_args()
    artifact = load_theme_timeline_artifact(
        args.theme, market_db_path=args.db, kb_vault=args.kb_vault,
        reflow_confirm_days=args.reflow_confirm,
        min_phase_days=args.min_phase_days,
    )
    if args.json:
        print(json.dumps(artifact.to_payload(), ensure_ascii=False, indent=2))
    else:
        text = lifecycle_markdown(artifact)
        print(text if text else f"未取到：{artifact.degrade_reason or '无数据'}")
    return 0 if artifact.available else 2


if __name__ == "__main__":
    raise SystemExit(_main())
