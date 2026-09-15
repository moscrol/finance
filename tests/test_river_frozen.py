"""冻结快照当内容版本源（OPT-01 第二刀）的契约测试。

全部用**合成库 + 真封印函数**：反例行「T 日 1% 被 T+7 修订成 9%」在生产里等不到，
必须构造；快照封印走 `pit_snapshot` 自己的 `_canonical_bytes / _seal_manifest`，
不是手搓相似物——绕开真封印造出来的夹具证不了验证器（fixture 复刻不了封印链的
失败分支）。

钉四件事（补强 spec OPT-01 验收 1 / 3 的机器化）：
1. T 日原值与 T+7 修订并存时，`slice(T, C=T, frozen)` 返回**原值**且 strict；
   不带版本源时同一查询**不得**返回修订值并标 strict（第一刀行为：降档/滤除）。
2. `slice(T, C=T+7, frozen)` 看到修订值；`list_content_versions` 给出两版本与替代关系。
3. 封印任何一环被破坏（gz 内容被改）→ 抛 FrozenSnapshotError，不静默回退。
4. 无 ≤C 快照 → 如实回落当前库并在 content_source 里声明；同参两次调用逐字段相同。
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import duckdb
import pytest

from intelligence.eval.pit_snapshot import _canonical_bytes, freeze_daily_snapshot
from intelligence.services.river import slice_river
from intelligence.services.river_frozen import (
    FrozenSnapshotError,
    best_snapshot_for,
    connect_frozen,
    list_content_versions,
)

T = "2026-09-01"
T7 = "2026-09-08"
SECTOR = "885001.FP"
SECTOR_NAME = "测试板块"
REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "market_feature_store" / "schema.sql"


def _build_live_db(path: Path) -> None:
    """合成主库：真 schema 全量 DDL + T 日**当时**的行（pct_chg=1.0）。"""
    con = duckdb.connect(str(path))
    try:
        con.execute(SCHEMA.read_text(encoding="utf-8"))
        con.execute(
            "INSERT INTO fact_market_daily (trade_date, market_stage, total_amount, updated_at, source)"
            " VALUES (?, '上行', 21000.0, ?, 'test')",
            [T, f"{T} 18:00:00"],
        )
        con.execute(
            "INSERT INTO fact_sector_daily_generation (trade_date, sector_universe_snapshot_id,"
            " sector_ts_code, sector_name, pct_chg, amount, diff_ratio, source, updated_at)"
            " VALUES (?, 'legacy', ?, ?, 1.0, 500.5, 11.0, 'test', ?)",
            [T, SECTOR, SECTOR_NAME, f"{T} 18:00:00"],
        )
    finally:
        con.close()


def _revise_live_db(path: Path) -> None:
    """模拟 T+7 的重发布：同一行被修订成 9.0，updated_at 被推到 T+7（第一刀钉过的现实）。"""
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "UPDATE fact_sector_daily_generation SET pct_chg = 9.0, updated_at = ?"
            " WHERE trade_date = ? AND sector_ts_code = ?",
            [f"{T7} 18:30:00", T, SECTOR],
        )
        con.execute(
            "UPDATE fact_market_daily SET updated_at = ? WHERE trade_date = ?",
            [f"{T7} 18:30:00", T],
        )
        con.execute(
            "INSERT INTO fact_market_daily (trade_date, market_stage, total_amount, updated_at, source)"
            " VALUES (?, '上行', 22000.0, ?, 'test')",
            [T7, f"{T7} 18:30:00"],
        )
    finally:
        con.close()


@pytest.fixture(scope="module")
def env(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """先装「当时」→ 用**真冻结入口**拍 S=T → 修订 → 再拍 S=T+7。

    封印走 `freeze_daily_snapshot` 本身，不手搓 manifest——绕开真写入路径造的
    夹具校验不了封印链（validate 演进一次，手搓件就变成过期的相似物）。
    """
    base = tmp_path_factory.mktemp("river-frozen")
    db = base / "live.duckdb"
    snaps = base / "pit-snapshots"
    _build_live_db(db)
    freeze_daily_snapshot(db, as_of=T, finance_root=REPO, kb_root=REPO, out_dir=snaps)
    _revise_live_db(db)
    freeze_daily_snapshot(db, as_of=T7, finance_root=REPO, kb_root=REPO, out_dir=snaps)
    ck = base / "checkpoints.jsonl"
    ck.write_text("", encoding="utf-8")
    return {"db": db, "snaps": snaps, "ck": ck}


def _slice(env: dict, cutoff: str, frozen: bool):
    return slice_river(
        T,
        SECTOR,
        knowledge_cutoff=cutoff,
        allow_hindsight=cutoff > T,
        db_path=env["db"],
        checkpoints_path=env["ck"],
        frozen_snapshot_root=env["snaps"] if frozen else None,
    )


def _sector_payload(sl) -> dict:
    market = sl.tracks["market"]
    assert isinstance(market, list), f"盘面轨应有对象，得到 {market}"
    for obj in market:
        if obj.ref.startswith("fact_sector_daily:"):
            return obj.payload
    raise AssertionError("盘面轨没有板块量价对象")


def test_回放当时_取回原值且strict(env: dict) -> None:
    sl = _slice(env, cutoff=T, frozen=True)
    assert sl.content_source and sl.content_source["kind"] == "frozen_snapshot"
    assert sl.content_source["as_of"] == T
    assert _sector_payload(sl)["pct_chg"] == 1.0, "T 日当时看到的是 1.0，不是后来修订的 9.0"
    assert sl.pit_grade == "strict", "快照行的 updated_at 是当时值（≤C），应恢复 strict"


def test_T7回看_看到修订值(env: dict) -> None:
    sl = _slice(env, cutoff=T7, frozen=True)
    assert sl.content_source and sl.content_source["as_of"] == T7
    assert _sector_payload(sl)["pct_chg"] == 9.0, "C=T+7 时修订已发生，应看到新版本"


def test_不带版本源_修订值不得冒充当时strict(env: dict) -> None:
    """第一刀的行为回归：主库行 updated_at=T+7 > C=T，降档；require_strict 下滤除。"""
    sl = _slice(env, cutoff=T, frozen=False)
    assert sl.content_source is None
    assert sl.pit_grade == "trade_date_only", "修订后的行不能标 strict——这正是第一刀堵的谎"
    strict = slice_river(
        T, SECTOR, knowledge_cutoff=T, require_strict=True,
        db_path=env["db"], checkpoints_path=env["ck"],
    )
    market = strict.tracks["market"]
    from intelligence.services.river import Gap

    assert isinstance(market, Gap) and market.reason == "pit_filtered"


def test_无更早快照_如实回落当前库(env: dict) -> None:
    early = "2026-08-15"
    sl = slice_river(
        early, SECTOR, db_path=env["db"], checkpoints_path=env["ck"],
        frozen_snapshot_root=env["snaps"],
    )
    assert sl.content_source and sl.content_source["kind"] == "live"
    assert "无 ≤" in sl.content_source["reason"]
    assert best_snapshot_for(env["snaps"], early) is None


def test_快照早于as_of_回落主库而非错报实体不存在(env: dict) -> None:
    """[as_of, C] 内没有快照、更早的有：快照的回看窗里不可能有 as_of 的行，
    用它跑会把「快照没拍到」错报成 entity_unresolved——必须回落主库并声明。"""
    later = "2026-09-09"  # 最近快照是 T7=09-08 < as_of
    sl = slice_river(
        later, SECTOR, db_path=env["db"], checkpoints_path=env["ck"],
        frozen_snapshot_root=env["snaps"],
    )
    assert sl.content_source and sl.content_source["kind"] == "live"
    assert "as_of 之前" in sl.content_source["reason"]


def test_封印被破坏_抛错不回退(env: dict, tmp_path: Path) -> None:
    import shutil

    broken = tmp_path / "broken-snaps"
    shutil.copytree(env["snaps"], broken)
    gz = broken / f"{T}.snapshot.json.gz"
    # 改内容重新 gzip：compressed_sha256 必然对不上——验证器必须在第一环就红
    tampered = json.loads(gzip.decompress(gz.read_bytes()))
    tampered["data"]["fact_sector_daily"][0]["pct_chg"] = 5.0
    gz.chmod(0o644)
    gz.write_bytes(gzip.compress(_canonical_bytes(tampered)))
    with pytest.raises(FrozenSnapshotError):
        slice_river(
            T, SECTOR, knowledge_cutoff=T, db_path=env["db"],
            checkpoints_path=env["ck"], frozen_snapshot_root=broken,
        )


def test_幂等_同参两次逐字段相同(env: dict) -> None:
    a = _slice(env, cutoff=T, frozen=True).to_dict()
    b = _slice(env, cutoff=T, frozen=True).to_dict()
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def test_版本史_两版本与替代关系可见(env: dict) -> None:
    out = list_content_versions(
        env["snaps"], "fact_sector_daily",
        {"trade_date": T, "sector_ts_code": SECTOR},
        db_path=env["db"],
    )
    assert len(out["versions"]) == 2, "1.0 → 9.0 应是两个内容版本"
    v1, v2 = out["versions"]
    assert v1["payload"]["pct_chg"] == 1.0 and v2["payload"]["pct_chg"] == 9.0
    assert v1["supersedes"] is None and v2["supersedes"] == v1["content_sha256"], "替代关系必须指向前一版"
    assert v1["first_seen_snapshot"] == T and v2["first_seen_snapshot"] == T7
    assert out["current"] is not None and out["current"]["pct_chg"] == 9.0, "主库当前值 = 修订值"


def test_快照覆盖集内缺表_空表不冒充当前库(env: dict) -> None:
    """SNAPSHOT_TABLES 内、这份快照没拍到的表：必须是空表（当时版本不可得），
    不能 VIEW 到当前库——否则今天的行会冒充「当时」。"""
    con = connect_frozen(env["snaps"], T, db_path=env["db"])
    try:
        n = con.execute("SELECT COUNT(*) FROM fact_stock_daily").fetchone()[0]
        assert n == 0
        kind = con.execute(
            "SELECT table_type FROM information_schema.tables"
            " WHERE table_catalog = 'frozen' AND table_name = 'fact_stock_daily'"
        ).fetchone()[0]
        assert kind == "BASE TABLE"
    finally:
        con.close()
