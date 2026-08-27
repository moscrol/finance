"""台阶轨迹 + 资格判断组件：Engine A 开口预取（视角判据组件化第一批）。

Spec: docs/superpowers/specs/2026-08-25-step-trajectory-qualification-design.md
live 对照实锤（run_20260825_113538）：同题预取仅 1 件（替补池），
「大盘资格盘」「板块近5日台阶」两口锅不在桌上（R-20260825-09/-10）。

冻结口径（spec §3）：
- 20 日均额窗口 = 截至站立日**含当日**（真库 23110.8 对上 live 探针 23111，
  不含当日 23145.4 对不上）→ 夹具数字构造成 incl/excl 可区分，变异必红。
- 「科技」经宽松匹配会臆配「量子科技」（词面近邻 ≠ 语义家族，
  R-20260825-11）→ 解析梯 fail closed，量子科技不得上桌。
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb

from intelligence.services.asof_prefetch import (
    QUALIFICATION_TITLE,
    TRAJECTORY_TITLE_SUFFIX,
    UNANCHORED_TRAJECTORY_TITLE,
    collect_prefetch_items,
)
from intelligence.services.query_understanding import (
    SIGNAL_STEP_TRAJECTORY,
    surface_research_signals,
)
from intelligence.services.research_contract import (
    OPERATOR_STEP_TRAJECTORY,
    OPERATOR_VOLUME_QUALIFICATION,
    compile_research_program,
)

# live 对照冻结题（~/.finance-runtime/live-vs-workbench-20260825/）
Q_OUTLOOK = "站在spt视角下，科技和医药板块接下来的走势怎么看，需要观察哪些个股的反馈"
Q_YSJS = "用spt的视角，分析下有色金属板块后续的走势，以及板块内有机会的个股有哪些"
Q_STAGE = "用spt的视角，回答下当前科技处于什么阶段，和之前哪一段的科技行情比较类似，个股怎么对标"
Q_FERMENT = "医药板块这波怎么发酵的，接下来的走势怎么看"

STANDING = date(2026, 7, 23)

# 5 个交易日窗口（fact_sector_daily 的 distinct 日期）
D1, D2, D3, D4, D5 = "2026-07-17", "2026-07-20", "2026-07-21", "2026-07-22", "2026-07-23"


def _db(tmp_path: Path, *, prior_market_days: int = 24, future_row: bool = True) -> Path:
    """标准夹具。

    市场行：prior_market_days 行 23000 + 站立日 20000（+可选 07-24 泄漏探测行
    99999）。prior=24 时含当日 20 日窗均额 = (20000+19×23000)/20 = 22850.0，
    不含当日 = 23000.0 —— 「含当日」变异可区分。
    """

    path = tmp_path / "prefetch.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "create table fact_market_daily(trade_date date, market_stage varchar,"
        " stage_day integer, total_amount double, amount_vs_yesterday_pct double,"
        " volume_state varchar, limit_up integer, limit_down integer,"
        " sh_index_pct_chg double)"
    )
    day = date(2026, 7, 22)
    rows = []
    for _ in range(prior_market_days):
        rows.append(f"('{day.isoformat()}', '底部横盘阶段', 1, 23000, 0, '正常量能', 50, 1, 0.1)")
        day -= timedelta(days=1)
    rows.append("('2026-07-23', '底部横盘阶段', 19, 20000, 6.82, '正常量能', 60, 2, 0.2)")
    if future_row:
        rows.append("('2026-07-24', '底部横盘阶段', 20, 99999, 400, '放量', 90, 0, 2.0)")
    con.execute("insert into fact_market_daily values " + ", ".join(rows))

    con.execute(
        "create table fact_sector_daily(trade_date date, sector_name varchar,"
        " pct_chg double, diff_ratio double, amount double)"
    )
    sector_rows = [
        # 医药：08-20 形状的缩影——放量双红反弹后台阶回落
        (D1, "医药", 3.72, 57.0, 2350.0),
        (D2, "医药", -1.0, -10.0, 2100.0),
        (D3, "医药", -1.5, -8.0, 1954.0),
        (D4, "医药", -3.54, -12.0, 1700.0),
        (D5, "医药", -3.07, -20.0, 1557.0),
        # 半导体：跌但边际量转正（live 答案的承接形状）
        (D1, "半导体", 0.5, 2.0, 4300.0),
        (D2, "半导体", -7.66, 3.75, 4231.0),
        (D3, "半导体", -0.65, -28.25, 3036.0),
        (D4, "半导体", 0.53, -17.65, 2500.0),
        (D5, "半导体", -3.17, 16.25, 2906.0),
        # 量子科技陷阱：站立日额度最大，宽松匹配会臆配给「科技」
        (D5, "量子科技", 1.0, 5.0, 5000.0),
        # 主线池其余解析目标（站立日一行足够包含解析）
        (D5, "有色金属", 2.0, 20.0, 1875.0),
        (D5, "消费零售", 0.5, 3.0, 800.0),
        (D5, "储能", 1.2, 8.0, 700.0),
        (D5, "军工", -0.3, 1.0, 600.0),
        (D5, "汽车", 0.1, 2.0, 650.0),
        (D5, "锂电池", 1.5, 9.0, 900.0),
        # 口径分歧夹具：同日两行互相矛盾（run_20260821 形状）
        (D4, "钙钛矿电池", 1.0, 5.0, 900.0),
        (D5, "钙钛矿电池", 2.0, 6.0, 922.49),
        (D5, "钙钛矿电池", 2.1, 6.1, 914.5),
        # 泄漏探测：站立日之后的行
        ("2026-07-24", "稀土永磁", 3.0, 20.0, 999.0),
    ]
    con.executemany(
        "insert into fact_sector_daily values (?, ?, ?, ?, ?)", sector_rows
    )

    con.execute(
        "create table fact_mainline_theme_daily(trade_date date,"
        " theme_name varchar, sector_count integer)"
    )
    mainline = [
        (D3, "半导体"), (D4, "半导体"), (D5, "半导体"),
        (D4, "有色金属"), (D5, "有色金属"),
        (D4, "消费零售"), (D5, "消费零售"),
        (D5, "储能"), (D5, "军工"), (D5, "汽车"), (D5, "锂电池"),
    ]
    con.executemany(
        "insert into fact_mainline_theme_daily values (?, ?, 1)", mainline
    )

    con.execute(
        "create table fact_sector_stock_daily(trade_date date,"
        " sector_name varchar, stock_name varchar, stock_ts_code varchar,"
        " amount double, pct_chg double)"
    )
    con.close()
    return path


def _collect(db: Path, question: str, *, subject: str, as_of: date = STANDING):
    return collect_prefetch_items(
        question=question,
        question_type="general_finance_qa",
        subject=subject,
        as_of=as_of,
        market_db_path=db,
    )


def _trajectory_items(items) -> list:
    return [item for item in items if item.title.endswith(TRAJECTORY_TITLE_SUFFIX)]


def _qualification(items):
    hits = [item for item in items if item.title == QUALIFICATION_TITLE]
    return hits[0] if hits else None


# ---------- 信号与编译器 ----------


def test_signal_fires_on_sector_outlook_asks() -> None:
    assert SIGNAL_STEP_TRAJECTORY in surface_research_signals(Q_OUTLOOK)
    assert SIGNAL_STEP_TRAJECTORY in surface_research_signals(Q_YSJS)
    # 无 板块/题材/主线/行业 词族不触发
    assert SIGNAL_STEP_TRAJECTORY not in surface_research_signals(Q_STAGE)
    assert SIGNAL_STEP_TRAJECTORY not in surface_research_signals("长电科技怎么看")


def test_signal_gated_off_for_market_watch() -> None:
    """盘面题不发（包路径 P1 另接）；变异：去掉路由排除 → 本条红。"""

    routed = surface_research_signals(
        "板块接下来的走势怎么看", question_class="market_watch"
    )
    assert SIGNAL_STEP_TRAJECTORY not in routed
    inferred = surface_research_signals("今天市场怎么样，板块走势怎么看")
    assert SIGNAL_STEP_TRAJECTORY not in inferred


def test_compiler_emits_both_operators_and_slots() -> None:
    program = compile_research_program(Q_OUTLOOK, question_class="general_finance_qa")
    assert OPERATOR_VOLUME_QUALIFICATION in program.operators
    assert OPERATOR_STEP_TRAJECTORY in program.operators
    slot_ids = {slot.slot_id for slot in program.required_fact_slots}
    assert {"volume_qualification", "volume_step_trajectory"} <= slot_ids
    stage = compile_research_program(Q_STAGE, question_class="general_finance_qa")
    assert OPERATOR_STEP_TRAJECTORY not in stage.operators


def test_contract_carries_both_slots() -> None:
    """operator → slot → 契约 required_outputs 全链路（#374 三处登记教训）。"""

    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.turn_controller import decide_turn

    decision = decide_turn(Q_OUTLOOK)
    context = build_episode_context(
        decision.task_frame,
        task_id="step-trajectory-contract",
        today="2026-08-25",
        latest_data_date="2026-08-24",
    )
    output_ids = tuple(item.output_id for item in context.contract.required_outputs)
    assert "volume_qualification" in output_ids
    assert "volume_step_trajectory" in output_ids


# ---------- 资格盘 ----------


def test_qualification_uses_inclusive_20d_window(tmp_path: Path) -> None:
    """均额=含当日 20 交易日窗（22850.0）；变异：改不含当日（23000.0）→ 红。"""

    item = _qualification(_collect(_db(tmp_path), Q_OUTLOOK, subject="科技、医药"))
    assert item is not None
    assert item.source_date == "2026-07-23"
    assert "20日均额（窗口=截至站立日最近20个交易日、含当日）=22850.0 亿" in item.detail
    assert "总量/均额比=87.5%" in item.detail
    assert "市场阶段=底部横盘阶段（第19天）" in item.detail
    metrics = {obs.metric: obs.value for obs in item.observations}
    assert metrics == {
        "total_amount": 20000.0,
        "amount_avg_20d": 22850.0,
        "amount_vs_avg20_pct": 87.5,
    }
    assert all(obs.as_of == "2026-07-23" for obs in item.observations)


def test_qualification_short_window_is_labeled_not_faked(tmp_path: Path) -> None:
    """N<20：如实标 N、按实有窗口计算；不称 20 日口径、不注册均额/比值观察值。"""

    db = _db(tmp_path, prior_market_days=11, future_row=False)
    item = _qualification(_collect(db, Q_OUTLOOK, subject="科技、医药"))
    assert item is not None
    assert "N=12" in item.detail
    assert "近12日均额" in item.detail
    assert "20日均额" not in item.detail
    # (20000 + 11×23000) / 12 = 22750.0
    assert "22750.0" in item.detail
    assert [obs.metric for obs in item.observations] == ["total_amount"]


def test_qualification_respects_as_of_cutoff(tmp_path: Path) -> None:
    """库里 07-24 有 99999 的行，问句截止 07-23：窗口不得越过站立日。"""

    item = _qualification(_collect(_db(tmp_path), Q_OUTLOOK, subject="科技、医药"))
    assert item is not None
    assert "99999" not in item.detail
    assert "2026-07-24" not in item.detail


# ---------- 台阶件 ----------


def test_trajectory_serves_exact_subject_sector(tmp_path: Path) -> None:
    items = _trajectory_items(_collect(_db(tmp_path), Q_OUTLOOK, subject="科技、医药"))
    med = [item for item in items if item.title == f"医药{TRAJECTORY_TITLE_SUFFIX}"]
    assert len(med) == 1
    detail = med[0].detail
    # 5 日台阶两端 + 双红戳（07-17 放量双红，其后回落）
    assert "2350" in detail and "1557" in detail
    assert "双红=是" in detail and "双红=否" in detail
    assert D1 in detail and D5 in detail
    assert med[0].source_date == "2026-07-23"
    assert med[0].observations


def test_family_word_fails_closed_not_quantum_tech(tmp_path: Path) -> None:
    """「科技」不得臆配「量子科技」（R-20260825-11）；科技系由主线池供数。

    变异：解析梯接入 resolve_query_themes 宽松轮 → 量子科技上桌 → 本条红。
    """

    items = _collect(_db(tmp_path), Q_OUTLOOK, subject="科技、医药")
    trajectories = _trajectory_items(items)
    titles = {item.title for item in trajectories}
    assert f"量子科技{TRAJECTORY_TITLE_SUFFIX}" not in titles
    assert f"半导体{TRAJECTORY_TITLE_SUFFIX}" in titles
    unanchored = [i for i in items if i.title == UNANCHORED_TRAJECTORY_TITLE]
    assert len(unanchored) == 1
    assert "「科技」未锚定到板块口径" in unanchored[0].detail


def test_trajectory_pool_capped_at_six(tmp_path: Path) -> None:
    """subject 命中优先占位，主线池补齐到 6，第 7 个不渲染不入收据。"""

    items = _trajectory_items(_collect(_db(tmp_path), Q_OUTLOOK, subject="科技、医药"))
    assert len(items) == 6
    titles = {item.title for item in items}
    assert f"医药{TRAJECTORY_TITLE_SUFFIX}" in titles
    assert f"汽车{TRAJECTORY_TITLE_SUFFIX}" not in titles


def test_trajectory_window_does_not_leak_past_standing(tmp_path: Path) -> None:
    for item in _trajectory_items(_collect(_db(tmp_path), Q_OUTLOOK, subject="科技、医药")):
        assert "2026-07-24" not in item.detail
        assert "稀土永磁" not in item.detail
        assert all(obs.as_of <= "2026-07-23" for obs in item.observations)


def test_divergent_rows_stay_declared_not_averaged(tmp_path: Path) -> None:
    """同日两行互相矛盾：显式分歧声明、该日不产观察值（run_20260821 回归锁）。"""

    items = _trajectory_items(_collect(_db(tmp_path), Q_OUTLOOK, subject="钙钛矿电池"))
    target = [i for i in items if i.title == f"钙钛矿电池{TRAJECTORY_TITLE_SUFFIX}"]
    assert len(target) == 1
    assert "口径分歧" in target[0].detail
    assert any(obs.as_of == D4 for obs in target[0].observations)
    assert not any(obs.as_of == D5 for obs in target[0].observations)


def test_ferment_anchored_sector_yields_to_timeline(tmp_path: Path) -> None:
    """发酵题：锚定板块由发酵时间轴供数，台阶池让位不双份；主线池照常。"""

    items = _collect(_db(tmp_path), Q_FERMENT, subject="医药")
    titles = [item.title for item in items]
    assert "医药 双红时间轴" in titles
    trajectories = {item.title for item in _trajectory_items(items)}
    assert f"医药{TRAJECTORY_TITLE_SUFFIX}" not in trajectories
    assert f"半导体{TRAJECTORY_TITLE_SUFFIX}" in trajectories


# ---------- 交付卫生 ----------


def test_missing_market_table_degrades_silently(tmp_path: Path) -> None:
    """库缺行情表：两件回空、开口不炸（预取不得杀 episode）。"""

    path = tmp_path / "bare.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "create table fact_sector_daily(trade_date date, sector_name varchar,"
        " pct_chg double, diff_ratio double, amount double)"
    )
    con.close()
    items = _collect(path, Q_OUTLOOK, subject="科技、医药")
    assert _qualification(items) is None
    assert _trajectory_items(items) == []


def test_items_carry_content_hash_for_e_numbers(tmp_path: Path) -> None:
    items = _collect(_db(tmp_path), Q_OUTLOOK, subject="科技、医药")
    qualification = _qualification(items)
    assert qualification is not None
    for item in (qualification, *_trajectory_items(items)):
        assert str(item.to_evidence().content_hash or "").strip()


def test_observation_values_registered_for_judge(tmp_path: Path) -> None:
    """判官对照：预取观察值是注册数字，残差引用不因未绑 E 号被判编造。"""

    from types import SimpleNamespace

    from intelligence.services.episode_semantic_verifier import (
        _bound_evidence_quantities,
    )

    items = _collect(_db(tmp_path), Q_OUTLOOK, subject="科技、医药")
    qualification = _qualification(items)
    assert qualification is not None
    evidence = tuple(
        item.to_evidence() for item in (qualification, *_trajectory_items(items))
    )
    outcome = SimpleNamespace(evidence=evidence, bindings=())
    quantities = _bound_evidence_quantities(outcome)
    # 注册口径是 %g 归一（22850.0 → "22850"），与判官核数一致
    assert "22850" in quantities
    assert "87.5" in quantities
    # 台阶行里的形状数字（半导体 07-23 边际量转正）同样已注册
    assert "16.25" in quantities
