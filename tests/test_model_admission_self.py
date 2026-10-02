"""准入全程自动：产物自带 configure 里配置的模型，每轮落产物时自动判一次；老产物按同一口径回查。

10-01 审查第 1 条：模型检查要全程自动，不能靠人记得跑脚本。装配根（GLMAgentRuntime）早把配置的
模型名写进 ``configure`` 快照，所以期望模型就在产物里——不需要再从外面告诉它。
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
from pathlib import Path

import pytest

from intelligence.eval import model_admission as ma
from intelligence.runtime.continuous_turn_adapter import _model_admission_receipt

REPO = Path(__file__).resolve().parents[1]


def _events(configured: str | None, served: list[str], branch: list[str] | None = None) -> list[dict]:
    events: list[dict] = []
    if configured is not None:
        events.append({"sequence": 1, "kind": "configure", "payload": {
            "model": configured, "providers": [{"name": "zhipu-coding", "model": configured}]}})
    for i, name in enumerate(served, start=len(events) + 1):
        events.append({"sequence": i, "kind": "model_turn", "payload": {"served_model": name}})
    if branch is not None:
        events.append({"sequence": len(events) + 1, "kind": "branch_completed",
                       "payload": {"branch_id": "branch-1", "llm_calls": len(branch), "served_models": branch}})
    return events


def test_configured_model_comes_from_the_configure_snapshot():
    assert ma.configured_models(_events("glm-5.3", [])) == ("glm-5.3",)
    assert ma.configured_models(_events("", [])) == ()
    assert ma.configured_models(_events(None, ["x"])) == ()


def test_thought_a_got_b_is_caught_automatically():
    """09-29 那次：配置写 glm-5.3，实际服务 glm-5.3-flash。"""

    result = ma.self_admission(_events("glm-5.3", ["glm-5.3-flash", "glm-5.3-flash"]))
    assert result is not None and result.verdict == ma.VERDICT_MISMATCH
    assert result.unexpected == {"glm-5.3-flash": 2}


def test_child_branch_is_part_of_the_automatic_check():
    result = ma.self_admission(_events("glm-5.3-flash", ["glm-5.3-flash"], branch=["glm-5.3"]))
    assert result is not None and result.verdict == ma.VERDICT_MISMATCH


def test_unknown_expected_is_not_guessed():
    assert ma.self_admission(_events(None, ["glm-5.3-flash"])) is None
    assert _model_admission_receipt(_events(None, ["glm-5.3-flash"]))["verdict"] == "unknown_expected"


def test_artifact_receipt_records_and_warns_without_blocking(caplog):
    with caplog.at_level(logging.WARNING, logger="intelligence.runtime.continuous_turn_adapter"):
        receipt = _model_admission_receipt(_events("glm-5.3", ["glm-5.3-flash"]))
    assert receipt["verdict"] == "mismatch" and receipt["expected"] == ["glm-5.3"]
    assert "model admission mismatch" in caplog.text
    ok = _model_admission_receipt(_events("glm-5.3-flash", ["glm-5.3-flash"], branch=["glm-5.3-flash"]))
    assert ok["verdict"] == "admitted" and ok["served"] == {"glm-5.3-flash": 2}


def test_broken_events_do_not_break_the_artifact(monkeypatch):
    def boom(events, source="episode"):
        raise RuntimeError("bad shape")

    monkeypatch.setattr(ma, "self_admission", boom)
    assert _model_admission_receipt([]) == {"verdict": "unavailable", "reason": "RuntimeError"}


def _cli():
    spec = importlib.util.spec_from_file_location("check_model_admission", REPO / "scripts" / "check_model_admission.py")
    cli = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("check_model_admission", cli)
    spec.loader.exec_module(cli)
    return cli


def _artifact(tmp_path: Path, name: str, events: list[dict]) -> Path:
    run = tmp_path / name
    run.mkdir()
    (run / "continuous-episode.json").write_text(json.dumps({"events": events}), encoding="utf-8")
    return run


def test_cli_expect_configured_rechecks_old_artifacts(tmp_path, capsys):
    cli = _cli()
    good = _artifact(tmp_path, "good", _events("glm-5.3-flash", ["glm-5.3-flash"]))
    bad = _artifact(tmp_path, "bad", _events("glm-5.3", ["glm-5.3-flash"]))
    blind = _artifact(tmp_path, "blind", _events(None, ["glm-5.3-flash"]))
    assert cli.main(["--expect-configured", "--no-episode-store", str(good)]) == 0
    assert cli.main(["--expect-configured", "--no-episode-store", str(good), str(bad)]) == 1
    assert cli.main(["--expect-configured", "--no-episode-store", str(blind)]) == 2
    assert "configure 快照里没有模型名" in capsys.readouterr().out


def test_cli_needs_exactly_one_way_to_say_what_is_expected(tmp_path):
    cli = _cli()
    run = _artifact(tmp_path, "r", _events("m", ["m"]))
    with pytest.raises(SystemExit):
        cli.main([str(run)])
    with pytest.raises(SystemExit):
        cli.main(["--expect-model", "m", "--expect-configured", str(run)])
