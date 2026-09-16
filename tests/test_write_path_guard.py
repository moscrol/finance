"""生产库写入守卫：无 --direct 必须 fail closed；有旗标必须留收据。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from market_feature_store import write_path
from market_feature_store.cli import cmd_daily_full_exec, cmd_daily_update


def test_staging_and_tmp_are_not_canonical_production(tmp_path):
    staging = tmp_path / "market_feature_store.duckdb.staging"
    other = tmp_path / "market_feature_store.duckdb"
    assert write_path.is_canonical_production(staging) is False
    assert write_path.is_canonical_production(other) is False
    assert write_path.production_write_blocked(direct=False, path=other) is None


def test_canonical_production_refuses_without_direct():
    reason = write_path.production_write_blocked(
        direct=False, path=write_path.canonical_production_path()
    )
    assert reason is not None
    assert "--direct" in reason
    assert "run_review_sync.py" in reason
    assert write_path.production_write_blocked(
        direct=True, path=write_path.canonical_production_path()
    ) is None


def test_daily_update_refuses_canonical_production_without_direct():
    args = SimpleNamespace(
        trade_date="2026-08-20",
        chart_table=None,
        skip_long=False,
        no_chart=True,
        stock_source="snapshot",
        status_json=None,
        direct=False,
    )
    with (
        patch(
            "market_feature_store.sync.sync_daily_full.preflight_daily_update",
            return_value={"ok": True, "problems": []},
        ),
        patch(
            "market_feature_store.write_path.is_canonical_production",
            return_value=True,
        ),
        patch("market_feature_store.sync.sync_daily_full.run_daily_update") as update,
    ):
        rc = cmd_daily_update(args)
    assert rc == 2
    update.assert_not_called()


def test_daily_update_direct_writes_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(write_path, "DIRECT_RECEIPT_DIR", tmp_path)
    args = SimpleNamespace(
        trade_date="2026-08-20",
        chart_table=None,
        skip_long=False,
        no_chart=True,
        stock_source="snapshot",
        status_json=None,
        direct=True,
    )
    with (
        patch(
            "market_feature_store.sync.sync_daily_full.preflight_daily_update",
            return_value={"ok": True, "problems": []},
        ),
        patch(
            "market_feature_store.write_path.is_canonical_production",
            return_value=True,
        ),
        patch(
            "market_feature_store.sync.sync_daily_full.run_daily_update",
            return_value={
                "trade_date": "2026-08-20",
                "ok": True,
                "steps": [],
                "validation": {"ok": True, "missing_fields": [], "tables": []},
            },
        ),
        patch.object(write_path, "connect", side_effect=RuntimeError("no db")),
    ):
        rc = cmd_daily_update(args)
    assert rc == 0
    receipts = list(tmp_path.glob("direct-write-2026-08-20-*.json"))
    assert len(receipts) == 1
    assert "direct-prod" in receipts[0].read_text(encoding="utf-8")


def test_run_daily_update_schedules_features():
    from market_feature_store.sync import sync_daily_full

    assert "_run_compute_features" in sync_daily_full.run_daily_update.__code__.co_names


def test_daily_full_exec_refuses_canonical_production_without_direct():
    args = SimpleNamespace(
        trade_date="2026-08-20",
        chart_table=None,
        skip_long=False,
        stock_source="snapshot",
        status_json=None,
        direct=False,
    )
    with (
        patch(
            "market_feature_store.write_path.is_canonical_production",
            return_value=True,
        ),
        patch("market_feature_store.sync.sync_daily_full.run_daily_full") as full,
    ):
        rc = cmd_daily_full_exec(args)
    assert rc == 2
    full.assert_not_called()


# ---------------------------------------------------------------------------
# QC G1（2026-09-13）：生产库身份不得随代码检出位置改变
# ---------------------------------------------------------------------------


def test_worktree_code_recognizes_main_tree_production(tmp_path, monkeypatch):
    """代码在附属 worktree 跑、真库在主检出树：仍必须认出并拦下。"""
    fake_main = tmp_path / "main-checkout"
    prod = fake_main / "db" / "market_feature_store.duckdb"
    prod.parent.mkdir(parents=True)
    prod.touch()
    monkeypatch.setattr(write_path, "_main_checkout_dir", lambda: fake_main)
    monkeypatch.delenv("MARKET_FEATURE_STORE_PRODUCTION_DB", raising=False)
    assert write_path.is_canonical_production(prod) is True
    reason = write_path.production_write_blocked(False, prod)
    assert reason is not None and "--direct" in reason
    # staging 副本与无关路径仍不误判
    assert write_path.is_canonical_production(
        prod.with_name(prod.name + ".staging")
    ) is False
    assert write_path.is_canonical_production(tmp_path / "other.duckdb") is False


def test_env_pin_recognizes_production_across_clones(tmp_path, monkeypatch):
    """独立 clone 场景（git common dir 帮不到）用 env 显式钉。"""
    prod = tmp_path / "elsewhere" / "market_feature_store.duckdb"
    prod.parent.mkdir(parents=True)
    prod.touch()
    monkeypatch.setattr(write_path, "_main_checkout_dir", lambda: None)
    monkeypatch.setenv("MARKET_FEATURE_STORE_PRODUCTION_DB", str(prod))
    assert write_path.is_canonical_production(prod) is True
    assert write_path.production_write_blocked(False, prod) is not None


def test_candidates_degrade_to_package_relative_without_git(monkeypatch):
    """git 解析失败 → 候选集退化但不误判非生产路径。"""
    monkeypatch.setattr(write_path, "_main_checkout_dir", lambda: None)
    monkeypatch.delenv("MARKET_FEATURE_STORE_PRODUCTION_DB", raising=False)
    cands = write_path.canonical_production_candidates()
    assert write_path.canonical_production_path() in cands
