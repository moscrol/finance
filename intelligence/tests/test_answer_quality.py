from __future__ import annotations

import unittest

from intelligence.services import llm_refine
from intelligence.services.answer_quality import (
    build_quality_context,
    classify_expectation_stage,
)


class ExpectationStageTests(unittest.TestCase):
    def test_l3_strong_but_l4_weak_is_fact_validated_but_priced_in(self) -> None:
        ctx = build_quality_context(
            evidence_lines=["英维克：公告披露液冷订单落地（公告, 2026-06-01, 质量 high） [R1]"],
            market_lines=["盘面未扩散，仅龙头高开低走 [S1]"],
            gap_lines=[],
        )

        self.assertEqual(ctx.stage, "事实验证但兑现分歧")
        self.assertIn("事实层不降级", ctx.guidance[0])
        self.assertTrue(any("预期是否已经提前交易" in item for item in ctx.critic_questions))

    def test_l1_l2_and_l4_without_l3_is_expectation_trade(self) -> None:
        ctx = build_quality_context(
            evidence_lines=["题材研报提示液冷需求扩张 [R1]", "核心层：英维克(002837|温控|high/L2) [G1]"],
            market_lines=["板块双红，涨停热度集中 [S1]"],
            gap_lines=["缺 L3 官方验证"],
        )

        self.assertEqual(ctx.stage, "预期交易")
        self.assertTrue(any("不是事实兑现" in item for item in ctx.guidance))
        self.assertTrue(any("缺哪个硬事实" in item for item in ctx.critic_questions))

    def test_methodology_checks_map_daily_review_signals_to_fupanhui_path(self) -> None:
        ctx = build_quality_context(
            evidence_lines=["核心层：瑞华泰(688323|PI膜|medium/L2) [G1]"],
            market_lines=[
                "市场环境：主升，成交 12345，涨停 68 / 跌停 5，容量前三 电子(29%,super_capacity) [S1]",
                "信号 double_red（90）：涨幅5.47%，边际量29.66%，成交883亿 [S2]",
                "信号 new_high_direction（44）：新高股14只，新高成交210亿 [S3]",
                "信号 limit_heat（12）：涨停5只，市场占比7.2 [S4]",
            ],
            gap_lines=[],
        )

        joined = "\n".join(ctx.methodology_checks)
        self.assertIn("市场量能", joined)
        self.assertIn("市场情绪", joined)
        self.assertIn("行业聚散度", joined)
        self.assertIn("板块承接", joined)
        self.assertIn("个股确认", joined)
        checklist = "\n".join(ctx.market_review_checklist)
        self.assertIn("周均线偏离度", checklist)
        self.assertIn("申万一级", checklist)
        self.assertIn("双红演变", checklist)
        self.assertIn("加权涨幅", checklist)

    def test_classify_expectation_stage_handles_empty_evidence(self) -> None:
        self.assertEqual(classify_expectation_stage(set(), set()), "证据不足")


class SynthesisPromptTests(unittest.TestCase):
    def test_methodology_projection_is_small_and_omits_stock_template(self) -> None:
        ctx = build_quality_context(
            evidence_lines=["RAG 检索架构说明"],
            market_lines=[],
            gap_lines=[],
        ).compact_for("methodology", "quick")

        block = ctx.to_prompt_block()
        self.assertLess(len(block), 1800)
        self.assertNotIn("个股/题材完整切入路径", block)
        self.assertNotIn("daily-agent 底层推理", block)

    def test_deep_stock_projection_keeps_hardness_and_lifecycle(self) -> None:
        ctx = build_quality_context(
            evidence_lines=["公司公告披露订单"],
            market_lines=["盘面未扩散"],
            gap_lines=["缺收入占比"],
        ).compact_for("stock_deep_dive", "deep")

        block = ctx.to_prompt_block()
        self.assertIn("个股/题材完整切入路径", block)
        self.assertIn("逻辑生命周期四问", block)
        self.assertLess(len(block), 3600)

    def test_quality_context_is_injected_into_synthesis_prompt(self) -> None:
        ctx = build_quality_context(
            evidence_lines=["英维克：公告披露液冷订单落地（公告, 2026-06-01, 质量 high） [R1]"],
            market_lines=["盘面未扩散 [S1]"],
            gap_lines=[],
        )

        messages = llm_refine.build_synthesis_messages(
            "英维克公告怎么看",
            "液冷服务器",
            "## 证据链\n- 英维克订单 [R1]",
            quality_context=ctx,
        )

        joined = "\n".join(str(m["content"]) for m in messages)
        self.assertIn("事实验证但兑现分歧", joined)
        self.assertIn("反方审稿", joined)
        self.assertIn("不要把盘面下跌直接等同于逻辑证伪", joined)
        self.assertIn("资金推动价格", joined)
        self.assertIn("成交占比环比", joined)
        self.assertIn("市场结构推演路径", joined)
        self.assertIn("硬性复盘视角", joined)
        self.assertIn("周均线偏离度", joined)
        self.assertIn("申万一级", joined)
        self.assertIn("双红演变", joined)
        self.assertIn("daily-agent 底层推理", joined)
        self.assertIn("old_logic_wakeup", joined)
        self.assertIn("盘面验证判断", joined)
        self.assertIn("历史有效性意识", joined)
        self.assertIn("不要出现“复盘会路径”", joined)
        self.assertIn("盘面反向解读", joined)
        self.assertIn("强板块、弱个股", joined)
        self.assertIn("支持什么结论，也否定什么结论", joined)
        self.assertIn("市场正在奖励谁、抛弃谁、犹豫谁", joined)
        self.assertIn("个股/题材完整切入路径", joined)
        self.assertIn("公司本体", joined)
        self.assertIn("产业链暴露", joined)
        self.assertIn("行业容量", joined)
        self.assertIn("题材结构", joined)
        self.assertIn("二阶导发散", joined)
        self.assertIn("逻辑生命周期四问", joined)
        self.assertIn("这条逻辑有没有真正产生过市场价值", joined)
        self.assertIn("CAR、相对强度、成交额边际", joined)
        self.assertIn("输出前质检器", joined)
        self.assertIn("覆盖率门槛", joined)
        self.assertIn("第一性原理门槛", joined)
        self.assertIn("用户影子反驳", joined)
        self.assertIn("是不是又在套模板", joined)
        self.assertIn("它是不是这条产业链的最优表达", joined)

    def test_quality_context_includes_daily_agent_lifecycle_framework(self) -> None:
        ctx = build_quality_context(
            evidence_lines=["题材研报提示半导体设备需求扩张 [R1]"],
            market_lines=[
                "priority=184.57，强势股=华特气体, 兴福电子；生命周期=升温验证；盘面验证=强验证 [S1]",
                "信号 double_red + new_high_direction + limit_heat；涨停 5 只，新高 14 只 [S2]",
            ],
            gap_lines=["缺 L3 官方验证"],
        )

        block = ctx.to_prompt_block()

        self.assertIn("新出现 → 旧逻辑唤醒 → 升温验证 → 加速定价", block)
        self.assertIn("priority变化", block)
        self.assertIn("强势股变化", block)
        self.assertIn("触发信号变化", block)
        self.assertIn("领先核心、同步确认、后排补涨", block)
        self.assertIn("证据层是否升级", block)
        self.assertIn("强势股是否扩散", block)
        self.assertIn("半衰期", block)

    def test_quality_context_includes_pre_output_quality_gate_and_shadow_critic(self) -> None:
        ctx = build_quality_context(
            evidence_lines=["瑞华泰：主营高性能 PI 膜，热控 PI 进入供应链，但缺客户金额 [R1]"],
            market_lines=["市场探底，涨家数MA5回落，先进封装涨停扩散收缩 [S1]"],
            gap_lines=["缺 L3 订单、客户验证、收入占比"],
        )

        block = ctx.to_prompt_block()

        self.assertIn("输出前质检器", block)
        self.assertIn("覆盖率门槛", block)
        self.assertIn("盘面融合门槛", block)
        self.assertIn("证据分层门槛", block)
        self.assertIn("二阶导门槛", block)
        self.assertIn("用户影子反驳", block)
        self.assertIn("是不是只看了个股", block)
        self.assertIn("证据够硬吗", block)
        self.assertIn("有没有主动寻找反证", block)

    def test_quality_context_includes_narrative_composer(self) -> None:
        ctx = build_quality_context(
            evidence_lines=["裕太微：PHY 是事实，DSP 是远期线索；缺客户验证 [R1]"],
            market_lines=["半导体板块强修复，但裕太微未进涨停/新高前排 [S1]"],
            gap_lines=["缺 L3 客户订单、DSP 流片和量产证据"],
        )

        block = ctx.to_prompt_block()

        self.assertIn("叙事编排器", block)
        self.assertIn("核心矛盾句", block)
        self.assertIn("视角不是小标题", block)
        self.assertIn("每段都要回答", block)
        self.assertIn("资金为什么选择/放弃/犹豫", block)

    def test_quality_context_requires_reverse_market_reasoning(self) -> None:
        ctx = build_quality_context(
            evidence_lines=["汇成股份：DDIC封测基本盘，参股鑫丰科技 [R1]"],
            market_lines=[
                "先进封装 priority 上升，强势股为中巨芯、雅克科技、有研粉材；汇成股份未进强势股榜 [S1]",
                "市场顶部横盘，成交额低于20日均量，涨家数MA5回落 [S2]",
            ],
            gap_lines=["缺先进封装客户验证"],
        )

        block = ctx.to_prompt_block()

        self.assertIn("板块 priority 上升但目标股不进强势股榜", block)
        self.assertIn("个股反弹、板块缩量/情绪回落", block)
        self.assertIn("技术修复或存量资金承接", block)
        self.assertIn("奖励的是容量核心/新高核心/涨停发动机", block)

    def test_quality_context_adds_sellside_winrate_reasoning_when_relevant(self) -> None:
        ctx = build_quality_context(
            evidence_lines=[
                "晚间卖方观点：机构胜率榜 T+5 强，覆盖密度显示功率半导体仅 1 家覆盖 [R1]",
                "卖方观点含涨价、交期和扩产信息 [R2]",
            ],
            market_lines=["盘面方向待接双红、新高集群和涨停热度验证 [S1]"],
            gap_lines=[],
        )

        block = ctx.to_prompt_block()

        self.assertIn("晚间卖方/机构胜率发散", block)
        self.assertIn("胜率不是买入信号", block)
        self.assertIn("T+5 强但 T+10 衰减", block)
        self.assertIn("高胜率机构推低覆盖方向", block)
        self.assertIn("优先发散、只作确认、反向谨慎", block)

    def test_quality_context_adds_high_position_mainline_reasoning_when_relevant(self) -> None:
        ctx = build_quality_context(
            evidence_lines=[
                "AI硬件主线里 CPO、PCB 高位分歧，半导体设备和存储仍有长鑫、海力士事件锚点 [R1]",
                "玻璃桥仍需验证量产阶段和是否解决真实瓶颈 [R2]",
            ],
            market_lines=["市场缩量，电子成交占比高，主线拥挤，题材从顺势进入第一次分歧 [S1]"],
            gap_lines=[],
        )

        block = ctx.to_prompt_block()

        self.assertIn("高位主线反证与生命周期推理", block)
        self.assertIn("边际预期、流动性、证据硬度和位置约束", block)
        self.assertIn("产业瑕疵审查", block)
        self.assertIn("发酵窗口、定价窗口、兑现窗口和二次验证窗口", block)
        self.assertIn("顺势、主升后第一次分歧", block)


if __name__ == "__main__":
    unittest.main()
