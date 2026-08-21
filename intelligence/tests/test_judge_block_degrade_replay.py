"""W1（R-20260821-07）原始工件重放：必需块否决从「横幅收场」改「降级保留」.

夹具冻结自两个生产 run 的 ``continuous-episode.json``（目录
``fixtures/judge-block-degrade/``，命名沿 ``pv-perovskite-e4.json`` 惯例）：

- ``huangshi-direct-assessment-955225``：个股换形探针。判官删三句（含一句
  真算术错「基本回吐全部涨幅」），``direct_assessment`` 的 marker 句陪葬，
  整格记 lost；历史公开稿以道歉横幅收场。
- ``taichen-counterpoint-491046``：R-05 A 臂。判官删 12 句，``counterpoint``
  整段消失（残块为空形态）；历史公开稿同样挂横幅。

before 读数来自夹具 ``historical_public_answer``（原 run 的 answer.md，
不重算历史行为）；after 由当前代码对同一份 draft/evidence/bindings 重放。
判官桩按 ``judge_reject_snippets`` 匹配句子否决——与原判官的删除范围一致。

live 不可按需强触发（沿 #298 模式），这两条即 W1 的机制证明。
"""

from __future__ import annotations

import json

from pathlib import Path

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchTaskContract,
)
from intelligence.services.task_frame import TaskFrame

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "judge-block-degrade"


def _load_case(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / name).read_text())


def _frame_from_case(case: dict) -> TaskFrame:
    return TaskFrame(
        raw_question=str(case["question"]),
        user_goal="重放原始 run 的判官删句处置",
        question_type=str(case["question_type"]),
        subject=str(case["subject"]),
        subject_kind=str(case["subject_kind"]),
        market_scope="A股",
        timeframe="当前",
        required_outputs=tuple(
            str(item["output_id"]) for item in case["required_outputs"]
        ),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _structural_from_case(case: dict):
    frame = _frame_from_case(case)
    evidence = tuple(
        AgentEvidence(
            tool=str(item.get("tool") or ""),
            title=str(item.get("title") or ""),
            detail=str(item.get("detail") or ""),
            source=str(item.get("source") or ""),
            source_date=item.get("source_date"),
            evidence_tier=str(item.get("evidence_tier") or ""),
            supports=tuple(item.get("supports") or ()),
            contradicts=tuple(item.get("contradicts") or ()),
            independent_key=str(item.get("independent_key") or ""),
            freshness=str(item.get("freshness") or "unknown"),
            content_hash=str(item.get("content_hash") or ""),
        )
        for item in case["evidence"]
    )
    bindings = tuple(
        OutputEvidenceBinding(
            str(item["output_id"]),
            tuple(item.get("evidence_hashes") or ()),
            gap=str(item.get("gap") or ""),
            basis=str(item.get("basis") or "evidence"),
        )
        for item in case["bindings"]
    )
    contract = ResearchTaskContract(
        task_id=f"replay-{case['source_run']}",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=tuple(
            RequiredOutput(
                str(item["output_id"]),
                str(item.get("description") or item["output_id"]),
                tuple(item.get("evidence_types") or ("market_data",)),
                bool(item.get("required", True)),
                grounding_mode=str(item.get("grounding_mode") or "evidence"),
            )
            for item in case["required_outputs"]
        ),
        allowed_capabilities=tuple(case.get("allowed_capabilities") or ()),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=str(case["draft"]),
        evidence=evidence,
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        ),
        bindings=bindings,
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    return frame, verify_episode_outcome(contract, outcome)


def _snippet_judge(case: dict):
    """一轮否决判官桩：按原 run 的删除范围（文本片段）reject，再判即 pass。"""

    snippets = tuple(case["judge_reject_snippets"])
    issues = tuple(case["judge_issues"])

    def judge(request):
        rejected = [
            int(item["index"])
            for item in request["sentences"]
            if any(snippet in str(item["text"]) for snippet in snippets)
        ]
        if rejected:
            return {
                "passed": False,
                "rejected_sentence_indexes": rejected,
                "issues": list(issues),
            }
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    return judge


def _replay(case: dict):
    frame, structural = _structural_from_case(case)
    return SemanticEpisodeVerifier(judge_fn=_snippet_judge(case)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )


def test_replay_huangshi_direct_assessment_keeps_remainder_no_banner() -> None:
    case = _load_case("huangshi-direct-assessment-955225.json")

    # before：历史公开稿（原 run answer.md）以道歉横幅收场。
    historical = case["historical_public_answer"]
    assert "结构缺口" in historical
    assert "应重做" in historical

    result = _replay(case)

    # 判官删句照常：算术错句与无据定性句被删。
    assert result.judge_status == "repaired"
    assert "基本回吐全部涨幅" not in result.public_answer
    assert "题材连板脉冲" not in result.public_answer
    # 格状态照 r24 口径记缺口。
    assert result.gap_output_ids == ("direct_assessment",)
    # after：残稿保留 + 块级【待复核】标注 + 无道歉横幅。
    assert "走势分四段" in result.public_answer
    assert "【待复核】" in result.public_answer
    assert "直接回答用户问题并说明判断强度" in result.public_answer
    assert "结构缺口" not in result.public_answer
    assert "应重做" not in result.public_answer
    assert "需补充直接证据" not in result.public_answer


def test_replay_taichen_counterpoint_empty_remainder_no_banner() -> None:
    case = _load_case("taichen-counterpoint-491046.json")

    historical = case["historical_public_answer"]
    assert "结构缺口" in historical
    assert "应重做" in historical

    result = _replay(case)

    assert result.judge_status == "repaired"
    # 反证段整段被判官合法删除（残块为空形态）。
    assert "反证与竞争性解释" not in result.public_answer
    assert result.gap_output_ids == ("counterpoint",)
    # 残稿（未被否决的句子）保留。
    assert "太辰光" in result.public_answer
    # after：块级标注可见、道歉横幅消失。
    assert "【待复核】" in result.public_answer
    assert "提供主要反证或竞争性解释" in result.public_answer
    assert "结构缺口" not in result.public_answer
    assert "应重做" not in result.public_answer
