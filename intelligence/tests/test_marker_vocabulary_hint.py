"""措辞门禁的词表必须让模型看得见。

背景（08-01 验收 C5 实测）：24 条证据全部绑定、正文写了反证内容，只因没用
`_MARKERS` 认的标记词，counterpoint 判 marker_absent，整份答案被换成缺口模板。
彼时初次合成的 prompt 只有「output_id：描述」，补写回灌只说「缺少措辞标记」
不说哪些词算数——模型在一张看不见的评分表上被打分，且被打了也无从改起。

本轮两处注入共用一个真源（`marker_vocabulary_hint` 读 `_MARKERS`）：
1. 初次合成：`render_prompt_constraint` → ask.py 的 `prompt_constraints`；
2. 补写回灌：`marker_absent` 的 gap 文本携带接受的标记词。

不改判定逻辑：什么算 fulfilled / marker_absent 一个分支都没动。
"""
from __future__ import annotations

from intelligence.services import answer_model as am
from intelligence.services.research_contract import RequiredOutput
from intelligence.services.task_fulfillment import (
    evaluate_task_fulfillment,
    marker_vocabulary_hint,
    render_prompt_constraint,
)


class TestMarkerVocabularyHint:
    def test_gated_output_lists_its_accepted_phrases(self) -> None:
        hint = marker_vocabulary_hint("counterpoint")
        assert "反证" in hint
        assert "除非" in hint
        assert "正文含任一即可" in hint

    def test_exempt_outputs_get_no_hint(self) -> None:
        """豁免槽位门禁本就不查标记，提示只会稀释真约束。"""
        assert marker_vocabulary_hint("direct_assessment") == ""
        assert marker_vocabulary_hint("supporting_evidence") == ""

    def test_unknown_output_gets_no_hint(self) -> None:
        assert marker_vocabulary_hint("no_such_slot") == ""

    def test_limit_caps_the_phrase_list(self) -> None:
        hint = marker_vocabulary_hint("prior_recall", limit=2)
        assert hint.count("、") == 1


class TestRenderPromptConstraint:
    def test_gated_output_carries_id_description_and_phrases(self) -> None:
        line = render_prompt_constraint(
            RequiredOutput("counterpoint", "反方观点或风险", (), True)
        )
        assert line.startswith("counterpoint：反方观点或风险（")
        assert "反证" in line

    def test_exempt_output_keeps_the_plain_format(self) -> None:
        """无提示时格式与旧版逐字节相同——没契约的调用方行为不变。"""
        line = render_prompt_constraint(
            RequiredOutput("direct_assessment", "直接判断", (), True)
        )
        assert line == "direct_assessment：直接判断"

    def test_split_on_first_colon_still_yields_the_description(self) -> None:
        """answer_model 按第一个全角冒号拆分登记合法标题，提示不得破坏它。"""
        line = render_prompt_constraint(
            RequiredOutput("counterpoint", "反方观点或风险", (), True)
        )
        description = line.split("：", 1)[-1]
        assert description.startswith("反方观点或风险")


class TestMarkerAbsentGapCarriesVocabulary:
    def test_c5_shape_gap_names_the_accepted_phrases(self) -> None:
        """C5 复刻：证据已绑定、正文已写到、只缺标记词 → gap 必须给出词表。

        正文刻意避开 counterpoint 的全部标记（反证/风险/相反/但/除非），
        claim 落在 counter 命名空间且绑定到词元重合的来源。
        """
        source = am.EvidenceRef(
            evidence_id="E1",
            source="本地知识库",
            detail="公司层面暂无负面记录",
        )
        claim = am.make_claim(
            claim_id="counter:1",
            text="公司层面暂无负面记录",
            claim_type="fact",
            theme="测试题材",
            status=am.ClaimStatus.VERIFIED,
            evidence_ids=("E1",),
        )
        verdict = evaluate_task_fulfillment(
            question="立新能源这两天涨了多少",
            required_outputs=(
                RequiredOutput("counterpoint", "反方观点或风险", (), True),
            ),
            answer_text="立新能源两日均上涨。公司层面暂无负面记录。",
            claims=(claim,),
            sources=(source,),
        )

        (item,) = verdict.items
        assert item.reason_code == "marker_absent"
        assert "已绑定，但正文缺少该输出的措辞标记" in item.gap
        assert "反证" in item.gap
        assert "除非" in item.gap
