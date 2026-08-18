"""冻结 30 题 live 驱动：grounded 车道、不碰 8792、失败分类、只读判分。"""

from __future__ import annotations

from pathlib import Path

from intelligence.eval import frozen_thirty_live as driver
from intelligence.eval import live_probe as probe
from intelligence.eval.frozen_question_set import load_frozen_question_set


def _spec(tmp_path: Path) -> probe.SidecarSpec:
    launcher = tmp_path / "start-finance-workbench"
    launcher.write_text("export FOO=1\nexec uvicorn --port 8792\n", encoding="utf-8")
    return probe.SidecarSpec(
        port=8796,
        repo_root=tmp_path / "repo",
        python=Path("/opt/venv/bin/python"),
        launcher=launcher,
        users_dir=tmp_path / "users",
        user="live-probe",
    )


def test_grounded_script_flips_presenter_and_never_execs_8792(tmp_path: Path) -> None:
    script = driver.grounded_sidecar_script(_spec(tmp_path))
    assert "WORKBENCH_GROUNDED_PRESENTER=1" in script
    assert "WORKBENCH_GROUNDED_PRESENTER=0" not in script
    assert "WORKBENCH_PERSIST_LLM_CONTEXT=1" in script
    assert "--port 8796" in script
    assert "--port 8792" not in script
    assert "grep '^export '" in script
    assert "exec uvicorn" not in script.split("grep", 1)[0]


def test_classify_timeout_is_infra_not_quality() -> None:
    assert (
        driver.classify_attempt(
            error="run x did not finish within 180s",
            status=None,
            artifacts={},
        )
        == "infra_fail"
    )


def test_classify_completed_without_triad_is_infra() -> None:
    assert (
        driver.classify_attempt(
            error=None,
            status="completed",
            artifacts={"answer.md": "/tmp/a.md"},
        )
        == "infra_fail"
    )


def test_classify_completed_triad_is_scored() -> None:
    artifacts = {
        "answer.md": "/tmp/a.md",
        "llm_context.json": "/tmp/c.json",
        "trace.jsonl": "/tmp/t.jsonl",
    }
    assert (
        driver.classify_attempt(error=None, status="completed", artifacts=artifacts)
        == "scored"
    )


def test_score_case_is_deterministic_and_does_not_call_llm() -> None:
    answer = (
        "本地 market_feature_store 显示 2026-07-23 上证下跌 1.2%。"
        "证据分层：[S1] 日报 [R2] 卖方。反方：量能不足。"
        "现阶段是反弹第 3 天。产业上消费电子库存去化。"
        "操作上只观察不追。个人方法是先看双红再看承接。"
        "600519 不是本题主体。"
    )
    first = driver.score_case("2026-07-23 今天市场怎么样", answer)
    second = driver.score_case("2026-07-23 今天市场怎么样", answer)
    assert first == second
    assert first["judge"] == "finance_answer_rubric"
    assert first["judge_kind"] == "deterministic"
    assert "total_score" in first
    assert "grade" in first


def test_market_subset_is_frozen_thirty_ids_only() -> None:
    loaded = load_frozen_question_set()
    ids = set(loaded["case_ids"])
    assert driver.MARKET_DEPENDENT_IDS <= ids
    assert "A1-market-overview" in driver.MARKET_DEPENDENT_IDS
    assert "ruihuatai-valuation" not in driver.MARKET_DEPENDENT_IDS


def test_build_measurement_keeps_as_of_metadata_without_rewriting_question() -> None:
    payload = driver.build_measurement(
        cases=[
            {
                "id": "A1-market-overview",
                "question": "2026-07-23 今天市场怎么样",
                "as_of": "2026-07-23",
                "classification": "scored",
                "quality": "quality_fail",
                "elapsed_seconds": 12.5,
            }
        ],
        sidecar_revision="4a3bb31366c2",
        answer_model="glm-5.2",
    )
    row = payload["cases"][0]
    assert row["question"] == "2026-07-23 今天市场怎么样"
    assert row["as_of"] == "2026-07-23"
    assert payload["as_of_injection"] == "none"
    assert payload["judge"]["kind"] == "deterministic"
    assert payload["judge"]["name"] == "finance_answer_rubric"
    assert payload["answer_model"] == "glm-5.2"
    assert payload["heterogeneous_scoring"] is True
    assert payload["sidecar_revision"] == "4a3bb31366c2"
