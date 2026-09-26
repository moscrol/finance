"""存证重放（scripts/judge_loss_point_replay.py）重建 outcome 时保留结构化观察值。

2026-09-09 版 ``_rebuild_outcome`` 把证据的 ``observations`` 置空；数值门 09-21 起把
观察值当支撑来源，借它做数值重放的复核脚本因此比生产少一路支撑。夹具走生产写存证的
``AgentOutcome.to_dict()`` 再过一遍 JSON，测的是真实存档形状，不是手写的猜测。
不调模型、不起服务、不碰 DuckDB。
"""

from __future__ import annotations

from dataclasses import replace
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from intelligence.services.agent_research import (  # noqa: E402
    AgentEvidence,
    StructuredObservation,
)
from intelligence.services.agent_runtime import (  # noqa: E402
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_semantic_verifier import (  # noqa: E402
    numeric_condition_repair_feedback,
)
from intelligence.services.episode_verifier import verify_episode_outcome  # noqa: E402
from intelligence.services.evidence_capabilities import EvidencePlan  # noqa: E402
from intelligence.services.research_contract import (  # noqa: E402
    RequiredOutput,
    ResearchTaskContract,
)
from intelligence.services.task_frame import TaskFrame  # noqa: E402
from scripts.judge_loss_point_replay import (  # noqa: E402
    _rebuild_outcome,
    main,
    replay_receipt,
)

AMOUNT = StructuredObservation(
    subject="低空经济", as_of="2026-09-18", metric="成交额亿", value=1862.79
)
LIMIT_UPS = StructuredObservation(
    subject="低空经济", as_of="2026-09-18", metric="涨停家数", value=2.0
)
# 1862.79 只在观察值里，证据正文没有这个数：这句的唯一支撑就是观察值。
OBSERVATION_ONLY = "若板块成交额跌破 1862.79 亿（E1），视为退潮确认。"
# 真正的新阈值：有没有观察值都该被数字门点名，证明门在工作、不是观察值一律放行。
NOVEL = "若成交额跌破 1800 亿则量能失效。"


def _episode(
    observations: tuple[StructuredObservation, ...] = (AMOUNT, LIMIT_UPS),
    *,
    question: str = "低空经济还能走多远？",
    question_type: str = "market_forecast",
    subject: str = "低空经济",
    tool: str = "market_data",
    detail: str = "交易日=2026-09-18；板块成交额与涨停家数见结构化观察值",
    draft: str = OBSERVATION_ONLY + NOVEL,
    output_ids: tuple[str, ...] = ("direct_assessment",),
) -> tuple[ResearchTaskContract, AgentOutcome]:
    frame = TaskFrame(
        raw_question=question,
        user_goal=question,
        question_type=question_type,
        subject=subject,
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="当前",
        required_outputs=output_ids,
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )
    evidence = AgentEvidence(
        tool=tool,
        title=f"{subject} 数据快照",
        detail=detail,
        source="结构化数据",
        source_date="2026-09-18",
        content_hash="HASH_REPLAY_FIXTURE",
        observations=observations,
    )
    required = tuple(RequiredOutput(item, item, (tool,), True) for item in output_ids)
    contract = ResearchTaskContract(
        task_id="replay-observations",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=required,
        allowed_capabilities=(tool,),
        research_tier="standard",
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=draft,
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=tuple(
            OutputEvidenceBinding(item, (evidence.content_hash,)) for item in output_ids
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    return contract, outcome


def _financial_episode() -> tuple[ResearchTaskContract, AgentOutcome]:
    """财报题：``metric_evidence`` 槽由 ``report_binding_gaps`` 按观察值核「最近 2 期」营收。"""

    return _episode(
        (
            StructuredObservation("中际旭创", "2026-06-30", "revenue_cum_yi", 180.5),
            StructuredObservation("中际旭创", "2026-03-31", "revenue_cum_yi", 80.2),
        ),
        question="中际旭创最近2期营收怎么样？",
        question_type="financial_analysis",
        subject="中际旭创",
        tool="financial_data",
        detail="2026-06-30累计营收180.5亿元；2026-03-31累计营收80.2亿元。",
        draft="中际旭创 2026 年中报累计营收 180.5 亿元，2026 年一季报累计营收 80.2 亿元（E1）。",
        output_ids=("financial_assessment", "metric_evidence"),
    )


def _write_archive(root: Path, contract: ResearchTaskContract, outcome: AgentOutcome) -> Path:
    """按生产存证形状写一份 continuous-episode.json（结构结论取生产那一刻的核验）。"""

    path = root / "u" / "runs" / "run_20260926_000000_000000" / "continuous-episode.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "contract": contract.to_dict(),
                "outcome": outcome.to_dict(),
                "structural_verifier": verify_episode_outcome(contract, outcome).to_dict(),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _archived(outcome: AgentOutcome) -> dict:
    """生产写 continuous-episode.json 的同一条路：to_dict → JSON。"""

    return json.loads(json.dumps(outcome.to_dict(), ensure_ascii=False))


def _flagged(contract: ResearchTaskContract, outcome: AgentOutcome) -> set[str]:
    """数字门点名的句子（与复核脚本同一入口：结构核验 → 数值条件预检）。"""

    verified = verify_episode_outcome(contract, outcome)
    return {
        json.loads(item)["sentence"]
        for item in numeric_condition_repair_feedback(verified)
    }


def test_rebuild_restores_observations_from_the_archive_shape() -> None:
    _contract, outcome = _episode()
    payload = _archived(outcome)
    assert payload["evidence"][0]["observations"][0]["value"] == 1862.79

    rebuilt = _rebuild_outcome(payload)

    # 整张卡逐字段还原，不只是观察值个数对上。
    assert rebuilt.evidence == outcome.evidence
    assert rebuilt.evidence[0].observations == (AMOUNT, LIMIT_UPS)


def test_rebuilt_observation_values_are_floats() -> None:
    """存档里有取数方写的整数值（生产存档实测 1128 条）；dataclass 契约是 float。"""

    _contract, outcome = _episode()
    payload = _archived(outcome)
    payload["evidence"][0]["observations"][1]["value"] = 2

    observations = _rebuild_outcome(payload).evidence[0].observations

    assert observations == (AMOUNT, LIMIT_UPS)
    assert [type(item.value) for item in observations] == [float, float]


def test_observation_only_quantity_stays_supported_after_replay() -> None:
    contract, outcome = _episode()
    production = _flagged(contract, outcome)
    assert production == {NOVEL}

    payload = _archived(outcome)
    assert _flagged(contract, _rebuild_outcome(payload)) == production
    # 09-09 的置空重建丢掉唯一支撑：同一句在重放里被判成「证据里没有的数量」。
    assert _flagged(contract, _rebuild_outcome(payload, keep_observations=False)) == {
        OBSERVATION_ONLY,
        NOVEL,
    }


def test_keep_observations_false_reproduces_the_emptied_rebuild() -> None:
    """对照臂要的是旧读数：只清观察值，卡上其余字段与默认重建一致。"""

    _contract, outcome = _episode()
    payload = _archived(outcome)

    kept = _rebuild_outcome(payload)
    emptied = _rebuild_outcome(payload, keep_observations=False)

    assert [item.observations for item in emptied.evidence] == [()]
    assert emptied.evidence == tuple(
        replace(item, observations=()) for item in kept.evidence
    )
    assert replace(emptied, evidence=kept.evidence) == kept


def test_rebuild_tolerates_missing_and_malformed_observations() -> None:
    """缺键 / 非列表 → 空；坏条目逐条跳过，不连坐同卡的好条目，也不让重建失败。

    ``value=True`` 与只有 ``subject`` 的条目是存档里真见过的形状（测试夹具产物）。
    """

    _contract, outcome = _episode()
    payload = _archived(outcome)
    card = payload["evidence"][0]
    good = {"subject": "A股", "as_of": "2026-09-14", "metric": "上涨家数", "value": 3120}
    card["observations"] = [
        good,
        {**good, "value": True},
        {"subject": "CXO概念"},
        {**good, "value": "3120"},
        {**good, "value": None},
        {**good, "value": float("nan")},
        {**good, "value": float("inf")},
        {**good, "value": 10**400},
        {**good, "metric": None},
        "上涨家数=3120",
        {**good, "unit": "家"},
    ]
    no_key = {key: value for key, value in card.items() if key != "observations"}
    payload["evidence"] += [
        {**no_key, "content_hash": "NO_KEY"},
        {**card, "content_hash": "NULL", "observations": None},
        {**card, "content_hash": "NOT_A_LIST", "observations": good},
    ]

    rebuilt = _rebuild_outcome(payload)

    expected = StructuredObservation("A股", "2026-09-14", "上涨家数", 3120.0)
    assert [item.observations for item in rebuilt.evidence] == [
        (expected, expected),
        (),
        (),
        (),
    ]


def test_financial_structural_replay_matches_production_only_with_observations(
    tmp_path: Path,
) -> None:
    """结构核验也读观察值：财报题 ``metric_evidence`` 按观察值核报告期与指标。

    09-09 的置空重建把这类题的有据槽判缺（required_output_gap），与存证的生产结构
    结论对不上，造出假的 structural_delta——复核存档实测 8 份财报题正是这个形状。
    """

    contract, outcome = _financial_episode()
    assert verify_episode_outcome(contract, outcome).verified_status == "completed"
    path = _write_archive(tmp_path, contract, outcome)

    kept = replay_receipt(path)
    emptied = replay_receipt(path, keep_observations=False)

    assert kept["replay_error"] is None and emptied["replay_error"] is None
    assert (kept["replayed_structural"], kept["replayed_codes"], kept["replayed_missing"]) == (
        "completed",
        [],
        [],
    )
    assert kept["structural_delta"] is False
    assert (
        emptied["replayed_structural"],
        emptied["replayed_codes"],
        emptied["replayed_missing"],
    ) == ("partial", ["required_output_gap"], ["metric_evidence"])
    assert emptied["structural_delta"] is True


def test_cli_keeps_observations_unless_asked_to_drop_them(tmp_path: Path, capsys) -> None:
    contract, outcome = _financial_episode()
    _write_archive(tmp_path, contract, outcome)
    common = ["--runs-dir", str(tmp_path), "--users", "u", "--json"]

    assert main([*common, str(tmp_path / "kept.json")]) == 0
    assert "observations=kept" in capsys.readouterr().out
    assert main([*common, str(tmp_path / "dropped.json"), "--drop-observations"]) == 0
    assert "observations=dropped" in capsys.readouterr().out

    def structural(name: str) -> list[str]:
        rows = json.loads((tmp_path / name).read_text(encoding="utf-8"))
        return [row["replayed_structural"] for row in rows]

    assert structural("kept.json") == ["completed"]
    assert structural("dropped.json") == ["partial"]
