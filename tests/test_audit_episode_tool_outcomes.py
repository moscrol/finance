"""episode 工具审计：按题型 × 数据集拆 finance_query 调用，列出注册了却没被调用的数据集。

背景（2026-09-30 质检 P1「按路由收窄工具面」）：每轮都把 40 个数据集的 schema 发给模型，
收窄要拿「各题型实际调了哪些」的证据说话。本测试钉住口径，默认输出保持原样。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
REAL_RUNS = REPO / "docs/verification/2026-09-21-judge-mode-k3/evidence/production-verification/runs"


def _load():
    name = "audit_episode_tool_outcomes_under_test"
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / "audit_episode_tool_outcomes.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


audit_tool = _load()


def _fq(dataset_detail: str, status: str = "success") -> dict:
    return {"provider": "duckdb_semantic_query", "capability": "finance_query", "status": status, "detail": dataset_detail}


def _episode(root: Path, name: str, payload: dict | str) -> None:
    run = root / name
    run.mkdir(parents=True)
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    (run / "continuous-episode.json").write_text(text, encoding="utf-8")


@pytest.fixture()
def runs_root(tmp_path):
    root = tmp_path / "runs"
    _episode(root, "run_a", {
        "contract": {"question_type": "stock_deep_dive"},
        "traces": [
            _fq("dataset=stock_daily; rows=5; fingerprint=x"),
            _fq("dataset=sector_daily; rows=0; fingerprint=y", "empty"),
            {"provider": "agent:kb_search", "capability": "agent_loop", "status": "success"},
        ],
    })
    _episode(root, "run_b", {"contract": {"question_type": "stock_deep_dive"},
                             "traces": [_fq("dataset=stock_daily; rows=3")]})
    # 没有 contract 时退到 task_frame；detail 里没有 dataset= 的记成「?」，不猜
    _episode(root, "run_c", {"task_frame": {"question_type": "market_overview"},
                             "traces": [_fq("rows=2; fingerprint=z")]})
    _episode(root, "run_d", {"traces": []})  # 哪儿都没有题型
    _episode(root, "run_e", "{broken json")  # 坏文件跳过（原有行为）
    return root


def test_by_route_dataset_breakdown(runs_root):
    report = audit_tool.audit(sorted(runs_root.glob("run_*")))
    assert report["runs"] == 4
    assert dict(report["route_runs"]) == {"stock_deep_dive": 2, "market_overview": 1, "?": 1}
    assert dict(report["by_route"]["stock_deep_dive"]) == {"stock_daily": 2, "sector_daily": 1}
    assert dict(report["by_route"]["market_overview"]) == {"?": 1}
    assert dict(report["dataset_status"]["sector_daily"]) == {"empty": 1}
    assert dict(report["per_tool"]["kb_search"]) == {"success": 1}  # agent 工具仍走运行时同一归一化
    assert audit_tool.never_called(report, ["market_daily", "sector_daily", "stock_daily"]) == ["market_daily"]


@pytest.mark.parametrize(
    ("detail", "dataset"),
    [
        ("dataset=stock_daily; rows=5", "stock_daily"),
        ("stale; dataset=theme-x_1; subject_exited_universe", "theme-x_1"),
        ("mydataset=zzz; rows=1", "?"),  # 不能把别的键里的子串当成数据集
        ("", "?"),
    ],
)
def test_dataset_parsing(detail, dataset):
    assert audit_tool._dataset({"detail": detail}) == dataset


def test_cli_by_dataset_and_default_output(runs_root, capsys):
    assert audit_tool.main([str(runs_root)]) == 0
    default = capsys.readouterr().out
    assert "按题型" not in default and "episode: 4 个" in default  # 默认输出不变

    assert audit_tool.main(["--by-dataset", str(runs_root)]) == 0
    out = capsys.readouterr().out
    assert "stock_deep_dive（2 个 episode，调用 3 次）：stock_daily 2 · sector_daily 1" in out
    assert "market_overview（1 个 episode，调用 1 次）" in out
    assert "只对所扫样本成立" in out


def test_cli_json_lists_registry_and_never_called(runs_root, capsys):
    from intelligence.services.finance_query import _DATASETS

    assert audit_tool.main(["--json", str(runs_root)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["registered_datasets"] == sorted(_DATASETS)
    assert "stock_daily" not in payload["never_called"] and "sector_daily" not in payload["never_called"]
    assert set(payload["never_called"]) == set(_DATASETS) - {"stock_daily", "sector_daily"}
    assert payload["by_route"]["stock_deep_dive"] == {"stock_daily": 2, "sector_daily": 1}


def test_cli_without_runs_exits_2(tmp_path, capsys):
    assert audit_tool.main([str(tmp_path)]) == 2
    assert "没有找到" in capsys.readouterr().err


@pytest.mark.skipif(not REAL_RUNS.is_dir(), reason="收据目录已移出仓库")
def test_real_committed_episodes():
    report = audit_tool.audit(sorted(REAL_RUNS.glob("run_*")))
    assert report["runs"] == 2
    assert dict(report["by_route"]["stock_deep_dive"]) == {"stock_daily": 2, "sector_stock_daily": 1, "sector_daily": 1}
    assert "general_finance_qa" in report["route_runs"] and not report["by_route"].get("general_finance_qa")
