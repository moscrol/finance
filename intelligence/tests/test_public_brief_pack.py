"""公开晚报包测试。spec: docs/superpowers/specs/2026-08-27-public-evening-brief-design.md

核心是许可白名单的两道保险（§1）：白名单外字段物理够不到渲染层（变异锁）、
渲染产物全文匹配不到供应商口径词与买卖词（deny-token，断言生效值）。
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from intelligence.services.market_watch_pack import BAG_MARKET, MarketWatchPack, PackBag
from intelligence.services import public_brief_pack
from intelligence.services.public_brief_pack import (
    DENY_TOKEN_RE,
    _public_market_row,
    run_public_evening_brief,
    write_outputs,
)


@pytest.fixture
def brief_db(tmp_path: Path) -> Path:
    path = tmp_path / "market.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            create table fact_market_daily(
                trade_date date, market_stage varchar, stage_day integer,
                total_amount double, amount_vs_yesterday_pct double,
                volume_state varchar, limit_up integer, limit_down integer,
                sh_index_pct_chg double, sh_index_close double, advancers integer
            )
            """
        )
        # 供应商标签（市场阶段/量能状态）刻意放进夹具：deny-token 测试要证明它们漏不出去。
        con.execute(
            "insert into fact_market_daily values "
            "('2026-07-23', '反弹阶段', 3, 30728.0, 3.9, '放量', 116, 2, "
            "0.65, 3620.5, 4260)"
        )
        con.execute(
            """
            create table fact_limit_advance_daily(
                trade_date date, stock_ts_code varchar, stock_name varchar,
                boards integer, first_limit_date date, theme varchar,
                pct_chg double, promotion_rate varchar, source varchar,
                updated_at timestamp
            )
            """
        )
        con.executemany(
            "insert into fact_limit_advance_daily values (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    "2026-07-23", "001258.SZ", "立新能源", 6, "2026-07-16",
                    "电站", 9.99, "1/1=100%", "fupanhui", "2026-07-23 18:00:00",
                ),
                (
                    "2026-07-23", "600001.SH", "甲股", 4, "2026-07-18",
                    "算力", 10.0, "1/2=50%", "fupanhui", "2026-07-23 18:00:00",
                ),
                (
                    "2026-07-23", "600002.SH", "乙股", 4, "2026-07-18",
                    "算力", 10.0, "1/2=50%", "fupanhui", "2026-07-23 18:00:00",
                ),
            ],
        )
    finally:
        con.close()
    return path


@pytest.fixture
def exports_dir(tmp_path: Path) -> Path:
    target = tmp_path / "exports"
    target.mkdir()
    # 列序与真实产物一致；「触发」列刻意带 double_red，证明公开版不读该列。
    (target / "2026-07-23-theme-candidates.md").write_text(
        "# 2026-07-23 市场触发候选简报\n\n"
        "## 二、核心候选 Deep（Top 10）\n\n"
        "| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| 1 | 工业金属 | 工业金属 | 有色金属 | 191.45 | double_red、limit_heat | 2 | 9 | 1 | - |\n"
        "| 2 | 光通信 | 光通信 | 计算机 | 94.07 | limit_heat | 5 | 12 | 5 | - |\n"
        "| 3 | 液冷 | 液冷 | 电力设备 | 89.0 | limit_advance_cluster | 5 | 12 | 5 | - |\n"
        "| 4 | 医药 | 医药 | 医药生物 | 97.21 | limit_heat | 5 | 12 | 1 | - |\n",
        encoding="utf-8",
    )
    return target


def test_facts_come_from_frozen_rows_and_method_card(
    brief_db: Path, exports_dir: Path
) -> None:
    brief = run_public_evening_brief(
        market_db_path=brief_db, exports_dir=exports_dir, cutoff="2026-07-23"
    )
    assert brief.status == "locked"
    assert brief.standing_date == "2026-07-23"
    html = brief.render_html()
    # 事实卡数字逐字来自冻结行
    for token in ("+0.65%", "30,728 亿", "116 / 2", "4260", "3620"):
        assert token in html, token
    # 连板段：最高板与分布
    assert "最高 6 板：立新能源" in html
    assert "6板 1 只" in html and "4板 2 只" in html
    # 题材段：只有名字与 KB 统计，前 3 条
    assert "工业金属" in html and "光通信" in html and "液冷" in html
    assert "医药" not in html  # limit=3
    assert "暴露公司 9" in html
    # 方法卡与免责
    assert "站立日 2026-07-23" in brief.method_card
    assert "不构成投资建议" in html
    assert brief.snapshot_id in html
    # 快照冻结：数字能在快照体里找到
    snapshot = brief.to_snapshot()
    assert snapshot["snapshot_id"] == brief.snapshot_id
    assert any("30,728" in fact["value"] for fact in snapshot["facts"])


def test_deny_tokens_never_leak(brief_db: Path, exports_dir: Path) -> None:
    """夹具里放了市场阶段/量能状态标签与 double_red 触发词，产物必须一个都不带。"""
    brief = run_public_evening_brief(
        market_db_path=brief_db, exports_dir=exports_dir, cutoff="2026-07-23"
    )
    html = brief.render_html()
    match = DENY_TOKEN_RE.search(html)
    assert match is None, f"公开产物泄漏口径词: {match.group(0) if match else ''}"
    # 快照同样不得携带供应商标签
    import json

    snapshot_text = json.dumps(brief.to_snapshot(), ensure_ascii=False)
    assert DENY_TOKEN_RE.search(snapshot_text) is None


def test_whitelist_physically_drops_unlisted_fields() -> None:
    """变异锁：袋行里塞进白名单外字段（diff_ratio / 阶段标签），准入层直接丢弃。"""
    row = {
        "trade_date": "2026-07-23",
        "total_amount": 30728.0,
        "diff_ratio": 99.87,
        "market_stage": "反弹阶段",
        "volume_state": "放量",
    }
    public = _public_market_row((row,))
    assert "diff_ratio" not in public
    assert "market_stage" not in public
    assert "volume_state" not in public
    assert public["total_amount"] == 30728.0
    # 白名单键即使缺失也只会是 None，不会引入名单外键
    assert set(public) <= set(public_brief_pack._MARKET_BAG_WHITELIST)


def test_missing_day_stops_with_no_numbers(brief_db: Path, exports_dir: Path) -> None:
    brief = run_public_evening_brief(
        market_db_path=brief_db, exports_dir=exports_dir, cutoff="2026-07-22"
    )
    assert brief.status == "empty"
    html = brief.render_html()
    assert "无行情" in html
    assert "亿" not in html  # 零数字：事实卡整段不出
    assert "最高" not in html


def test_locked_db_is_not_reported_as_no_data(
    monkeypatch: pytest.MonkeyPatch, exports_dir: Path
) -> None:
    locked_bag = PackBag(
        name=BAG_MARKET,
        requested_date="2026-07-23",
        served_date=None,
        status="locked",
        rows=(),
    )
    tape = MarketWatchPack(
        standing_date="2026-07-23",
        explicit=True,
        calendar_disclosure=None,
        bags=(locked_bag,),
    )
    monkeypatch.setattr(
        public_brief_pack, "run_market_watch_pack", lambda *a, **k: tape
    )
    brief = run_public_evening_brief(
        market_db_path="/nonexistent.duckdb",
        exports_dir=exports_dir,
        cutoff="2026-07-23",
    )
    assert brief.status == "locked_db"
    assert "不是该日无行情" in (brief.stop_text or "")


def test_theme_and_ladder_gaps(brief_db: Path, tmp_path: Path) -> None:
    """theme-candidates 缺失 + 连板表无该日行 → 两段缺口句，不借数、不报错。"""
    con = duckdb.connect(str(brief_db))
    try:
        con.execute("delete from fact_limit_advance_daily")
    finally:
        con.close()
    empty_exports = tmp_path / "no-exports"
    empty_exports.mkdir()
    brief = run_public_evening_brief(
        market_db_path=brief_db, exports_dir=empty_exports, cutoff="2026-07-23"
    )
    assert brief.ladder is None
    assert brief.themes == ()
    html = brief.render_html()
    assert "连板梯队数据未同步" in html
    assert "题材候选产物未生成" in html


def test_png_degrades_without_chrome(
    brief_db: Path, exports_dir: Path, tmp_path: Path
) -> None:
    brief = run_public_evening_brief(
        market_db_path=brief_db, exports_dir=exports_dir, cutoff="2026-07-23"
    )
    result = write_outputs(
        brief, tmp_path / "out", png=True, chrome_path="/nonexistent/chrome"
    )
    assert Path(result["html"]).exists()
    assert "png" not in result
    assert "png_error" in result


def test_cli_brief_writes_html(
    brief_db: Path, exports_dir: Path, tmp_path: Path
) -> None:
    import argparse

    from intelligence.cli import cmd_brief

    args = argparse.Namespace(
        date="2026-07-23",
        db=str(brief_db),
        exports_dir=str(exports_dir),
        out_dir=str(tmp_path / "briefs"),
        png=False,
        write_snapshot=False,
    )
    assert cmd_brief(args) == 0
    assert (tmp_path / "briefs" / "2026-07-23" / "evening.html").exists()
