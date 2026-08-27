"""export-increment 是备份产物：读 staging 库、失败降告警，不得阻塞换名。

失败形状（2026-08-27 18:42 夜跑实测）：staging 架构下 sync/双门全绿，
export_increment.py 不吃 ``MARKET_FEATURE_STORE_DB``、按默认路径读**生产库**——
换名前生产库必然没有当日行 → 「无数据」rc=1 → `run_release_steps` 把它算进
全绿判定 → wrapper 不换名 → **生产库停在昨日**（readiness `market_data_consistency`
红）。备份步失败阻塞数据链 = 本末倒置；26g（08-26）人工已判它「告警级」，
本文件把该判断固化进代码。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "skills" / "daily-full-review" / "scripts" / "run_review_sync.py"
    spec = importlib.util.spec_from_file_location("run_review_sync_export_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_run_step(fail_labels: set[str], recorded: list):
    def fake(label, argv, timeout):
        recorded.append((label, argv))
        status = "fail" if label in fail_labels else "ok"
        return {"label": label, "status": status, "code": 1 if status == "fail" else 0, "elapsed": 0.1}

    return fake


def test_export_fail_does_not_block_release():
    """备份失败 → 告警级：run_release_steps 仍返回 True（允许换名）。"""
    module = _load()
    recorded: list = []
    with patch.object(
        module, "run_step", side_effect=_fake_run_step({"export-increment"}, recorded)
    ):
        results, ok = module.run_release_steps("2026-08-27", timeout=300)
    assert ok is True
    assert [r["label"] for r in results] == [
        "same-day-gate",
        "cross-day-gate",
        "export-increment",
    ]


def test_gate_fail_still_blocks_release():
    """质量门失败仍然 fail-closed——降级只给备份步，不给门。"""
    module = _load()
    recorded: list = []
    with patch.object(
        module, "run_step", side_effect=_fake_run_step({"same-day-gate"}, recorded)
    ):
        _, ok = module.run_release_steps("2026-08-27", timeout=300)
    assert ok is False
    recorded.clear()
    with patch.object(
        module, "run_step", side_effect=_fake_run_step({"cross-day-gate"}, recorded)
    ):
        _, ok = module.run_release_steps("2026-08-27", timeout=300)
    assert ok is False


def test_export_reads_staging_db_when_env_set(monkeypatch):
    """staging 语境（MARKET_FEATURE_STORE_DB 已设）下 export 必须读那个库——
    当日数据在 staging 里，读默认生产路径必空。"""
    module = _load()
    recorded: list = []
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", "/tmp/staging-test.duckdb")
    with patch.object(module, "run_step", side_effect=_fake_run_step(set(), recorded)):
        module.run_release_steps("2026-08-27", timeout=300)
    export_argv = next(argv for label, argv in recorded if label == "export-increment")
    assert "--db" in export_argv
    assert export_argv[export_argv.index("--db") + 1] == "/tmp/staging-test.duckdb"


def test_export_uses_default_db_without_env(monkeypatch):
    """无环境变量（手动直跑生产库语境）保持既有默认路径行为。"""
    module = _load()
    recorded: list = []
    monkeypatch.delenv("MARKET_FEATURE_STORE_DB", raising=False)
    with patch.object(module, "run_step", side_effect=_fake_run_step(set(), recorded)):
        module.run_release_steps("2026-08-27", timeout=300)
    export_argv = next(argv for label, argv in recorded if label == "export-increment")
    assert "--db" not in export_argv
