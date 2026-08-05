"""落盘的 fulfillment 判定必须自带「按哪张词表评的」和「为什么没绑上」。

背景（实测，2026-08-06）：`report.json` 里带 `task_fulfillment` 的只有 5/82。
排查结论不是「写的地方少了」，而是**两条执行路径用的是两套门禁**：

- `conversation_orchestrator:2780` 走 `evaluate_answer_spec_fulfillment`，
  判定同时落 `report.json`（:2791）和 `trace.jsonl`（:2792 `_trace`）。
- `continuous_episode` 路径**从不调用**它，用的是 `episode_verifier` 的
  `structural_verifier.completion`。45 个 continuous run 全部没有
  `task_fulfillment` 键，这正是那 81%。

所以这一轮加的不是新落盘点，而是把两样**下游复算不出来的东西**升成字段：

1. `evaluated_output_ids`：本轮实际评分的 post-alias 词表。契约到达门禁前经过
   `_merge_frame_outputs` 的别名归一，拿 TaskFrame 的 `required_outputs` 复算
   得到的是另一张表。
2. `reason_code`：四种未绑定成因的机器可读版本。`gap` 那句中文把四种成因写进
   同一个句子，想统计「哪种最常见」就得反解中文，而措辞随时会改。

`task_fulfillment.py` 自己的注释写了为什么这件事要紧：「四种情况长得一模一样，
正是这道门禁坏了很久没被发现的原因」。

本轮是**纯 instrumentation**：不改判定逻辑，不动 `_LEGACY_OUTPUT_ALIASES`、
`_MARKERS`、`_OUTPUT_CLAIM_NAMESPACES`。
"""
from __future__ import annotations

from intelligence.services import answer_model as am
from intelligence.services.research_contract import RequiredOutput
from intelligence.services.task_fulfillment import (
    FulfillmentItem,
    FulfillmentVerdict,
    evaluate_task_fulfillment,
)


def _claim(claim_id: str, text: str, claim_type: str = "fact", **kw) -> am.Claim:
    kw.setdefault("theme", "测试题材")
    kw.setdefault("status", am.ClaimStatus.VERIFIED)
    return am.make_claim(claim_id=claim_id, text=text, claim_type=claim_type, **kw)


def _required(output_id: str, description: str = "描述") -> RequiredOutput:
    return RequiredOutput(output_id, description, (), True)


class TestReasonCodeIsMachineReadable:
    """四种成因各自钉一条。判据是 reason_code，不是中文 gap 的子串。"""

    def test_no_candidate_claim(self) -> None:
        """registry 里一条候选都取不到——要修的是上游生产者。"""
        verdict = evaluate_task_fulfillment(
            question="问题",
            required_outputs=(_required("chain_mapping"),),
            answer_text="正文与产业链无关",
            claims=(),
            sources=(),
        )

        (item,) = verdict.items
        assert item.reason_code == "no_candidate_claim"
        assert item.candidate_count == 0

    def test_text_absent(self) -> None:
        """有候选，但正文根本没写它——要修的是合成层。"""
        verdict = evaluate_task_fulfillment(
            question="问题",
            required_outputs=(_required("chain_mapping"),),
            claims=(_claim("chain:1", "上游材料环节由某公司承担"),),
            answer_text="完全不相干的一段话",
            sources=(),
        )

        (item,) = verdict.items
        assert item.reason_code == "text_absent"
        assert item.candidate_count == 1

    def test_evidence_unbound(self) -> None:
        """正文写到了，但证据没绑上——要修的是绑定，不是文案。"""
        verdict = evaluate_task_fulfillment(
            question="问题",
            required_outputs=(_required("chain_mapping"),),
            claims=(_claim("chain:1", "上游材料环节由某公司承担"),),
            answer_text="上游材料环节由某公司承担",
            sources=(),
        )

        (item,) = verdict.items
        assert item.reason_code == "evidence_unbound"
        assert item.candidate_count == 1

    def test_fulfilled_items_carry_no_reason_code(self) -> None:
        """fulfilled 不该带成因码——有值就说明分支串了。"""
        source = am.EvidenceRef(
            evidence_id="E1",
            source="本地知识库",
            detail="上游材料环节由某公司承担",
        )
        verdict = evaluate_task_fulfillment(
            question="问题",
            required_outputs=(_required("chain_mapping"),),
            claims=(
                _claim(
                    "chain:1",
                    "上游材料环节由某公司承担",
                    claim_type="company_mapping",
                    evidence_ids=("E1",),
                ),
            ),
            answer_text="产业链上游材料环节由某公司承担",
            sources=(source,),
        )

        (item,) = verdict.items
        assert item.status == "fulfilled"
        assert item.reason_code == ""


class TestPersistedShape:
    """to_dict 是落盘的形状——这里断言的就是 report.json / trace.jsonl 里能看到什么。"""

    def test_evaluated_output_ids_is_the_post_alias_vocabulary(self) -> None:
        """落的是**实际评分**的词表，不是 frame 词表。

        下游拿 TaskFrame.required_outputs 复算，得到的是别名归一**之前**那张表。
        差异恰好落在 direct_answer / evidence_boundary 这类别名槽位上。
        """
        verdict = evaluate_task_fulfillment(
            question="问题",
            required_outputs=(
                _required("direct_assessment"),
                _required("counterpoint"),
            ),
            answer_text="一段正文",
            claims=(),
            sources=(),
        )

        payload = verdict.to_dict()

        assert payload["evaluated_output_ids"] == [
            "direct_assessment",
            "counterpoint",
        ]

    def test_reason_code_counts_saves_downstream_from_parsing_chinese(self) -> None:
        """成因分布直接落成计数，下游不必反解 gap 那句中文。"""
        verdict = evaluate_task_fulfillment(
            question="问题",
            required_outputs=(
                _required("chain_mapping"),
                _required("financial_assessment"),
            ),
            answer_text="不相干",
            claims=(),
            sources=(),
        )

        counts = verdict.to_dict()["reason_code_counts"]

        assert counts == {"no_candidate_claim": 2}

    def test_item_payload_carries_both_new_fields(self) -> None:
        verdict = evaluate_task_fulfillment(
            question="问题",
            required_outputs=(_required("chain_mapping"),),
            claims=(_claim("chain:1", "上游材料环节由某公司承担"),),
            answer_text="上游材料环节由某公司承担",
            sources=(),
        )

        (item,) = verdict.to_dict()["items"]

        assert item["reason_code"] == "evidence_unbound"
        assert item["candidate_count"] == 1
        # 中文 gap 保留——它是给人读的，不是被替换掉了。
        assert "证据未能绑定" in item["gap"]

    def test_existing_keys_are_untouched(self) -> None:
        """新增字段不能改动既有键，下游读 status/reason/items 的代码不该受影响。"""
        payload = FulfillmentVerdict(
            "missing",
            (FulfillmentItem("x", "missing", gap="g"),),
            "理由",
        ).to_dict()

        assert payload["status"] == "missing"
        assert payload["reason"] == "理由"
        assert payload["items"][0]["output_id"] == "x"
        assert payload["items"][0]["gap"] == "g"

    def test_defaults_keep_external_construction_working(self) -> None:
        """外部构造点（test_fulfillment_repair_round）不传新字段也要能用。"""
        item = FulfillmentItem(output_id="x", status="missing", gap="g")

        assert item.reason_code == ""
        assert item.candidate_count == 0
