from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from intelligence.eval import acceptance
from intelligence.eval.acceptance_runs import RunArtifactError, select_latest_case_runs


def _case(case_id: str, tier: str) -> dict[str, object]:
    return {"case_id": case_id, "tier": tier, "turns": []}


def _write_run(
    path: Path,
    generated_at: str,
    cases: list[dict[str, object]],
) -> None:
    path.write_text(
        json.dumps({"generated_at": generated_at, "cases": cases}),
        encoding="utf-8",
    )


def test_latest_case_runs_preserve_cases_from_separate_run_files(
    tmp_path: Path,
) -> None:
    _write_run(
        tmp_path / "20260801T010000Z.json",
        "20260801T010000Z",
        [_case("A1-market-overview", "high_freq")],
    )
    _write_run(
        tmp_path / "20260801T020000Z.json",
        "20260801T020000Z",
        [_case("B1-theme-photoresist", "mid_freq")],
    )

    selected = select_latest_case_runs(
        tmp_path,
        {
            "A1-market-overview": "high_freq",
            "B1-theme-photoresist": "mid_freq",
        },
    )

    assert selected["A1-market-overview"].source_path.name == (
        "20260801T010000Z.json"
    )
    assert selected["A1-market-overview"].source_sha256 == hashlib.sha256(
        (tmp_path / "20260801T010000Z.json").read_bytes()
    ).hexdigest()
    assert selected["B1-theme-photoresist"].source_path.name == (
        "20260801T020000Z.json"
    )


def test_newer_run_replaces_only_cases_it_contains(tmp_path: Path) -> None:
    case_tiers = {
        "A1-market-overview": "high_freq",
        "A2-next-day-call": "high_freq",
    }
    _write_run(
        tmp_path / "z-old.json",
        "20260801T010000Z",
        [
            _case("A1-market-overview", "high_freq"),
            _case("A2-next-day-call", "high_freq"),
        ],
    )
    _write_run(
        tmp_path / "a-new.json",
        "20260801T020000Z",
        [_case("A1-market-overview", "high_freq")],
    )

    selected = select_latest_case_runs(tmp_path, case_tiers)

    assert selected["A1-market-overview"].generated_at == "20260801T020000Z"
    assert selected["A1-market-overview"].source_path.name == "a-new.json"
    assert selected["A2-next-day-call"].generated_at == "20260801T010000Z"


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_case",
        "wrong_tier",
        "duplicate_case",
        "bad_json",
        "non_object",
        "missing_generated_at",
        "invalid_generated_at",
        "non_list_cases",
        "non_object_case",
    ],
)
def test_invalid_run_fails_closed(tmp_path: Path, mutation: str) -> None:
    path = tmp_path / "mutated.json"
    cases = [_case("A1-market-overview", "high_freq")]
    payload: object = {
        "generated_at": "20260801T010000Z",
        "cases": cases,
    }
    if mutation == "unknown_case":
        cases = [_case("Z9-unknown", "high_freq")]
    elif mutation == "wrong_tier":
        cases = [_case("A1-market-overview", "mid_freq")]
    elif mutation == "duplicate_case":
        cases = [*cases, *cases]
    elif mutation == "non_object":
        payload = []
    elif mutation == "missing_generated_at":
        payload = {"cases": cases}
    elif mutation == "invalid_generated_at":
        payload = {"generated_at": "2026-08-01", "cases": cases}
    elif mutation == "non_list_cases":
        payload = {"generated_at": "20260801T010000Z", "cases": {}}
    elif mutation == "non_object_case":
        payload = {"generated_at": "20260801T010000Z", "cases": ["A1"]}

    if isinstance(payload, dict) and mutation in {
        "unknown_case",
        "wrong_tier",
        "duplicate_case",
    }:
        payload["cases"] = cases

    if mutation == "bad_json":
        path.write_text("{not-json", encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RunArtifactError):
        select_latest_case_runs(
            tmp_path,
            {"A1-market-overview": "high_freq"},
        )


def _stub_run_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        acceptance,
        "load_cases",
        lambda: {
            "cases": [
                {
                    "id": "A1-market-overview",
                    "tier": "high_freq",
                    "query": "market?",
                }
            ]
        },
    )
    monkeypatch.setattr(acceptance, "preflight", lambda _base: (True, "ready"))
    monkeypatch.setattr(
        acceptance,
        "ask_once",
        lambda _base, _user, question, _timeout: acceptance.TurnTrace(
            question=question,
            answer="answer",
            status="completed",
        ),
    )


def test_run_output_writes_exact_requested_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_run_dependencies(monkeypatch)
    output = tmp_path / "nested" / "live-receipt.json"

    assert acceptance.main(["run", "--output", str(output)]) == 0

    assert output.is_file()
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["cases"][0]["case_id"] == "A1-market-overview"
    # preflight 被 stub、未跑探针：不得把 unset 误盖成污染窗口
    assert saved["data_probe"] is None
    assert saved["data_probe_ok"] is None
    assert saved["window_contamination"] is None


def test_run_stamps_window_contamination_when_probe_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-12：探针失败的批必须一眼能认出污染窗口，不能静默混进干净批。"""

    def failed_preflight(_base: str) -> tuple[bool, str]:
        acceptance._last_data_probe = {
            "tool": "finance_query",
            "status": "tool_exception",
            "elapsed_ms": 3,
            "row_count": 0,
            "detail": "db_missing",
        }
        return True, "revision=deadbeef data_probe: finance_query=tool_exception"

    _stub_run_dependencies(monkeypatch)
    monkeypatch.setattr(acceptance, "preflight", failed_preflight)
    output = tmp_path / "contaminated.json"
    assert acceptance.main(["run", "--output", str(output)]) == 0
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["data_probe"]["status"] == "tool_exception"
    assert saved["data_probe_ok"] is False
    assert saved["window_contamination"] == "finance_query"
    assert "data_probe: finance_query=tool_exception" in saved["preflight_detail"]


def test_run_output_refuses_to_overwrite_existing_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "live-receipt.json"
    output.write_text("sealed", encoding="utf-8")

    def unexpected_preflight(_base: str) -> tuple[bool, str]:
        raise AssertionError("an existing output must be refused before live work")

    monkeypatch.setattr(acceptance, "preflight", unexpected_preflight)

    assert acceptance.main(["run", "--output", str(output)]) == 2
    assert output.read_text(encoding="utf-8") == "sealed"


def test_run_without_output_keeps_timestamp_named_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_run_dependencies(monkeypatch)

    class FrozenDateTime:
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:
            return datetime(2026, 8, 1, 3, 53, 25, tzinfo=timezone.utc)

    monkeypatch.setattr(acceptance, "datetime", FrozenDateTime)
    monkeypatch.setattr(acceptance, "RUNS_DIR", tmp_path)

    assert acceptance.main(["run"]) == 0

    output = tmp_path / "20260801T035325Z.json"
    assert output.is_file()
    assert json.loads(output.read_text(encoding="utf-8"))["generated_at"] == (
        "20260801T035325Z"
    )


def test_board_aggregates_case_runs_and_shows_each_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_run(
        tmp_path / "20260801T010000Z.json",
        "20260801T010000Z",
        [_case("A1-market-overview", "high_freq")],
    )
    _write_run(
        tmp_path / "20260801T020000Z.json",
        "20260801T020000Z",
        [_case("B1-theme-photoresist", "mid_freq")],
    )
    monkeypatch.setattr(acceptance, "RUNS_DIR", tmp_path)

    assert acceptance.main(["board"]) == 0
    output = capsys.readouterr().out

    assert "20260801T010000Z" in output
    assert "20260801T020000Z" in output
    assert "| 题 | 组 | 来源 | 运行 |" in output
    a1 = next(line for line in output.splitlines() if line.startswith("| A1-"))
    b1 = next(line for line in output.splitlines() if line.startswith("| B1-"))
    c1 = next(line for line in output.splitlines() if line.startswith("| C1-"))
    assert "| 010000Z |" in a1
    assert "| 020000Z |" in b1
    assert "| — | ⬜ 未跑 |" in c1


def test_board_run_selects_one_artifact_with_single_run_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    chosen = tmp_path / "20260801T010000Z.json"
    _write_run(
        chosen,
        "20260801T010000Z",
        [_case("A1-market-overview", "high_freq")],
    )
    _write_run(
        tmp_path / "20260801T020000Z.json",
        "20260801T020000Z",
        [_case("B1-theme-photoresist", "mid_freq")],
    )
    monkeypatch.setattr(acceptance, "RUNS_DIR", tmp_path)

    assert acceptance.main(["board", "--run", str(chosen)]) == 0
    output = capsys.readouterr().out

    assert "20260801T010000Z" in output
    assert "20260801T020000Z" not in output
    a1 = next(line for line in output.splitlines() if line.startswith("| A1-"))
    b1 = next(line for line in output.splitlines() if line.startswith("| B1-"))
    assert "| 010000Z |" in a1
    assert "| — | ⬜ 未跑 |" in b1


@pytest.mark.parametrize(
    "sidecar_flag",
    [
        "--truth-observations",
        "--experience-labels",
        "--information-comparisons",
    ],
)
def test_board_sidecar_requires_explicit_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    sidecar_flag: str,
) -> None:
    monkeypatch.setattr(acceptance, "RUNS_DIR", tmp_path)

    assert acceptance.main(["board", sidecar_flag, "sidecar.json"]) == 2

    output = capsys.readouterr().out
    assert "sidecar" in output
    assert "--run" in output
