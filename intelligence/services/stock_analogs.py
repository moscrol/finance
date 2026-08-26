"""D11 个股走势类比块：从个股自身历史里找「和当前形态相似的窗口」及其后续走法。

背景（为什么要这个块）：
    行情对标历史已有两级——D8 题材级（fact_sector_daily 自身历史）、D10 市场级
    （十维情绪向量）。个股级缺席：「英维克现在这段走势，历史上类似的窗口后来怎么走」
    没有模块能答。本块做确定性版：**只列历史事实，不给概率**。

设计（沿 D8 的纪律，特征换成个股可得字段）：
    - **确定性意图路由**：applies 层只看类比词面（与 D8 同表）；目标个股在 build 层
      解析（代码/名称都要查库）——解析不到个股时返回空块，不污染题材问答。
    - **形态签名**：当前窗口（默认 20 交易日）的（强势天数[涨幅≥5%]、成交额首末比、
      均涨），在该股自身全部历史上滑窗（步长 5 日）算同口径签名，按加权距离取最近的
      K 段互不重叠窗口。与 D8 同构：签名匹配的是量价结构，不是 K 线逐日形状
      （q9 蒸馏结论：历史类比匹配场景结构，不做像素级 K 线相似）。
    - **后续走法只报事实**，且按用户验证纪律给多窗口：每段类比窗口之后 5/10/20 日的
      累计涨幅、**区间最高累计涨幅、达峰天数、峰后回撤**——不只看固定末值。
    - 缺数（库不可用/个股无行/历史太短/无相似窗口）显式声明，禁止外推。
    - 口径警示：pct_chg 为供应商日涨跌幅，除权除息日可能含跳变；复利累计仅供
      结构对照，不是精确收益回测。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from intelligence.paths import default_market_db_path
from intelligence.services import retrieval_cache
from intelligence.services import reading_baseline

DEFAULT_MARKET_DB_PATH = default_market_db_path()

DEFAULT_WINDOW = 20
STRIDE = 5
TOP_K = 3
FORWARD_HORIZONS = (5, 10, 20)
MIN_HISTORY_MULTIPLE = 3  # 与 D8/D10 一致
STRONG_DAY_PCT = 5.0      # 个股「强势日」阈值（涨幅 ≥5%）

# 与 D8 同一张类比词面表（个股/题材的区分在目标解析层，不在词面层）
_ANALOG_TERMS = (
    "类似",
    "类比",
    "相似",
    "对标",
    "历史上",
    "上一次",
    "上次",
    "先例",
    "过往",
    "以往",
    "历史相似",
    "历史类比",
    "复盘过去",
    "历史经验",
)


def parse_stock_analog_intent(query: str) -> bool:
    """applies 层路由：命中类比词面即可（个股解析需要查库，留给 build 层）。"""
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return False
    return any(term in text for term in _ANALOG_TERMS)


def _clean_stock_text(value: Any) -> str:
    """供应商名称/代码偶发 CHAR 填充（尾部 \\x00）；展示和子串匹配前先剥掉。"""
    return str(value or "").replace("\x00", "").strip()


@dataclass(frozen=True)
class StockSignature:
    strong_days: int              # 窗口内涨幅 ≥5% 的天数
    amount_ratio: float | None    # 成交额首末比（末/首）
    avg_pct: float | None         # 日均涨跌幅


@dataclass(frozen=True)
class StockAnalogArtifact:
    window: int
    stock_code: str | None
    stock_name: str | None
    current_signature: dict[str, Any] | None
    analogs: tuple[dict[str, Any], ...]
    evidence_id: str = "D11"
    degrade_reason: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.analogs)

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "window": self.window,
            "available": self.available,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "current_signature": self.current_signature,
            "analogs": list(self.analogs),
            "degrade_reason": self.degrade_reason,
        }


def _signature(rows: list[tuple]) -> StockSignature:
    """rows 为升序 (trade_date, pct_chg, amount)。"""
    pcts = [float(r[1]) for r in rows if r[1] is not None]
    amounts = [float(r[2]) for r in rows if r[2] is not None]
    strong = sum(1 for p in pcts if p >= STRONG_DAY_PCT)
    ratio = (amounts[-1] / amounts[0]) if len(amounts) >= 2 and amounts[0] else None
    avg_pct = sum(pcts) / len(pcts) if pcts else None
    return StockSignature(strong, ratio, avg_pct)


def _distance(a: StockSignature, b: StockSignature, window: int) -> float | None:
    if a.amount_ratio is None or b.amount_ratio is None or a.avg_pct is None or b.avg_pct is None:
        return None
    return (
        2.0 * abs(a.strong_days - b.strong_days) / max(window, 1)
        + abs(a.amount_ratio - b.amount_ratio)
        + 0.5 * abs(a.avg_pct - b.avg_pct)
    )


def _forward_facts(rows: list[tuple], horizon: int) -> dict[str, Any] | None:
    """类比窗口之后 horizon 日的实际走法（只报事实）。行数不足返回 None。

    按验证纪律给多观测量：累计涨幅之外必须有区间最高、达峰天数、峰后回撤——
    「只看固定第 N 日终值」是被本仓市场假设验证规则明确禁止的读法。
    """
    if len(rows) < horizon:
        return None
    seg = rows[:horizon]
    level = 1.0
    levels: list[float] = []
    valid = 0
    for r in seg:
        if r[1] is not None:
            level *= 1.0 + float(r[1]) / 100.0
            valid += 1
        levels.append(level)
    if valid < max(1, horizon // 2):
        return None
    cum_pct = (levels[-1] - 1.0) * 100.0
    peak_idx = max(range(len(levels)), key=lambda i: levels[i])
    peak = levels[peak_idx]
    max_cum_pct = (peak - 1.0) * 100.0
    drawdown_from_peak = ((levels[-1] / peak) - 1.0) * 100.0 if peak > 0 else None
    return {
        "cum_pct": cum_pct,
        "max_cum_pct": max_cum_pct,
        "days_to_peak": peak_idx + 1,
        "drawdown_from_peak_pct": drawdown_from_peak,
    }


def find_stock_analog_windows(
    rows: list[tuple],
    window: int = DEFAULT_WINDOW,
    stride: int = STRIDE,
    top_k: int = TOP_K,
) -> tuple[StockSignature | None, list[dict[str, Any]]]:
    """rows 为该股升序全历史 (trade_date, pct_chg, amount)。

    返回（当前签名，最相似的 K 段互不重叠历史窗口及其后续多窗口事实）。
    """
    n = len(rows)
    if n < window * MIN_HISTORY_MULTIPLE:
        return None, []
    current = _signature(rows[n - window:])
    candidates: list[tuple[float, int]] = []
    for start in range(0, n - 2 * window, stride):
        sig = _signature(rows[start:start + window])
        d = _distance(current, sig, window)
        if d is not None:
            candidates.append((d, start))
    candidates.sort()
    picked: list[dict[str, Any]] = []
    used: list[tuple[int, int]] = []
    for d, start in candidates:
        end = start + window
        if any(not (end <= s or start >= e) for s, e in used):
            continue
        seg = rows[start:end]
        forwards = {h: _forward_facts(rows[end:end + h], h) for h in FORWARD_HORIZONS}
        picked.append(
            {
                "start_date": str(seg[0][0]),
                "end_date": str(seg[-1][0]),
                "distance": round(d, 3),
                "signature": asdict(_signature(seg)),
                "forwards": forwards,
            }
        )
        used.append((start, end))
        if len(picked) >= top_k:
            break
    return current, picked


def _resolve_stock(con: Any, query: str) -> tuple[str, str] | None:
    """从 query 解析目标个股（6 位代码优先，其次名称子串命中最长者）。

    名称目录只取 **最新交易日** 一行宇宙，不扫全表。applies 层只要类比词面
    就会进 build——题材/情绪类比问（D8/D10）没有个股时也会走到这里；生产库
    ``fact_stock_daily`` 是百万行事实表，全历史 ``group by stock_ts_code, stock_name``
    会把每一次「历史上类似」都做成一次全表扫描。最新日有日期索引，量级是当日
    股票数（约数千），不是历史行数。代价：已更名/已退市且当日不在表里的旧名
    解析不到，降级为空块（与「只对标当前这只正在交易的股」一致）。
    """
    code_match = re.search(r"\b(\d{6})(?:\.(SH|SZ|BJ))?\b", str(query or ""), re.I)
    if code_match:
        raw, suffix = code_match.group(1), code_match.group(2)
        if suffix:
            rows = con.execute(
                "select stock_ts_code, stock_name from fact_stock_daily "
                "where stock_ts_code=? order by trade_date desc limit 1",
                [f"{raw}.{suffix.upper()}"],
            ).fetchall()
        else:
            rows = con.execute(
                "select stock_ts_code, stock_name from fact_stock_daily "
                "where stock_ts_code like ? order by trade_date desc limit 1",
                [f"{raw}.%"],
            ).fetchall()
        if rows:
            code = _clean_stock_text(rows[0][0])
            name = _clean_stock_text(rows[0][1]) or code
            return code, name
    rows = con.execute(
        """
        select stock_ts_code, any_value(stock_name)
        from fact_stock_daily
        where trade_date = (select max(trade_date) from fact_stock_daily)
          and stock_name is not null and stock_name <> ''
        group by stock_ts_code
        """
    ).fetchall()
    q = str(query or "")
    matches = []
    for code, name in rows:
        cleaned_name = _clean_stock_text(name)
        cleaned_code = _clean_stock_text(code)
        if cleaned_name and cleaned_name in q:
            matches.append((cleaned_code, cleaned_name))
    if matches:
        matches.sort(key=lambda item: len(item[1]), reverse=True)
        return matches[0]
    return None


def load_stock_analog_artifact(
    query: str,
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
) -> StockAnalogArtifact:
    """解析目标个股 → 取全历史 → 滑窗类比。全程只读；每级缺数显式降级。"""
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    if not db_path.exists():
        return StockAnalogArtifact(
            window, None, None, None, (), degrade_reason="D11 个股类比库不存在"
        )
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return StockAnalogArtifact(
            window, None, None, None, (), degrade_reason="D11 个股类比库不可读"
        )
    con = db_result.connection
    try:
        resolved = _resolve_stock(con, query)
        if resolved is None:
            return StockAnalogArtifact(
                window, None, None, None, (),
                degrade_reason="D11 未在问题中解析到库内个股（代码/名称均未命中）",
            )
        code, name = resolved
        rows = con.execute(
            """
            select trade_date, pct_chg, amount
            from fact_stock_daily
            where stock_ts_code = ?
            order by trade_date asc
            """,
            [code],
        ).fetchall()
        current, analogs = find_stock_analog_windows(rows, window=window)
        if current is None:
            return StockAnalogArtifact(
                window, code, name, None, (),
                degrade_reason=(
                    f"D11 {name} 历史行数不足（<{window * MIN_HISTORY_MULTIPLE} 交易日），无法类比"
                ),
            )
        if not analogs:
            return StockAnalogArtifact(
                window, code, name, asdict(current), (),
                degrade_reason=f"D11 {name} 未找到可比历史窗口（签名字段缺失）",
            )
        return StockAnalogArtifact(window, code, name, asdict(current), tuple(analogs))
    except Exception:
        return StockAnalogArtifact(
            window, None, None, None, (), degrade_reason="D11 个股类比查询失败"
        )
    finally:
        try:
            con.close()
        except Exception:
            pass


def _fmt(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _fwd_text(fwd: dict[str, Any] | None) -> str:
    if fwd is None:
        return "—"
    return (
        f"累计{_fmt(fwd['cum_pct'])}%/区间最高{_fmt(fwd['max_cum_pct'])}%"
        f"/{fwd['days_to_peak']}日达峰/峰后{_fmt(fwd['drawdown_from_peak_pct'])}%"
    )


def stock_analog_block_for_llm(
    query: str,
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
) -> str:
    """把个股类比渲染成带 [D11] 引用编号的确定性数据块（空串=未取到/不适用）。"""
    artifact = load_stock_analog_artifact(query, market_db_path, window=window)
    # 「问题里根本没有个股」是常态（题材类比走 D8），不渲染缺口行，直接空块。
    if artifact.stock_code is None:
        return ""
    lines = ["## 个股走势类比块 [D11]"]
    lines.extend(reading_baseline.block_rule_lines("D11"))
    lines.append(
        f"- 口径：{artifact.stock_name}（{artifact.stock_code}）自身历史上与"
        f"「最近 {window} 个交易日形态」（强势天数[≥{STRONG_DAY_PCT:.0f}%]/成交额首末比/均涨）"
        "加权距离最近的窗口，及其后续 5/10/20 日实际走法；"
        "本地 DuckDB fact_stock_daily 逐日行计算，非 LLM 生成。"
        "pct_chg 为供应商日涨跌幅，除权除息日可能含跳变，复利累计仅供结构对照。"
    )
    if not artifact.available:
        lines.append(f"- 数据缺口：{artifact.degrade_reason or 'D11 无可比窗口'}，禁止外推。")
        return "\n".join(lines)
    sig = artifact.current_signature or {}
    lines.append("")
    lines.append(
        f"### 当前形态（近 {window} 日）：强势日 {sig.get('strong_days', '—')} 天 · "
        f"量首末比 ×{_fmt(sig.get('amount_ratio'))} · 均涨 {_fmt(sig.get('avg_pct'))}%"
    )
    lines.append("| 历史相似窗口 | 距离 | 窗口内形态 | 后续5日 | 后续10日 | 后续20日 |")
    lines.append("|" + "---|" * 6)
    for a in artifact.analogs:
        s = a["signature"]
        lines.append(
            f"| {a['start_date']}~{a['end_date']} | {a['distance']} | "
            f"强势{s['strong_days']}天/量×{_fmt(s['amount_ratio'])}/均涨{_fmt(s['avg_pct'])}% | "
            f"{_fwd_text(a['forwards'][5])} | {_fwd_text(a['forwards'][10])} | {_fwd_text(a['forwards'][20])} |"
        )
    lines.append("")
    lines.append(
        "- 使用要求：个股历史类比是**小样本历史事实，不是概率预测**。只能表述为"
        "「该股历史上 X 段相似窗口中，后续 N 日实际为…」，禁止把样本频率说成上涨概率、"
        "禁止在样本外编情景；相似度只基于量价结构，不含基本面/题材/大盘环境差异，"
        "须提示读者叠加 D8（题材）与 D10（市场环境）交叉核对；后续走法须同时看"
        "区间最高与峰后回撤，不得只引用固定末日累计值。"
    )
    return "\n".join(lines)
