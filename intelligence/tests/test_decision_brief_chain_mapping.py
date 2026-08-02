"""DecisionBrief 必须有承载产业链/公司映射的槽位。

Grounded Composer 是「围绕 DecisionBrief 回答」的，且它的提示词只接收
query + DecisionBrief + claim registry——不接收 answer_spec.to_prompt_block()。
所以 owner 的 output_contract 对这条成文路径是死信道（实测：约束确实进了
answer_spec 的「运行约束」小节，正文却完全不受影响）。

原先 brief 的 7 个字段里没有产业链的位置，registry 里 12 条 company: claim
无处可放，于是 brief 把它们整批丢掉：实测 supports=[market:S1..S4, summary:market,
trigger:1..3]、counterevidence=[summary:company-gap, counter:1]，一个 company: 都没有。
结果是 12 家有名有姓的候选（东方锆业 L1/core、中一科技 L1/core、三祥新材 L2/core…）
进不了正文，chain_mapping 这个必需输出永远无法满足，整份答案被 fail-closed
换成 190 字的「请补充数据源」。
"""
from __future__ import annotations

import json

from intelligence.services import llm_refine
from intelligence.services.answer_model import (
    AnswerSpec,
    ClaimStatus,
    DecisionBrief,
    make_claim,
    parse_decision_brief,
    resolve_answer_profile,
)


def _spec() -> AnswerSpec:
    claims = tuple(
        make_claim(
            claim_id=cid,
            text=text,
            claim_type="fact",
            theme="固态电池",
            status=ClaimStatus.CANDIDATE,
            evidence_ids=("G2",),
        )
        for cid, text in (
            ("summary:market", "盘面信号全面转强"),
            ("company:东方锆业", "东方锆业与固态电池存在公司级映射"),
            ("company:中一科技", "中一科技与固态电池存在公司级映射"),
        )
    )
    return AnswerSpec(
        research_spec=resolve_answer_profile("固态电池现在怎么看"),
        summary=claims[:1],
        verified_facts=(),
        company_table=(),
        counter_evidence=(),
        gaps=(),
        triggers=(),
        next_actions=(),
        sources=(),
        system_notices=(),
        candidate_facts=claims[1:],
    )


def test_brief_carries_chain_mapping() -> None:
    brief = DecisionBrief(
        direct_answer="a",
        core_tension="b",
        supports=("summary:market",),
        chain_mapping=("company:东方锆业",),
    )

    assert brief.to_dict()["chain_mapping"] == ["company:东方锆业"]


def test_parser_reads_chain_mapping_from_the_model_output() -> None:
    payload = json.dumps(
        {
            "direct_answer": "候选已列出",
            "core_tension": "盘面强但无硬证据",
            "supports": ["summary:market"],
            "chain_mapping": ["company:东方锆业", "company:中一科技"],
        },
        ensure_ascii=False,
    )

    brief, issues = parse_decision_brief(payload, _spec())

    assert brief is not None
    assert brief.chain_mapping == ("company:东方锆业", "company:中一科技")
    assert not [i for i in issues if i.severity == "error"]


def test_invalid_id_elsewhere_does_not_silently_wipe_chain_mapping() -> None:
    """漏了这个字段的话，出现一个无效 id 就会把整份产业链映射清空。"""
    payload = json.dumps(
        {
            "direct_answer": "a",
            "core_tension": "b",
            "supports": ["summary:market", "claim:不存在"],
            "chain_mapping": ["company:东方锆业"],
        },
        ensure_ascii=False,
    )

    brief, _issues = parse_decision_brief(payload, _spec())

    assert brief is not None
    assert brief.chain_mapping == ("company:东方锆业",)


def test_invalid_chain_mapping_ids_are_dropped_not_invented() -> None:
    payload = json.dumps(
        {
            "direct_answer": "a",
            "core_tension": "b",
            "supports": ["summary:market"],
            "chain_mapping": ["company:东方锆业", "company:查无此司"],
        },
        ensure_ascii=False,
    )

    brief, _issues = parse_decision_brief(payload, _spec())

    assert brief is not None
    assert "company:查无此司" not in brief.chain_mapping


def test_both_prompts_carry_the_requirement() -> None:
    """两端都要说：brief 要填，composer 要写。少一端就等于没改。"""
    assert "chain_mapping" in llm_refine._DECISION_BRIEF_SYSTEM_PROMPT
    assert "company:" in llm_refine._DECISION_BRIEF_SYSTEM_PROMPT
    assert "整批省略" in llm_refine._DECISION_BRIEF_SYSTEM_PROMPT

    assert "chain_mapping" in llm_refine._GROUNDED_COMPOSER_SYSTEM_PROMPT
    assert "产业链环节" in llm_refine._GROUNDED_COMPOSER_SYSTEM_PROMPT
    assert "不得升级为已确认" in llm_refine._GROUNDED_COMPOSER_SYSTEM_PROMPT


def test_wrong_family_is_replaced_by_the_registry_truth() -> None:
    """模型挑错家族时用确定性方式收口。

    实测：加了槽位之后 brief 确实填了，但填的是 data:D4:3..7（主线板块数据），
    而 registry 里明明有 12 条 company: claim。claim 家族是可确定识别的，
    不该交给模型选——它只负责措辞，不负责选证据族。
    """
    payload = json.dumps(
        {
            "direct_answer": "a",
            "core_tension": "b",
            "supports": ["summary:market"],
            "chain_mapping": ["data:D4:3", "data:D4:4"],
        },
        ensure_ascii=False,
    )

    brief, _issues = parse_decision_brief(payload, _spec())

    assert brief is not None
    assert brief.chain_mapping == ("company:东方锆业", "company:中一科技")


def test_correct_family_is_left_alone() -> None:
    payload = json.dumps(
        {
            "direct_answer": "a",
            "core_tension": "b",
            "supports": ["summary:market"],
            "chain_mapping": ["company:中一科技"],
        },
        ensure_ascii=False,
    )

    brief, _issues = parse_decision_brief(payload, _spec())

    assert brief is not None
    assert brief.chain_mapping == ("company:中一科技",)


def test_empty_slot_is_filled_from_the_registry() -> None:
    """模型整批省略时也要补回来——那正是这条链路最初的失败方式。"""
    payload = json.dumps(
        {"direct_answer": "a", "core_tension": "b", "supports": ["summary:market"]},
        ensure_ascii=False,
    )

    brief, _issues = parse_decision_brief(payload, _spec())

    assert brief is not None
    assert brief.chain_mapping == ("company:东方锆业", "company:中一科技")


def test_no_chain_claims_means_no_chain_mapping() -> None:
    """registry 里没有产业链族时，模型填什么都是错的，直接清空。"""
    from intelligence.services.answer_model import (
        AnswerSpec,
        ClaimStatus,
        make_claim,
        resolve_answer_profile,
    )

    spec = AnswerSpec(
        research_spec=resolve_answer_profile("今天大盘怎么样"),
        summary=(
            make_claim(
                claim_id="summary:market",
                text="盘面转强",
                claim_type="fact",
                theme="A股",
                status=ClaimStatus.VERIFIED,
                evidence_ids=("S1",),
            ),
        ),
        verified_facts=(),
        company_table=(),
        counter_evidence=(),
        gaps=(),
        triggers=(),
        next_actions=(),
        sources=(),
        system_notices=(),
    )
    payload = json.dumps(
        {
            "direct_answer": "a",
            "core_tension": "b",
            "supports": ["summary:market"],
            "chain_mapping": ["data:D4:3"],
        },
        ensure_ascii=False,
    )

    brief, _issues = parse_decision_brief(payload, spec)

    assert brief is not None
    assert brief.chain_mapping == ()
