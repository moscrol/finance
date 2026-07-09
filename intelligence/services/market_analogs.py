"""D8 历史类比检索块：从题材自身历史里找「和当前形态相似的窗口」及其后续走法。

背景（为什么要这个块）：
    「历史上类似的切换怎么走」两轮基准题都答不出——数据全在 DuckDB，但没有模块
    把「当前 N 日形态」和「历史同形态窗口 + 后续实际走势」对齐取出来。Knevo 用
    LLM 印象流补这段（无溯源），我们做确定性版：**只列历史事实，不给概率**。

设计（沿用 D6 的参数化白名单纪律）：
    - **确定性意图路由**：命中「类似/类比/历史上/上一次/先例/过往/复盘过去」
      词面才触发，避免污染普通盘面问答。
    - **形态签名**：当前窗口（默认 20 交易日）的（双红天数、成交额首末比、均涨），
      在该题材自身全部历史上滑窗（步长 5 日）算同口径签名，按加权距离取最近的
      K 段互不重叠窗口。
    - **后续走法只报事实**：每段类比窗口之后 5/10/20 交易日的均涨、双红天数、
      成交额变化——全部来自 fact_sector_daily 逐日行，非 LLM 生成。
    - 缺数（库不可用/题材无行/历史太短/无相似窗口）显式声明，禁止外推。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WINDOW = 20
STRIDE = 5
TOP_K = 3
FORWARD_HORIZONS = (5, 10, 20)
MIN_HISTORY_MULTIPLE = 3  # 历史至少要有 3 个窗口长度才谈得上找类比

_ANALOG_TERMS = (
    "类似",
    "类比",
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


def parse_analog_intent(query: str) -> bool:
    """确定性意图路由：命中「类似/历史上/上一次/先例」类词面才触发。"""
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return False
    return any(term in text for term in _ANALOG_TERMS)


@dataclass(frozen=True)
class Signature:
    double_red_days: int
    amount_ratio: float | None
    avg_pct: float | None


def _signature(rows: list[tuple]) -> Signature:
    """rows 为升序 (trade_date, pct_chg, diff_ratio, amount)。"""
    amounts = [float(r[3]) for r in rows if r[3] is not None]
    pcts = [float(r[1]) for r in rows if r[1] is not None]
    double_red = sum(
        1 for r in rows
        if r[1] is not None and r[2] is not None and r[3] is not None
        and float(r[1]) > 0 and float(r[2]) > 10 and float(r[3]) > 500
    )
    ratio = (amounts[-1] / amounts[0]) if len(amounts) >= 2 and amounts[0] else None
    avg_pct = sum(pcts) / len(pcts) if pcts else None
    return Signature(double_red, ratio, avg_pct)


def _distance(a: Signature, b: Signature, window: int) -> float | None:
    if a.amount_ratio is None or b.amount_ratio is None or a.avg_pct is None or b.avg_pct is None:
        return None
    return (
        2.0 * abs(a.double_red_days - b.double_red_days) / max(window, 1)
        + abs(a.amount_ratio - b.amount_ratio)
        + 0.5 * abs(a.avg_pct - b.avg_pct)
    )


def find_analog_windows(
    rows: list[tuple],
    window: int = DEFAULT_WINDOW,
    stride: int = STRIDE,
    top_k: int = TOP_K,
) -> tuple[Signature | None, list[dict[str, Any]]]:
    """rows 为该题材升序全历史。返回（当前签名，最相似的 K 段历史窗口及后续走法）。

    历史窗口须与当前窗口不重叠、且相互不重叠；每段带后续 5/10/20 日事实。
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
        sig = _signature(seg)
        forwards: dict[int, dict[str, Any] | None] = {}
        for h in FORWARD_HORIZONS:
            fwd = rows[end:end + h]
            if len(fwd) < h:
                forwards[h] = None
                continue
            fsig = _signature(fwd)
            forwards[h] = {
                "avg_pct": fsig.avg_pct,
                "double_red_days": fsig.double_red_days,
                "amount_ratio": fsig.amount_ratio,
            }
        picked.append(
            {
                "start_date": str(seg[0][0]),
                "end_date": str(seg[-1][0]),
                "distance": round(d, 3),
                "signature": sig,
                "forwards": forwards,
            }
        )
        used.append((start, end))
        if len(picked) >= top_k:
            break
    return current, picked


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
    return f"均涨{_fmt(fwd['avg_pct'])}%/双红{fwd['double_red_days']}天/量×{_fmt(fwd['amount_ratio'])}"


def analog_block_for_llm(
    query: str,
    anchored_theme: str | None,
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
) -> str:
    """把历史类比窗口渲染成带 [D8] 引用编号的确定性数据块（空串=未取到）。"""
    db_path = Path(market_db_path).expanduser() if market_db_path else REPO_ROOT / "db" / "market_feature_store.duckdb"
    if not db_path.exists():
        return ""
    try:
        import duckdb  # type: ignore
    except Exception:
        return ""
    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except Exception:
        return ""
    try:
        from intelligence.services.market_midterm import resolve_query_themes

        themes = resolve_query_themes(con, query, anchored_theme, limit=2)
        if not themes:
            return ""
        lines = ["## 历史类比检索块 [D8]"]
        lines.append(
            f"- 口径：题材自身历史上与「最近 {window} 个交易日形态」（双红天数/成交额首末比/均涨）"
            "加权距离最近的窗口，及其后续 5/10/20 日实际走法；"
            "本地 DuckDB fact_sector_daily 逐日行计算，非 LLM 生成。"
        )
        rendered = 0
        for theme in themes:
            rows = con.execute(
                """
                select trade_date, pct_chg, diff_ratio, amount
                from fact_sector_daily
                where sector_name = ?
                order by trade_date asc
                """,
                [theme],
            ).fetchall()
            current, analogs = find_analog_windows(rows, window=window)
            if current is None:
                lines.append(
                    f"- 数据缺口：{theme} 历史行数不足（<{window * MIN_HISTORY_MULTIPLE} 交易日），"
                    "无法做历史类比，禁止用其他来源外推。"
                )
                continue
            if not analogs:
                lines.append(f"- 数据缺口：{theme} 未找到可比历史窗口（签名字段缺失），禁止外推。")
                continue
            rendered += 1
            lines.append("")
            lines.append(
                f"### {theme} 当前形态（近 {window} 日）：双红 {current.double_red_days} 天 · "
                f"量首末比 ×{_fmt(current.amount_ratio)} · 均涨 {_fmt(current.avg_pct)}%"
            )
            lines.append("| 历史相似窗口 | 距离 | 窗口内形态 | 后续5日 | 后续10日 | 后续20日 |")
            lines.append("|" + "---|" * 6)
            for a in analogs:
                sig = a["signature"]
                lines.append(
                    f"| {a['start_date']}~{a['end_date']} | {a['distance']} | "
                    f"双红{sig.double_red_days}天/量×{_fmt(sig.amount_ratio)}/均涨{_fmt(sig.avg_pct)}% | "
                    f"{_fwd_text(a['forwards'][5])} | {_fwd_text(a['forwards'][10])} | {_fwd_text(a['forwards'][20])} |"
                )
        if rendered == 0 and len(lines) <= 2:
            return ""
        lines.append("")
        lines.append(
            "- 使用要求：历史类比是**小样本历史事实，不是概率预测**。只能表述为"
            "「历史上 X 段相似窗口中，后续 N 日实际为…」，禁止把样本频率说成切换概率、"
            "禁止在样本外编情景；相似度基于盘面形态，不含基本面/消息面差异，须提示读者自行核对背景。"
        )
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        try:
            con.close()
        except Exception:
            pass
