"""用户贴进来的材料能不能被算：``no_bound_evidence`` 那条死路的回归锁。

2026-09-11 的生产实测（run_20260911_191540_746155）：用户贴一张表让系统算，同一回合
``derived_calculation`` 被调 37 次，**21 次以 ``no_bound_evidence`` 拒绝**、18 次死在
``table() missing 1 required positional argument: 'rows'``，一个 ``calc-*.json`` 都没落。
模型最后如实写下「全部数字为手工复算、未经工具核验」——诚实，但交付不了。

这里锁的是两条：材料内容进不进账本、进了之后会不会被别的规则再悄悄拿掉。
第二条比第一条更值得锁：``EvidenceLedger.append`` 对不合格证据是**静默 continue**，
接错了不会报错，只会让下一个人在 run 目录里看到一个空账本和一段合理的降级话术。
"""

from __future__ import annotations

from datetime import date

from intelligence.services import derived_calculation as dc
from intelligence.services import sandbox_fincalc as fincalc
from intelligence.services.answer_model import is_hard_evidence_tier
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.services.material_evidence import (
    MATERIAL_EVIDENCE_TIER,
    materials_as_evidence,
)
from intelligence.services.query_understanding import understand_query
from intelligence.services.task_frame import build_task_frame

_TABLE_QUESTION = """帮我算一下这三家 2026 年中报的毛利率，并按毛利率排序。

公司\t营业收入(亿元)\t营业成本(亿元)\t研发费用(亿元)
中际旭创\t248.60\t171.53\t9.82
新易盛\t131.44\t83.19\t4.05
天孚通信\t42.17\t24.98\t2.31
"""


def _frame(question: str, conversation_context: str | None = None):
    return build_task_frame(
        question,
        understand_query(question),
        conversation_context=conversation_context,
    )


# ------------------------------------------------------------------ 材料 → 证据


def test_pasted_table_becomes_one_bindable_evidence_item():
    """最基本的一条：贴了表，本回合就有一条带 content_hash 的证据。

    ``content_hash`` 不是可选装饰——``run_derived_calculation`` 的 inputs 只收有哈希
    的证据（``item for item in evidence if item.content_hash``），空哈希等于没提供。
    """

    items = materials_as_evidence(_frame(_TABLE_QUESTION))

    assert len(items) == 1
    item = items[0]
    assert item.content_hash
    assert item.evidence_tier == MATERIAL_EVIDENCE_TIER
    assert "中际旭创" in item.detail


def test_material_evidence_is_not_hard_evidence():
    """材料里的数是材料自己的说法，不是市场事实——提示词已经这么写，档位必须同口径。

    否则用户贴一段自己写的判断，就能让结论被判成「有硬证据支撑」。
    """

    item = materials_as_evidence(_frame(_TABLE_QUESTION))[0]

    assert not is_hard_evidence_tier(item.evidence_tier, (item.content_hash,))


def test_table_numbers_reach_observations_not_only_the_detail_text():
    """表里的数走 ``observations``，不指望 ``detail``。

    ``detail`` 进沙箱截 600 字符、进模型视图截 240，一张 30 行的表两头都装不下。
    下游读结构化观察值「不回头解析 detail 自由文本」是仓内既定约定。
    """

    item = materials_as_evidence(_frame(_TABLE_QUESTION))[0]
    values = {(obs.subject, obs.metric): obs.value for obs in item.observations}

    assert values[("中际旭创", "营业收入(亿元)")] == 248.60
    assert values[("天孚通信", "营业成本(亿元)")] == 24.98
    # 行标签不当成指标：首列是主体，不该再冒出一条 metric="公司" 的观察值。
    assert not any(obs.metric == "公司" for obs in item.observations)


def test_units_are_kept_in_the_metric_name_and_never_rescaled():
    """``12.3%`` 记成 12.3、单位挂在指标名上，不悄悄除以 100。

    静默改写用户给的数字比读不出来危险得多：读不出来会报缺口，改写了只会算错。
    """

    question = "这两家谁的净利率高？\n\n公司\t净利率\n甲公司\t12.3%\n乙公司\t8.7%\n"
    item = materials_as_evidence(_frame(question))[0]
    values = {(obs.subject, obs.metric): obs.value for obs in item.observations}

    assert values[("甲公司", "净利率·%")] == 12.3


# -------------------------------------------------- 进了账本之后不会被悄悄拿掉


def test_material_newer_than_the_cutoff_survives_the_ledger():
    """**这条是本文件的重点。** 材料比信息截止日新时不能被静默丢弃。

    ``EvidenceLedger.append`` 对 ``source_date`` 晚于截止日的证据是 ``continue``——
    不抛、不记、不降级。用户贴一份比库还新的数据恰恰是最常见的场景（「今天刚出的
    数，你帮我算」），把材料内日期填进 ``source_date`` 会让这类回合退回原样：账本
    空、计算被拒、答案是一段合理的降级话术。所以材料**不填 source_date**。

    反证方式：把截止日钉在材料日期之前，再看它在不在账本里。
    """

    question = "帮我算这两天的环比。\n\n日期\t成交额(亿)\n2026-09-10\t18422.5\n2026-09-11\t19133.8\n"
    items = materials_as_evidence(_frame(question))
    assert items and items[0].source_date in (None, "")

    ledger = EvidenceLedger(information_cutoff=date(2026, 9, 1))
    ledger.append(items[0])

    assert len(ledger.items()) == 1


def test_calculation_no_longer_refuses_a_turn_that_only_has_material():
    """端到端：只有材料、没取过数的回合，计算工具必须接活。

    这正是实测里 21 次 ``no_bound_evidence`` 的那个形状。
    """

    items = materials_as_evidence(_frame(_TABLE_QUESTION))
    outcome = dc.run_derived_calculation(
        script="emit(build_result(summary={'n': len(EVIDENCE)}))",
        purpose="材料可计算性回归锁",
        evidence=items,
    )

    assert not isinstance(outcome, dc.CalculationError), getattr(outcome, "message", "")
    assert outcome.input_evidence_hashes == (items[0].content_hash,)


def test_the_script_can_read_the_pasted_numbers_out_of_evidence():
    """沙箱里真的能把用户贴的数取出来算——不是「有一条证据」而已。"""

    items = materials_as_evidence(_frame(_TABLE_QUESTION))
    script = (
        "rows = [o for e in EVIDENCE for o in e['observations']]\n"
        "rev = next(o['value'] for o in rows"
        " if o['subject'] == '中际旭创' and o['metric'].startswith('营业收入'))\n"
        "cost = next(o['value'] for o in rows"
        " if o['subject'] == '中际旭创' and o['metric'].startswith('营业成本'))\n"
        "emit(build_result(summary={'毛利率': round((rev - cost) / rev * 100, 2)}))\n"
    )
    outcome = dc.run_derived_calculation(
        script=script, purpose="材料取数回归锁", evidence=items
    )

    assert not isinstance(outcome, dc.CalculationError), getattr(outcome, "message", "")
    assert outcome.result["summary"]["毛利率"] == 31.0


# ------------------------------------------------------------ 哪些材料算「在场」


def test_earlier_material_enters_only_when_this_turn_points_at_it():
    """身份表带着旧材料是为了让模型认得「这篇」，不代表用户要拿它算数。

    证据账本是「本回合可引用的东西」：宽进会让上一个话题的表被算进这一轮。
    """

    block = (
        "user: 看看这个\n"
        "公司\t营收\n甲\t10\n乙\t20\n"
        "assistant: 收到。\n"
    )
    referenced = materials_as_evidence(
        _frame("这张表里谁的营收高？", conversation_context=block),
        block,
    )
    unrelated = materials_as_evidence(
        _frame("低空经济和商业航天哪个更值得看？", conversation_context=block),
        block,
    )

    assert len(referenced) == 1
    assert unrelated == ()


def test_recompute_on_the_same_numbers_rebinds_the_earlier_table():
    """「把假设改一个再算一遍……在同一批数上重算」——一个指代词都没有。

    2026-09-11 实测（run_20260911_195835_021357）用的就是这句话：``references_material``
    判 False，上一轮的表不入账，``derived_calculation`` 第一道门就拒，「改假设重算」
    这条工作流在结构上做不到。

    为什么重算不走 ``inputs_from_calc``：证据是内容寻址的，同一份材料重新入账得到
    **同一个 content_hash**，于是这一轮的 ``input_evidence_hashes`` 与上一轮逐字节相同，
    「在同一批数上算的」由哈希本身证明。``inputs_from_calc`` 要解的是另一个问题——
    取数昂贵或不可复现时别重取——对用户贴的表不适用。
    """

    block = f"user: {_TABLE_QUESTION}\nassistant: （上一轮给出了毛利率排序）\n"
    question = (
        "把假设改一个再算一遍：假设这三家的研发费用里有 30% 是资本化的、"
        "不计入当期费用，在同一批数上重算研发费用率，排序有没有变化。"
    )

    first = materials_as_evidence(_frame(_TABLE_QUESTION))
    again = materials_as_evidence(_frame(question, conversation_context=block), block)

    assert len(again) == 1
    # 同一批数的可验证定义：哈希相同，不是「模型说它用了同一批」。
    assert again[0].content_hash == first[0].content_hash


def test_recompute_without_any_material_is_not_turned_into_a_clarification():
    """严格放宽的反证：重算意图只能多绑材料，不能多问一句歧义。

    「刚才那个成交额再算一遍」的数来自库、从没有过材料。若让重算意图也把守缺材料
    车道，这种回合会被追问「你说的这篇是哪篇」——把一个能直接答的回合变成一次反问，
    比原来的漏绑更糟。
    """

    block = "user: 今天成交额多少\nassistant: 1.9 万亿\n"
    frame = _frame("刚才那个成交额再算一遍，换成剔除 ST 的口径。", conversation_context=block)

    assert frame.referenced_material_ids == ()
    assert frame.ambiguities == ()


def test_a_turn_without_any_material_produces_no_evidence():
    """没有材料的问题，本接线一个字节都不改——旧行为的守门测试。"""

    assert materials_as_evidence(_frame("今天沪深两市成交额多少？")) == ()


# --------------------------------------------------------- fincalc.table 两参形式


def test_table_accepts_the_two_argument_shape_models_actually_write():
    """``table(name, rows)``：实测里模型连撞 18 次 TypeError 的那个形状。

    工具契约的可用性由调用方**实际写出来的形状**定义，不由签名的整洁度定义。
    """

    built = fincalc.table("毛利率", [{"公司": "中际旭创", "毛利率": 31.0}])

    assert built["columns"] == ["公司", "毛利率"]
    assert built["rows"] == [["中际旭创", 31.0]]


def test_the_three_argument_form_is_unchanged():
    """严格放宽：原来能跑的调用逐字节不变。"""

    assert fincalc.table("t", ["a", "b"], [[1, 2]]) == {
        "name": "t",
        "columns": ["a", "b"],
        "rows": [[1, 2]],
        "unit": None,
        "note": None,
    }
