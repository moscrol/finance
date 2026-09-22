from __future__ import annotations

import re
import unittest

from intelligence.services.answer_claim_scope import (
    CALENDAR_DATASETS,
    FUND_FLOW_METRICS,
    RULE_FUND_FLOW,
    RULE_LATEST_TRADING_DAY,
    RULE_ORDER,
    RULE_SCOPE_OVERREACH,
    RULE_UNIT_GAP,
    ClaimEvidenceContext,
    review_answer_claims,
    split_sentences,
    summarize_issues,
)

# 2026-09-21 K3 首跑原句（docs/verification/2026-09-22-k3-acceptance/）
REAL_DATE_CLAIM = "2026-09-18（最近一个已收盘交易日）收盘 73.00 元，涨幅 7.75%。"
REAL_SCOPE_CLAIM = "长电科技当日涨幅 7.75%，跑赢其所有归属板块。"
REAL_FLOW_CLAIM = "成交额放大至 114.90 亿元，显示资金当日集中流入封测方向。"
REAL_UNIT_CLAIM = (
    "材料未注明公告日期、是否审计、合并或分部口径及币种单位，故精确性以该段文字为限。"
)
# 同一篇答案里并存的合法句："单位X"是指标名，不是单位缺口声明。
REAL_METRIC_NAME_LINES = (
    "材料没有给出单位投资额对应产能、达产进度、良率与爬坡周期。",
    "材料没有给出项目经济性测算，如折旧摊销、单位成本、投资回收期。",
)

MARKET_CONTEXT = ClaimEvidenceContext(
    question="长电科技最近表现如何？",
    evidence_dates=("2026-09-17", "2026-09-18"),
    calendar_evidence=False,
    compared_scope_count=5,
    known_scope_total=20,
    fund_flow_evidence=False,
)
MATERIAL_CONTEXT = ClaimEvidenceContext(
    question="某公司营业收入 180 亿元，净利润 9 亿元，投资收益 50 亿元，求净利率。",
)


def _rules(answer: str, context: ClaimEvidenceContext) -> list[str]:
    return [issue.rule for issue in review_answer_claims(answer, context).issues]


class LatestTradingDayRuleTests(unittest.TestCase):
    def test_flags_latest_trading_day_without_calendar_evidence(self) -> None:
        report = review_answer_claims(REAL_DATE_CLAIM, MARKET_CONTEXT)
        self.assertEqual([RULE_LATEST_TRADING_DAY], report.rules_hit())
        issue = report.issues[0]
        self.assertIn("2026-09-18", issue.reason)
        self.assertIn("库内", issue.remedy)

    def test_calendar_evidence_clears_the_same_sentence(self) -> None:
        context = ClaimEvidenceContext(
            evidence_dates=("2026-09-18",), calendar_evidence=True
        )
        self.assertEqual([], _rules(REAL_DATE_CLAIM, context))

    def test_in_database_qualifier_is_accepted(self) -> None:
        answer = "库内最新交易日为 2026-09-18，数据截至该日。"
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))

    def test_available_data_phrasing_is_accepted(self) -> None:
        answer = "以库内最新可用数据 2026-09-18 计算。"
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))

    def test_archived_disclaimer_is_not_inverted_into_a_violation(self) -> None:
        # 仓内已归档答案的原句（golden_answers/snapshots）：它否认自己是最新
        # 交易日，正是本规则想要的写法，当时被误报过一次。
        answer = (
            "以下使用截至 2026-07-08 的历史盘面快照，"
            "仅供辅助判断，不能视为最新交易日复盘。"
        )
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))

    def test_negation_alone_clears_the_claim(self) -> None:
        answer = "2026-09-18 并非最近一个已收盘交易日，仅是本次取到的最后一行。"
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))


class QualifierBindingTests(unittest.TestCase):
    """2026-09-22 审查探针：限定词必须紧挨断言，整句放行会放走真缺陷。"""

    def test_data_cutoff_wording_no_longer_clears_the_claim(self) -> None:
        # 首跑原句只把「数据日期：」换成「数据截至」，越界断言一字未改。
        # 旧实现会静默——而本模块自己的 remedy 正是这么建议写的。
        answer = "**数据截至 2026-09-18（最近一个已收盘交易日）**"
        self.assertEqual([RULE_LATEST_TRADING_DAY], _rules(answer, MARKET_CONTEXT))

    def test_snapshot_wording_alone_no_longer_clears_the_claim(self) -> None:
        answer = "以下为历史盘面快照，2026-07-08 是最近一个已收盘交易日。"
        self.assertEqual([RULE_LATEST_TRADING_DAY], _rules(answer, MARKET_CONTEXT))

    def test_binding_qualifier_next_to_the_claim_still_clears(self) -> None:
        answer = "库内最新交易日为 2026-09-18，数据截至该日。"
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))

    def test_every_claim_in_a_sentence_must_be_bound(self) -> None:
        answer = "库内最新交易日为 2026-09-18，也就是最近一个已收盘交易日。"
        self.assertEqual([RULE_LATEST_TRADING_DAY], _rules(answer, MARKET_CONTEXT))


class FundFlowDisclaimerShapeTests(unittest.TestCase):
    """审查方曾把「页脚免责仍报警」当成误报，实测后自己推翻。

    真正的合规写法（正文不谈方向、页脚声明未取数）本来就不命中；仍报的
    那两种，正文都还留着「资金集中流入」——与免责句自相矛盾，报警是对的。
    三条都钉成回归，防止后人再把它当误报“修”掉。
    """

    def test_footer_disclaimer_does_not_excuse_a_live_flow_claim(self) -> None:
        answer = (
            "显示资金当日集中流入封测方向。\n\n"
            "**数据说明**：本次未取资金流数据，方向不做判断。"
        )
        self.assertEqual([RULE_FUND_FLOW], _rules(answer, MARKET_CONTEXT))

    def test_activity_only_body_with_footer_is_clean(self) -> None:
        answer = (
            "成交额放大 133%，成交活跃度显著提升。\n\n"
            "**数据说明**：本次未取资金流数据，方向不做判断。"
        )
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))

    def test_immediate_retraction_still_reports_the_contradiction(self) -> None:
        answer = "显示资金当日集中流入封测方向。但本次未取资金流数据，该推断不成立。"
        self.assertEqual([RULE_FUND_FLOW], _rules(answer, MARKET_CONTEXT))


class BacktestFalsePositiveTests(unittest.TestCase):
    """1347 个历史 run 回测里压出来的误报，全是真实答案原句。

    共同特征：答案在**诚实地说自己没数据**，却被当成越界断言。
    误报这些句子等于惩罚诚实，比漏报更坏。
    """

    def test_available_in_this_round_is_a_bound_qualifier(self) -> None:
        answer = (
            "- 数据截至 2026-09-18，这是本轮可得的最近一个已收盘交易日，"
            "不是提问当天（2026-09-20，周末）的实时行情（E1）。"
        )
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))

    def test_currently_available_is_a_bound_qualifier(self) -> None:
        answer = (
            "证据边界：以上数据来自本地结构化市场总览数据，截至 2026-09-18 收盘，"
            "这是当前可得的最新已收盘交易日；"
        )
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))

    def test_not_retrieved_and_no_assertion_is_clean(self) -> None:
        answer = "两日的分板块净流入、主力资金明细未查得，资金来源结论不做断言。"
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))

    def test_asking_for_more_evidence_is_clean(self) -> None:
        answer = (
            "要证明增量资金，需要补充能区分的证据——如板块/个股级别的净流入数据、"
            "边际量（放量且上涨的板块结构）、新开户或两融余额变化等。"
        )
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))

    def test_cannot_verify_is_clean(self) -> None:
        answer = (
            "若仅指价与资金净流入双红，本地数据未返回当日板块级资金净流入字段，无法核验。"
        )
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))

    def test_bare_parenthetical_claim_still_reports(self) -> None:
        # 与上面对照：没有任何限定的裸断言，仍须报。
        answer = "**证据边界**：盘面数据截至 2026-09-18（最新已收盘交易日）；"
        self.assertEqual([RULE_LATEST_TRADING_DAY], _rules(answer, MARKET_CONTEXT))


class RegistryFactTests(unittest.TestCase):
    """证据常量跟着 finance_query 注册表走，漂了就红。"""

    def test_fund_flow_metric_constant_matches_registry(self) -> None:
        from intelligence.services import finance_query

        pattern = re.compile(r"(fund|net_inflow|net_amount)", re.IGNORECASE)
        registry = {
            name
            for dataset in finance_query._DATASETS.values()
            for name in (getattr(dataset, "metrics", {}) or {})
            if pattern.search(name)
        }
        self.assertEqual(registry, set(FUND_FLOW_METRICS))

    def test_no_trading_calendar_dataset_exists(self) -> None:
        # 日历事实只在 market_feature_store/trading_days.py，agent 取不到；
        # 所以 calendar_evidence 只能人工声明。哪天真加了日历 dataset，这条会红。
        from intelligence.services import finance_query

        calendar_like = {
            name
            for name in finance_query._DATASETS
            if re.search(r"(calendar|trading_day|trade_cal)", name, re.IGNORECASE)
        }
        self.assertEqual(set(), calendar_like)
        self.assertEqual(frozenset(), CALENDAR_DATASETS)


class ScopeRuleTests(unittest.TestCase):
    def test_flags_universal_scope_beyond_comparison(self) -> None:
        report = review_answer_claims(REAL_SCOPE_CLAIM, MARKET_CONTEXT)
        self.assertEqual([RULE_SCOPE_OVERREACH], report.rules_hit())
        self.assertIn("5", report.issues[0].reason)
        self.assertIn("20", report.issues[0].reason)

    def test_unknown_total_is_still_flagged(self) -> None:
        context = ClaimEvidenceContext(compared_scope_count=5, known_scope_total=None)
        report = review_answer_claims(REAL_SCOPE_CLAIM, context)
        self.assertEqual([RULE_SCOPE_OVERREACH], report.rules_hit())
        self.assertIn("全集本次未取", report.issues[0].reason)

    def test_full_coverage_is_accepted(self) -> None:
        context = ClaimEvidenceContext(compared_scope_count=20, known_scope_total=20)
        self.assertEqual([], _rules(REAL_SCOPE_CLAIM, context))

    def test_bounded_phrasing_is_accepted(self) -> None:
        answer = "已比较的 5 个板块中，全部板块均被跑赢。"
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))

    def test_no_scope_evidence_stays_silent(self) -> None:
        context = ClaimEvidenceContext(compared_scope_count=None, known_scope_total=20)
        self.assertEqual([], _rules(REAL_SCOPE_CLAIM, context))


class FundFlowRuleTests(unittest.TestCase):
    def test_flags_flow_direction_without_flow_evidence(self) -> None:
        report = review_answer_claims(REAL_FLOW_CLAIM, MARKET_CONTEXT)
        self.assertEqual([RULE_FUND_FLOW], report.rules_hit())
        self.assertIn("成交额", report.issues[0].reason)

    def test_flow_evidence_clears_the_claim(self) -> None:
        context = ClaimEvidenceContext(
            compared_scope_count=5, known_scope_total=20, fund_flow_evidence=True
        )
        self.assertEqual([], _rules(REAL_FLOW_CLAIM, context))

    def test_explicit_disclaimer_is_accepted(self) -> None:
        answer = "成交额放大至 114.90 亿元，但本次未取资金流数据，不能据此判断净流入。"
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))

    def test_activity_only_phrasing_is_accepted(self) -> None:
        answer = "成交额由 49.31 亿元放大至 114.90 亿元，成交活跃度明显提升。"
        self.assertEqual([], _rules(answer, MARKET_CONTEXT))

    def test_main_force_variant_is_flagged(self) -> None:
        answer = "主力持续净流入，筹码在集中。"
        self.assertEqual([RULE_FUND_FLOW], _rules(answer, MARKET_CONTEXT))


class UnitGapRuleTests(unittest.TestCase):
    def test_flags_unit_gap_when_input_gives_unit(self) -> None:
        report = review_answer_claims(REAL_UNIT_CLAIM, MATERIAL_CONTEXT)
        self.assertEqual([RULE_UNIT_GAP], report.rules_hit())
        self.assertIn("亿元", report.issues[0].reason)

    def test_currency_only_gap_is_accepted(self) -> None:
        answer = "材料未注明币种（人民币或美元），比值不受影响。"
        self.assertEqual([], _rules(answer, MATERIAL_CONTEXT))

    def test_metric_named_unit_is_not_a_unit_gap(self) -> None:
        # 首跑实测的误报形状："单位投资额""单位成本"是指标名称。
        for line in REAL_METRIC_NAME_LINES:
            with self.subTest(line=line):
                self.assertEqual([], _rules(line, MATERIAL_CONTEXT))

    def test_long_gap_list_ending_in_unit_is_flagged(self) -> None:
        # 首跑实测的漏报形状：真正的单位声明距动词 20 字，短窗口接不住。
        report = review_answer_claims(REAL_UNIT_CLAIM, MATERIAL_CONTEXT)
        self.assertEqual([RULE_UNIT_GAP], report.rules_hit())
        self.assertIn("币种单位", report.issues[0].quote)

    def test_question_without_unit_stays_silent(self) -> None:
        context = ClaimEvidenceContext(question="营业收入 180，净利润 9，求净利率。")
        self.assertEqual([], _rules(REAL_UNIT_CLAIM, context))


class ReportShapeTests(unittest.TestCase):
    def test_four_real_quotes_hit_four_distinct_rules(self) -> None:
        answer = "\n".join(
            [REAL_DATE_CLAIM, REAL_SCOPE_CLAIM, REAL_FLOW_CLAIM, REAL_UNIT_CLAIM]
        )
        context = ClaimEvidenceContext(
            question=MATERIAL_CONTEXT.question,
            evidence_dates=MARKET_CONTEXT.evidence_dates,
            compared_scope_count=5,
            known_scope_total=20,
        )
        report = review_answer_claims(answer, context)
        self.assertEqual(list(RULE_ORDER), report.rules_hit())
        self.assertFalse(report.clean)
        self.assertEqual(4, report.sentences_scanned)

    def test_rewritten_answer_is_clean(self) -> None:
        answer = (
            "库内最新可用交易日 2026-09-18（数据截至该日）收盘 73.00 元，涨幅 7.75%。"
            "已比较的 5 个板块中全部跑赢，其余归属板块本次未取。"
            "成交额由 49.31 亿元放大至 114.90 亿元，成交活跃度提升；"
            "本次未取资金流数据，方向不做判断。"
            "材料未注明币种（人民币或美元），比值不受影响。"
        )
        context = ClaimEvidenceContext(
            question=MATERIAL_CONTEXT.question,
            evidence_dates=MARKET_CONTEXT.evidence_dates,
            compared_scope_count=5,
            known_scope_total=20,
        )
        report = review_answer_claims(answer, context)
        self.assertTrue(report.clean, msg=summarize_issues(report.issues))

    def test_repeated_sentence_reports_once(self) -> None:
        answer = f"{REAL_FLOW_CLAIM}\n{REAL_FLOW_CLAIM}"
        self.assertEqual([RULE_FUND_FLOW], _rules(answer, MARKET_CONTEXT))

    def test_empty_answer_is_clean(self) -> None:
        report = review_answer_claims("", MARKET_CONTEXT)
        self.assertTrue(report.clean)
        self.assertEqual(0, report.sentences_scanned)

    def test_default_context_only_checks_text_only_rules(self) -> None:
        # 没有证据上下文时：范围与单位两条缺分母/缺输入，保持沉默不臆断；
        # 日期与资金方向两条只靠文本即可判定，照常报。
        answer = "\n".join(
            [REAL_DATE_CLAIM, REAL_SCOPE_CLAIM, REAL_FLOW_CLAIM, REAL_UNIT_CLAIM]
        )
        report = review_answer_claims(answer)
        self.assertEqual([RULE_LATEST_TRADING_DAY, RULE_FUND_FLOW], report.rules_hit())

    def test_serialized_report_carries_boundary_and_fields(self) -> None:
        report = review_answer_claims(REAL_SCOPE_CLAIM, MARKET_CONTEXT)
        payload = report.to_dict()
        self.assertEqual(1, payload["issue_count"])
        self.assertIn("boundary", payload)
        self.assertEqual(5, payload["context"]["compared_scope_count"])
        issue = payload["issues"][0]
        self.assertEqual(
            {"rule", "label", "quote", "reason", "remedy"}, set(issue.keys())
        )
        self.assertTrue(issue["quote"])

    def test_long_sentence_quote_is_truncated(self) -> None:
        answer = "板块表现：" + "长电科技表现强势，" * 12 + "跑赢其所有归属板块。"
        report = review_answer_claims(answer, MARKET_CONTEXT)
        self.assertEqual(1, len(report.issues))
        self.assertTrue(report.issues[0].quote.endswith("…"))
        self.assertLessEqual(len(report.issues[0].quote), 81)

    def test_summary_lines_pair_label_with_quote(self) -> None:
        report = review_answer_claims(REAL_FLOW_CLAIM, MARKET_CONTEXT)
        line = summarize_issues(report.issues)[0]
        self.assertTrue(line.startswith("无资金流证据推断资金方向："))
        self.assertIn("集中流入", line)


class SentenceSplitTests(unittest.TestCase):
    def test_splits_on_chinese_punctuation_and_newlines(self) -> None:
        self.assertEqual(
            ["甲。", "乙；", "丙", "丁！"], split_sentences("甲。乙；丙\n丁！")
        )

    def test_blank_input_yields_no_sentences(self) -> None:
        self.assertEqual([], split_sentences("  \n  "))


if __name__ == "__main__":
    unittest.main()
