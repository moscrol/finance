"""默认选盘面快照时，文件名最新 ≠ 内容可用。

背景：收盘后到夜间管线跑完之间，导出器会为当日写出一个 found=False、
candidate_count=0 的文件（warnings 全是 market daily row not found）。
旧实现取 sorted(...)[-1]，会选中这个空文件，工作台于是答"没有主线"——
而前一交易日明明有 50 个候选。这比快照过期更糟：过期至少还能答，空快照
是静默答空。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services import retrieval_cache
from intelligence.services.ask import load_theme_candidates


def _write(base: Path, date: str, candidates: int, *, found: bool = True) -> None:
    (base / f"{date}-theme-candidates.json").write_text(
        json.dumps(
            {
                "found": found,
                "trade_date": date,
                "candidate_count": candidates,
                "candidates": [{"canonical_concept": f"题材{i}"} for i in range(candidates)],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """快照缓存按 path+mtime 键，跨用例复用会串味。"""
    monkeypatch.setattr(retrieval_cache, "shared_cache", lambda: retrieval_cache.RetrievalCache())


def test_empty_latest_snapshot_falls_back_to_last_usable_day(tmp_path: Path) -> None:
    _write(tmp_path, "2026-07-29", 50)
    _write(tmp_path, "2026-07-30", 0, found=False)

    loaded = load_theme_candidates(tmp_path, None)

    assert loaded["found"] is True
    assert loaded["doc"]["trade_date"] == "2026-07-29"
    assert loaded["doc"]["candidate_count"] == 50
    # 回退必须说出口，否则用户以为看到的是今天的盘面。
    assert any("2026-07-30" in w and "2026-07-29" in w for w in loaded["warnings"])


def test_usable_latest_snapshot_wins_and_reports_no_staleness(tmp_path: Path) -> None:
    _write(tmp_path, "2026-07-29", 50)
    _write(tmp_path, "2026-07-30", 42)

    loaded = load_theme_candidates(tmp_path, None)

    assert loaded["doc"]["trade_date"] == "2026-07-30"
    assert loaded["warnings"] == []


def test_explicit_date_is_never_second_guessed(tmp_path: Path) -> None:
    """显式点名某天就给那天——回测/复盘要的是那天的真实快照，空也得是空。"""
    _write(tmp_path, "2026-07-29", 50)
    _write(tmp_path, "2026-07-30", 0, found=False)

    loaded = load_theme_candidates(tmp_path, "2026-07-30")

    assert loaded["doc"]["trade_date"] == "2026-07-30"
    assert loaded["doc"]["candidate_count"] == 0


def test_all_snapshots_empty_still_returns_latest_with_reason(tmp_path: Path) -> None:
    _write(tmp_path, "2026-07-29", 0, found=False)
    _write(tmp_path, "2026-07-30", 0, found=False)

    loaded = load_theme_candidates(tmp_path, None)

    assert loaded["doc"]["trade_date"] == "2026-07-30"
    assert any("均无候选" in w for w in loaded["warnings"])


def test_corrupt_snapshot_is_skipped_not_fatal(tmp_path: Path) -> None:
    _write(tmp_path, "2026-07-29", 50)
    (tmp_path / "2026-07-30-theme-candidates.json").write_text("{ 截断的 json", encoding="utf-8")

    loaded = load_theme_candidates(tmp_path, None)

    assert loaded["doc"]["trade_date"] == "2026-07-29"
