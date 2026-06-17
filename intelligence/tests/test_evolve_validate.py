"""evolution/validate.py 的单元测试：前瞻收益计算（无前视）+ 胜率聚合。

覆盖 strategy-evolve 流水线里**确定性、无外部依赖**的验证核心：
- forward_returns：T+h = D0 之后第 h 个交易日收盘，ret%=(close_h/close_0-1)*100；
  只读 cal[i+h]（绝不回引 D0 之后字段以外的列），状态分 ok/pending/missing。
- aggregate：把逐票收益聚合成 n/win/mean/strong/fail（pending、missing 不计入分母）。

validate.py 不连真库——forward_returns 只通过 con.execute(sql,params).fetchall() 取数，
本测试用一个最小 FakeCon 喂固定行，故无需 DuckDB 即可跑（与 test_evolve_params 同放
intelligence/tests/，`from evolution import ...` 在仓库根 PYTHONPATH 下解析）。
"""
from __future__ import annotations

import unittest

from evolution import validate as vmod


class _FakeCon:
    """最小只读连接桩：calendar 走 trading_calendar 查询，其余走收盘查询。"""

    def __init__(self, calendar: list[str], closes: dict[tuple[str, str], float]) -> None:
        self._calendar = calendar
        self._closes = closes
        self._sql = ""

    def execute(self, sql: str, params=None):
        self._sql = sql
        return self

    def fetchall(self):
        if "distinct trade_date" in self._sql:
            return [(d,) for d in self._calendar]
        # 收盘查询：返回 (code, day, close)；多返回的行不影响 .get 精确查找。
        return [(code, day, close) for (code, day), close in self._closes.items()]


_CAL = ["D1", "D2", "D3", "D4", "D5"]
_HORIZONS = [1, 3]
_PICKS = {"D1": ["AAA", "DDD"], "D2": ["CCC"], "D3": ["BBB"]}
_CLOSES = {
    ("AAA", "D1"): 100.0, ("AAA", "D2"): 110.0, ("AAA", "D4"): 130.0,
    ("DDD", "D1"): 50.0,                       # 有基准、无未来收盘 -> missing
    ("BBB", "D3"): 200.0, ("BBB", "D4"): 180.0,
    # CCC 全缺 -> 基准 missing
}

_PARAMS = {"validation": {"win_gt": 0, "strong_ge": 5, "fail_le": -5}}


class ForwardReturnsTests(unittest.TestCase):
    def setUp(self) -> None:
        con = _FakeCon(_CAL, _CLOSES)
        self.ret, self.cal = vmod.forward_returns(con, _PICKS, _HORIZONS)

    def test_calendar_passthrough(self) -> None:
        self.assertEqual(self.cal, _CAL)

    def test_ok_return_math(self) -> None:
        # D1->D2 = +10%；D1->cal[3]=D4 = +30%
        self.assertEqual(self.ret[("D1", "AAA")][1],
                         {"status": "ok", "target": "D2", "ret_pct": 10.0})
        self.assertEqual(self.ret[("D1", "AAA")][3],
                         {"status": "ok", "target": "D4", "ret_pct": 30.0})

    def test_negative_return(self) -> None:
        self.assertEqual(self.ret[("D3", "BBB")][1],
                         {"status": "ok", "target": "D4", "ret_pct": -10.0})

    def test_pending_when_horizon_beyond_calendar(self) -> None:
        # BBB 在 D3(idx2)，h=3 -> idx5 越过 5 天日历 -> pending
        self.assertEqual(self.ret[("D3", "BBB")][3],
                         {"status": "pending", "target": None, "ret_pct": None})

    def test_missing_base_close(self) -> None:
        # CCC 无任何收盘 -> 基准缺，但 target 已定位
        self.assertEqual(self.ret[("D2", "CCC")][1],
                         {"status": "missing", "target": "D3", "ret_pct": None})
        self.assertEqual(self.ret[("D2", "CCC")][3],
                         {"status": "missing", "target": "D5", "ret_pct": None})

    def test_missing_future_close(self) -> None:
        # DDD 有基准、无未来收盘
        self.assertEqual(self.ret[("D1", "DDD")][1],
                         {"status": "missing", "target": "D2", "ret_pct": None})

    def test_date_not_in_calendar_is_missing(self) -> None:
        con = _FakeCon(_CAL, _CLOSES)
        ret, _ = vmod.forward_returns(con, {"DX": ["AAA"]}, _HORIZONS)
        self.assertEqual(ret[("DX", "AAA")][1],
                         {"status": "missing", "target": None, "ret_pct": None})

    def test_empty_picks_returns_empty(self) -> None:
        con = _FakeCon(_CAL, _CLOSES)
        ret, cal = vmod.forward_returns(con, {"D1": []}, _HORIZONS)
        self.assertEqual(ret, {})
        self.assertEqual(cal, _CAL)


class AggregateTests(unittest.TestCase):
    def setUp(self) -> None:
        con = _FakeCon(_CAL, _CLOSES)
        ret, _ = vmod.forward_returns(con, _PICKS, _HORIZONS)
        self.agg = vmod.aggregate(ret, _PICKS, _HORIZONS, _PARAMS)

    def test_h1_counts_and_rates(self) -> None:
        # ok: AAA +10, BBB -10 -> n=2；missing: DDD, CCC
        a = self.agg[1]
        self.assertEqual((a["n"], a["pending"], a["missing"]), (2, 0, 2))
        self.assertEqual(a["win"], 50.0)    # 1/2 > 0
        self.assertEqual(a["mean"], 0.0)    # (10-10)/2
        self.assertEqual(a["strong"], 50.0)  # 1/2 >= 5
        self.assertEqual(a["fail"], 50.0)    # 1/2 <= -5

    def test_h3_counts_and_rates(self) -> None:
        # ok: AAA +30 -> n=1；pending: BBB；missing: DDD, CCC
        a = self.agg[3]
        self.assertEqual((a["n"], a["pending"], a["missing"]), (1, 1, 2))
        self.assertEqual(a["win"], 100.0)
        self.assertEqual(a["mean"], 30.0)
        self.assertEqual(a["strong"], 100.0)
        self.assertEqual(a["fail"], 0.0)

    def test_empty_sample_yields_none_rates(self) -> None:
        # 全 missing -> n=0 -> 比率 None，不抛零除
        con = _FakeCon(_CAL, _CLOSES)
        picks = {"D2": ["CCC"]}  # CCC 基准全缺
        ret, _ = vmod.forward_returns(con, picks, _HORIZONS)
        agg = vmod.aggregate(ret, picks, _HORIZONS, _PARAMS)
        for h in _HORIZONS:
            self.assertEqual(agg[h]["n"], 0)
            self.assertIsNone(agg[h]["win"])
            self.assertIsNone(agg[h]["mean"])
            self.assertIsNone(agg[h]["strong"])
            self.assertIsNone(agg[h]["fail"])


if __name__ == "__main__":
    unittest.main()
