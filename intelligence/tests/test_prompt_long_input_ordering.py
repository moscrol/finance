"""长输入在前、问题在最后。

官方长上下文指引（platform.claude.com prompt-engineering/claude-prompting-best-practices
→ Long context prompting）：「把长文档和长输入放在提示词靠顶部的位置，在问题、指令和示例
之上」，并注明「问题放在最后可以把回答质量提升最多 30%，多文档复杂输入尤其明显」。

这三个 builder 原本完全相反：用户问题排最前，最长的 claim registry（12,000 字符预算，
通常占整段 prompt 的绝大部分）压在最后。

与 prompt caching 不冲突：registry 每轮都变，用户消息本来就没有可复用前缀；可缓存的
system 消息位置未动。
"""
from __future__ import annotations

import pytest

from intelligence.services import llm_refine

QUERY = "你觉得a股明天会怎么走"
REGISTRY = '{"claim_id":"generic:verified:1","text":"2026-07-30：指数 -0.62%"}'
REQUIRED = ("direct_assessment：针对预测窗口的直接判断",)


def _user(messages: list[dict]) -> str:
    return next(m["content"] for m in messages if m["role"] == "user")


ALL_BUILDERS = [
    pytest.param(
        lambda: llm_refine.build_decision_brief_messages(
            QUERY, REGISTRY, required_outputs=REQUIRED
        ),
        id="decision_brief",
    ),
    pytest.param(
        lambda: llm_refine.build_grounded_composer_messages(
            QUERY, "brief", REGISTRY, required_outputs=REQUIRED
        ),
        id="composer",
    ),
    pytest.param(
        lambda: llm_refine.build_grounding_judge_messages(QUERY, "答案正文", REGISTRY),
        id="judge",
    ),
]


@pytest.mark.parametrize("build", ALL_BUILDERS)
def test_registry_comes_before_the_question(build) -> None:
    content = _user(build())

    assert content.index(REGISTRY) < content.index(QUERY)


@pytest.mark.parametrize("build", ALL_BUILDERS)
def test_the_question_is_last(build) -> None:
    """问题放在最后——这是官方给出 30% 数字的那一条。"""
    content = _user(build())

    assert content.rstrip().endswith(QUERY)


@pytest.mark.parametrize("build", ALL_BUILDERS)
def test_registry_is_delimited(build) -> None:
    """给长输入一个明确边界，避免它和后面的指令在模型眼里糊成一片。"""
    content = _user(build())

    assert "<claim_registry>" in content
    assert "</claim_registry>" in content
    assert content.index("<claim_registry>") < content.index("</claim_registry>")


def test_required_outputs_still_reach_the_prompt() -> None:
    """重排顺序不能把上一轮修好的东西挤掉。"""
    content = _user(
        llm_refine.build_grounded_composer_messages(
            QUERY, "brief", REGISTRY, required_outputs=REQUIRED
        )
    )

    assert "direct_assessment" in content
    assert "只能用 claim registry 里的事实来覆盖" in content


def test_system_prompt_position_is_unchanged() -> None:
    """system 消息是唯一可缓存的部分，位置不能动。"""
    messages = llm_refine.build_grounded_composer_messages(QUERY, "brief", REGISTRY)

    assert messages[0]["role"] == "system"


def test_repair_turn_also_leads_with_the_registry() -> None:
    content = llm_refine.claim_binding_revision_user_content(["第 2 句越界"], REGISTRY)

    assert content.index(REGISTRY) < content.index("第 2 句越界")


def test_composer_perspective_block_between_registry_and_query() -> None:
    """视角约束进 user turn（保缓存），排在长输入之后、用户问题之前。"""
    block = "### SPT-Molmansk\n- 证据层级：盘面量价资金结构"
    content = _user(
        llm_refine.build_grounded_composer_messages(
            QUERY, "brief", REGISTRY, perspective_block=block
        )
    )

    assert "本轮视角约束" in content
    assert "claim/EvidenceAtom 绑定" in content
    assert content.index(REGISTRY) < content.index(block) < content.index(f"用户问题：{QUERY}")


def test_composer_without_perspective_block_is_unchanged() -> None:
    """空视角块与旧版逐字节一致（neutral 模式不改变 grounded 行为）。"""
    baseline = llm_refine.build_grounded_composer_messages(
        QUERY, "brief", REGISTRY, required_outputs=REQUIRED
    )
    with_empty = llm_refine.build_grounded_composer_messages(
        QUERY, "brief", REGISTRY, required_outputs=REQUIRED, perspective_block=""
    )

    assert baseline == with_empty
