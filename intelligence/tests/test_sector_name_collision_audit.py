"""板块撞名审计：判据是「重叠」，不是「代码数」。离线锁，自建小库。

生产实锤 run_20260821_114642_385979：同名多代码并存 → 按 sector_name 查
返回同日多行 → 预取把矛盾当事实投递 → 模型只能写区间 → 判官判编造 →
摘掉两个必填输出。脏在数据层，代价在答案层，隔着四层。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None

pytestmark = pytest.mark.skipif(duckdb is None, reason="duckdb 不可用")

_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "audit_sector_name_collisions.py"


def _module():
    spec = importlib.util.spec_from_file_location("audit_collisions", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _db(path: Path, rows: list[tuple]) -> Path:
    con = duckdb.connect(str(path))
    con.execute(
        "create table fact_sector_daily ("
        "trade_date date, sector_name varchar, sector_ts_code varchar)"
    )
    con.executemany(
        "insert into fact_sector_daily values (?, ?, ?)", rows
    )
    con.close()
    return path


def test_overlapping_codes_are_flagged(tmp_path: Path) -> None:
    """同一天两个代码都有行 → 撞名，重叠天数计对。"""

    db = _db(tmp_path / "a.duckdb", [
        ("2026-08-07", "PCB", "885959.TI"),
        ("2026-08-07", "PCB", "990026.FP"),
        ("2026-08-06", "PCB", "885959.TI"),
        ("2026-08-06", "PCB", "990026.FP"),
    ])
    found = _module()._collisions(db)
    assert "PCB" in found
    assert found["PCB"]["overlapping_days"] == 2
    assert found["PCB"]["codes"] == ["885959.TI", "990026.FP"]


def test_clean_handover_is_not_flagged(tmp_path: Path) -> None:
    """正常换代：旧代码停、新代码起，两段不重叠 → **不得**报撞名。

    只按「代码数 > 1」判会把每一次正常换代都误报成故障，
    门禁会变成永久红灯，然后被所有人无视。
    """

    db = _db(tmp_path / "b.duckdb", [
        ("2026-07-01", "光伏", "OLD.TI"),
        ("2026-07-02", "光伏", "OLD.TI"),
        ("2026-08-01", "光伏", "NEW.FP"),
        ("2026-08-02", "光伏", "NEW.FP"),
    ])
    assert "光伏" not in _module()._collisions(db)


def test_single_code_is_not_flagged(tmp_path: Path) -> None:
    db = _db(tmp_path / "c.duckdb", [
        ("2026-08-07", "PCB概念", "990027.FP"),
        ("2026-08-06", "PCB概念", "990027.FP"),
    ])
    assert _module()._collisions(db) == {}


def _run_main(mod, monkeypatch, db: Path, baseline: Path) -> int:
    monkeypatch.setattr(mod, "BASELINE_PATH", baseline)
    monkeypatch.setattr(mod, "_db_path", lambda: db)
    monkeypatch.setattr(sys, "argv", ["audit_sector_name_collisions.py"])
    return mod.main()


def test_empty_baseline_flags_all_collisions(tmp_path: Path, monkeypatch, capsys) -> None:
    """无 baseline → 现存重叠全报，exit 1。按代码数判会把换代也报进来。"""

    db = _db(tmp_path / "d.duckdb", [
        ("2026-08-07", "PCB", "885959.TI"),
        ("2026-08-07", "PCB", "990026.FP"),
        ("2026-07-01", "光伏", "OLD.TI"),
        ("2026-08-01", "光伏", "NEW.FP"),
    ])
    baseline = tmp_path / "baseline.json"
    baseline.write_text("{}\n", encoding="utf-8")
    assert _run_main(_module(), monkeypatch, db, baseline) == 1
    out = capsys.readouterr().out
    assert "PCB" in out
    assert "光伏" not in out


def test_matching_baseline_passes(tmp_path: Path, monkeypatch) -> None:
    db = _db(tmp_path / "e.duckdb", [
        ("2026-08-07", "PCB", "885959.TI"),
        ("2026-08-07", "PCB", "990026.FP"),
    ])
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"PCB": {"codes": ["885959.TI", "990026.FP"], "overlapping_days": 1}})
        + "\n",
        encoding="utf-8",
    )
    assert _run_main(_module(), monkeypatch, db, baseline) == 0


def test_worsened_overlap_is_flagged(tmp_path: Path, monkeypatch, capsys) -> None:
    db = _db(tmp_path / "f.duckdb", [
        ("2026-08-07", "小金属", "A"),
        ("2026-08-07", "小金属", "B"),
        ("2026-08-06", "小金属", "A"),
        ("2026-08-06", "小金属", "B"),
    ])
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"小金属": {"codes": ["A", "B"], "overlapping_days": 1}}) + "\n",
        encoding="utf-8",
    )
    assert _run_main(_module(), monkeypatch, db, baseline) == 1
    out = capsys.readouterr().out
    assert "恶化" in out
    assert "1 → 2" in out


def test_unreachable_db_skips_and_says_not_pass(monkeypatch, capsys) -> None:
    mod = _module()
    monkeypatch.setattr(mod, "_db_path", lambda: None)
    monkeypatch.setattr(sys, "argv", ["audit_sector_name_collisions.py"])
    assert mod.main() == 0
    assert "不是通过" in capsys.readouterr().out
