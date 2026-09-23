"""整库「改前快照」必须走 clone_to_staging（APFS clonefile），不能各处自写 shutil.copy2。

背景：2026-09-23 盘上静置 20 份 3.4 GB 的整库拷贝（68 GB），全是修库 / 门禁 / 基线导出
的只读快照。同卷 `cp -c` 是 copy-on-write 克隆：秒级完成、初始零额外占盘。
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_feature_store import db  # noqa: E402
from scripts import db_baseline_export  # noqa: E402
from scripts import db_delta_pull  # noqa: E402

DATE = "2026-07-10"


def _build(path: Path, val: int) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute("create table fact_a (trade_date varchar, val integer)")
        con.execute("insert into fact_a values (?, ?)", [DATE, val])
    finally:
        con.close()


def test_clone_is_bytewise_identical_and_reports_method(tmp_path):
    src = tmp_path / "src.duckdb"
    _build(src, 7)
    dst = tmp_path / "dst.duckdb"
    info = db.clone_to_staging(src, dst)
    assert info["method"] in ("clonefile", "copy")
    assert dst.read_bytes() == src.read_bytes()
    assert info["bytes"] == dst.stat().st_size
    con = duckdb.connect(str(dst), read_only=True)
    try:
        assert con.execute("select val from fact_a").fetchone() == (7,)
    finally:
        con.close()


def test_baseline_export_snapshot_goes_through_clone(tmp_path, monkeypatch):
    calls: list[tuple[Path, Path]] = []
    real = db.clone_to_staging

    def spy(source, dest):
        calls.append((Path(source), Path(dest)))
        return real(source, dest)

    monkeypatch.setattr(db_baseline_export, "_clone_db", spy)
    src = tmp_path / "src.duckdb"
    _build(src, 1)
    out = tmp_path / "baseline.zip"
    manifest = db_baseline_export.export_baseline(str(src), str(out), DATE)
    assert [c[0] for c in calls] == [src]
    with zipfile.ZipFile(out) as archive:
        assert manifest["db_file"] in archive.namelist()


def test_delta_pull_rollback_copy_goes_through_clone(tmp_path, monkeypatch):
    calls: list[tuple[Path, Path]] = []
    real = db.clone_to_staging

    def spy(source, dest):
        calls.append((Path(source), Path(dest)))
        return real(source, dest)

    monkeypatch.setattr(db_delta_pull, "_clone_db", spy)
    src = tmp_path / "src.duckdb"
    _build(src, 7)
    baseline_zip = tmp_path / f"mfs-baseline-{DATE}.zip"
    db_baseline_export.export_baseline(str(src), str(baseline_zip), DATE)
    target = tmp_path / "target.duckdb"
    _build(target, 1)  # 目标库已存在 → 恢复基线前要留 .baseline-rollback（成功后 restore 自己会删掉它）
    db_delta_pull.restore_baseline(str(baseline_zip), str(target))
    assert calls == [(target, Path(str(target) + ".baseline-rollback"))]
    con = duckdb.connect(str(target), read_only=True)
    try:
        assert con.execute("select val from fact_a").fetchone() == (7,)
    finally:
        con.close()
