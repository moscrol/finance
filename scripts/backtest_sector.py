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

import argparse
import sys
from datetime import date as date_cls
from pathlib import Path
from dataclasses import dataclass

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from market_feature_store.analysis import turning_points as _turning_points  # noqa: E402
from market_feature_store.analysis.sector_data import SectorDataProvider  # noqa: E402
from market_feature_store.db import DB_PATH as CANONICAL_DB_PATH  # noqa: E402

MA5_MIN_SWING = _turning_points.MA5_MIN_SWING
VOLUME_SURGE_PCT = _turning_points.VOLUME_SURGE_PCT
Signal = _turning_points.Signal
SignalDetector = _turning_points.SignalDetector

DB_PATH = CANONICAL_DB_PATH

# ---------------------------------------------------------------------------
# 默认参数
# ---------------------------------------------------------------------------
DEFAULT_TOP_N = 5            # 每次信号买入板块数
DEFAULT_HOLD_DAYS = 3        # 持有交易日数
DEFAULT_MIN_MARGINAL = 10.0  # 边际量最低阈值（%）
DEFAULT_MIN_PCT_CHG = 0.0    # 当日涨幅最低阈值（%）

# SignalDetector is imported from market_feature_store.analysis.turning_points.
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
                 allow_overlap: bool = False,
                 provider: SectorDataProvider | None = None):
        self.top_n = top_n
        self.hold_days = hold_days
        self.min_marginal = min_marginal
        self.min_pct_chg = min_pct_chg
        self.initial_capital = initial_capital
        self.allow_overlap = allow_overlap  # 是否允许重叠持仓

        self.provider = provider if provider is not None else SectorDataProvider()

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

            # --- 检查信号（信号日收盘后确认，次一交易日入场） ---
            if date in signal_dates:
                can_enter = self.allow_overlap or len(active_positions) == 0
                entry_idx = i + 1
                exit_idx = entry_idx + self.hold_days
                has_exit_date = exit_idx <= len(trading_dates) - 1
                if can_enter and capital > 0 and has_exit_date:
                    sectors = self._select_sectors(date, trading_dates)
                    if sectors:
                        entry_date = trading_dates[entry_idx]
                        exit_date = trading_dates[exit_idx]

                        # 等权分配资金
                        position_capital = capital / max(1, len(active_positions) + 1)
                        # 简化：新仓位占用全部可用资金的一部分
                        # 如果没有重叠，新仓位 = 全部资金
                        alloc = capital if not self.allow_overlap else capital * 0.5

                        active_positions.append(
                            (entry_date, exit_date, sectors, alloc, signal_map[date].type)
                        )

            # --- 记录当日净值 ---
            # 未实现盈亏 = 活跃仓位的当日价值变化
            unrealized = 0.0
            for entry_d, exit_d, sectors, entry_cap, _ in active_positions:
                if date < entry_d:
                    continue
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

def scan_params(start: str, end: str, db_path: str | Path = DB_PATH):
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
                    provider=SectorDataProvider(db_path),
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

def _date_arg(value: str) -> str:
    try:
        return date_cls.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期必须是 YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="板块边际量策略回测")
    parser.add_argument("--from", dest="start", type=_date_arg, help="起始交易日 YYYY-MM-DD")
    parser.add_argument("--to", dest="end", type=_date_arg, help="结束交易日 YYYY-MM-DD")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_N, help="每个信号日最多买入板块数")
    parser.add_argument("--hold", type=int, default=DEFAULT_HOLD_DAYS, help="持有交易日数")
    parser.add_argument(
        "--min-marginal",
        type=float,
        default=DEFAULT_MIN_MARGINAL,
        help="边际量最低阈值（%%）",
    )
    parser.add_argument(
        "--min-pct",
        type=float,
        default=DEFAULT_MIN_PCT_CHG,
        help="板块当日涨幅最低阈值（%%）",
    )
    parser.add_argument("--overlap", action="store_true", help="允许持仓重叠")
    parser.add_argument("--scan", action="store_true", help="扫描预设参数组合")
    parser.add_argument(
        "--db-path",
        default=str(DB_PATH),
        help="canonical DuckDB 路径，默认读取 MARKET_FEATURE_STORE_DB 或主库",
    )
    return parser


def _resolve_dates(
    provider: SectorDataProvider,
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> tuple[str, str]:
    auto_start, auto_end = provider.get_date_range()
    start = args.start or auto_start
    end = args.end or auto_end
    if start is None or end is None:
        parser.error("fact_sector_daily 没有可用交易日")
    if start > end:
        parser.error("--from 不能晚于 --to")
    return start, end


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.top <= 0 or args.hold <= 0:
        parser.error("--top 和 --hold 必须是正整数")

    provider = None
    try:
        provider = SectorDataProvider(args.db_path)
        start, end = _resolve_dates(provider, args, parser)
        print(f"回测区间: {start} → {end}")

        if args.scan:
            provider.close()
            provider = None
            scan_params(start, end, args.db_path)
            return 0

        engine = SectorBacktestEngine(
            top_n=args.top,
            hold_days=args.hold,
            min_marginal=args.min_marginal,
            min_pct_chg=args.min_pct,
            allow_overlap=args.overlap,
            provider=provider,
        )
        result = engine.run(start, end)
        provider = None
        print_result(result)
        return 0
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    finally:
        if provider is not None:
            provider.close()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
