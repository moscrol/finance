"""工具饥饿遥测：只观测、不改模型可见文案、写入失败不影响主流程。"""

from __future__ import annotations

import json
from pathlib import Path

from intelligence.eval.tool_hunger import (
    aggregate_hunger_runs,
    write_hunger_report,
)
from intelligence.runtime.episode_tool_batch import ToolBatchExecutor
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import ModelToolCall
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.evidence_capabilities import EvidencePlan, EvidenceRequirement
from intelligence.services.finance_query import (
    FinanceQuerySpec,
    FinanceQueryValidationError,
    validation_retry_hint,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
)
from intelligence.services.tool_hunger import (
    HUNGER_FILENAME,
    JsonlHungerSink,
    bind_run_hunger,
    hunger_context,
    record_hunger,
)
from intelligence.tests.test_agent import _session
from intelligence.tests.test_episode_tools import _market_forecast_frame

UNKNOWN_TOOL_TEXT = "未知工具「nope_tool」。"
UNKNOWN_DATASET = "hunger_probe_nonexistent_dataset"


def _read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _finance_query_observation(tmp_path: Path):
    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="hunger-unknown-dataset",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-24",
        latest_data_date="2026-07-24",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )
    return registry.execute(
        "finance_query",
        {
            "dataset": UNKNOWN_DATASET,
            "metrics": ["auction_pct"],
            "dimensions": ["trade_date", "stock_name"],
            "filters": [{"field": "panel_key", "op": "eq", "value": "zt"}],
            "group_by": [],
            "order_by": [],
            "limit": 5,
        },
        context=context,
        step_id="hunger-unknown-dataset:1",
    )


def _expected_unknown_dataset_observation() -> str:
    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": UNKNOWN_DATASET,
            "metrics": ["auction_pct"],
            "dimensions": ["trade_date", "stock_name"],
            "filters": [{"field": "panel_key", "op": "eq", "value": "zt"}],
            "group_by": [],
            "order_by": [],
            "limit": 5,
        }
    )
    error = FinanceQueryValidationError(f"unknown dataset: {spec.dataset}")
    return (
        f"结构化查询参数无效：{str(error)[:160]}；重试提示："
        f"{validation_retry_hint(spec, error)}"
    )


def test_unknown_tool_records_hunger_and_keeps_model_text(tmp_path: Path) -> None:
    sink_path = tmp_path / HUNGER_FILENAME
    session = _session()
    with bind_run_hunger(tmp_path, run_id="run_inline"):
        text = session._run_tool("nope_tool", {"x": 1, "q": "竞价"})
    assert text == UNKNOWN_TOOL_TEXT
    events = _read_events(sink_path)
    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "unknown_tool"
    assert event["requested_name"] == "nope_tool"
    assert event["arg_keys"] == ["x", "q"]
    assert event["run_id"] == "run_inline"
    assert event["lane"] == "inline"
    assert "竞价" not in json.dumps(event, ensure_ascii=False)


def test_finance_query_rejected_keeps_model_text_and_full_dataset(
    tmp_path: Path,
) -> None:
    expected = _expected_unknown_dataset_observation()
    with bind_run_hunger(tmp_path, run_id="run_episode"):
        observation = _finance_query_observation(tmp_path)
    assert observation.observation == expected
    events = _read_events(tmp_path / HUNGER_FILENAME)
    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "finance_query_rejected"
    assert event["dataset"] == UNKNOWN_DATASET
    assert event["requested_name"] == UNKNOWN_DATASET
    assert event["metrics"] == ["auction_pct"]
    assert event["dimensions"] == ["trade_date", "stock_name"]
    assert event["filters"] == [{"field": "panel_key", "op": "eq"}]
    assert event["failure_code"] == "invalid_query"
    assert event["run_id"] == "run_episode"
    assert "zt" not in json.dumps(event, ensure_ascii=False)


def test_hunger_write_failure_does_not_change_unknown_tool_text() -> None:
    class BoomSink:
        def record(self, _event: object) -> None:
            raise OSError("disk full")

    session = _session()
    with hunger_context(BoomSink(), run_id="run_boom"):
        text = session._run_tool("nope_tool", {"x": 1})
    assert text == UNKNOWN_TOOL_TEXT


def test_hunger_write_failure_does_not_change_finance_query_observation(
    tmp_path: Path,
) -> None:
    class BoomSink:
        def record(self, _event: object) -> None:
            raise OSError("disk full")

    expected = _expected_unknown_dataset_observation()
    with hunger_context(BoomSink(), run_id="run_boom"):
        observation = _finance_query_observation(tmp_path)
    assert observation.observation == expected


def test_record_hunger_swallows_sink_errors() -> None:
    class BoomSink:
        def record(self, _event: object) -> None:
            raise RuntimeError("nope")

    with hunger_context(BoomSink()):
        record_hunger(event_type="unknown_tool", requested_name="x")


def test_capability_denied_is_distinct_from_unknown_tool(tmp_path: Path) -> None:
    def runner(query: str, _context: object):
        return (
            [
                AgentEvidence(
                    tool="web_search",
                    title="hit",
                    detail=query,
                    source="test",
                    content_hash="h1",
                )
            ],
            "ok",
            ProviderTrace(
                provider="test",
                capability="web_search",
                status="success",
                result_count=1,
            ),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="web_search",
                capability="web_search",
                description="web",
                cost="external",
                freshness="current",
                runner=runner,
            ),
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="market",
                cost="local",
                freshness="current",
                runner=runner,
            ),
        )
    )
    contract = ResearchTaskContract(
        task_id="hunger-denied",
        question="q",
        subject="s",
        subject_kind="company",
        question_type="valuation_estimate",
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
        ),
        allowed_capabilities=("market_data",),
        research_tier="quick",
        evidence_plan=EvidencePlan(
            requirements=(EvidenceRequirement("market_data", "market_data", True),)
        ),
    )
    context = ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(2.0),
        policy=ResearchPolicy("quick", 4, 2.0, 0.0),
        trace_parent_id="hunger-denied",
    )
    session = ToolBatchExecutor().new_session()
    with bind_run_hunger(tmp_path, run_id="run_denied"):
        result = session.execute(
            (
                ModelToolCall("unknown", "shell", {"cmd": "SECRET_PAYLOAD"}),
                ModelToolCall("denied", "web_search", {"query": "竞价"}),
            ),
            registry=registry,
            context=context,
            remaining_slots=4,
        )
    assert [item.error for item in result.items] == [
        "unknown_or_unauthorized_tool",
        "unknown_or_unauthorized_tool",
    ]
    events = _read_events(tmp_path / HUNGER_FILENAME)
    by_type = {event["event_type"]: event for event in events}
    assert by_type["unknown_tool"]["requested_name"] == "shell"
    assert by_type["unknown_tool"]["arg_keys"] == ["cmd"]
    assert by_type["capability_denied"]["requested_name"] == "web_search"
    assert by_type["capability_denied"]["capability"] == "web_search"
    dumped = json.dumps(events, ensure_ascii=False)
    assert "竞价" not in dumped
    assert "SECRET_PAYLOAD" not in dumped


def test_aggregator_counts_fixture_runs_and_keeps_samples(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    first = runs / "run_aaa"
    second = runs / "run_bbb"
    empty = runs / "run_ccc"
    first.mkdir(parents=True)
    second.mkdir()
    empty.mkdir()
    (first / HUNGER_FILENAME).write_text(
        json.dumps(
            {
                "event_type": "finance_query_rejected",
                "requested_name": "auction_stock_daily",
                "dataset": "auction_stock_daily",
                "run_id": "run_aaa",
                "ts": "2026-08-18T01:00:00+08:00",
            },
            ensure_ascii=False,
        )
        + "\n"
        + json.dumps(
            {
                "event_type": "unknown_tool",
                "requested_name": "shell",
                "run_id": "run_aaa",
                "ts": "2026-08-18T01:01:00+08:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (second / HUNGER_FILENAME).write_text(
        json.dumps(
            {
                "event_type": "finance_query_rejected",
                "requested_name": "auction_stock_daily",
                "dataset": "auction_stock_daily",
                "run_id": "run_bbb",
                "ts": "2026-08-18T02:00:00+08:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    report = aggregate_hunger_runs(runs)
    assert report["runs_scanned"] == 3
    assert report["event_count"] == 3
    groups = {
        (item["event_type"], item["requested_name"]): item
        for item in report["groups"]
    }
    rejected = groups[("finance_query_rejected", "auction_stock_daily")]
    assert rejected["count"] == 2
    assert rejected["sample_run_ids"] == ["run_aaa", "run_bbb"]
    unknown = groups[("unknown_tool", "shell")]
    assert unknown["count"] == 1
    assert unknown["sample_run_ids"] == ["run_aaa"]


def test_aggregator_empty_runs_dir_does_not_crash(tmp_path: Path) -> None:
    empty = tmp_path / "runs"
    empty.mkdir()
    report = aggregate_hunger_runs(empty)
    assert report["runs_scanned"] == 0
    assert report["event_count"] == 0
    assert report["groups"] == []
    paths = write_hunger_report(report, tmp_path / "out")
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["event_count"] == 0
    markdown = paths["md"].read_text(encoding="utf-8")
    assert "工具饥饿" in markdown
    assert "0" in markdown


def test_cli_tool_hunger_writes_report(tmp_path: Path, capsys) -> None:
    from intelligence.cli import main

    runs = tmp_path / "runs"
    runs.mkdir()
    out = tmp_path / "out"
    assert main(
        [
            "tool-hunger",
            "--runs-dir",
            str(runs),
            "--since",
            "all",
            "--out-dir",
            str(out),
            "--stem",
            "tool-hunger-test",
        ]
    ) == 0
    captured = capsys.readouterr()
    assert "tool-hunger-test.json" in captured.out
    report = json.loads((out / "tool-hunger-test.json").read_text(encoding="utf-8"))
    assert report["event_count"] == 0


def test_jsonl_sink_is_created_only_on_record(tmp_path: Path) -> None:
    with bind_run_hunger(tmp_path, run_id="run_idle"):
        pass
    assert not (tmp_path / HUNGER_FILENAME).exists()
    sink = JsonlHungerSink(tmp_path / HUNGER_FILENAME, run_id="run_idle")
    with hunger_context(sink, run_id="run_idle"):
        record_hunger(event_type="unknown_tool", requested_name="ghost")
    assert (tmp_path / HUNGER_FILENAME).is_file()
