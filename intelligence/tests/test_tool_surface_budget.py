"""工具面预算（2026-10-01）：给模型看的工具说明只许变小、不许悄悄长回去。

首测 8 个工具 35,939 字符，finance_query 占 89%；其中字段名在 schema 里按「全部
dataset 的并集」列了五遍（10,742 字符），信息却严格少于按表列出的字段表。
去重后 24,489 字符。这里钉住三件事：并集枚举不许回来、按表字段表必须完整、
总量不超过预算（棘轮：真要加，先改预算并在 PR 里说明换来了什么）。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from intelligence.services import episode_tools, finance_query

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("tool_surface_report", REPO / "scripts" / "tool_surface_report.py")
assert _spec and _spec.loader
tool_surface_report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool_surface_report)

# 棘轮预算（字符）。当前读数 finance_query≈20.5k、全部≈24.5k，留约 10% 余量。
FINANCE_QUERY_BUDGET = 22_500
TOTAL_SURFACE_BUDGET = 27_000
_ALLOWED_ENUM_PATHS = {
    ("properties", "dataset"),
    ("properties", "filters", "items", "properties", "op"),
    ("properties", "order_by", "items", "properties", "direction"),
}


def _enum_paths(node, path=()):
    if isinstance(node, dict):
        if "enum" in node:
            yield path
        for key, value in node.items():
            yield from _enum_paths(value, (*path, key))
    elif isinstance(node, list):
        for value in node:
            yield from _enum_paths(value, path)


def test_finance_query_schema_has_no_union_field_enums() -> None:
    paths = set(_enum_paths(episode_tools._agent_finance_parameters()))
    assert paths <= _ALLOWED_ENUM_PATHS, f"并集字段枚举又回来了：{sorted(paths - _ALLOWED_ENUM_PATHS)}"


def test_per_dataset_field_table_is_complete() -> None:
    """去掉并集枚举的前提：每张表的每个字段都在按表字段表里，且归属正确。"""

    hint = finance_query.dataset_field_hint()
    sections = dict(part.split(": ", 1) for part in hint.split("；"))
    assert set(sections) == set(finance_query._DATASETS)
    for name, definition in finance_query._DATASETS.items():
        dims_part, metrics_part = sections[name].split("; ")
        dims = set(dims_part.removeprefix("dimensions=").split(",")) - {""}
        metrics = set(metrics_part.removeprefix("metrics=").split(",")) - {""}
        assert dims == set(definition.dimensions), name
        assert metrics == set(definition.metrics), name


def test_field_slots_point_the_model_at_the_per_dataset_table() -> None:
    properties = episode_tools._agent_finance_parameters()["properties"]
    for slot in ("metrics", "dimensions"):
        assert "可用字段" in properties[slot]["description"], slot


def test_tool_surface_stays_within_budget() -> None:
    for question_type in ("market_watch", "stock_deep_dive"):
        report = tool_surface_report.measure(question_type)
        by_name = {row["name"]: row for row in report["tools"]}
        assert by_name["finance_query"]["total_chars"] <= FINANCE_QUERY_BUDGET, by_name["finance_query"]
        assert report["total_chars"] <= TOTAL_SURFACE_BUDGET, report
