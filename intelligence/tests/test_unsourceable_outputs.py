"""证伪条件本来就可以没有出处，门禁只该校验它写没写进正文。

实测 2026-07-31「固态电池现在怎么看」：反证类 claim 是
  counter:1  缺少公告等公司级硬证据：若公司在互动易口径保守/否认…直接性将明显下降
  counter:2  盘面未验证：市场尚未用真金白银选择这条逻辑…
两条的 evidence_atom_ids 都是空的，claim_type=expectation。

绑定要求 evidence_ids 非空，所以 counterpoint 永远判缺，整份答案被 fail-closed
换成 190 字。但「若 X 发生则逻辑弱化」是推理结论，不是可回查的事实——要求它
带出处是范畴错误，和要求中文 claim 与英文文件路径有词元重合是同一类错。

generic_research_owner 早有同样的例外（「尚无反向证据」是可审计结论），只是它
精确匹配 counter_evidence，而这里的 output_id 叫 counterpoint——同一概念两个名字。
"""
from __future__ import annotations

import pytest

from intelligence.services.answer_model import ClaimStatus, EvidenceRef, make_claim
from intelligence.services.research_contract import RequiredOutput
from intelligence.services.task_fulfillment import evaluate_task_fulfillment

COUNTER_TEXT = "缺少公告等公司级硬证据：若公司否认，这条逻辑的直接性将明显下降"


def _required(output_id: str) -> tuple[RequiredOutput, ...]:
    return (
        RequiredOutput(
            output_id=output_id, description="反证", evidence_types=(), required=True
        ),
    )


def _claim(claim_id: str = "counter:1", claim_type: str = "expectation"):
    return make_claim(
        claim_id=claim_id,
        text=COUNTER_TEXT,
        claim_type=claim_type,
        theme="固态电池",
        status=ClaimStatus.CANDIDATE,
    )


@pytest.mark.parametrize("output_id", ["counterpoint", "counter_evidence", "risk"])
def test_unsourced_falsification_fulfils_when_it_is_written(output_id: str) -> None:
    verdict = evaluate_task_fulfillment(
        question="固态电池现在怎么看",
        required_outputs=_required(output_id),
        answer_text=f"固态电池盘面转强，但{COUNTER_TEXT}。",
        claims=(_claim(),),
        sources=(),
    )

    assert [item.status for item in verdict.items] == ["fulfilled"]
    assert verdict.status == "complete"


def test_it_still_has_to_appear_in_the_answer() -> None:
    """放宽的是出处，不是「必须写进正文」这条。"""
    verdict = evaluate_task_fulfillment(
        question="q",
        required_outputs=_required("counterpoint"),
        answer_text="正文里但是完全没有提到这条反证。",
        claims=(_claim("counter:9"),),
        sources=(),
    )

    assert [item.status for item in verdict.items] == ["missing"]


def test_only_reasoned_claim_types_qualify() -> None:
    """事实句不能借这条通道免除出处——只有 expectation/gap 是推理结论。"""
    verdict = evaluate_task_fulfillment(
        question="q",
        required_outputs=_required("counterpoint"),
        answer_text=f"但{COUNTER_TEXT}。",
        claims=(_claim(claim_type="fact"),),
        sources=(),
    )

    assert [item.status for item in verdict.items] != ["fulfilled"]


def test_other_outputs_do_not_get_the_exemption() -> None:
    """只有反证族免出处；结论、产业链映射等仍要有证据。"""
    verdict = evaluate_task_fulfillment(
        question="q",
        required_outputs=(
            RequiredOutput(
                output_id="chain_mapping",
                description="产业链",
                evidence_types=(),
                required=True,
            ),
        ),
        answer_text=f"产业链上游：{COUNTER_TEXT}。",
        claims=(_claim("company:某司"),),
        sources=(),
    )

    assert [item.status for item in verdict.items] != ["fulfilled"]


def test_a_sourced_counterpoint_still_binds_normally() -> None:
    """有出处的反证走原来的路径，行为不变。"""
    sourced = make_claim(
        claim_id="counter:2",
        text="盘面未验证：市场尚未选择这条逻辑",
        claim_type="expectation",
        theme="固态电池",
        status=ClaimStatus.CANDIDATE,
        evidence_ids=("S1",),
    )
    source = EvidenceRef(
        evidence_id="S1",
        source="盘面未验证 市场尚未选择",
        detail="",
        tier="market_data",
        source_date=None,
    )

    verdict = evaluate_task_fulfillment(
        question="q",
        required_outputs=_required("counterpoint"),
        answer_text="但盘面未验证：市场尚未选择这条逻辑。",
        claims=(sourced,),
        sources=(source,),
    )

    assert [item.status for item in verdict.items] == ["fulfilled"]
    assert verdict.items[0].evidence_ids == ("S1",)
