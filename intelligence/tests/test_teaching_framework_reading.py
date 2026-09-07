"""授课框架读数进带读：句子只摆读数、不出名单不出代码、过合规门；上证卡片是可分享的纯 SVG；不接旁路库逐字节不变。"""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from intelligence.services import guided_reading as gr
from intelligence.services.teaching_framework.reading import DISCLAIMER, index_card_svg, teaching_lines
from intelligence.services.teaching_framework.river_objects import teaching_objects
from intelligence.tests.teaching_sidecar_fixture import STOCK_NAMES, build_sidecar

SLICE_PLAIN = {
    "as_of": "2026-01-12", "entity_id": "990306.FP", "entity_name": "算力租赁", "knowledge_cutoff": "2026-01-12", "pit_grade": "strict",
    "tracks": {"market": [{"object_type": "label", "ref": "fact_sector_daily:990306.FP@2026-01-12", "source_hash": "abc", "payload": {"pct_chg": 3.2}}]},
}


@pytest.fixture
def sidecar(tmp_path: Path) -> Path:
    return build_sidecar(tmp_path / "labels.duckdb")


def _objects(sidecar: Path, day: str) -> list[dict]:
    return [o.to_dict() for o in teaching_objects(sidecar, day, top=2)]


def test_teaching_lines_read_the_numbers_and_never_name_a_stock(sidecar: Path) -> None:
    lines = teaching_lines(_objects(sidecar, "2026-01-12"))
    text = "\n".join(lines)
    assert lines[0].startswith("阶段：左底向下｜置信：3/6 条视角命中，缺 1 条，领先第二名 1 分｜来源状态：高位震荡｜转点：turn_down")
    assert lines[1] == "量能：shrink（量能比 84）｜偏离度带：below｜周均线下方第 1 天（首次下穿周期）"
    assert lines[2] == "亏钱效应：是（连续第 2 天）｜承接 5 日均值 0.80%"
    assert lines[3] == ("资金面：龙虎榜席位净流入 12.3 亿（占全市场成交 0.71‰，5 日均 0.55‰），买盘/卖盘 1.90（5 日均 1.70）"
                        "｜涨停封单占流通市值中位 96（万/亿），厚封单占比 48%｜昨日涨停股竞价涨幅中位 3.25%，为正 80%｜成交额前 100 占全市场 18.7%")
    assert lines[4].startswith("王朝链：最近见顶的王朝 W0（2025-12-12 → 2026-01-09），覆灭窗自 2026-01-12 起，至今有标签 1 天、亏钱效应日 1 天；其前 2：申万一级 2 个（电子 1、通信 1）；载体 趋势 1，连板 1")
    assert "进入这一波的衔接" not in lines[4]  # W0 是第一波：没有进入它的衔接
    assert lines[5] == "区间涨幅高标：20 日前 2：申万一级 2 个（电子 1、通信 1），连板高标 1 只，在位天数中位 2，入组门槛 40%；60 日前 1：申万一级 1 个（汽车 1），连板高标 0 只，在位天数中位 9，入组门槛 120%"
    # 不出名单、不出代码：夹具里的名字与代码一个都不许出现；合规门（方向词 / 时点词 / 概率 / 代码）零命中。
    assert not any(name in text for name in STOCK_NAMES) and ".SH" not in text and ".SZ" not in text
    assert gr.lint_output(text) == []


def test_teaching_lines_describe_the_handoff_once_the_next_wave_has_peaked(sidecar: Path) -> None:
    lines = teaching_lines(_objects(sidecar, "2026-02-06"))
    dyn = next(x for x in lines if x.startswith("王朝链"))
    assert "最近见顶的王朝 W1（2026-01-21 → 2026-02-05）" in dyn
    assert "进入这一波的衔接：上一王朝 W0 覆灭窗 2026-01-12 → 2026-01-20，本波前 2 里 1 只相对分离、2 只窗内创新高" in dyn
    assert gr.lint_output("\n".join(lines)) == []


def test_index_card_is_pure_svg_with_stage_bands_losing_days_and_no_names(sidecar: Path) -> None:
    lines = teaching_lines(_objects(sidecar, "2026-01-12"))
    svg = index_card_svg(sidecar, "2026-01-12", lines, days=60)
    assert svg.startswith("<svg ") and svg.rstrip().endswith("</svg>")
    assert "上证指数 · 授课框架读数 · 2026-01-12" in svg
    assert "#c9d8f0" in svg and "#fbe3b6" in svg  # 左底向下 / 高位震荡 的底色都画了
    assert svg.count("<circle") == 1  # 截至 01-12 只有它自己是亏钱效应日
    assert "<polyline" in svg and DISCLAIMER in svg and "tf-v0.2+test" in svg
    assert not any(name in svg for name in STOCK_NAMES) and ".SH" not in svg
    # 之后的日子不能画进 as_of 之前的卡片：01-14 的收盘 3312.5 不在里面。
    assert "3312.5" not in svg and "6 个交易日" in svg
    # 没有任何标签的日子：卡片仍是合法 SVG，说明原因。
    empty = index_card_svg(sidecar, "2025-01-01", [], days=60)
    assert "之前没有有标签的交易日" in empty and empty.rstrip().endswith("</svg>")


def test_guided_reading_moves_teaching_objects_into_their_own_section(sidecar: Path) -> None:
    objs = _objects(sidecar, "2026-01-12")
    slice_with = {**SLICE_PLAIN, "tracks": {"market": [*SLICE_PLAIN["tracks"]["market"], *objs]}}
    plain = gr.build(SLICE_PLAIN)
    with_teaching = gr.build(slice_with, teaching_card="2026-01-12-teaching-card.svg")
    # 逐轨事实里没有教学对象（它们不按 object_type｜k=v 摊开），单独成段。
    assert with_teaching.facts["market"] == plain.facts["market"]
    assert with_teaching.teaching and with_teaching.teaching_card == "2026-01-12-teaching-card.svg"
    rendered = gr.render(with_teaching)
    assert "## 授课框架读数（只摆读数，不下结论；不出名单）" in rendered and "![上证指数 · 授课框架读数](2026-01-12-teaching-card.svg)" in rendered
    assert rendered.index("## 授课框架读数") < rendered.index("## 判读")  # 读数在前，判读（待母本）紧随
    assert "- 待授课框架 v0（G-01）落地；母本由人写，此处不生成推断。" in rendered
    assert gr.lint_output(rendered) == []
    # 没有教学对象：既没有这一段，to_dict 里也只是空值；卡片名不会被误挂上去。
    assert plain.teaching == [] and plain.teaching_card is None and "授课框架读数" not in gr.render(plain)
    assert gr.build(SLICE_PLAIN, teaching_card="x.svg").teaching_card is None


def test_resolve_teaching_db_prefers_argument_then_env_and_ignores_missing_files(sidecar: Path, tmp_path: Path) -> None:
    assert gr.resolve_teaching_db(None) is None
    assert gr.resolve_teaching_db(sidecar) == sidecar
    assert gr.resolve_teaching_db(tmp_path / "missing.duckdb") is None
    with mock.patch.dict(os.environ, {gr.ENV_TEACHING_DB: str(sidecar)}):
        assert gr.resolve_teaching_db(None) == sidecar
        assert gr.resolve_teaching_db(tmp_path / "missing.duckdb") is None  # 显式参数优先，哪怕它不存在也不回落到环境变量


def test_write_teaching_card_writes_only_when_the_slice_has_teaching_objects(sidecar: Path, tmp_path: Path) -> None:
    out = tmp_path / "exports" / "2026-01-12-teaching-card.svg"
    assert gr.write_teaching_card(sidecar, "2026-01-12", SLICE_PLAIN, out) is None and not out.exists()
    slice_with = {**SLICE_PLAIN, "tracks": {"market": [*SLICE_PLAIN["tracks"]["market"], *_objects(sidecar, "2026-01-12")]}}
    assert gr.write_teaching_card(sidecar, "2026-01-12", slice_with, out) == "2026-01-12-teaching-card.svg"
    assert out.read_text(encoding="utf-8").startswith("<svg ")
