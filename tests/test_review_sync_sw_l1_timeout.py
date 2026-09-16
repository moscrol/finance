"""申万一必须吃 heavy_timeout：300s 在 hist 窗口上连炸过三晚。"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "skills" / "daily-full-review" / "scripts" / "run_review_sync.py"
    spec = importlib.util.spec_from_file_location("run_review_sync_timeout_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preflight_local_plan_skips_fupanhui_checks():
    """plan=local 零复盘会请求：preflight 不得发起 CDP/登录探测，也不得报这两类问题。"""
    module = _load()
    with patch.object(
        module.urllib.request, "urlopen",
        side_effect=AssertionError("local 计划不应发起 CDP/复盘会探测"),
    ):
        problems = module.preflight(require_fupanhui=False)
    assert not any(("CDP" in p) or ("fupanhui" in p) for p in problems)


def test_sw_l1_uses_heavy_timeout_index_stays_light():
    module = _load()
    recorded: list[tuple[str, int]] = []

    def fake_run_step(label, argv, timeout):
        recorded.append((label, timeout))
        return {"label": label, "status": "ok", "code": 0, "elapsed": 0.1}

    with patch.object(module, "run_step", side_effect=fake_run_step):
        plan = dict(module.build_plan("2026-08-20", timeout=300, heavy_timeout=600))
        plan["sw-l1-daily"]()
        plan["index-daily"]()

    assert ("sw-l1-daily", 600) in recorded
    assert ("index-daily", 300) in recorded
