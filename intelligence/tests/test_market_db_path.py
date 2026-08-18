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


@pytest.mark.parametrize("var", ["FINANCE_WS", "FINANCE_ROOT"])
def test_every_documented_data_root_var_is_honored(monkeypatch, tmp_path, var) -> None:
    monkeypatch.setenv(var, str(tmp_path))

    assert paths.default_market_db_path().parent == tmp_path / "db"


def test_workbench_repo_root_loses_to_finance_ws(monkeypatch, tmp_path) -> None:
    """launcher 双设时数据根必须是私有仓，不能是代码快照。

    现状（修前）``data_repo_root`` 把 ``WORKBENCH_REPO_ROOT`` 排在 ``FINANCE_WS``
    前面，生产启动器正好双设，盘面库和 exports 都解析进没有 ``db/`` 的快照树。
    """
    code = tmp_path / "code-snapshot"
    data = tmp_path / "private-data"
    monkeypatch.setenv("WORKBENCH_REPO_ROOT", str(code))
    monkeypatch.setenv("FINANCE_WS", str(data))

    assert paths.data_repo_root() == data
    assert paths.default_market_db_path() == data / "db" / "market_feature_store.duckdb"


def test_workbench_repo_root_alone_is_not_a_data_root(monkeypatch, tmp_path) -> None:
    """``WORKBENCH_REPO_ROOT`` 是代码根概念，单独出现时不得被当成数据根。"""
    monkeypatch.setenv("WORKBENCH_REPO_ROOT", str(tmp_path / "code-snapshot"))
    code_root = Path(paths.__file__).resolve().parent.parent

    assert paths.data_repo_root() == code_root
    assert paths.default_market_db_path() == code_root / "db" / "market_feature_store.duckdb"


def test_ask_types_data_repo_root_is_the_paths_function() -> None:
    """两处分叉正是这次没被测试拦住的原因；收口后必须是同一个函数。"""
    from intelligence.services import ask_types

    assert ask_types._data_repo_root is paths.data_repo_root


def test_daily_review_and_research_owner_call_default_market_db_path() -> None:
    """handoff 六方：这两个 skill 必须走修复后的数据根函数，不能拼代码根。"""
    root = Path(__file__).resolve().parents[1]
    for rel in (
        "workbench_skills/daily_review.py",
        "workbench_skills/research_owner.py",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        assert "default_market_db_path()" in text, rel
        assert 'context.repo_root / "db"' not in text, rel


def test_run_ask_daily_projection_uses_data_repo_root() -> None:
    """app.py REPO_ROOT 是代码根；日报投影读 exports，必须改走数据根函数。"""
    text = (
        Path(__file__).resolve().parents[1] / "api" / "app.py"
    ).read_text(encoding="utf-8")
    assert "daily_projection_modules(" in text
    assert "data_repo_root()" in text
    assert "daily_projection_modules(\n                repo_root\n            )" not in text


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
