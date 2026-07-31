"""registry 超预算时告知模型，而不是静默丢弃。

马书 ch28「不足四 截断告知不等于行动」讲的正是这个：CC 的大工具结果超过 50K
字符时会写明「Full output saved to /tmp/... [Showing first 50000 characters of
N total]」——遵循「告知而非隐藏」原则。作者同时指出**告知 ≠ 模型会去读**
（注意力经济：读完整内容意味着多一次工具调用），但那是下一层的问题；
我们连告知都没有。

不对称的具体形状：

    门禁    task_fulfillment 看 answer_spec 全集
    composer 只看 grounded_claim_registry_block(max_chars=12_000)

实测 10 个 0731 run 里 2 个超窗（最大 15,429 字符 / 71 条 → 入窗 54、丢 17，
丢的全是 company_table 的 company_mapping / company_evidence），但**两个 run
的 answer_status 都是 complete**——所以这是潜在不对称而不是已发生的故障。
补一行告知是零成本的那一半；上 LLM 选择（小模型选 ≤5 条）会再加一次串行调用
去解决一个还没发生的问题，不划算。
"""
from __future__ import annotations

import json

from intelligence.services import answer_model


def _block(claim_count: int, max_chars: int | None) -> str:
    """构造 claim_count 条 claim 的 registry，走真实的 builder。"""
    spec = answer_model.AnswerSpec(
        research_spec=answer_model.resolve_answer_profile("问题", "主题", "forecast"),
        verified_facts=tuple(
            answer_model.Claim(
                claim_id=f"c{i}",
                text=f"第 {i} 条证据，" + "填充" * 30,
                claim_type="verified",
                theme="测试主题",
            )
            for i in range(claim_count)
        ),
        summary=(),
        candidate_facts=(),
        company_table=(),
        counter_evidence=(),
        gaps=(),
        triggers=(),
        next_actions=(),
        sources=(),
        system_notices=(),
    )
    return answer_model.grounded_claim_registry_block(
        spec, query="", max_chars=max_chars
    )


def _lines(block: str) -> list[str]:
    return [line for line in block.splitlines() if line.strip()]


def test_no_notice_when_everything_fits() -> None:
    """没丢东西就别加噪声。"""
    block = _block(3, 100_000)

    assert "未纳入" not in block
    assert len(_lines(block)) == 3


def test_no_notice_when_the_budget_is_unlimited() -> None:
    assert "未纳入" not in _block(50, None)


def test_dropped_claims_are_announced() -> None:
    block = _block(50, 2_000)
    lines = _lines(block)

    assert "未纳入" in lines[-1]
    assert len(lines) < 50


def test_the_count_is_accurate() -> None:
    """报的数字必须对得上——报错了比不报更坏。"""
    block = _block(50, 2_000)
    lines = _lines(block)
    claim_lines = [line for line in lines if "未纳入" not in line]
    reported = int(
        json.loads(lines[-1])["note"].split("另有 ")[1].split(" 条")[0]
    )

    assert reported == 50 - len(claim_lines)


def test_the_notice_itself_stays_inside_the_budget() -> None:
    """一边写预算一边超预算就说不过去了。

    告知行挤不下时要再让出一条最低分的 claim，并把计数改对。
    """
    for budget in (400, 700, 1_100, 2_000, 5_000):
        block = _block(50, budget)

        assert len(block) <= budget, f"budget={budget} 超了 {len(block) - budget}"


def test_the_notice_never_displaces_the_last_claim() -> None:
    """预算紧到只能留一个时，留证据不留告知。

    证据是目的，告知是元数据。第一版写反了——挤不下就一路让出 claim，
    最后窗口里只剩一句「另有 N 条未纳入」、一条证据都没有。
    既有测试 test_grounded_registry_window_is_hard_bounded_and_hardness_ranked
    （max_chars 正好等于一行）抓住了它。
    """
    one_line = len(_lines(_block(50, None))[0])
    block = _block(50, one_line)
    lines = _lines(block)

    assert len(lines) == 1
    assert "未纳入" not in lines[0]
    assert len(block) <= one_line


def test_the_notice_does_not_invite_the_model_to_invent() -> None:
    """告知「有东西没给你」时必须同时说清「别猜」。

    否则等于提示模型「还有更多证据存在」，反而鼓励它编。
    """
    note = _lines(_block(50, 2_000))[-1]

    assert "不要臆测" in note
    assert "按缺口处理" in note


def test_the_notice_is_last_so_it_does_not_split_the_claims() -> None:
    lines = _lines(_block(50, 2_000))

    assert "未纳入" in lines[-1]
    assert all("未纳入" not in line for line in lines[:-1])
