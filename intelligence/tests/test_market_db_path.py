"""盘面 DuckDB 默认路径必须跟随数据根，而不是代码根。

回归：18 处调用点原先写死 ``REPO_ROOT / "db" / "market_feature_store.duckdb"``，
其中 REPO_ROOT 是 runtime 代码快照根。库不在仓树内时整个盘面证据层静默消失——
实测 8 个真实问题全部命中"本轮没有连接本地市场数据"，同期 exports 因为走
DATA_REPO_ROOT 反而正常，两者不一致正是这个 bug 的表征。
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from intelligence import paths


@pytest.fixture(autouse=True)
def _clear_roots(monkeypatch):
    for name in (
        "MARKET_FEATURE_STORE_DB",
        "WORKBENCH_REPO_ROOT",
        "FINANCE_WS",
        "FINANCE_ROOT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_explicit_db_override_wins(monkeypatch, tmp_path) -> None:
    target = tmp_path / "custom" / "market.duckdb"
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(target))

    assert paths.default_market_db_path() == target


def test_db_follows_the_data_root_not_the_code_root(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FINANCE_WS", str(tmp_path))

    resolved = paths.default_market_db_path()

    assert resolved == tmp_path / "db" / "market_feature_store.duckdb"
    assert Path(paths.__file__).parent.parent not in resolved.parents


@pytest.mark.parametrize(
    "var", ["WORKBENCH_REPO_ROOT", "FINANCE_WS", "FINANCE_ROOT"]
)
def test_every_documented_data_root_var_is_honored(monkeypatch, tmp_path, var) -> None:
    monkeypatch.setenv(var, str(tmp_path))

    assert paths.default_market_db_path().parent == tmp_path / "db"


def test_explicit_override_beats_the_data_root(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "data-root"))
    target = tmp_path / "elsewhere" / "market.duckdb"
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(target))

    assert paths.default_market_db_path() == target


def test_falls_back_to_the_code_root_when_nothing_is_configured() -> None:
    resolved = paths.default_market_db_path()

    assert resolved.name == "market_feature_store.duckdb"
    assert resolved.parent.name == "db"


def test_market_modules_share_one_default(monkeypatch, tmp_path) -> None:
    """盘面模块必须解析到同一路径，否则盘面层会各读各的库。"""
    monkeypatch.setenv("FINANCE_WS", str(tmp_path))
    expected = tmp_path / "db" / "market_feature_store.duckdb"

    resolved = set()
    for name in (
        "intelligence.services.ask_types",
        "intelligence.services.ask_blocks",
        "intelligence.services.market_analogs",
        "intelligence.services.market_timeseries",
        "intelligence.services.market_moneyflow",
        "intelligence.services.market_dragon",
        "intelligence.services.market_midterm",
    ):
        module = importlib.reload(importlib.import_module(name))
        resolved.add(module.DEFAULT_MARKET_DB_PATH)

    assert resolved == {expected}
