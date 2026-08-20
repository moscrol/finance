from __future__ import annotations

import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.market_regime_analogs import (
    DEFAULT_WINDOW,
    FEATURES,
    find_regime_analogs,
    load_market_regime_artifact,
    load_market_regime_vectors,
    parse_regime_intent,
    regime_block_for_llm,
    signature_distance,
    standardize_vectors,
    window_signature,
)

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None


class ParseRegimeIntentTests(unittest.TestCase):
    def test_env_plus_analog_terms_route(self) -> None:
        self.assertTrue(parse_regime_intent("历史上有没有类似现在这种情绪环境"))
        self.assertTrue(parse_regime_intent("对标历史，现在的行情像哪一段"))
        self.assertTrue(parse_regime_intent("上一次这种涨停潮之后市场怎么走"))

    def test_env_only_does_not_route(self) -> None:
        self.assertFalse(parse_regime_intent("今天市场情绪怎么样"))
        self.assertFalse(parse_regime_intent("现在的盘面赚钱效应如何"))

    def test_theme_level_analog_does_not_route(self) -> None:
        # 题材级类比是 D8 的领地：只有类比词、没有环境词 → 不触发
        self.assertFalse(parse_regime_intent("历史上信创类似的走势后来怎么走"))
        self.assertFalse(parse_regime_intent(""))


def _day(i: int) -> str:
    return (date(2025, 1, 1) + timedelta(days=i)).isoformat()


def _vec(i: int, hot: bool) -> dict:
    """合成每日情绪向量：hot=涨停潮情绪环境，否则为缩量弱势环境。"""
    if hot:
        return {
            "trade_date": _day(i),
            "total_amount": 18000.0,
            "advancers": 3800.0,
            "limit_up": 120.0,
            "limit_down": 5.0,
            "sh_deviation_pct": 3.0,
            "sh_index_pct_chg": 1.2,
            "max_boards": 7.0,
            "double_red_theme_count": 12.0,
            "top1_theme_share": 0.3,
            "new_high_count": 200.0,
        }
    return {
        "trade_date": _day(i),
        "total_amount": 8000.0,
        "advancers": 1500.0,
        "limit_up": 30.0,
        "limit_down": 20.0,
        "sh_deviation_pct": -1.5,
        "sh_index_pct_chg": -0.3,
        "max_boards": 3.0,
        "double_red_theme_count": 2.0,
        "top1_theme_share": 0.1,
        "new_high_count": 20.0,
    }


def _history(n: int, hot_ranges: list[tuple[int, int]]) -> list[dict]:
    return [
        _vec(i, any(a <= i < b for a, b in hot_ranges))
        for i in range(n)
    ]


class StandardizeTests(unittest.TestCase):
    def test_z_scores_and_none_preserved(self) -> None:
        rows = _history(60, [(0, 30)])
        rows[5]["limit_up"] = None
        z_rows, dropped = standardize_vectors(rows)
        self.assertEqual(dropped, [])
        self.assertIsNone(z_rows[5]["limit_up"])
        values = [r["limit_up"] for r in z_rows if r["limit_up"] is not None]
        self.assertAlmostEqual(sum(values) / len(values), 0.0, places=6)

    def test_constant_and_empty_features_dropped(self) -> None:
        rows = _history(60, [])
        for r in rows:
            r["top1_theme_share"] = 0.1  # 常量维（本身就是常量历史）
            r["new_high_count"] = None  # 全空维
        z_rows, dropped = standardize_vectors(rows)
        self.assertIn("new_high_count", dropped)
        # 全弱势历史中很多维都是常量 → 常量维应被剔除而非产生除零
        self.assertNotIn("total_amount", z_rows[0].keys() - set())
        for feat in dropped:
            self.assertNotIn(feat, z_rows[0])


class SignatureDistanceTests(unittest.TestCase):
    def test_identical_windows_distance_zero(self) -> None:
        rows = _history(120, [(0, 120)])
        # 加一点变化避免全常量被剔除
        for i, r in enumerate(rows):
            r["total_amount"] = 18000.0 + (i % 7) * 100
            r["limit_up"] = 120.0 + (i % 5)
        z_rows, _ = standardize_vectors(rows)
        a = window_signature(z_rows[0:20])
        b = window_signature(z_rows[0:20])
        d = signature_distance(a, b, total_dims=len(FEATURES))
        self.assertIsNotNone(d)
        self.assertAlmostEqual(d, 0.0, places=9)

    def test_missing_dims_penalized(self) -> None:
        rows = _history(120, [(0, 60)])
        for i, r in enumerate(rows):
            r["total_amount"] = 10000.0 + i * 10
        z_rows, _ = standardize_vectors(rows)
        full_a = window_signature(z_rows[0:20])
        full_b = window_signature(z_rows[20:40])
        d_full = signature_distance(full_a, full_b, total_dims=len(FEATURES))
        # 同样两个窗口，砍掉一半维度 → 覆盖率惩罚应使距离不小于全维版
        half_stats_a = dict(list(full_a.stats.items())[: max(1, full_a.dims // 2)])
        half_stats_b = {k: v for k, v in full_b.stats.items() if k in half_stats_a}
        from intelligence.services.market_regime_analogs import RegimeSignature

        d_half = signature_distance(
            RegimeSignature(half_stats_a),
            RegimeSignature(half_stats_b),
            total_dims=len(FEATURES),
        )
        assert d_full is not None and d_half is not None
        # 惩罚系数 total/used：维度减半 → 系数翻倍
        self.assertGreaterEqual(d_half * 1e9, d_full * 1e9)

    def test_no_shared_dims_returns_none(self) -> None:
        from intelligence.services.market_regime_analogs import RegimeSignature

        a = RegimeSignature({"limit_up": (1.0, 0.0)})
        b = RegimeSignature({"max_boards": (1.0, 0.0)})
        self.assertIsNone(signature_distance(a, b, total_dims=len(FEATURES)))


class FindRegimeAnalogsTests(unittest.TestCase):
    def test_short_history_returns_none(self) -> None:
        current, analogs, _ = find_regime_analogs(_history(30, []), window=DEFAULT_WINDOW)
        self.assertIsNone(current)
        self.assertEqual(analogs, [])

    def test_finds_planted_hot_regime(self) -> None:
        # 历史 40-60 日是涨停潮环境，当前（末尾 20 日）也是涨停潮 → 应命中历史热窗口
        vectors = _history(200, [(40, 60), (180, 200)])
        current, analogs, dropped = find_regime_analogs(vectors, window=20)
        assert current is not None
        self.assertTrue(analogs)
        best = analogs[0]
        self.assertEqual(best["start_date"], _day(40))
        self.assertEqual(best["end_date"], _day(59))
        # 命中窗口的原始摘要应是热环境量纲
        self.assertAlmostEqual(best["raw_summary"]["limit_up"], 120.0)
        # 后续 5/10/20 日事实存在且是弱势环境的事实
        for h in (5, 10, 20):
            fwd = best["forwards"][h]
            assert fwd is not None
            self.assertIsNotNone(fwd["sh_index_cum_pct"])
            self.assertAlmostEqual(fwd["avg_limit_up"], 30.0)

    def test_analog_windows_do_not_overlap(self) -> None:
        vectors = _history(300, [(40, 60), (100, 120), (280, 300)])
        _, analogs, _ = find_regime_analogs(vectors, window=20, top_k=3)
        spans = [(a["start_date"], a["end_date"]) for a in analogs]
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                s1, e1 = spans[i]
                s2, e2 = spans[j]
                self.assertTrue(e1 <= s2 or e2 <= s1)

    def test_missing_feature_dims_still_match(self) -> None:
        vectors = _history(200, [(40, 60), (180, 200)])
        for r in vectors:
            r["new_high_count"] = None
            r["top1_theme_share"] = None
        current, analogs, dropped = find_regime_analogs(vectors, window=20)
        assert current is not None
        self.assertTrue(analogs)
        self.assertIn("new_high_count", dropped)
        self.assertIn("top1_theme_share", dropped)


@unittest.skipIf(duckdb is None, "duckdb 不可用")
class LoaderAndBlockTests(unittest.TestCase):
    def _make_db(
        self,
        path: Path,
        n: int = 200,
        hot_ranges: list[tuple[int, int]] | None = None,
        with_aux: bool = True,
    ) -> None:
        hot_ranges = hot_ranges if hot_ranges is not None else [(40, 60), (180, 200)]
        con = duckdb.connect(str(path))
        con.execute(
            "create table fact_market_daily ("
            "trade_date date, total_amount double, advancers integer, "
            "limit_up integer, limit_down integer, sh_deviation_pct double, "
            "sh_index_pct_chg double)"
        )
        if with_aux:
            con.execute(
                "create table fact_limit_advance_daily "
                "(trade_date date, stock_ts_code varchar, boards integer)"
            )
            con.execute(
                "create table fact_sector_daily "
                "(trade_date date, sector_name varchar, pct_chg double, "
                "diff_ratio double, amount double)"
            )
            con.execute(
                "create table fact_theme_limit_heat_daily "
                "(trade_date date, sector_name varchar, market_share double)"
            )
            con.execute(
                "create table fact_stock_high_daily "
                "(trade_date date, stock_ts_code varchar)"
            )
        for i in range(n):
            hot = any(a <= i < b for a, b in hot_ranges)
            v = _vec(i, hot)
            con.execute(
                "insert into fact_market_daily values (?, ?, ?, ?, ?, ?, ?)",
                [
                    v["trade_date"], v["total_amount"], v["advancers"],
                    v["limit_up"], v["limit_down"], v["sh_deviation_pct"],
                    v["sh_index_pct_chg"],
                ],
            )
            if not with_aux:
                continue
            con.execute(
                "insert into fact_limit_advance_daily values (?, 's1', ?)",
                [v["trade_date"], int(v["max_boards"])],
            )
            for k in range(int(v["double_red_theme_count"])):
                con.execute(
                    "insert into fact_sector_daily values (?, ?, 2.5, 15.0, 900.0)",
                    [v["trade_date"], f"题材{k}"],
                )
            con.execute(
                "insert into fact_theme_limit_heat_daily values (?, '题材0', ?)",
                [v["trade_date"], v["top1_theme_share"]],
            )
            for k in range(int(v["new_high_count"] // 20)):
                con.execute(
                    "insert into fact_stock_high_daily values (?, ?)",
                    [v["trade_date"], f"h{k}"],
                )
        con.close()

    def test_loader_assembles_vectors(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db, n=60, hot_ranges=[(0, 30)])
            con = duckdb.connect(str(db), read_only=True)
            vectors, missing = load_market_regime_vectors(con)
            con.close()
        self.assertEqual(missing, [])
        self.assertEqual(len(vectors), 60)
        hot = vectors[0]
        self.assertAlmostEqual(hot["total_amount"], 18000.0)
        self.assertEqual(hot["max_boards"], 7.0)
        self.assertEqual(hot["double_red_theme_count"], 12.0)
        self.assertIsNotNone(hot["new_high_count"])

    def test_block_renders_with_citation_and_discipline(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            block = regime_block_for_llm(db)
        self.assertIn("[D10]", block)
        self.assertIn("当前情绪环境", block)
        self.assertIn("后续5日", block)
        self.assertIn("不是概率预测", block)

    def test_missing_aux_tables_degrade_with_gap_line(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db, with_aux=False)
            artifact = load_market_regime_artifact(db)
            block = regime_block_for_llm(db)
        self.assertTrue(artifact.available)
        for feat in ("max_boards", "double_red_theme_count", "top1_theme_share", "new_high_count"):
            self.assertIn(feat, artifact.missing_features)
        self.assertIn("数据缺口", block)
        self.assertIn("已按覆盖率降权", block)

    def test_short_history_declares_degrade(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db, n=30, hot_ranges=[(0, 30)])
            artifact = load_market_regime_artifact(db)
            block = regime_block_for_llm(db)
        self.assertFalse(artifact.available)
        self.assertIsNotNone(artifact.degrade_reason)
        self.assertEqual(block, "")

    def test_missing_db_returns_empty(self) -> None:
        self.assertEqual(regime_block_for_llm("/nonexistent/x.duckdb"), "")
        artifact = load_market_regime_artifact("/nonexistent/x.duckdb")
        self.assertFalse(artifact.available)
        self.assertIsNotNone(artifact.degrade_reason)

    def test_artifact_payload_serializes(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            artifact = load_market_regime_artifact(db)
        payload = artifact.to_payload()
        self.assertEqual(payload["evidence_id"], "D10")
        self.assertTrue(payload["available"])
        self.assertIsInstance(payload["analogs"], list)
        self.assertIsInstance(payload["current_summary"], dict)


class WiringTests(unittest.TestCase):
    """D10 接线断言（slice 2）：注册表门控 / claim 状态 / 路由 / 研究操作符。"""

    def test_registry_gating_via_enabled_providers(self) -> None:
        from intelligence.services import evidence_registry
        from intelligence.services.ask import AskOptions

        on = AskOptions(query="q")
        off = AskOptions(
            query="q",
            enabled_providers=evidence_registry.without_providers("D10"),
        )
        self.assertTrue(evidence_registry.provider_enabled(on, "D10"))
        self.assertFalse(evidence_registry.provider_enabled(off, "D10"))

    def test_d10_claims_are_inferred_not_verified(self) -> None:
        # 类比是推演不是当期事实：D10 行绝不能被铸成 VERIFIED（同 D8 的 P0 纪律）
        from intelligence.services.answer_model import ClaimStatus
        from intelligence.services.ask_synthesis import _claims_from_data_block

        claims = _claims_from_data_block(
            "- 与 2025-12 情绪窗口距离 0.64，后续 10 日指数 +0.97%",
            "D10",
            "市场情绪环境类比",
            "全市场",
        )
        self.assertTrue(claims)
        self.assertTrue(all(c.status == ClaimStatus.INFERRED for c in claims))

    def test_regime_query_routes_to_comparison_analog(self) -> None:
        from intelligence.services.turn_controller import _fine_grained_route_row

        row = _fine_grained_route_row("对标历史，现在这种情绪环境像哪一段")
        assert row is not None
        self.assertEqual(row.route_id, "comparison_analog")

    def test_regime_query_yields_history_analog_operator(self) -> None:
        from intelligence.services.query_understanding import _research_operators

        self.assertIn(
            "history_analog",
            _research_operators("对标历史，现在这种情绪环境像哪一段"),
        )


if __name__ == "__main__":
    unittest.main()
