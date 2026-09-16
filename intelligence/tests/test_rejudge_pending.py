"""W2: posterior rejudge writes receipts and never mutates the published answer."""

from __future__ import annotations

import json
from pathlib import Path

from intelligence.services.rejudge_pending import (
    append_pending_from_artifact,
    published_answer_sha256,
    rejudge_verdict,
    run_offline_rejudge,
    summarize_receipts,
)
from scripts import rejudge_pending as cli

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "eval"
    / "fixtures"
    / "rejudge-unavailable-run.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_confirm_and_overturn_are_both_representable() -> None:
    assert (
        rejudge_verdict(
            original_judge_status="unavailable",
            report={"passed": True, "rejected_sentence_indexes": []},
        )
        == "confirm"
    )
    assert (
        rejudge_verdict(
            original_judge_status="unavailable",
            report={"passed": False, "rejected_sentence_indexes": [1]},
        )
        == "overturn"
    )
    assert (
        rejudge_verdict(original_judge_status="unavailable", report=None)
        == "unavailable"
    )


def test_fixture_rejudge_writes_receipt_and_leaves_answer_file_untouched(
    tmp_path: Path,
) -> None:
    fixture = _fixture()
    answer = tmp_path / "answer.md"
    answer.write_text(fixture["published_answer"], encoding="utf-8")
    before = answer.read_text(encoding="utf-8")
    before_mtime = answer.stat().st_mtime_ns
    receipt_path = tmp_path / "fixture-unavailable-20260819-rejudge.json"

    def pass_judge(_request):
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    receipt = run_offline_rejudge(
        fixture,
        pass_judge,
        receipt_path=receipt_path,
        published_answer_path=answer,
    )
    assert receipt["verdict"] == "confirm"
    assert receipt["overturn"] is False
    assert receipt["published_answer_unchanged"] is True
    assert receipt_path.is_file()
    assert answer.read_text(encoding="utf-8") == before
    assert answer.stat().st_mtime_ns == before_mtime
    assert receipt["published_answer_sha256"] == published_answer_sha256(before)


def test_overturn_receipt_still_does_not_rewrite_published_answer(
    tmp_path: Path,
) -> None:
    fixture = _fixture()
    answer = tmp_path / "answer.md"
    answer.write_text(fixture["published_answer"], encoding="utf-8")
    receipt_path = tmp_path / "overturn-rejudge.json"

    def reject_judge(_request):
        return {
            "passed": False,
            "rejected_sentence_indexes": [1],
            "issues": ["unsupported numeric condition"],
        }

    receipt = run_offline_rejudge(
        fixture,
        reject_judge,
        receipt_path=receipt_path,
        published_answer_path=answer,
    )
    assert receipt["verdict"] == "overturn"
    assert receipt["overturn"] is True
    assert receipt["published_answer_unchanged"] is True
    assert answer.read_text(encoding="utf-8") == fixture["published_answer"]


def test_append_pending_index_and_cli_fixture_receipt(
    tmp_path: Path, monkeypatch
) -> None:
    index = tmp_path / "index.jsonl"
    monkeypatch.setenv("FINANCE_REJUDGE_PENDING_INDEX", str(index))
    artifact = {
        "run_id": "run_fixture",
        "published_answer": "hat answer",
        "semantic_verifier": {
            "judge_status": "unavailable",
            "exc_class": "TimeoutError",
            "timeout_asked": 25.0,
            "public_answer": "hat answer",
            "judge_request": {"question": "q", "sentences": []},
        },
    }
    written = append_pending_from_artifact(artifact, index_path=index)
    assert written == index
    rows = [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["pending_rejudge"] is True
    assert rows[0]["degrade_class"] == "judge_unavailable"

    receipt_dir = tmp_path / "runs"
    exit_code = cli.main(
        [
            "--fixture",
            str(FIXTURE),
            "--receipt-dir",
            str(receipt_dir),
        ]
    )
    assert exit_code == 0
    receipt = json.loads(
        (receipt_dir / "fixture-unavailable-20260819-rejudge.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["verdict"] == "confirm"


def test_pending_row_is_a_self_contained_replay_fixture(
    tmp_path: Path,
) -> None:
    """R-20260829-04：新式行内联请求与答案——工件删掉也能重放。

    旧形状：行里只有 sha 指纹，run_id/artifact_path 双空，工件被清理即
    永不可重放（2026-08-29 清账实测 49/93）。
    """

    index = tmp_path / "index.jsonl"
    artifact = {
        "published_answer": "self contained answer",
        "contract": {"task_id": "task-sc-01"},
        "semantic_verifier": {
            "judge_status": "unavailable",
            "exc_class": "TimeoutError",
            "public_answer": "self contained answer",
            "judge_request": {"question": "q", "sentences": [{"index": 1}]},
        },
    }
    append_pending_from_artifact(artifact, index_path=index)
    row = json.loads(index.read_text(encoding="utf-8").splitlines()[0])
    assert row["has_judge_request"] is True
    assert row["judge_request"] == {"question": "q", "sentences": [{"index": 1}]}
    assert row["published_answer"] == "self contained answer"
    assert row["episode_task_id"] == "task-sc-01"

    # 行即夹具：不经任何工件，直接离线重放。
    receipt = run_offline_rejudge(
        row,
        lambda _request: {
            "passed": True,
            "rejected_sentence_indexes": [],
            "issues": [],
        },
    )
    assert receipt["verdict"] == "confirm"
    assert receipt["published_answer_unchanged"] is True


def test_replayable_rows_split_from_stale_rows(tmp_path: Path) -> None:
    from intelligence.services.rejudge_pending import replayable_pending_rows

    index = tmp_path / "index.jsonl"
    old_style = {
        "schema": "rejudge_pending.v1",
        "status": "pending",
        "judge_status": "unavailable",
        "published_answer_sha256": "a" * 64,
        "has_judge_request": True,  # 旧语义：工件里有；行内没有
    }
    new_style = {
        "schema": "rejudge_pending.v1",
        "status": "pending",
        "judge_status": "unavailable",
        "published_answer_sha256": "b" * 64,
        "has_judge_request": True,
        "judge_request": {"question": "q", "sentences": []},
        "published_answer": "x",
        "run_id": "run-new",
    }
    with index.open("w", encoding="utf-8") as handle:
        for row in (old_style, new_style):
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    replayable, stale = replayable_pending_rows(index)
    assert [row["run_id"] for row in replayable] == ["run-new"]
    assert len(stale) == 1, "旧式行必须如实归 stale，不硬清也不假装可重放"


def test_cli_export_fixtures_writes_only_replayable_rows(
    tmp_path: Path,
) -> None:
    index = tmp_path / "index.jsonl"
    artifact = {
        "published_answer": "exportable",
        "contract": {"task_id": "task-exp-01"},
        "semantic_verifier": {
            "judge_status": "unavailable",
            "public_answer": "exportable",
            "judge_request": {"question": "q", "sentences": []},
        },
    }
    append_pending_from_artifact(artifact, index_path=index)
    stale_row = {
        "schema": "rejudge_pending.v1",
        "status": "pending",
        "judge_status": "unavailable",
        "published_answer_sha256": "c" * 64,
    }
    with index.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(stale_row, ensure_ascii=False) + "\n")

    fixtures_dir = tmp_path / "fixtures"
    exit_code = cli.main(
        [
            "--index",
            str(index),
            "--export-fixtures",
            str(fixtures_dir),
        ]
    )
    assert exit_code == 0
    exported = sorted(path.name for path in fixtures_dir.glob("*.json"))
    assert exported == ["task-exp-01.json"], "stale 行不得被导出冒充可重放"
    fixture = json.loads((fixtures_dir / "task-exp-01.json").read_text("utf-8"))
    assert fixture["judge_request"]["question"] == "q"


def test_summarize_overturn_rate() -> None:
    summary = summarize_receipts(
        [
            {"verdict": "confirm"},
            {"verdict": "overturn"},
            {"verdict": "unavailable"},
        ]
    )
    assert summary["overturn_count"] == 1
    assert summary["confirm_count"] == 1
    assert summary["overturn_rate"] == 0.5
