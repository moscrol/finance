"""W5 / G1a：涨停封板时间数据块 [D18]。

spec: docs/superpowers/specs/2026-09-10-knevo-arch-delta-worklist.md W5
（2026-09-11 评审修订版：**只交数据出口，不迁 SPT-A06**）。

这一单守两件事：
1. 正向——命中封板题形时块出现，且首封/末封时点确实落到 prompt 里；
2. 反向——当日没有封板时间读数时**不注入、不出空块**（空壳块会让模型以为
   「查过了、没有」，那是静默降级的另一种形状）。

以及一条纪律钉：SPT-A06 依赖的 `open_times` 仍恒 NULL（G1b 未修），所以本块
**不得**携带该规则文本，规则本体必须仍在 `_PENDING_RULES`。
"""

from __future__ import annotations

import duckdb
import pytest

from intelligence.services import reading_baseline
from intelligence.services.market_timeseries import (
    limit_seal_time_block_for_llm,
    parse_limit_seal_intent,
)


POSITIVE = (
    "今天哪些是秒板",
    "先导智能几点封板的",
    "炸板回封的票多不多",
    "涨停梯队的节奏怎么样",
    "涨停的先后顺序是什么",
    "一字板有哪些",
)

NEGATIVE = (
    "今天涨停多少家",
    "液冷板块怎么看",
    "隔夜美股映射哪些板块",
    "英维克客户证据硬不硬",
    "数据安全中期赔率怎么看",
)


def _make_db(tmp_path, rows: list[tuple], *, name: str = "seal.duckdb"):
    db_path = tmp_path / name
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE fact_theme_limit_stock_daily (
            trade_date DATE,
            sector_ts_code TEXT,
            sector_name TEXT,
            stock_ts_code TEXT,
            stock_name TEXT,
            limit_times INTEGER,
            limit_status TEXT,
            first_limit_time TEXT,
            last_limit_time TEXT,
            open_times INTEGER,
            ths_concept_top TEXT
        )
        """
    )
    if rows:
        con.executemany(
            "INSERT INTO fact_theme_limit_stock_daily VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
    con.close()
    return db_path


def _rows() -> list[tuple]:
    # 秒板股一股两题材（去重后应只出一行、题材合并）；回封股盘中开板后回封。
    return [
        ("2026-09-10", "990013.FP", "液冷", "300001.SZ", "秒板股", 3, "涨停",
         "092500", "092500", None, "液冷概念"),
        ("2026-09-10", "990014.FP", "温控", "300001.SZ", "秒板股", 3, "涨停",
         "092500", "092500", None, "液冷概念"),
        ("2026-09-10", "990015.FP", "机器人", "300002.SZ", "回封股", 1, "涨停",
         "103012", "142233", None, "机器人概念"),
    ]


def test_intent_positive_samples_route() -> None:
    for query in POSITIVE:
        assert parse_limit_seal_intent(query), query


def test_intent_negative_samples_do_not_route() -> None:
    for query in NEGATIVE:
        assert not parse_limit_seal_intent(query), query
    assert not parse_limit_seal_intent("")
    assert not parse_limit_seal_intent("   ")


def test_block_renders_seal_times_deduped_by_stock(tmp_path) -> None:
    block = limit_seal_time_block_for_llm(_make_db(tmp_path, _rows()))

    assert "[D18]" in block
    assert "2026-09-10" in block
    assert "first_limit_time" in block
    # HHMMSS → 可读时点
    assert "首封 09:25:00" in block
    assert "首封 10:30:12" in block
    assert "末封 14:22:33" in block
    # 一股两题材只出一行，题材合并
    assert block.count("秒板股(300001.SZ)") == 1
    assert "液冷" in block and "温控" in block
    # 覆盖率行：分母是去重后的涨停家数
    assert "当日涨停 2 只" in block
    assert "其中 2 只有封板时间读数" in block
    # 首封升序
    assert block.index("秒板股") < block.index("回封股")
    assert "盘中开板后回封" in block


def test_block_discloses_open_times_gap_and_does_not_carry_pending_rule(tmp_path) -> None:
    """G1b 未修 → 块必须自报「判不了换手」，且不得夹带 SPT-A06 规则本体。"""
    block = limit_seal_time_block_for_llm(_make_db(tmp_path, _rows()))

    assert "open_times" in block
    assert "无法判定换手是否充分" in block

    pending = {rule.id: rule for rule, _gap, _note in reading_baseline.pending_rules()}
    assert "SPT-A06" in pending, "G1b 未修前该规则必须仍在 _PENDING_RULES"
    assert pending["SPT-A06"].rule not in block
    assert "后排标的不具备参与价值" not in block
    assert "SPT-A06" not in block


@pytest.mark.parametrize(
    "rows",
    [
        # 有涨停行，但封板时间整列为空 → 不出块（反向验收的主场景）
        [
            ("2026-09-10", "990013.FP", "液冷", "300001.SZ", "无时间股", 1, "涨停",
             None, None, None, "液冷概念"),
            ("2026-09-10", "990014.FP", "温控", "300002.SZ", "也无时间", 1, "涨停",
             "", "", None, "温控概念"),
        ],
        # 空表
        [],
    ],
)
def test_no_seal_data_injects_nothing(tmp_path, rows) -> None:
    block = limit_seal_time_block_for_llm(_make_db(tmp_path, rows, name="empty.duckdb"))
    assert block == ""


def test_missing_db_returns_empty(tmp_path) -> None:
    assert limit_seal_time_block_for_llm(tmp_path / "nope.duckdb") == ""


def test_scope_narrows_to_theme_and_falls_back_honestly(tmp_path) -> None:
    db_path = _make_db(tmp_path, _rows())

    narrowed = limit_seal_time_block_for_llm(db_path, theme="液冷")
    assert "已按「液冷」收口" in narrowed
    assert "秒板股" in narrowed
    assert "回封股" not in narrowed
    # 收口不改覆盖率分母：当日全市场读数照实报
    assert "当日涨停 2 只" in narrowed

    # 该题材当日没有封板读数时，退回全市场并说明，而不是假装无数据
    fallback = limit_seal_time_block_for_llm(db_path, theme="固态电池")
    assert "「固态电池」当日无封板时间读数，以下为全市场" in fallback
    assert "秒板股" in fallback and "回封股" in fallback


def test_assembly_forwards_requested_date_to_on_date() -> None:
    """装配面对账：``ask.py`` 的 D18 闭包必须把问句日期传进 ``on_date``。

    下面 ``test_on_date_respects_as_of`` 只证明**函数**认 as-of；函数认、装配面
    不传，「9 月 5 日哪些是秒板」照样拿全库最新交易日的读数——参数在场 ≠ 被读
    （`granted-budget-fields-must-be-read-at-the-enforcement-point` 同一形状）。
    走 AST 不执行 ask.py：该模块导入重依赖，与 conformance_datablocks 的装配面
    扫描同一取舍。
    """
    import ast
    from pathlib import Path as _Path

    import intelligence.services.ask as ask_mod

    tree = ast.parse(_Path(ask_mod.__file__).read_text(encoding="utf-8"))
    fns = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in ("_d18_applies", "_build_d18")
    }
    assert set(fns) == {"_d18_applies", "_build_d18"}, "D18 装配闭包改名或消失"

    # 门控侧解析问句日期
    applies_calls = {
        node.func.id
        for node in ast.walk(fns["_d18_applies"])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "market_review_requested_date" in applies_calls, (
        "_d18_applies 未解析问句日期，D18 只会取全库最新交易日"
    )

    # 取数侧把它作为 on_date 关键字传下去
    forwarded = [
        node
        for node in ast.walk(fns["_build_d18"])
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", None) == "limit_seal_time_block_for_llm"
        and any(kw.arg == "on_date" for kw in node.keywords)
    ]
    assert forwarded, "_build_d18 调用 limit_seal_time_block_for_llm 时漏传 on_date"


def test_on_date_respects_as_of(tmp_path) -> None:
    rows = _rows() + [
        ("2026-09-11", "990013.FP", "液冷", "300003.SZ", "次日股", 1, "涨停",
         "093000", "093000", None, "液冷概念"),
    ]
    db_path = _make_db(tmp_path, rows, name="asof.duckdb")

    latest = limit_seal_time_block_for_llm(db_path)
    assert "2026-09-11" in latest
    assert "次日股" in latest

    earlier = limit_seal_time_block_for_llm(db_path, on_date="2026-09-10")
    assert "2026-09-10" in earlier
    assert "次日股" not in earlier
