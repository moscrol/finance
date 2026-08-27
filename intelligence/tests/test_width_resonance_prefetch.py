"""宽度共振袋：概念×申万一级同日对照（Engine A 开口预取，视角判据组件化第二批）。

工单：docs/superpowers/specs/2026-08-26-width-resonance-bag-workorder.md（§P1）
台账：R-20260826-02。
双臂对照实锤（~/.finance-runtime/trace-diff-spt-forward-20260826/）：同题产品臂
引用了「宽度夺价」画像判据但没有做数据验证；react 臂做了概念×申万一级对照，
拿到「概念涨、行业负」反证后把结论降了一级——这是两臂最大质量分差点。

冻结口径（工单 §P1）：
- 袋只交付事实对照行，判语（宽度成立/只是概念锐度）留给解读方按画像规则写。
- 站立日与其余袋同源（`_standing_on_or_before`），禁止第二套口径。
- 概念缺 sw_l1 映射、或申万表缺该日行 → 该行如实标「缺数」，不猜、不省略。
- 空集也要上桌：无符合条件概念时交付空集声明，让模型知道「查过了」。
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb

from intelligence.services.asof_prefetch import collect_prefetch_items
from intelligence.services.market_watch_pack import (
    WIDTH_RESONANCE_DISCLAIMER,
    WIDTH_RESONANCE_TITLE,
    render_width_resonance_lines,
    width_resonance_rows,
)
from intelligence.services.research_contract import (
    OPERATOR_WIDTH_RESONANCE,
    compile_research_program,
)

Q_OUTLOOK = "站在spt视角下，科技和医药板块接下来的走势怎么看，需要观察哪些个股的反馈"
Q_FORWARD = "基于spt的视角，你认为后续什么板块有机会，板块内什么个股有机会"
Q_STAGE = "用spt的视角，回答下当前科技处于什么阶段，和之前哪一段的科技行情比较类似，个股怎么对标"

STANDING = date(2026, 7, 23)
D_STAND = "2026-07-23"
D_LEAK = "2026-07-24"


def _db(tmp_path: Path, *, sw_rows: bool = True, qualifying: bool = True) -> Path:
    path = tmp_path / "width.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "create table fact_market_daily(trade_date date, market_stage varchar,"
        " stage_day integer, total_amount double, amount_vs_yesterday_pct double,"
        " volume_state varchar, limit_up integer, limit_down integer,"
        " sh_index_pct_chg double)"
    )
    day = date(2026, 7, 22)
    rows = []
    for _ in range(24):
        rows.append(
            f"('{day.isoformat()}', '底部横盘阶段', 1, 23000, 0, '正常量能', 50, 1, 0.1)"
        )
        day -= timedelta(days=1)
    rows.append(f"('{D_STAND}', '底部横盘阶段', 19, 20000, 6.82, '正常量能', 60, 2, 0.2)")
    con.execute("insert into fact_market_daily values " + ", ".join(rows))

    con.execute(
        "create table fact_sector_daily(trade_date date, sector_name varchar,"
        " pct_chg double, diff_ratio double, amount double, sw_l1 varchar)"
    )
    sector_rows: list[tuple[str, str, float, float, float, str | None]] = []
    if qualifying:
        sector_rows.extend(
            [
                # 锐度无宽度形状：概念放量上涨、对应申万一级为负
                (D_STAND, "光缆概念", 4.9, 41.6, 480.0, "通信"),
                (D_STAND, "电网概念", 1.5, 10.2, 914.0, "电力设备"),
                # 共振形状：概念与行业同涨
                (D_STAND, "白酒概念", 2.0, 20.0, 500.0, "食品饮料"),
                # 缺映射：sw_l1 为 NULL → 该行「缺数」
                (D_STAND, "神秘概念", 3.0, 30.0, 300.0, None),
                # 排序垫底 + 限量裁剪目标（diff 最小的三个）
                (D_STAND, "概念甲", 1.0, 9.0, 260.0, "通信"),
                (D_STAND, "概念乙", 1.1, 8.0, 250.0, "通信"),
                (D_STAND, "概念丙", 1.2, 7.0, 240.0, "通信"),
            ]
        )
    # 门槛外：成交额不足 / 下跌概念——不得上桌
    sector_rows.append((D_STAND, "迷你概念", 5.0, 50.0, 50.0, "通信"))
    sector_rows.append((D_STAND, "绿盘概念", -2.0, 60.0, 800.0, "通信"))
    # 泄漏探测：站立日之后的行不得进入对照
    sector_rows.append((D_LEAK, "泄漏概念", 9.0, 99.0, 9999.0, "通信"))
    con.executemany(
        "insert into fact_sector_daily values (?, ?, ?, ?, ?, ?)", sector_rows
    )

    con.execute(
        "create table fact_sw_l1_daily(trade_date date, sw_l1 varchar, pct_chg double)"
    )
    if sw_rows:
        con.executemany(
            "insert into fact_sw_l1_daily values (?, ?, ?)",
            [
                (D_STAND, "通信", -0.23),
                (D_STAND, "电力设备", -1.06),
                (D_STAND, "食品饮料", 1.8),
                # 泄漏探测：次日行业行不得被当作站立日行
                (D_LEAK, "通信", 9.9),
            ],
        )
    con.close()
    return path


def _collect(db: Path, question: str = Q_OUTLOOK):
    return collect_prefetch_items(
        question=question,
        question_type="general_finance_qa",
        subject="科技、医药",
        as_of=STANDING,
        market_db_path=db,
    )


def _width_item(items):
    hits = [item for item in items if item.title == WIDTH_RESONANCE_TITLE]
    return hits[0] if hits else None


# ---------- 编译器 ----------


def test_compiler_emits_width_operator_with_step_trajectory() -> None:
    """台阶信号三件套：资格盘、台阶、宽度对照同门进出。"""

    for question in (Q_OUTLOOK, Q_FORWARD):
        program = compile_research_program(
            question, question_class="general_finance_qa"
        )
        assert OPERATOR_WIDTH_RESONANCE in program.operators, question
    stage = compile_research_program(Q_STAGE, question_class="general_finance_qa")
    assert OPERATOR_WIDTH_RESONANCE not in stage.operators


def test_width_operator_carries_no_required_slot() -> None:
    """可选供给不签约（替补单 probe_id 教训：无读取方的字段不先写）。"""

    program = compile_research_program(Q_OUTLOOK, question_class="general_finance_qa")
    slot_ids = {slot.slot_id for slot in program.required_fact_slots}
    assert "width_resonance" not in slot_ids


# ---------- 事实行构建 ----------


def test_rows_join_sw_l1_and_fail_closed_on_missing_mapping(tmp_path: Path) -> None:
    con = duckdb.connect(str(_db(tmp_path)), read_only=True)
    try:
        rows = width_resonance_rows(con, D_STAND)
    finally:
        con.close()
    names = [row["sector_name"] for row in rows]
    # diff 降序 + 限量 6：diff 最小的「概念丙」被裁掉
    assert names == ["光缆概念", "神秘概念", "白酒概念", "电网概念", "概念甲", "概念乙"]
    by_name = {row["sector_name"]: row for row in rows}
    assert by_name["光缆概念"]["sw_l1"] == "通信"
    assert by_name["光缆概念"]["sw_l1_pct"] == -0.23
    assert by_name["白酒概念"]["sw_l1_pct"] == 1.8
    # 缺映射 → sw_l1_pct 为 None（渲染层标「缺数」）
    assert by_name["神秘概念"]["sw_l1"] is None
    assert by_name["神秘概念"]["sw_l1_pct"] is None
    # 门槛与泄漏：小额、绿盘、次日行都不得上桌
    assert "迷你概念" not in by_name
    assert "绿盘概念" not in by_name
    assert "泄漏概念" not in by_name


def test_rows_mark_missing_when_sw_table_has_no_standing_rows(tmp_path: Path) -> None:
    """申万表缺站立日行：袋仍上桌，行全部「缺数」，不得拿次日行冒充。"""

    con = duckdb.connect(str(_db(tmp_path, sw_rows=False)), read_only=True)
    try:
        rows = width_resonance_rows(con, D_STAND)
    finally:
        con.close()
    assert rows, "申万侧缺数不应清空概念侧事实"
    assert all(row["sw_l1_pct"] is None for row in rows)


def test_rows_empty_when_standing_none(tmp_path: Path) -> None:
    con = duckdb.connect(str(_db(tmp_path)), read_only=True)
    try:
        assert width_resonance_rows(con, None) == ()
    finally:
        con.close()


# ---------- 渲染 ----------


def test_render_carries_facts_and_missing_marker(tmp_path: Path) -> None:
    con = duckdb.connect(str(_db(tmp_path)), read_only=True)
    try:
        rows = width_resonance_rows(con, D_STAND)
    finally:
        con.close()
    lines = render_width_resonance_lines(rows)
    joined = "\n".join(lines)
    assert "概念「光缆概念」+4.90%/边际量+41.6%/成交480亿 ↔ 申万一级「通信」-0.23%" in joined
    assert "概念「神秘概念」+3.00%/边际量+30.0%/成交300亿 ↔ 申万一级「缺数」" in joined


# ---------- 开口预取端到端 ----------


def test_prefetch_item_served_date_and_disclaimer(tmp_path: Path) -> None:
    item = _width_item(_collect(_db(tmp_path)))
    assert item is not None
    assert item.source_date == D_STAND
    # 限定语在前（预算+声明式截断纪律）：判语归属声明必须先于事实行
    assert item.detail.startswith(WIDTH_RESONANCE_DISCLAIMER)
    assert "泄漏概念" not in item.detail
    assert item.tool == "market_data"


def test_prefetch_declares_empty_pool(tmp_path: Path) -> None:
    """空集也要上桌：让模型知道「查过了、当日无放量上涨概念」。"""

    item = _width_item(_collect(_db(tmp_path, qualifying=False)))
    assert item is not None
    assert "无符合条件的放量上涨概念" in item.detail


def test_stage_question_gets_no_width_item(tmp_path: Path) -> None:
    assert _width_item(_collect(_db(tmp_path), question=Q_STAGE)) is None
