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

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from intelligence.services import retrieval_cache
from intelligence.paths import default_market_db_path

REPO_ROOT = Path(__file__).resolve().parents[2]


DEFAULT_MARKET_DB_PATH = default_market_db_path()

# 跨题材历史剧本库（人工审核卡）：同题材量化匹配只能覆盖库内历史，
# 剧本卡把「2019 半导体 / 2022 信创」这类长历史、跨题材案例结构化后供特征匹配；
# 只有 review_status=approved 的卡才会进块（人工把关数字后生效，保可溯源纪律）。
PLAYBOOK_PATH = REPO_ROOT / "intelligence" / "data" / "market_playbooks.jsonl"
PLAYBOOK_LOOKBACK = 60
PLAYBOOK_TOP_K = 2
# 特征→归一化尺度（差异除以尺度后大致落在 0~1）
_PLAYBOOK_FEATURE_SCALES: dict[str, float] = {
    "drawdown_pct": 10.0,  # 回撤深度（%）
    "rebound_retrace_ratio": 0.4,  # 反弹收复比例（0~1）
    "volume_shrink_ratio": 0.4,  # 末5日均量/窗口峰值5日均量
}

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


@dataclass(frozen=True)
class HistoricalAnalogArtifact:
    window: int
    themes: tuple[dict[str, Any], ...]
    missing_themes: tuple[str, ...]
    evidence_id: str = "D8"
    degrade_reason: str | None = None

    @property
    def available(self) -> bool:
        return any(theme.get("analogs") for theme in self.themes)

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "window": self.window,
            "available": self.available,
            "themes": list(self.themes),
            "missing_themes": list(self.missing_themes),
            "degrade_reason": self.degrade_reason,
        }


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


def load_historical_analog_artifact(
    query: str,
    anchored_theme: str | None,
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
) -> HistoricalAnalogArtifact:
    db_path = (
        Path(market_db_path).expanduser()
        if market_db_path
        else DEFAULT_MARKET_DB_PATH
    )
    if not db_path.exists():
        return HistoricalAnalogArtifact(
            window,
            (),
            (),
            degrade_reason="D8 历史类比库不存在",
        )
    try:
        import duckdb  # type: ignore
    except Exception:
        return HistoricalAnalogArtifact(
            window,
            (),
            (),
            degrade_reason="D8 历史类比依赖不可用",
        )
    try:
        con = retrieval_cache.connect_readonly(db_path)
    except Exception:
        return HistoricalAnalogArtifact(
            window,
            (),
            (),
            degrade_reason="D8 历史类比库不可读",
        )
    try:
        from intelligence.services.market_midterm import resolve_query_themes

        themes = resolve_query_themes(con, query, anchored_theme, limit=2)
        artifacts: list[dict[str, Any]] = []
        missing: list[str] = []
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
            if current is None or not analogs:
                missing.append(theme)
                continue
            normalized_analogs: list[dict[str, Any]] = []
            for analog in analogs:
                normalized = dict(analog)
                signature = normalized.get("signature")
                if isinstance(signature, Signature):
                    normalized["signature"] = asdict(signature)
                normalized_analogs.append(normalized)
            artifacts.append(
                {
                    "theme": theme,
                    "current_signature": asdict(current),
                    "analogs": normalized_analogs,
                }
            )
        reason = None
        if not artifacts:
            reason = "D8 未找到足够历史数据的类似窗口"
        return HistoricalAnalogArtifact(
            window,
            tuple(artifacts),
            tuple(missing),
            degrade_reason=reason,
        )
    except Exception:
        return HistoricalAnalogArtifact(
            window,
            (),
            (),
            degrade_reason="D8 历史类比查询失败",
        )
    finally:
        try:
            con.close()
        except Exception:
            pass


def load_playbooks(path: Path | None = None, include_drafts: bool = False) -> list[dict[str, Any]]:
    """读剧本库 JSONL；默认只返回人工审核通过（review_status=approved）的卡。"""
    p = path or PLAYBOOK_PATH
    if not p.exists():
        return []
    cards: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            card = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(card, dict):
            continue
        status = str((card.get("source") or {}).get("review_status") or "").strip()
        if include_drafts or status == "approved":
            cards.append(card)
    return cards


def current_pattern_features(rows: list[tuple], lookback: int = PLAYBOOK_LOOKBACK) -> dict[str, float] | None:
    """从题材逐日行提取剧本匹配用形态特征（近 lookback 日）：
    回撤深度 / 反弹收复比例 / 量能萎缩比。行数不足或无有效回撤时返回 None（不硬匹）。"""
    seg = [r for r in rows[-lookback:] if r[1] is not None]
    if len(seg) < lookback // 2:
        return None
    prices: list[float] = []
    level = 1.0
    for r in seg:
        level *= 1.0 + float(r[1]) / 100.0
        prices.append(level)
    hi_idx = max(range(len(prices)), key=lambda i: prices[i])
    tail = prices[hi_idx:]
    low_off = min(range(len(tail)), key=lambda i: tail[i])
    hi, low, last = prices[hi_idx], tail[low_off], prices[-1]
    if hi <= 0 or hi == low:
        return None
    features: dict[str, float] = {
        "drawdown_pct": (low / hi - 1.0) * 100.0,
        "rebound_retrace_ratio": (last - low) / (hi - low),
    }
    amounts = [float(r[3]) for r in seg if r[3] is not None]
    if len(amounts) >= 10:
        peak5 = max(
            sum(amounts[i:i + 5]) / 5 for i in range(len(amounts) - 4)
        )
        last5 = sum(amounts[-5:]) / 5
        if peak5 > 0:
            features["volume_shrink_ratio"] = last5 / peak5
    return features


def playbook_distance(current: dict[str, float], pattern: dict[str, Any]) -> float | None:
    """特征空间加权距离；双方都有的维度才参与，缺维按覆盖率惩罚（不伪造缺失维度）。"""
    acc, used = 0.0, 0
    for feat, scale in _PLAYBOOK_FEATURE_SCALES.items():
        a, b = current.get(feat), pattern.get(feat)
        if a is None or b is None:
            continue
        try:
            acc += abs(float(a) - float(b)) / scale
        except (TypeError, ValueError):
            continue
        used += 1
    if used == 0:
        return None
    return (acc / used) * (len(_PLAYBOOK_FEATURE_SCALES) / used)


def match_playbooks(
    current: dict[str, float],
    cards: list[dict[str, Any]],
    top_k: int = PLAYBOOK_TOP_K,
) -> list[tuple[float, dict[str, Any]]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for card in cards:
        d = playbook_distance(current, card.get("pattern") or {})
        if d is not None:
            scored.append((d, card))
    scored.sort(key=lambda x: x[0])
    return scored[:top_k]


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


def _playbook_section(rows: list[tuple] | None, path: Path | None = None) -> list[str]:
    """跨题材剧本类比小节：当前形态特征 × 剧本库 approved 卡的特征距离匹配。"""
    if not rows:
        return []
    current = current_pattern_features(rows)
    if current is None:
        return []
    approved = load_playbooks(path)
    lines = ["### 跨题材历史剧本类比（人工审核剧本库）"]
    lines.append(
        f"- 当前形态特征（近 {PLAYBOOK_LOOKBACK} 日）：回撤 {_fmt(current.get('drawdown_pct'))}% · "
        f"反弹收复 {_fmt(current.get('rebound_retrace_ratio'))} · "
        f"末5日量/峰值量 {_fmt(current.get('volume_shrink_ratio'))}"
    )
    if not approved:
        drafts = len(load_playbooks(path, include_drafts=True))
        lines.append(
            f"- 数据缺口：剧本库暂无人工审核通过（approved）的剧本卡（库内共 {drafts} 张，含待审核），"
            "跨题材类比缺席；禁止由 LLM 自行补编历史案例。"
        )
        return lines
    matches = match_playbooks(current, approved)
    if not matches:
        lines.append("- 数据缺口：approved 剧本卡与当前形态无可比特征维度，跨题材类比缺席，禁止外推。")
        return lines
    lines.append("| 剧本 | 距离 | 历史形态 | 后续走法（事实） | 催化剂 | 数据溯源 |")
    lines.append("|" + "---|" * 6)
    for d, card in matches:
        pat = card.get("pattern") or {}
        outcome = card.get("outcome") or {}
        catalyst = card.get("catalyst") or {}
        source = card.get("source") or {}
        pat_text = (
            f"回撤{_fmt(pat.get('drawdown_pct'))}%/收复{_fmt(pat.get('rebound_retrace_ratio'))}"
            f"/量{_fmt(pat.get('volume_shrink_ratio'))}"
        )
        fwd = "、".join(
            f"{h.replace('fwd_', '后续').replace('d_pct', '日')} {_fmt(outcome.get(h))}%"
            for h in ("fwd_20d_pct", "fwd_60d_pct")
            if outcome.get(h) is not None
        )
        outcome_text = str(outcome.get("path") or "—") + (f"（{fwd}）" if fwd else "")
        lines.append(
            f"| {card.get('theme', '—')} {card.get('period', '')} | {d:.3f} | {pat_text} | "
            f"{outcome_text} | {catalyst.get('type', '—')}：{catalyst.get('desc', '—')} | "
            f"{source.get('data', '—')} |"
        )
    return lines


def analog_block_for_llm(
    query: str,
    anchored_theme: str | None,
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
) -> str:
    """把历史类比窗口渲染成带 [D8] 引用编号的确定性数据块（空串=未取到）。"""
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    if not db_path.exists():
        return ""
    try:
        import duckdb  # type: ignore
    except Exception:
        return ""
    try:
        con = retrieval_cache.connect_readonly(db_path)
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
        first_theme_rows: list[tuple] | None = None
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
            if rows and first_theme_rows is None:
                first_theme_rows = rows
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
        playbook_lines = _playbook_section(first_theme_rows)
        if playbook_lines:
            lines.append("")
            lines.extend(playbook_lines)
        if rendered == 0 and not playbook_lines and len(lines) <= 2:
            return ""
        lines.append("")
        lines.append(
            "- 使用要求：历史类比是**小样本历史事实，不是概率预测**。只能表述为"
            "「历史上 X 段相似窗口中，后续 N 日实际为…」，禁止把样本频率说成切换概率、"
            "禁止在样本外编情景；相似度基于盘面形态，不含基本面/消息面差异，须提示读者自行核对背景；"
            "跨题材剧本卡是人工审核的历史事实摘录，引用时须带卡内数据溯源，禁止 LLM 自行补编库外历史案例。"
        )
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        try:
            con.close()
        except Exception:
            pass
