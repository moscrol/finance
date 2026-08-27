"""空袋替补观察探针：主线无双红匹配时按预案补带标签的观察池。

Spec: docs/superpowers/specs/2026-08-25-substitute-observation-probe-design.md
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from intelligence.services.ask import bind_market_watch_pack
from intelligence.services.ask_types import AskOptions
from intelligence.services.market_watch_pack import (
    PROBE_ROLE_OBSERVATION,
    merge_into_public_answer,
    run_market_watch_pack,
)
from intelligence.services.outlook_delivery_gate import strip_outlook_violations

A1_QUERY = "2026-07-23 今天市场怎么样"


def _seed(
    tmp_path: Path,
    *,
    med_dual_red: bool = False,
    themes: tuple[tuple[str, int, int], ...] = (("医药", 6, 1), ("有色金属", 5, 2)),
    med_sector_date: str = "2026-07-23",
    med_stock_date: str = "2026-07-23",
    ysjs_stock_date: str = "2026-07-23",
    include_zhongyiyao: bool = True,
) -> Path:
    path = tmp_path / "market.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        """
        create table fact_market_daily(
          trade_date date, market_stage varchar, stage_day integer,
          total_amount double, amount_vs_yesterday_pct double, volume_state varchar,
          limit_up integer, limit_down integer, sh_index_pct_chg double
        )
        """
    )
    con.execute(
        "insert into fact_market_daily values "
        "('2026-07-23', '反弹阶段', 3, 21949.97, -17.27, '缩量观望', 116, 2, 0.2519),"
        "('2026-07-22', '反弹阶段', 2, 20000, -5, '缩量', 90, 1, 0.1)"
    )
    con.execute(
        """
        create table fact_mainline_theme_daily(
          trade_date date, theme_name varchar, sector_count integer, min_sort integer
        )
        """
    )
    for name, count, sort in themes:
        con.execute(
            "insert into fact_mainline_theme_daily values ('2026-07-23', ?, ?, ?)",
            [name, count, sort],
        )
    con.execute(
        """
        create table fact_sector_daily(
          trade_date date, sector_name varchar,
          pct_chg double, diff_ratio double, amount double
        )
        """
    )
    # 严格双红：通信设备 / PCB（pct>0 且 diff>10 且 amount>500）
    con.execute(
        "insert into fact_sector_daily values "
        "('2026-07-23', '通信设备', 2.5, 15.0, 900),"
        "('2026-07-23', 'PCB', 3.0, 12.0, 700)"
    )
    # 医药匹配板块：默认不双红；med_dual_red=True 时医药商业升双红
    med_row = (1.2, 12.0, 900.0) if med_dual_red else (-0.5, 3.0, 900.0)
    con.execute(
        "insert into fact_sector_daily values (?, '医药商业', ?, ?, ?)",
        [med_sector_date, *med_row],
    )
    if include_zhongyiyao:
        con.execute(
            "insert into fact_sector_daily values "
            "('2026-07-23', '中医药', 0.8, 4.0, 400)"
        )
    con.execute(
        "insert into fact_sector_daily values "
        "('2026-07-23', '有色金属冶炼', 1.5, 8.0, 800)"
    )
    con.execute(
        """
        create table fact_sector_stock_daily(
          trade_date date, sector_name varchar, stock_name varchar,
          stock_ts_code varchar, amount double, pct_chg double
        )
        """
    )
    con.execute(
        "insert into fact_sector_stock_daily values "
        f"('{med_stock_date}', '医药商业', '国药一致', '000028.SZ', 25.0, -0.8),"
        f"('{med_stock_date}', '医药商业', '上海医药', '601607.SH', 20.0, 0.3),"
        f"('{med_stock_date}', '医药商业', '九州通', '600998.SH', 15.0, -1.1),"
        f"('{ysjs_stock_date}', '有色金属冶炼', '紫金矿业', '601899.SH', 50.0, 2.0),"
        f"('{ysjs_stock_date}', '有色金属冶炼', '洛阳钼业', '603993.SH', 30.0, 1.4)"
    )
    con.execute(
        """
        create table fact_theme_limit_heat_daily(
          trade_date date, sector_name varchar,
          limit_up_count integer, market_share double
        )
        """
    )
    con.execute(
        "insert into fact_theme_limit_heat_daily values ('2026-07-23', '储能', 40, 0.1)"
    )
    con.close()
    return path


def _pack(db: Path, *, probes: bool = True):
    return run_market_watch_pack(
        A1_QUERY,
        market_db_path=db,
        substitute_probes=probes,
    )


# ---------- §7.1 触发与产出 ----------


def test_probe_fires_for_unmatched_mainline_themes(tmp_path: Path) -> None:
    pack = _pack(_seed(tmp_path))
    assert len(pack.probes) == 2
    by_theme = {p.rows[0]["theme"]: p for p in pack.probes if p.rows}
    assert set(by_theme) == {"医药", "有色金属"}
    med = by_theme["医药"]
    assert med.status == "hit"
    assert med.role == PROBE_ROLE_OBSERVATION
    assert med.requested_date == "2026-07-23"
    assert med.served_date == "2026-07-23"
    # 成交额最大的匹配板块（医药商业 900 > 中医药 400），前 2 只个股带代码
    assert med.rows[0]["sector_name"] == "医药商业"
    assert [r["stock_name"] for r in med.rows] == ["国药一致", "上海医药"]
    assert all(r["stock_code"] for r in med.rows)
    ysjs = by_theme["有色金属"]
    assert [r["stock_name"] for r in ysjs.rows] == ["紫金矿业", "洛阳钼业"]


def test_probe_skips_theme_matched_by_dual_red(tmp_path: Path) -> None:
    pack = _pack(_seed(tmp_path, med_dual_red=True))
    themes = {p.rows[0]["theme"] for p in pack.probes if p.rows}
    assert "医药" not in themes
    assert themes == {"有色金属"}


def test_probe_caps_at_two_themes(tmp_path: Path) -> None:
    pack = _pack(
        _seed(
            tmp_path,
            themes=(("医药", 6, 1), ("有色金属", 5, 2), ("机器人", 4, 3)),
        )
    )
    assert len(pack.probes) == 2
    probed = [p.trigger for p in pack.probes]
    assert any("医药" in t for t in probed)
    assert any("有色金属" in t for t in probed)
    assert not any("机器人" in t for t in probed)
    # 第 3 个题材仍在缺口句里
    gap = pack.mainline_dual_red_gap()
    assert gap is not None and "机器人" in gap


def test_probe_no_match_is_honest(tmp_path: Path) -> None:
    pack = _pack(_seed(tmp_path, themes=(("量子科技", 3, 1),)))
    assert len(pack.probes) == 1
    probe = pack.probes[0]
    assert probe.status == "no_match"
    assert probe.rows == ()
    assert probe.served_date is None
    rendered = pack.render()
    assert "无可替补观察对象" in rendered
    assert "国药一致" not in rendered


def test_probe_never_serves_neighbor_day(tmp_path: Path) -> None:
    # 医药：匹配板块行只在 07-22（个股行留在 07-23，专抓「板块查询改 <=」的变异）；
    # 有色：板块行在 07-23 但个股行只在 07-22（专抓「个股查询改 <=」的变异）。
    pack = _pack(
        _seed(
            tmp_path,
            med_sector_date="2026-07-22",
            med_stock_date="2026-07-23",
            ysjs_stock_date="2026-07-22",
            include_zhongyiyao=False,
        )
    )
    assert {p.status for p in pack.probes} == {"no_match"}
    for probe in pack.probes:
        assert probe.rows == ()
        assert probe.served_date is None
    rendered = pack.render()
    assert "紫金矿业" not in rendered
    assert "国药一致" not in rendered
    assert "医药商业" not in rendered


# ---------- §7.2 渲染与合并 ----------


def test_render_gap_before_probe_block_and_label_first(tmp_path: Path) -> None:
    pack = _pack(_seed(tmp_path))
    rendered = pack.render()
    gap_at = rendered.index("缺口")
    block_at = rendered.index("替补观察")
    assert gap_at < block_at
    assert "非机会" in rendered
    for line in rendered.splitlines():
        if "国药一致" in line or "紫金矿业" in line:
            label_at = line.index(PROBE_ROLE_OBSERVATION)
            assert label_at < line.index(
                "国药一致" if "国药一致" in line else "紫金矿业"
            )
    # served_date 收据在渲染里可见
    assert "served_date=2026-07-23" in rendered


def test_merge_keeps_probe_block_with_owner_prose(tmp_path: Path) -> None:
    pack = _pack(_seed(tmp_path))
    merged = merge_into_public_answer("owner 正文：今日成交 21949.97 亿。", pack)
    assert "替补观察" in merged
    assert "国药一致" in merged
    assert "owner 正文" in merged


def test_default_off_keeps_probes_empty(tmp_path: Path) -> None:
    pack = _pack(_seed(tmp_path), probes=False)
    assert pack.probes == ()
    assert "替补观察" not in pack.render()


def test_bind_enables_probes_and_supplemental_carries_block(tmp_path: Path) -> None:
    options = AskOptions(
        query=A1_QUERY,
        market_db_path=_seed(tmp_path),
        compose=True,
    )
    bound = bind_market_watch_pack(options, frame=None)
    pack = bound.market_watch_pack
    assert pack is not None
    assert len(pack.probes) == 2
    assert "替补观察" in (bound.supplemental_evidence or "")
    assert PROBE_ROLE_OBSERVATION in (bound.supplemental_evidence or "")


# ---------- 判官对照：交付闸不误杀注册替补行 ----------


def test_probe_lines_survive_outlook_gate(tmp_path: Path) -> None:
    rendered = _pack(_seed(tmp_path)).render()
    assert strip_outlook_violations(rendered) == rendered
