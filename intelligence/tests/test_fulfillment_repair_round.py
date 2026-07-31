"""门禁判缺 → 定向补写一轮 → 重新过门禁 → 仍不过才 fail-closed。

原先的形状是二值的：一个必需输出判缺，整份答案换成缺口模板。

官方 Claude Code 对被拒的工具调用不是直接终止，而是把拒绝消息**作为 tool
result** 交回模型，让它换方法或说明无法继续（`PermissionDenied` hook 的官方
用例原文就是「告诉模型它可以重试」）。ch04「模式三 分层错误级联」给了它的通用
形式——Bash 出错只取消同级 Bash、不动 Read/Grep，为的是避开「完全隔离（错误
被忽视）」和「全局中止（一个小错误杀死整个会话）」两个极端。我们原先站在
「全局中止」这一极。

三条硬约束都做在 ``repair_unfulfilled_answer`` 内部，不依赖调用方守规矩：
1. 只补一轮（函数里没有循环；额外调用由 turn 级 LlmCallLedger 兜底）
2. 补写只能用 registry 里已有的事实
3. 补写后必须重新过门禁——**这是唯一容易写错成放宽门禁的地方**
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from intelligence.services import ask_synthesis, llm_refine, task_fulfillment
from intelligence.services.task_fulfillment import (
    FulfillmentItem,
    FulfillmentVerdict,
)


@dataclass(frozen=True)
class _Output:
    output_id: str
    description: str = "描述"
    required: bool = True


def _verdict(*missing_ids: str) -> FulfillmentVerdict:
    return FulfillmentVerdict(
        status="missing",
        items=tuple(
            FulfillmentItem(
                output_id=output_id,
                status="missing",
                gap="registry 里没有该输出对应的 claim",
            )
            for output_id in missing_ids
        ),
    )


@pytest.fixture
def stub_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ask_synthesis.answer_model,
        "grounded_claim_registry_block",
        lambda *a, **k: '{"claim_id":"c1","text":"指数 -0.62%"}',
    )


def _repair(**overrides):
    kwargs = {
        "question": "明天怎么走",
        "answer_text": "上一版正文。",
        "answer_spec": object(),
        "verdict": _verdict("invalidation"),
        "required_outputs": (_Output("invalidation"),),
        "timeout": 30,
    }
    kwargs.update(overrides)
    return ask_synthesis.repair_unfulfilled_answer(**kwargs)


class TestRegateIsMandatory:
    """约束 3：补写后必须重新过门禁。"""

    def test_revision_that_still_fails_is_discarded(
        self, monkeypatch: pytest.MonkeyPatch, stub_registry: None
    ) -> None:
        """模型交回了东西，但仍不满足契约 → 必须返回 None（走 fail-closed）。

        这是最容易写错的一条：跑过修复轮不是放行的理由。
        """
        monkeypatch.setattr(
            llm_refine,
            "synthesize_messages",
            lambda *a, **k: (
                llm_refine.SynthesisResult("补写后的正文", "p", "m", "stop"),
                "",
            ),
        )
        monkeypatch.setattr(
            task_fulfillment,
            "evaluate_answer_spec_fulfillment",
            lambda **k: _verdict("invalidation"),
        )

        assert _repair() is None

    def test_revision_that_passes_is_returned_with_the_new_verdict(
        self, monkeypatch: pytest.MonkeyPatch, stub_registry: None
    ) -> None:
        monkeypatch.setattr(
            llm_refine,
            "synthesize_messages",
            lambda *a, **k: (
                llm_refine.SynthesisResult("补齐了失效条件的正文", "p", "m", "stop"),
                "",
            ),
        )
        passed = FulfillmentVerdict(status="complete", items=())
        monkeypatch.setattr(
            task_fulfillment,
            "evaluate_answer_spec_fulfillment",
            lambda **k: passed,
        )

        result = _repair()

        assert result is not None
        text, verdict = result
        assert text == "补齐了失效条件的正文"
        assert verdict is passed

    def test_the_recheck_runs_on_the_revised_text_not_the_original(
        self, monkeypatch: pytest.MonkeyPatch, stub_registry: None
    ) -> None:
        """重判必须喂新正文——喂旧正文等于没重判。"""
        seen: dict[str, object] = {}
        monkeypatch.setattr(
            llm_refine,
            "synthesize_messages",
            lambda *a, **k: (
                llm_refine.SynthesisResult("新正文", "p", "m", "stop"),
                "",
            ),
        )

        def spy(**kwargs):
            seen.update(kwargs)
            return FulfillmentVerdict(status="complete", items=())

        monkeypatch.setattr(
            task_fulfillment, "evaluate_answer_spec_fulfillment", spy
        )
        _repair(answer_text="旧正文")

        assert seen["answer_text"] == "新正文"


class TestOnlyOneRound:
    """约束 1：只补一轮，且预算耗尽时自动退回今天的行为。"""

    def test_the_model_is_called_exactly_once(
        self, monkeypatch: pytest.MonkeyPatch, stub_registry: None
    ) -> None:
        calls: list[int] = []

        def counting(*a, **k):
            calls.append(1)
            return (
                llm_refine.SynthesisResult("补写", "p", "m", "stop"),
                "",
            )

        monkeypatch.setattr(llm_refine, "synthesize_messages", counting)
        monkeypatch.setattr(
            task_fulfillment,
            "evaluate_answer_spec_fulfillment",
            lambda **k: _verdict("invalidation"),
        )
        _repair()

        assert len(calls) == 1

    def test_budget_exhaustion_degrades_instead_of_raising(
        self, monkeypatch: pytest.MonkeyPatch, stub_registry: None
    ) -> None:
        """turn 级 ledger 拒发时修复轮不发生，退回今天的 fail-closed。

        这就是为什么**不需要第二个计数器**——预算已经有人管了。
        """
        monkeypatch.setattr(
            llm_refine,
            "synthesize_messages",
            lambda *a, **k: (None, "LLM 调用预算耗尽（本轮上限 40 次尝试）"),
        )

        assert _repair() is None


class TestSourceConstraint:
    """约束 2：补写只能用 registry 里已有的事实。"""

    def test_the_prompt_carries_the_source_constraint(self) -> None:
        content = llm_refine.fulfillment_revision_user_content(
            (("invalidation", "registry 里没有该输出对应的 claim"),),
            '{"claim_id":"c1"}',
            "上一版正文",
        )

        assert "只能用 claim registry 里的事实来覆盖" in content
        assert "不要为了凑齐而编" in content

    def test_the_prompt_names_the_specific_gap(self) -> None:
        """回灌的是诊断而不是「你没写全」——模型要能定位到改哪里。"""
        content = llm_refine.fulfillment_revision_user_content(
            (("invalidation", "候选 3 条但正文里没出现它们的文本"),),
            '{"claim_id":"c1"}',
            "上一版正文",
        )

        assert "invalidation" in content
        assert "候选 3 条但正文里没出现它们的文本" in content

    def test_the_prompt_asks_for_a_patch_not_a_rewrite(self) -> None:
        content = llm_refine.fulfillment_revision_user_content(
            (("invalidation", "缺口"),), "{}", "上一版正文"
        )

        assert "不要重写整篇答案" in content
        assert "上一版正文" in content

    def test_long_input_comes_before_the_instruction(self) -> None:
        """与三个 composer builder 一致：长输入在前、指令在最后。"""
        registry = '{"claim_id":"c1","text":"很长的证据"}'
        content = llm_refine.fulfillment_revision_user_content(
            (("invalidation", "缺口"),), registry, "上一版正文"
        )

        assert content.index(registry) < content.index("只能用 claim registry")


class TestNoOpGuards:
    def test_nothing_missing_means_no_call(
        self, monkeypatch: pytest.MonkeyPatch, stub_registry: None
    ) -> None:
        called: list[int] = []
        monkeypatch.setattr(
            llm_refine,
            "synthesize_messages",
            lambda *a, **k: called.append(1) or (None, ""),
        )

        assert _repair(verdict=FulfillmentVerdict(status="complete", items=())) is None
        assert called == []

    def test_empty_registry_means_no_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """registry 空时补写无据可依，别浪费一次调用。"""
        called: list[int] = []
        monkeypatch.setattr(
            ask_synthesis.answer_model,
            "grounded_claim_registry_block",
            lambda *a, **k: "   ",
        )
        monkeypatch.setattr(
            llm_refine,
            "synthesize_messages",
            lambda *a, **k: called.append(1) or (None, ""),
        )

        assert _repair() is None
        assert called == []

    def test_empty_revision_is_discarded(
        self, monkeypatch: pytest.MonkeyPatch, stub_registry: None
    ) -> None:
        monkeypatch.setattr(
            llm_refine,
            "synthesize_messages",
            lambda *a, **k: (
                llm_refine.SynthesisResult("   ", "p", "m", "stop"),
                "",
            ),
        )

        assert _repair() is None
