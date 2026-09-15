"""合规词表的有牙测试（roadmap G-12a）。

每条错误码都要有**正例 + 反例**：只钉正例的门禁，改成 ``return []`` 也全绿。
反例同样重要——过度拦截会把合法的观察变量逼下线，那种误伤比漏一个词更难被发现。
"""

from __future__ import annotations

import unittest

from intelligence.services import compliance_gate as cg


class HitTests(unittest.TestCase):
    def _codes(self, text: str) -> set[str]:
        return {h.code for h in cg.scan(text)}

    def test_direction_words_rejected(self) -> None:
        for text in ("明天可以低吸", "建议加仓", "该清仓了", "看多这个方向"):
            self.assertIn(cg.E_DIRECTION, self._codes(text), text)

    def test_timing_words_rejected(self) -> None:
        for text in ("给个买点", "明天买什么", "介入时点在哪"):
            self.assertIn(cg.E_TIMING, self._codes(text), text)

    def test_next_day_direction_rejected(self) -> None:
        self.assertIn(cg.E_NEXT_DAY_DIRECTION, self._codes("说说第二天的方向"))

    def test_target_price_rejected(self) -> None:
        for text in ("目标价 30", "能涨到 25 元", "看到 18 块"):
            self.assertIn(cg.E_TARGET_PRICE, self._codes(text), text)

    def test_probability_with_number_rejected(self) -> None:
        for text in ("胜率 70%", "把握80", "大概率会延续", "七成把握"):
            self.assertIn(cg.E_PROBABILITY, self._codes(text), text)

    def test_bare_probability_word_allowed(self) -> None:
        """裸「概率」不带数字时放行——产品要说得出「本产品不给概率」这句话。"""
        self.assertNotIn(cg.E_PROBABILITY, self._codes("本产品不给概率与胜率"))

    def test_stock_code_rejected(self) -> None:
        for text in ("600519.SH 值得看", "关注 300750", "002594 的公告"):
            self.assertIn(cg.E_STOCK_SCOPE, self._codes(text), text)

    def test_sector_code_and_date_not_stock(self) -> None:
        """板块代码与日期串不能被当成个股——误拦会把合法实体挡在门外。"""
        for text in ("801080.TI 的边际量", "883418.FP 走强", "20260906 的切片"):
            self.assertNotIn(cg.E_STOCK_SCOPE, self._codes(text), text)

    def test_holding_words_not_direction(self) -> None:
        """「基金重仓股占比」是合法观察变量：拦它等于逼用户放弃一个能看的量。"""
        for text in ("基金重仓股占比变化", "两融余额与仓位水平"):
            self.assertNotIn(cg.E_DIRECTION, self._codes(text), text)

    def test_strategy_word_only_in_marketing_codes(self) -> None:
        codes = {h.code for h in cg.scan("这套策略很稳", codes=cg.MARKETING_CODES)}
        self.assertIn(cg.E_STRATEGY_WORD, codes)
        # 观察剧本硬门不含这条：内部字段里出现「策略」不该拦，它是对外用词纪律。
        self.assertNotIn(cg.E_STRATEGY_WORD, self._codes("这套策略很稳"))

    def test_internal_module_names_allowed(self) -> None:
        for text in ("策略一矩阵每日更新", "策略进化 suggest", "策略矩阵"):
            codes = {h.code for h in cg.scan(text, codes=cg.MARKETING_CODES)}
            self.assertNotIn(cg.E_STRATEGY_WORD, codes, text)

    def test_hit_carries_fixable_context(self) -> None:
        (hit,) = [h for h in cg.scan("明天要不要低吸这个题材") if h.code == cg.E_DIRECTION]
        self.assertEqual(hit.term, "低吸")
        self.assertIn("低吸", hit.context)
        self.assertTrue(hit.hint, "错误必须带可执行的改法，只给错误码等于没提示")

    def test_clean_text_passes(self) -> None:
        self.assertEqual(cg.scan("盘面轨：成交额与边际量是否延续"), [])

    def test_codes_subset_is_respected(self) -> None:
        text = "目标价 30 且大概率延续"
        self.assertEqual(cg.scan(text, codes=(cg.E_TARGET_PRICE,))[0].code, cg.E_TARGET_PRICE)
        self.assertEqual(len(cg.scan(text, codes=(cg.E_TARGET_PRICE,))), 1)

    def test_is_stock_entity(self) -> None:
        self.assertTrue(cg.is_stock_entity("600519.SH"))
        self.assertTrue(cg.is_stock_entity("300750"))
        self.assertFalse(cg.is_stock_entity("801080.TI"))
        self.assertFalse(cg.is_stock_entity("算力租赁"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
