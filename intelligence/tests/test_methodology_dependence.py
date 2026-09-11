"""OPT-05 相关样本：依赖感知读数（日期块重采样）、保守合成、跨窗 purge。

钉 spec 验收原文的机器化：
- 「复制同日相关板块不会凭复制次数提升有效独立证据」
- 「有效块不足时输出 insufficient，不能退回原始二项检验宣布通过」
- 「固定种子重复统计结果一致」
- 「发现窗末尾 T+5 outcome 跨界被剔除」
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from intelligence.services.methodology_backtest.labels import build_labels
from intelligence.services.methodology_backtest.outcomes import build_outcomes
from intelligence.services.methodology_backtest.stats import (
    block_bootstrap_readout,
    combined_verdict,
)

REPO = Path(__file__).resolve().parents[2]
SELFTEST = REPO / "scripts" / "methodology_backtest_selftest.py"


def _events_spread(n_dates: int, per_day: int, *, success_rate: float = 1.0) -> list[tuple[str, str, bool]]:
    """n_dates 个连续事件日 × 每日 per_day 个实体；前 success_rate 比例命中。"""
    out: list[tuple[str, str, bool]] = []
    for i in range(n_dates):
        d = f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}"
        for j in range(per_day):
            out.append((f"e{j}", d, (i * per_day + j) % 100 < success_rate * 100))
    return out


class TestBlockBootstrap:
    def test_同日复制不提升有效独立证据(self) -> None:
        """400 个事件：散在 60 天 → 块数够、可 supported；同样 400 个挤在 6 天 → insufficient_blocks。
        事件总数相同，结论只由独立单元（日期块）决定——复制多少次都变不出证据。"""
        spread = block_bootstrap_readout(
            _events_spread(60, 7), p0=0.5, block_len=5
        )
        assert spread.n_blocks >= 10 and spread.verdict == "supported", spread.to_dict()
        crowded = block_bootstrap_readout(
            _events_spread(6, 70), p0=0.5, block_len=5
        )
        assert crowded.n_events == spread.n_events == 420
        assert crowded.verdict == "insufficient_blocks", "6 个事件日复制 70 倍也只有 1 个完整块"
        assert crowded.boot_p_lo is None, "块不足时不出区间——不给『退回二项检验』留数字"

    def test_固定种子幂等_换种子生效(self) -> None:
        events = _events_spread(60, 3, success_rate=0.7)
        a = block_bootstrap_readout(events, p0=0.5, block_len=5)
        b = block_bootstrap_readout(events, p0=0.5, block_len=5)
        assert a.to_dict() == b.to_dict(), "同输入同种子必须逐字段相同"
        c = block_bootstrap_readout(events, p0=0.5, block_len=5, seed=7)
        assert (c.boot_p_lo, c.boot_p_hi) != (a.boot_p_lo, a.boot_p_hi), "种子不同分布应不同——否则 seed 没在用"
        assert c.seed == 7 and a.seed != 7, "种子必须入账"

    def test_全负事件_块足时才refuted(self) -> None:
        assert (
            block_bootstrap_readout(_events_spread(60, 3, success_rate=0.0), p0=0.5, block_len=5).verdict
            == "refuted"
        )
        assert (
            block_bootstrap_readout(_events_spread(8, 30, success_rate=0.0), p0=0.5, block_len=5).verdict
            == "insufficient_blocks"
        ), "同日负样本同样不独立——块不足时连 refuted 也不出"

    def test_簇计数_同实体近邻归簇(self) -> None:
        # e0 在第 0/2/4 个事件日触发（间隔 ≤ block）→ 1 簇；在第 20 个事件日再触发 → 第 2 簇
        dates = [f"2026-01-{d:02d}" for d in range(1, 25)]
        events = [("e0", dates[0], True), ("e0", dates[2], True), ("e0", dates[4], True), ("e0", dates[20], True)]
        rd = block_bootstrap_readout(events, p0=0.5, block_len=5)
        assert rd.n_clusters == 2 and rd.n_events == 4


class TestCombinedVerdict:
    @pytest.mark.parametrize(
        ("independent", "dependence", "expected"),
        [
            ("supported", "supported", "supported"),
            ("refuted", "refuted", "refuted"),
            ("supported", "not_distinguishable", "not_distinguishable"),
            ("refuted", "not_distinguishable", "not_distinguishable"),
            ("not_distinguishable", "supported", "not_distinguishable"),
            ("supported", "insufficient_blocks", "insufficient_n"),
            ("refuted", "insufficient_blocks", "insufficient_n"),
            ("insufficient_n", "supported", "insufficient_n"),
        ],
    )
    def test_保守合成矩阵(self, independent: str, dependence: str, expected: str) -> None:
        final, _note = combined_verdict(independent, dependence)
        assert final == expected

    def test_不一致时note说明两道读数(self) -> None:
        final, note = combined_verdict("supported", "not_distinguishable")
        assert final == "not_distinguishable"
        assert note and "supported" in note and "not_distinguishable" in note


@pytest.fixture(scope="module")
def synthetic_small(tmp_path_factory: pytest.TempPathFactory) -> dict:
    spec = importlib.util.spec_from_file_location("mb_selftest_dependence", SELFTEST)
    st = importlib.util.module_from_spec(spec)
    sys.modules["mb_selftest_dependence"] = st
    spec.loader.exec_module(st)
    root = tmp_path_factory.mktemp("dependence")
    src, lab = root / "src.duckdb", root / "labels.duckdb"
    st.build_sample_db(src, n_days=240, n_sectors=12)
    build_labels(src, lab)
    build_outcomes(src, lab)
    return {"st": st, "labels": lab}


class TestPurge:
    def test_窗末跨界事件被剔且如实计数(self, synthetic_small: dict) -> None:
        """把窗口终点压到某个事件日：该日事件的 T+5 outcome 落在窗外，必须被 purge。"""
        import duckdb as _duckdb

        st = synthetic_small["st"]
        full = st.run(synthetic_small["labels"], st.POSITIVE_RULE)
        assert full.purge_cut_date is not None
        con = _duckdb.connect(str(synthetic_small["labels"]), read_only=True)
        try:
            # 找一个「事件日 = 窗口终点」的切法：终点后不足 5 个交易日 → 该日事件全跨窗
            some_event_date = full.events_sample[-1]["trade_date"]
        finally:
            con.close()
        from intelligence.services.methodology_backtest.runner import run_rule
        from intelligence.services.methodology_backtest.rules import parse_rule

        rule = parse_rule(st.POSITIVE_RULE)
        con = _duckdb.connect(str(synthetic_small["labels"]), read_only=True)
        try:
            clipped = run_rule(con, rule, end=some_event_date)
        finally:
            con.close()
        assert clipped.n_purged > 0, "窗末事件的 outcome 伸出窗外，必须被剔"
        assert clipped.purge_cut_date is not None and clipped.purge_cut_date < some_event_date
        kept_dates = {row["trade_date"] for row in clipped.events_sample}
        assert all(d <= clipped.purge_cut_date for d in kept_dates), "留下的事件全部在 cut 之内"

    def test_收据带依赖段与purge计数(self, synthetic_small: dict) -> None:
        from intelligence.services.methodology_backtest.receipts import build_receipt

        st = synthetic_small["st"]
        res = st.run(synthetic_small["labels"], st.POSITIVE_RULE)
        receipt = build_receipt(
            res, rule_path=None, rule_sha256=None,
            environment={"tree": "t", "branch": "b", "revision": "r", "dirty": False,
                         "interpreter": "py", "python_version": "3", "duckdb_version": "d"},
        )
        dep = receipt["dependence"]
        assert dep is not None and dep["method"] == "circular_date_block_bootstrap_v1"
        assert dep["seed"] == 20260911 and dep["n_boot"] == 500 and dep["block_len"] == rule_horizon(st)
        assert receipt["events"]["n_purged_cross_window"] == res.n_purged
        assert receipt["events"]["purge_cut_date"] == res.purge_cut_date
        assert {"n_events", "n_dates", "n_clusters", "n_blocks", "boot_p_lo", "boot_p_hi"} <= set(dep)


def rule_horizon(st) -> int:
    return int(st.POSITIVE_RULE["outcome"]["success"]["horizon"])
