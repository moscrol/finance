"""判读基线的守门测试。

守的是三件在设计文档里写死、但代码里很容易被后人改掉的事：
1. 自限阀 FY-A10 必须排第一（先装自限阀再装规则）；
2. 只装结构性判读，不得混进未回测的数字阈值；
3. env 总开关能整块关掉——没有它就无法做 A/B，也就永远回答不了
   「内置判读到底有没有让答案变好」。

裁定与来源见 ``docs/learning/reading-rules-inventory-2026-08-19.md``。
"""

from __future__ import annotations

import pathlib
import re

from intelligence.services import llm_refine, reading_baseline


def test_self_limiting_rule_comes_first() -> None:
    """FY-A10 必须是第一条：它是唯一约束其他内置规则的规则。

    顺序反了会有一段时间里全部判读不带失效条件地生效——这正是用户自己那条
    「禁止把单次观察写成定律」要防的事。
    """
    rules = reading_baseline.baseline_rules()
    assert rules, "默认应有生效规则"
    assert rules[0].id == "FY-A10", f"自限阀必须排第一，当前首条是 {rules[0].id}"


def test_no_unbacktested_numeric_thresholds() -> None:
    """基线只收结构性判读；带数字阈值的属 B 类，须先经本地回测标定。

    用户对外部框架的自评是「结构可信，单点阈值没有回测支撑」
    （docs/learning/knevo-distill/q15-认知压力测试信号分层.md:176）。
    这条测试防的是后人图省事把「成交额<80%」这类数字直接塞进基线。
    """
    numeric = re.compile(r"\d+\s*(?:%|倍|日均|分位)")
    offenders = [
        (r.id, m.group())
        for r in reading_baseline.baseline_rules()
        for m in [numeric.search(r.rule)]
        if m
    ]
    assert not offenders, f"基线混入未回测数字阈值：{offenders}"


def test_every_rule_carries_id_and_provenance() -> None:
    """每条规则都要能被追回来源——出问题时查得到它是哪一档证据进来的。"""
    for rule in reading_baseline.baseline_rules():
        assert rule.id and rule.title and rule.rule, rule
        assert rule.source, f"{rule.id} 缺来源标注"
        assert f"[{rule.id}]" in reading_baseline.baseline_guidance()


def test_kill_switch_restores_byte_identical_input() -> None:
    """总开关关掉后，注入侧全部归零（全局块与数据块内两处都要归零）。"""
    off = {"FINANCE_READING_BASELINE": "0"}
    assert reading_baseline.baseline_rules(off) == ()
    assert reading_baseline.baseline_guidance(off) == ""
    for block in reading_baseline.registered_blocks():
        assert reading_baseline.block_rule_lines(block, off) == [], block

    # 缺省与显式真值都算开启
    assert reading_baseline.enabled({})
    assert reading_baseline.enabled({"FINANCE_READING_BASELINE": "1"})
    assert not reading_baseline.enabled({"FINANCE_READING_BASELINE": "off"})


def test_block_rule_lines_only_for_registered_block() -> None:
    """未登记的块返回空列表，不得静默造一条规则出来。"""
    assert reading_baseline.block_rule_lines("D8")[0].startswith("- 判读[SPT-A11]：")
    assert reading_baseline.block_rule_lines("NOPE-999") == []


def test_every_registered_block_is_actually_wired() -> None:
    """登记了规则的块必须真的在某个数据块里被 extend——否则是「配置生效、模型没看到」。

    这道门守的是本批最容易出的错：规则表加了一项，但忘了在渲染函数里接线，
    单测全绿、模型永远看不到。用源码搜接线点，不依赖跑通数据库。
    """
    services = pathlib.Path(__file__).resolve().parents[1] / "services"
    wired = set()
    for path in services.glob("*.py"):
        wired.update(
            re.findall(r'block_rule_lines\(\s*"([^"]+)"', path.read_text(encoding="utf-8"))
        )
    missing = sorted(set(reading_baseline.registered_blocks()) - wired)
    assert not missing, f"这些块登记了判读规则但没有接线：{missing}"


def test_block_rules_carry_id_and_provenance() -> None:
    """块级规则同样要带 id 与来源；且不得混入未回测数字阈值。"""
    numeric = re.compile(r"\d+\s*(?:%|倍|日均|分位)")
    for block in reading_baseline.registered_blocks():
        for rule in reading_baseline.block_rules(block):
            assert rule.id and rule.rule and rule.source, (block, rule)
            assert not numeric.search(rule.rule), f"{rule.id} 混入数字阈值"


def test_pending_rules_never_reach_the_prompt() -> None:
    """批三规则已裁定采纳，但缺数据源——绝不能注入。

    注入一条模型拿不到数据的判读，等于要求它按不存在的输入做判断，
    诱发编造。这道门守的是「补数据的人顺手把规则挪进 _BLOCK_RULES 却没接数据」。
    """
    pending_ids = {rule.id for rule, _, _ in reading_baseline.pending_rules()}
    assert pending_ids, "批三清单不应为空"

    injected = set(reading_baseline.baseline_guidance())
    live_ids = {r.id for r in reading_baseline.baseline_rules()}
    for block in reading_baseline.registered_blocks():
        live_ids |= {r.id for r in reading_baseline.block_rules(block)}

    overlap = pending_ids & live_ids
    assert not overlap, f"这些规则缺数据源却已注入：{sorted(overlap)}"
    for rule_id in pending_ids:
        assert rule_id not in reading_baseline.baseline_guidance()
    del injected


def test_pending_rules_declare_their_data_gap() -> None:
    """每条待激活规则必须写明卡在哪个缺口 id 与缺什么——否则补数据的人无从下手。"""
    for rule, gap_id, gap_note in reading_baseline.pending_rules():
        assert rule.id and rule.rule and rule.source, rule
        assert re.fullmatch(r"G\d+", gap_id), (rule.id, gap_id)
        assert len(gap_note) > 10, (rule.id, gap_note)


def test_ranking_rule_defers_to_existing_skill_rubric() -> None:
    """FY-A03' 必须写明「不替代既有排序口径」。

    2026-08-19 对表结论：整条五维排序内置会用 5 维稀释掉 serenity-alpha
    ranking-rubric 的 4 条硬禁止（禁止只因涨得少／龙头最强／概念相关／卖方
    强推排第一）。故只取降解版，且必须显式让位。
    """
    rule = next(
        r for r in reading_baseline.block_rules("D1") if r.id == "FY-A03'"
    )
    assert "serenity-alpha" in rule.rule
    assert "不替代" in rule.rule


def test_baseline_outranks_experience_cards_in_system_prompt() -> None:
    """判读基线必须排在经验卡片与样板之前，且标签写明「强制」。

    先例：contract_guidance 被塞进「历史经验卡片」标题下时模型遵守率极低——
    语义标签给错，模型把强制项当可选参考（llm_refine.build_synthesis_messages
    docstring 记录的 2026-08-13 workbench 实测）。基线是同一类东西。
    """
    messages = llm_refine.build_synthesis_messages(
        "问题",
        "题材",
        "证据",
        experience_guidance="EXP",
        exemplar_guidance="SAMPLE",
        baseline_guidance=reading_baseline.baseline_guidance(),
    )
    system = messages[0]["content"]
    assert "判读基线" in system
    assert "强制" in system.split("判读基线")[1][:60]
    assert system.index("判读基线") < system.index("历史经验卡片")
    assert system.index("判读基线") < system.index("高分样板")


def test_not_passing_baseline_leaves_prompt_unchanged() -> None:
    """不传 baseline_guidance 时系统提示词逐字节不变（旧调用方不受影响）。"""
    system = llm_refine.build_synthesis_messages("问题", "题材", "证据")[0]["content"]
    assert "判读基线" not in system
