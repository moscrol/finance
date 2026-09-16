"""本地自选股清单。

这份清单原来只存在于飞书多维表格，是那 5 个 skill 里唯一**没有本地副本**的东西
（指标都能从 fact_stock_daily 重算，清单不能——它是人的意图）。所以它必须有家、
可读可写、且不因为一个格式错误就整条链失效。
"""

from __future__ import annotations

import pytest

from market_feature_store import watchlist as wl


@pytest.fixture(autouse=True)
def _isolated_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_WATCHLIST_DIR", str(tmp_path / "watchlists"))


def test_roundtrip_preserves_order():
    wl.save_watchlist(["飞龙股份", "禾望电气", "芯源微"])
    assert wl.load_watchlist() == ["飞龙股份", "禾望电气", "芯源微"]


def test_comments_and_blank_lines_are_ignored():
    path = wl.watchlist_path("default")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# 这是说明\n飞龙股份\n\n  禾望电气  # 行尾注释\n\n# 末尾注释\n",
        encoding="utf-8",
    )
    assert wl.load_watchlist() == ["飞龙股份", "禾望电气"]


def test_duplicates_collapse_on_save_and_load():
    wl.save_watchlist(["甲", "甲", "乙", " 甲 "])
    assert wl.load_watchlist() == ["甲", "乙"]


def test_missing_file_returns_empty_not_error():
    """清单不存在不是异常——调用方自己决定是报错还是走空。"""
    assert wl.load_watchlist("还没建过") == []


def test_named_lists_are_separate():
    wl.save_watchlist(["甲"], name="default")
    wl.save_watchlist(["乙", "丙"], name="打板池")

    assert wl.load_watchlist("default") == ["甲"]
    assert wl.load_watchlist("打板池") == ["乙", "丙"]
    assert wl.list_watchlists() == ["default", "打板池"]


def test_path_traversal_rejected():
    """清单名来自命令行，别让它写到别处去。"""
    with pytest.raises(ValueError):
        wl.watchlist_path("../../etc/passwd")
    with pytest.raises(ValueError):
        wl.watchlist_path(".ssh/id_rsa")


def test_header_is_written_as_comments():
    path = wl.save_watchlist(["甲"], header="来源说明\n第二行")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# 来源说明\n# 第二行\n")
    assert wl.load_watchlist() == ["甲"]


def test_env_var_overrides_location(tmp_path, monkeypatch):
    target = tmp_path / "elsewhere"
    monkeypatch.setenv("FINANCE_WATCHLIST_DIR", str(target))
    path = wl.save_watchlist(["甲"])
    assert path.parent == target
