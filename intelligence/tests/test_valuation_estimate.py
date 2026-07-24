"""researcher-valuation P2：估值确定性计算的纯函数测试（不联网）."""

from __future__ import annotations

import unittest

from intelligence.services import valuation_estimate as ve


def _snap(code: str, name: str, mv=None, pe=None, pb=None) -> ve.ValuationSnapshot:
    return ve.ValuationSnapshot(ts_code=code, name=name, total_mv_yi=mv, pe_ttm=pe, pb=pb)


class TestPeerBand(unittest.TestCase):
    def test_band_min_median_max(self):
        self.assertEqual(ve.peer_band([30.0, 10.0, 20.0]), (10.0, 20.0, 30.0))

    def test_band_even_count_uses_mid_average(self):
        self.assertEqual(ve.peer_band([10.0, 20.0, 30.0, 40.0]), (10.0, 25.0, 40.0))

    def test_band_filters_none_and_nonpositive(self):
        self.assertEqual(ve.peer_band([None, -5.0, 12.0, 18.0]), (12.0, 15.0, 18.0))

    def test_band_needs_two_valid(self):
        self.assertIsNone(ve.peer_band([15.0, None]))


class TestPercentileRank(unittest.TestCase):
    def test_rank(self):
        self.assertEqual(ve.percentile_rank([10.0, 20.0, 30.0, 40.0], 30.0), 75.0)

    def test_rank_missing_target(self):
        self.assertIsNone(ve.percentile_rank([10.0, 20.0], None))


class TestBuildValuationBlock(unittest.TestCase):
    def test_block_with_target_and_peers(self):
        target = _snap("600000", "目标公司", mv=500.0, pe=25.0, pb=3.0)
        peers = [
            _snap("600001", "可比甲", pe=20.0, pb=2.5),
            _snap("600002", "可比乙", pe=30.0, pb=4.0),
            _snap("600003", "可比丙", pe=40.0, pb=5.0),
        ]
        block = ve.build_valuation_block(target, peers)
        self.assertIn("[D5]", block)
        self.assertIn("目标公司", block)
        self.assertIn("20.0 ~ 40.0", block)  # PE band
        self.assertIn("PB 情景计算锚", block)
        self.assertIn("保守 2.5 ~ 3.0 倍", block)
        self.assertIn("中性 3.0 ~ 4.0 倍", block)
        self.assertIn("乐观 4.0 ~ 5.0 倍", block)
        self.assertIn("假设净资产不变", block)
        self.assertIn("缺历史分位", block)  # explicit gap
        self.assertIn("禁止输出单点目标价", block)

    def test_block_without_target_is_gap(self):
        block = ve.build_valuation_block(None, [])
        self.assertIn("缺目标估值快照", block)

    def test_block_fetch_disabled(self):
        block = ve.build_valuation_block(None, [], fetch_disabled=True)
        self.assertIn(ve.FETCH_ENV_FLAG, block)

    def test_block_without_peers_marks_gap(self):
        target = _snap("600000", "目标公司", mv=100.0, pe=15.0, pb=2.0)
        block = ve.build_valuation_block(target, [])
        self.assertIn("缺可比集", block)


class TestSnapshotsFor(unittest.TestCase):
    def test_skips_failed_fetch(self):
        def fake_fetch(code, name=""):
            if code == "600001":
                return None
            return _snap(code, name, pe=10.0)

        out = ve.snapshots_for([("600001", "甲"), ("600002", "乙")], fetcher=fake_fetch)
        self.assertEqual([s.ts_code for s in out], ["600002"])


class TestSecid(unittest.TestCase):
    def test_market_prefix(self):
        self.assertEqual(ve._secid("600519.SH"), "1.600519")
        self.assertEqual(ve._secid("000001"), "0.000001")
        self.assertEqual(ve._secid("300750.SZ"), "0.300750")


if __name__ == "__main__":
    unittest.main()


class TestValuationBlockWiring(unittest.TestCase):
    def test_valuation_exemplar_prefix_routed(self):
        from intelligence.services.ask import _EXEMPLAR_PREFIX_BY_TYPE
        from intelligence.services.answer_orchestrator import QUESTION_VALUATION

        self.assertEqual(_EXEMPLAR_PREFIX_BY_TYPE[QUESTION_VALUATION], "valuation-")

    def test_block_for_llm_disabled_by_env(self):
        import os

        from intelligence.services.ask import _valuation_block_for_llm

        old = os.environ.get(ve.FETCH_ENV_FLAG)
        os.environ[ve.FETCH_ENV_FLAG] = "0"
        try:
            block = _valuation_block_for_llm("600519 贵不贵", None, "/nonexistent.duckdb")
            self.assertIn(ve.FETCH_ENV_FLAG, block)
        finally:
            if old is None:
                os.environ.pop(ve.FETCH_ENV_FLAG, None)
            else:
                os.environ[ve.FETCH_ENV_FLAG] = old

    def test_block_for_llm_code_only_query_uses_fetcher(self):
        from intelligence.services.ask import _valuation_block_for_llm

        def fake_fetch(code, name=""):
            return _snap(code, name or "目标", mv=100.0, pe=18.0, pb=2.0)

        block = _valuation_block_for_llm(
            "600519 贵不贵", None, "/nonexistent.duckdb", fetcher=fake_fetch
        )
        self.assertIn("[D5]", block)
        self.assertIn("PE(TTM) 18.0", block)
