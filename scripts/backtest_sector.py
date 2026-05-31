"""板块级别回测引擎。

在转折信号日（放量>10% / MA5峰谷次日）买入高边际量板块，
持有N日后卖出，计算回测指标。

用法:
    python3 scripts/backtest_sector.py                    # 默认参数回测
    python3 scripts/backtest_sector.py --top 5 --hold 3  # 买5个板块，持有3天
    python3 scripts/backtest_sector.py --min-marginal 15 # 边际量阈值15%
    python3 scripts/backtest_sector.py --from 2025-11-01 --to 2026-01-15

架构参考 vibe-trading: DataProvider → SignalDetector → BacktestEngine
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

import duckdb
import numpy as np

DB_PATH = Path(__file__).parent.parent / "db" / "market.duckdb"

# ---------------------------------------------------------------------------
# 默认参数
# ---------------------------------------------------------------------------
DEFAULT_TOP_N = 5            # 每次信号买入板块数
DEFAULT_HOLD_DAYS = 3        # 持有交易日数
DEFAULT_MIN_MARGINAL = 10.0  # 边际量最低阈值（%）
DEFAULT_MIN_PCT_CHG = 0.0    # 当日涨幅最低阈值（%）

# 信号检测阈值（与 detect_turning_points.py 一致）
VOLUME_SURGE_PCT = 10.0      # 较昨日成交额增长 > 10%
MA5_MIN_SWING = 500          # MA5 最小波动幅度


# ===================================================================
# SectorDataProvider — 从 DuckDB 加载数据
# ===================================================================

class SectorDataProvider:
    """板块数据提供者，封装 DuckDB 查询。

    对应 vibe-trading 的 DataLoader Protocol：
    - 输入：日期范围
    - 输出：板块日收益率 + 市场指标 + 涨家数
    """

    def __init__(self, db_path: str | Path = DB_PATH):
        self._conn = duckdb.connect(str(db_path), read_only=True)

    # ----- 板块数据 -----

    def get_sector_price_matrix(self, start: str, end: str) -> dict[str, dict[str, float]]:
        """返回 {date: {ts_code: pct_chg}} 矩阵。

        只包含 pct_chg 非空的记录。
        """
        rows = self._conn.execute("""
            SELECT date, ts_code, pct_chg
            FROM sector_marginal
            WHERE date >= ? AND date <= ?
              AND pct_chg IS NOT NULL
            ORDER BY date, ts_code
        """, [start, end]).fetchall()

        matrix: dict[str, dict[str, float]] = defaultdict(dict)
        for date, ts_code, pct_chg in rows:
            matrix[str(date)][ts_code] = float(pct_chg)
        return dict(matrix)

    def get_sector_marginal(self, date: str) -> dict[str, dict]:
        """返回某日所有板块的边际量和涨幅。"""
        rows = self._conn.execute("""
            SELECT ts_code, sector, diff_ratio, pct_chg, amount
            FROM sector_marginal
            WHERE date = ?
        """, [date]).fetchall()

        return {
            ts_code: {"sector": sector,
                      "diff_ratio": float(dr) if dr is not None else None,
                      "pct_chg": float(pc) if pc is not None else None,
                      "amount": float(am) if am is not None else None}
            for ts_code, sector, dr, pc, am in rows
        }

    # ----- 市场数据 -----

    def get_market_data(self, start: str, end: str) -> list[dict]:
        """返回每日市场指标列表。"""
        rows = self._conn.execute("""
            SELECT date, volume, volume_change, limit_up, limit_down,
                   week_ma, deviation
            FROM daily_market
            WHERE date >= ? AND date <= ?
            ORDER BY date
        """, [start, end]).fetchall()

        return [
            {"date": str(r[0]), "volume": r[1], "volume_change": r[2],
             "limit_up": r[3], "limit_down": r[4],
             "week_ma": r[5], "deviation": r[6]}
            for r in rows
        ]

    def get_advancers(self, start: str, end: str) -> list[dict]:
        """返回涨家数+MA5序列。"""
        rows = self._conn.execute("""
            SELECT date, count, ma5
            FROM advancers
            WHERE date >= ? AND date <= ?
            ORDER BY date
        """, [start, end]).fetchall()

        return [
            {"date": str(r[0]), "count": r[1], "ma5": float(r[2]) if r[2] else None}
            for r in rows
        ]

    def get_trading_dates(self, start: str, end: str) -> list[str]:
        """返回 sector_marginal 表中所有交易日（去重排序）。"""
        rows = self._conn.execute("""
            SELECT DISTINCT date FROM sector_marginal
            WHERE date >= ? AND date <= ?
            ORDER BY date
        """, [start, end]).fetchall()
        return [str(r[0]) for r in rows]

    def close(self):
        self._conn.close()


# ===================================================================
# SignalDetector — 转折信号检测
# ===================================================================

@dataclass
class Signal:
    date: str
    type: str          # "volume_surge" | "peak_next" | "valley_next"
    detail: str        # 人类可读描述
    ma5: float | None  # 当日 MA5 值

    def __repr__(self):
        return f"Signal({self.date}, {self.type}, {self.detail})"


class SignalDetector:
    """转折信号检测器。

    三种信号：
    1. 大盘放量 — 成交额较前日增长 > 10%
    2. MA5 峰次日 — MA5 大波段顶点的下一个交易日
    3. MA5 谷次日 — MA5 大波段底点的下一个交易日
    """

    def __init__(self,
                 volume_surge_pct: float = VOLUME_SURGE_PCT,
                 ma5_min_swing: float = MA5_MIN_SWING):
        self.volume_surge_pct = volume_surge_pct
        self.ma5_min_swing = ma5_min_swing

    def detect(self,
               market_data: list[dict],
               advancers: list[dict]) -> list[Signal]:
        """检测所有信号，返回信号列表。"""

        adv_dict = {a["date"]: a for a in advancers}
        mkt_dict = {m["date"]: m for m in market_data}

        # 取所有有 advancers 数据的日期作为全集
        dates = sorted(adv_dict.keys())
        if not dates:
            return []

        signals: list[Signal] = []

        # --- 信号1: 大盘放量 ---
        prev_vol = None
        for d in dates:
            m = mkt_dict.get(d)
            if m is None or m["volume"] is None:
                prev_vol = m["volume"] if m else prev_vol
                continue
            vol = m["volume"]
            if prev_vol and prev_vol > 0:
                chg = (vol - prev_vol) / prev_vol * 100
                if chg > self.volume_surge_pct:
                    signals.append(Signal(
                        date=d,
                        type="volume_surge",
                        detail=f"成交额 {prev_vol:.0f}→{vol:.0f} (+{chg:.1f}%)",
                        ma5=adv_dict[d]["ma5"] if d in adv_dict else None,
                    ))
            prev_vol = vol

        # --- 信号2 & 3: MA5 峰/谷次日 ---
        pivots = self._find_pivots(adv_dict, dates)
        for d in dates:
            idx = dates.index(d)
            if idx == 0:
                continue
            prev_d = dates[idx - 1]
            if prev_d in pivots:
                pt = pivots[prev_d]
                signals.append(Signal(
                    date=d,
                    type=f"{'peak' if pt == 'peak' else 'valley'}_next",
                    detail=f"{'顶' if pt == 'peak' else '谷'}点日 {prev_d} MA5={adv_dict[prev_d]['ma5']:.0f}",
                    ma5=adv_dict[d]["ma5"] if d in adv_dict else None,
                ))

        # 去重 + 按日期排序（同一天可能有多个信号，合并）
        return self._dedup_signals(signals)

    def _find_pivots(self, adv_dict: dict, dates: list[str]) -> dict[str, str]:
        """Zigzag 算法找 MA5 大波段峰谷。

        返回 {date: 'peak'|'valley'}
        """
        # 构建 MA5 序列
        ma5_seq = []
        for d in dates:
            a = adv_dict.get(d)
            if a and a["ma5"] is not None:
                ma5_seq.append((d, a["ma5"]))

        if len(ma5_seq) < 3:
            return {}

        pivots = [ma5_seq[0]]
        direction = None  # 1=up, -1=down

        for i in range(1, len(ma5_seq)):
            cur_date, cur_ma5 = ma5_seq[i]
            _, last_ma5 = pivots[-1]

            if direction is None:
                if cur_ma5 > last_ma5:
                    direction = 1
                elif cur_ma5 < last_ma5:
                    direction = -1
                if direction == 1 and cur_ma5 > last_ma5:
                    pivots[-1] = (cur_date, cur_ma5)
                elif direction == -1 and cur_ma5 < last_ma5:
                    pivots[-1] = (cur_date, cur_ma5)
                continue

            if direction == 1:
                if cur_ma5 > last_ma5:
                    pivots[-1] = (cur_date, cur_ma5)
                elif last_ma5 - cur_ma5 >= self.ma5_min_swing:
                    pivots.append((cur_date, cur_ma5))
                    direction = -1
            else:
                if cur_ma5 < last_ma5:
                    pivots[-1] = (cur_date, cur_ma5)
                elif cur_ma5 - last_ma5 >= self.ma5_min_swing:
                    pivots.append((cur_date, cur_ma5))
                    direction = 1

        result = {}
        for i, (pdate, pma5) in enumerate(pivots):
            if i == 0:
                continue
            prev_pma5 = pivots[i - 1][1]
            result[pdate] = "peak" if pma5 > prev_pma5 else "valley"
        return result

    def _dedup_signals(self, signals: list[Signal]) -> list[Signal]:
        """合并同一天的多个信号。"""
        by_date: dict[str, list[Signal]] = defaultdict(list)
        for s in signals:
            by_date[s.date].append(s)

        merged = []
        for date in sorted(by_date):
            items = by_date[date]
            types = [s.type for s in items]
            details = "; ".join(s.detail for s in items)
            merged.append(Signal(
                date=date,
                type="+".join(types),
                detail=details,
                ma5=items[0].ma5,
            ))
        return merged


# ===================================================================
# TradeRecord + BacktestResult
# ===================================================================

@dataclass
class TradeRecord:
    entry_date: str
    exit_date: str
    sectors: list[str]            # 买入的板块 ts_code
    sector_returns: dict[str, float]  # {ts_code: return_pct}
    basket_return: float          # 等权组合收益（%）
    signal_type: str
    holding_days: int


@dataclass
class BacktestResult:
    trades: list[TradeRecord]
    equity_curve: list[dict]       # [{date, equity, drawdown}]
    initial_capital: float
    final_capital: float
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    avg_return_pct: float
    profit_factor: float
    n_trades: int
    n_signal_days: int
    n_trading_days: int
    params: dict


# ===================================================================
# SectorBacktestEngine — 事件驱动回测引擎
# ===================================================================

class SectorBacktestEngine:
    """板块级别回测引擎。

    逐日迭代，在信号日选板块建仓，持有期满平仓。

    参考 vibe-trading base.py 的事件循环结构：
    for each bar → on_bar() → check_signals() → rebalance() → calc_pnl()
    """

    def __init__(self,
                 top_n: int = DEFAULT_TOP_N,
                 hold_days: int = DEFAULT_HOLD_DAYS,
                 min_marginal: float = DEFAULT_MIN_MARGINAL,
                 min_pct_chg: float = DEFAULT_MIN_PCT_CHG,
                 initial_capital: float = 1_000_000.0,
                 allow_overlap: bool = False):
        self.top_n = top_n
        self.hold_days = hold_days
        self.min_marginal = min_marginal
        self.min_pct_chg = min_pct_chg
        self.initial_capital = initial_capital
        self.allow_overlap = allow_overlap  # 是否允许重叠持仓

        self.provider = SectorDataProvider()

    def run(self, start: str, end: str) -> BacktestResult:
        """执行回测。"""

        # --- 加载数据 ---
        price_matrix = self.provider.get_sector_price_matrix(start, end)
        trading_dates = sorted(price_matrix.keys())
        if not trading_dates:
            raise ValueError(f"日期范围 {start}~{end} 无可用板块数据")

        market_data = self.provider.get_market_data(start, end)
        advancers = self.provider.get_advancers(start, end)

        # --- 检测信号 ---
        detector = SignalDetector()
        all_signals = detector.detect(market_data, advancers)
        signal_dates = {s.date for s in all_signals}
        signal_map = {s.date: s for s in all_signals}

        # --- 构建价格序列 ---
        # price[ts_code][date] = 归一化价格（基期=100）
        sector_prices = self._build_price_series(price_matrix, trading_dates)

        # --- 回测主循环 ---
        capital = self.initial_capital
        peak_capital = capital
        max_dd = 0.0
        equity_curve: list[dict] = []
        trades: list[TradeRecord] = []
        daily_returns: list[float] = []

        # 活跃仓位：[(entry_date, exit_date, sectors, entry_capital)]
        active_positions: list[tuple[str, str, list[str], float, str]] = []

        prev_capital = capital

        for i, date in enumerate(trading_dates):
            # --- 检查持仓到期 ---
            closed_today = []
            for pos in active_positions:
                entry_d, exit_d, sectors, entry_cap, sig_type = pos
                if date >= exit_d:
                    # 计算该仓位的收益
                    sector_rets = {}
                    valid = 0
                    for sec in sectors:
                        r = self._calc_return(sector_prices, sec, entry_d, exit_d)
                        if r is not None:
                            sector_rets[sec] = r
                            valid += 1

                    if valid > 0:
                        basket_ret = sum(sector_rets.values()) / len(sectors)
                        # 没有 sector_rets 数据的板块按0算
                        pnl = entry_cap * (sum(sector_rets.values()) / len(sectors)) / 100
                    else:
                        basket_ret = 0.0
                        pnl = 0.0

                    capital += pnl
                    closed_today.append(pos)

                    trades.append(TradeRecord(
                        entry_date=entry_d,
                        exit_date=exit_d,
                        sectors=sectors,
                        sector_returns=sector_rets,
                        basket_return=basket_ret,
                        signal_type=sig_type,
                        holding_days=trading_dates.index(exit_d) - trading_dates.index(entry_d),
                    ))

            for pos in closed_today:
                active_positions.remove(pos)

            # --- 检查信号 ---
            if date in signal_dates:
                can_enter = self.allow_overlap or len(active_positions) == 0
                has_exit_date = i + self.hold_days <= len(trading_dates) - 1
                if can_enter and capital > 0 and has_exit_date:
                    sectors = self._select_sectors(date, trading_dates)
                    if sectors:
                        # 计算出场日
                        exit_idx = i + self.hold_days
                        exit_date = trading_dates[exit_idx]

                        # 等权分配资金
                        position_capital = capital / max(1, len(active_positions) + 1)
                        # 简化：新仓位占用全部可用资金的一部分
                        # 如果没有重叠，新仓位 = 全部资金
                        alloc = capital if not self.allow_overlap else capital * 0.5

                        active_positions.append(
                            (date, exit_date, sectors, alloc, signal_map[date].type)
                        )

            # --- 记录当日净值 ---
            # 未实现盈亏 = 活跃仓位的当日价值变化
            unrealized = 0.0
            for entry_d, exit_d, sectors, entry_cap, _ in active_positions:
                for sec in sectors:
                    r = self._calc_return(sector_prices, sec, entry_d, date)
                    if r is not None:
                        unrealized += entry_cap / len(sectors) * r / 100

            total_equity = capital + unrealized

            if total_equity > peak_capital:
                peak_capital = total_equity
            dd = (peak_capital - total_equity) / peak_capital * 100 if peak_capital > 0 else 0
            if dd > max_dd:
                max_dd = dd

            equity_curve.append({
                "date": date,
                "equity": round(total_equity, 2),
                "drawdown": round(dd, 2),
            })

            # 日收益率
            if prev_capital > 0:
                daily_returns.append((total_equity - prev_capital) / prev_capital)
            prev_capital = total_equity

        # 强制平仓（回测结束）
        for entry_d, _, sectors, entry_cap, sig_type in active_positions:
            exit_d = trading_dates[-1]
            sector_rets = {}
            for sec in sectors:
                r = self._calc_return(sector_prices, sec, entry_d, exit_d)
                if r is not None:
                    sector_rets[sec] = r
            basket_ret = sum(sector_rets.values()) / max(1, len(sector_rets))
            capital += entry_cap * basket_ret / 100
            trades.append(TradeRecord(
                entry_date=entry_d, exit_date=exit_d,
                sectors=sectors, sector_returns=sector_rets,
                basket_return=basket_ret, signal_type=sig_type,
                holding_days=trading_dates.index(exit_d) - trading_dates.index(entry_d),
            ))

        final_capital = capital

        # --- 计算指标 ---
        total_ret = (final_capital - self.initial_capital) / self.initial_capital * 100
        n_years = len(trading_dates) / 244
        annual_ret = ((final_capital / self.initial_capital) ** (1 / max(n_years, 0.01)) - 1) * 100 if n_years > 0 else 0
        sharpe = self._calc_sharpe(daily_returns, n_years)
        win_trades = [t for t in trades if t.basket_return > 0]
        win_rate = len(win_trades) / max(1, len(trades)) * 100
        avg_ret = np.mean([t.basket_return for t in trades]) if trades else 0

        gross_profit = sum(t.basket_return for t in trades if t.basket_return > 0)
        gross_loss = abs(sum(t.basket_return for t in trades if t.basket_return < 0))
        profit_factor = gross_profit / max(gross_loss, 0.01)

        self.provider.close()

        return BacktestResult(
            trades=trades,
            equity_curve=equity_curve,
            initial_capital=self.initial_capital,
            final_capital=round(final_capital, 2),
            total_return_pct=round(total_ret, 2),
            annualized_return_pct=round(annual_ret, 2),
            sharpe_ratio=round(sharpe, 2),
            max_drawdown_pct=round(max_dd, 2),
            win_rate_pct=round(win_rate, 1),
            avg_return_pct=round(avg_ret, 2),
            profit_factor=round(profit_factor, 2),
            n_trades=len(trades),
            n_signal_days=len(signal_dates),
            n_trading_days=len(trading_dates),
            params={
                "top_n": self.top_n,
                "hold_days": self.hold_days,
                "min_marginal": self.min_marginal,
                "min_pct_chg": self.min_pct_chg,
                "allow_overlap": self.allow_overlap,
            },
        )

    # ----- 内部方法 -----

    def _build_price_series(self, matrix: dict, dates: list[str]) -> dict[str, dict[str, float]]:
        """从 pct_chg 矩阵构建每个板块的归一化价格序列。"""
        # 找出所有板块
        all_sectors: set[str] = set()
        for d in dates:
            all_sectors.update(matrix.get(d, {}).keys())

        prices: dict[str, dict[str, float]] = {}
        for sec in all_sectors:
            prices[sec] = {}
            base = 100.0
            for d in dates:
                pct = matrix.get(d, {}).get(sec)
                if pct is not None:
                    base *= (1 + pct / 100)
                prices[sec][d] = base
        return prices

    def _calc_return(self, prices: dict, sector: str, entry: str, exit: str) -> float | None:
        """计算板块从 entry 到 exit 的收益率（%）。"""
        sec_prices = prices.get(sector)
        if sec_prices is None:
            return None
        p_entry = sec_prices.get(entry)
        p_exit = sec_prices.get(exit)
        if p_entry is None or p_exit is None or p_entry == 0:
            return None
        return (p_exit / p_entry - 1) * 100

    def _select_sectors(self, date: str, all_dates: list[str]) -> list[str]:
        """在信号日选择满足条件的板块。"""
        data = self.provider.get_sector_marginal(date)
        if not data:
            return []

        # 检查 pct_chg 是否可用（该日至少有一个板块有 pct_chg）
        has_pct = any(v["pct_chg"] is not None for v in data.values())

        candidates = []
        for ts_code, vals in data.items():
            dr = vals["diff_ratio"]
            pc = vals["pct_chg"]

            if dr is None:
                continue
            if dr < self.min_marginal:
                continue
            if has_pct:
                if pc is None or pc < self.min_pct_chg:
                    continue

            candidates.append((ts_code, dr))

        # 按边际量降序，取 top N
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in candidates[:self.top_n]]

    def _calc_sharpe(self, daily_returns: list[float], n_years: float) -> float:
        """计算年化夏普比率。"""
        if len(daily_returns) < 2:
            return 0.0
        mean_ret = np.mean(daily_returns)
        std_ret = np.std(daily_returns, ddof=1)
        if std_ret == 0:
            return 0.0
        return (mean_ret / std_ret) * np.sqrt(244)


# ===================================================================
# 输出格式化
# ===================================================================

def print_result(r: BacktestResult):
    """打印回测结果。"""

    # 参数
    p = r.params
    print(f"\n{'='*70}")
    print(f"  板块回测结果")
    print(f"{'='*70}")
    print(f"  参数: top_n={p['top_n']}  hold={p['hold_days']}天  "
          f"边际量≥{p['min_marginal']}%  涨幅≥{p['min_pct_chg']}%  "
          f"重叠={'开' if p['allow_overlap'] else '关'}")
    print(f"  回测区间: {r.equity_curve[0]['date']} → {r.equity_curve[-1]['date']}  "
          f"({r.n_trading_days}个交易日)")

    # 收益指标
    print(f"\n  ┌─ 收益 ─────────────────────────────")
    print(f"  │ 初始资金:    {r.initial_capital:>12,.0f}")
    print(f"  │ 最终资金:    {r.final_capital:>12,.0f}")
    print(f"  │ 总收益率:    {r.total_return_pct:>+11.2f}%")
    print(f"  │ 年化收益:    {r.annualized_return_pct:>+11.2f}%")

    # 风险指标
    print(f"  ├─ 风险 ─────────────────────────────")
    print(f"  │ 最大回撤:    {r.max_drawdown_pct:>11.2f}%")
    print(f"  │ 夏普比率:    {r.sharpe_ratio:>11.2f}")

    # 交易统计
    print(f"  ├─ 交易 ─────────────────────────────")
    print(f"  │ 信号日数:    {r.n_signal_days:>11}")
    print(f"  │ 实际交易:    {r.n_trades:>11} 笔")
    print(f"  │ 胜率:        {r.win_rate_pct:>10.1f}%")
    print(f"  │ 平均收益:    {r.avg_return_pct:>+10.2f}%")
    print(f"  │ 盈亏比:      {r.profit_factor:>11.2f}")

    # 逐笔交易
    if r.trades:
        print(f"\n  ┌─ 逐笔交易 ─────────────────────────")
        print(f"  │ {'入场':<12} {'出场':<12} {'持仓':>4} {'板块数':>4} {'收益':>8} {'胜':>3} {'信号'}")
        print(f"  │ {'-'*58}")
        total_ret = 0
        for t in r.trades:
            win = "✓" if t.basket_return > 0 else "✗"
            print(f"  │ {t.entry_date:<12} {t.exit_date:<12} {t.holding_days:>4}天 "
                  f"{len(t.sectors):>4} {t.basket_return:>+7.2f}% {win:>3} "
                  f"{t.signal_type[:20]}")
            total_ret += t.basket_return
        print(f"  │ {'-'*58}")
        print(f"  │ {'累计':>42} {total_ret:>+7.2f}%")

    # 净值曲线摘要
    print(f"\n  ┌─ 净值摘要 ─────────────────────────")
    eq = r.equity_curve
    print(f"  │ 起始: {eq[0]['date']}  {eq[0]['equity']:>12,.0f}")
    print(f"  │ 结束: {eq[-1]['date']}  {eq[-1]['equity']:>12,.0f}")
    peak_eq = max(e["equity"] for e in eq)
    peak_date = [e for e in eq if e["equity"] == peak_eq][0]
    print(f"  │ 峰值: {peak_date['date']}  {peak_eq:>12,.0f}")

    print(f"{'='*70}\n")


# ===================================================================
# 参数扫描
# ===================================================================

def scan_params(start: str, end: str):
    """扫描不同参数组合的回测结果。"""
    print(f"\n{'='*70}")
    print(f"  参数扫描  {start} → {end}")
    print(f"{'='*70}")
    print(f"  {'top_n':<6} {'hold':<6} {'min_marg':<9} {'总收益':>8} {'年化':>8} "
          f"{'夏普':>6} {'回撤':>7} {'胜率':>6} {'笔数':>4}")
    print(f"  {'-'*65}")

    results = []
    for top_n in [3, 5, 8]:
        for hold in [1, 3, 5, 10]:
            for min_marg in [5, 10, 15]:
                engine = SectorBacktestEngine(
                    top_n=top_n, hold_days=hold, min_marginal=min_marg,
                )
                try:
                    r = engine.run(start, end)
                    results.append((r, top_n, hold, min_marg))
                    print(f"  {top_n:<6} {hold:<6} {min_marg:<9} "
                          f"{r.total_return_pct:>+7.2f}% {r.annualized_return_pct:>+7.2f}% "
                          f"{r.sharpe_ratio:>6.2f} {r.max_drawdown_pct:>6.2f}% "
                          f"{r.win_rate_pct:>5.1f}% {r.n_trades:>4}")
                except Exception as e:
                    print(f"  {top_n:<6} {hold:<6} {min_marg:<9} ERROR: {e}")

    # 最优结果
    if results:
        results.sort(key=lambda x: x[0].sharpe_ratio, reverse=True)
        best = results[0]
        print(f"\n  ★ 最优（按夏普）: top_n={best[1]} hold={best[2]} "
              f"min_marginal={best[3]} → 夏普={best[0].sharpe_ratio} "
              f"总收益={best[0].total_return_pct:+.2f}%")


# ===================================================================
# CLI
# ===================================================================

def parse_date(s: str) -> str:
    """统一日期格式 YYYY-MM-DD。"""
    return s


def main():
    args = sys.argv[1:]

    # 默认参数
    start = None
    end = None
    top_n = DEFAULT_TOP_N
    hold_days = DEFAULT_HOLD_DAYS
    min_marginal = DEFAULT_MIN_MARGINAL
    min_pct_chg = DEFAULT_MIN_PCT_CHG
    allow_overlap = False
    scan = False

    i = 0
    while i < len(args):
        if args[i] == "--from" and i + 1 < len(args):
            start = args[i + 1]; i += 2
        elif args[i] == "--to" and i + 1 < len(args):
            end = args[i + 1]; i += 2
        elif args[i] == "--top" and i + 1 < len(args):
            top_n = int(args[i + 1]); i += 2
        elif args[i] == "--hold" and i + 1 < len(args):
            hold_days = int(args[i + 1]); i += 2
        elif args[i] == "--min-marginal" and i + 1 < len(args):
            min_marginal = float(args[i + 1]); i += 2
        elif args[i] == "--min-pct" and i + 1 < len(args):
            min_pct_chg = float(args[i + 1]); i += 2
        elif args[i] == "--overlap":
            allow_overlap = True; i += 1
        elif args[i] == "--scan":
            scan = True; i += 1
        else:
            i += 1

    # 自动确定日期范围
    if start is None or end is None:
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        auto = conn.execute("""
            SELECT MIN(date), MAX(date) FROM sector_marginal
            WHERE pct_chg IS NOT NULL
        """).fetchone()
        conn.close()
        if start is None:
            start = str(auto[0])
        if end is None:
            end = str(auto[1])

    print(f"回测区间: {start} → {end}")

    if scan:
        scan_params(start, end)
    else:
        engine = SectorBacktestEngine(
            top_n=top_n, hold_days=hold_days,
            min_marginal=min_marginal, min_pct_chg=min_pct_chg,
            allow_overlap=allow_overlap,
        )
        result = engine.run(start, end)
        print_result(result)


if __name__ == "__main__":
    main()
