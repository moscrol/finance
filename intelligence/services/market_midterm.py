"""D6 多日/中期视角数据块：把「当日盘面快照」补上「多日趋势 + 拥挤度分位」。

背景（为什么要这个块）：
    brief/D4 主线块本质是「当日截面」——它回答「今天谁最强」。但用户问
    「未来 3-6 个月中期赔率 / 配置价值」时，当日双红最强 ≠ 中期赔率最优：
    当日强恰恰可能是短期拥挤度已高、透支了中期空间。若只喂当日截面给 LLM，
    它会把「今天信创双红 90 分」误当成「信创中期赔率第一」。这就是行业赔率
    对比题里出现的**时间尺度错配**。

设计（沿用 D0 时序块的 metric-store 纪律）：
    - **确定性意图路由**：正则识别「中期/中长线/赔率/配置/未来 N 个月」这类
      时间尺度意图词；命中才追加本块，避免污染短线盘面问答。
    - **参数化白名单查询，不拼 SQL**：题材名从 fact_sector_daily 的
      distinct sector_name 里做子串匹配解析（用户问题只决定「查哪些题材」），
      每个题材跑固定口径：近 N 日双红天数、成交额首末趋势、均涨、边际量均值、
      涨停热度趋势、以及**拥挤度分位**（最新成交额在自身 trailing-60 日分布里的
      分位——高分位=拥挤=中期赔率打折）。
    - 缺数显式声明（题材在板块表无独立行 / 库不可用），禁止外推。

可迁移知识点：
    - 「拥挤度分位」是把绝对量（成交额）转成相对历史的分位，规避「量大就是好」
      的误读——这套「值→自身历史分位」的做法在因子中性化、异常检测里也常用。
    - 「意图路由决定证据权重」是 RAG/agent 里很通用的一招：同一批底层数据，
      按 query 意图（短线 vs 中期）选择性加权/召回，而不是无差别全喂。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intelligence.services import retrieval_cache

from market_feature_store.signals import is_double_red
from intelligence.paths import default_market_db_path

REPO_ROOT = Path(__file__).resolve().parents[2]


DEFAULT_MARKET_DB_PATH = default_market_db_path()

DEFAULT_WINDOW = 20
MIN_WINDOW = 5
MAX_WINDOW = 120
CROWDING_LOOKBACK = 60  # 拥挤度分位的回看窗口（交易日）

# 中期/赔率/配置意图词。命中任一即视为「中期时间尺度」问题。
_MIDTERM_TERMS = (
    "中期",
    "中长期",
    "中长线",
    "赔率",
    "配置价值",
    "配置窗口",
    "季度维度",
    "未来半年",
    "下半年",
)
# 「未来 3 个月 / 3-6 个月 / 6 个月」这类显式月度时间窗。
_MONTH_WINDOW_RE = re.compile(r"未来\s*\d{1,2}\s*(?:[-~到至]\s*\d{1,2}\s*)?个月|(?<!\d)\d{1,2}\s*[-~]\s*\d{1,2}\s*个月")

# 常被拿来对比、但在 fact_sector_daily 里没有独立板块行（个股跨板块分散）的题材别名。
# 用途：query 点名了这类题材时，本块必须显式声明「该题材无板块多日数据」，
# 而不是静默把它从对比里剔除——静默剔除会让 LLM 误以为对比集只有能查到的那几个。
# 这是一个可扩展的小白名单，不做自由文本抽取（避免误命中）。
_GAP_THEME_ALIASES: dict[str, tuple[str, ...]] = {
    "数据安全": ("数据安全", "网络安全", "信息安全", "网安"),
}


@dataclass(frozen=True)
class MidtermIntent:
    window: int


@dataclass(frozen=True)
class MidtermTrendArtifact:
    window: int
    trends: tuple[dict[str, Any], ...]
    missing_themes: tuple[str, ...]
    evidence_id: str = "D6"
    degrade_reason: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.trends)

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "window": self.window,
            "available": self.available,
            "trends": list(self.trends),
            "missing_themes": list(self.missing_themes),
            "degrade_reason": self.degrade_reason,
        }


def parse_midterm_intent(query: str) -> MidtermIntent | None:
    """确定性意图路由：识别「中期/赔率/配置/未来 N 个月」时间尺度问题。

    只要命中中期意图词或显式月度时间窗即触发；窗口固定用 DEFAULT_WINDOW 个交易日
    （盘面多日趋势看 20 日足够，月度时间窗不改变盘面回看长度，只改变意图判定）。
    """
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return None
    has_intent = any(term in text for term in _MIDTERM_TERMS) or _MONTH_WINDOW_RE.search(str(query or "")) is not None
    if not has_intent:
        return None
    return MidtermIntent(window=DEFAULT_WINDOW)


def resolve_query_themes(con: Any, query: str, anchored_theme: str | None = None, limit: int = 4) -> list[str]:
    """从 query 里解析出要对比的题材（子串匹配 distinct sector_name，长名优先）。

    - 只做「板块表里已存在的题材名」子串匹配，天然把 query 收敛到可查口径；
    - 长名优先避免「数据要素」被「数据」抢先命中；
    - anchored_theme（上游锚定题材）兜底，保证至少有一个题材可查。
    """
    text = re.sub(r"\s+", "", str(query or ""))
    try:
        names = [str(r[0]) for r in con.execute(
            "select distinct sector_name from fact_sector_daily where sector_name is not null"
        ).fetchall()]
    except Exception:
        names = []
    names_sorted = sorted({n for n in names if n}, key=len, reverse=True)
    hit: list[str] = []
    remaining = text
    for name in names_sorted:
        if name in remaining and name not in hit:
            hit.append(name)
            remaining = remaining.replace(name, "□")
        if len(hit) >= limit:
            break
    if anchored_theme and anchored_theme not in hit:
        # 锚定题材放到末尾兜底（不抢占用户显式点名的题材顺序）。
        if any(anchored_theme in n or n in anchored_theme for n in names_sorted):
            hit.append(anchored_theme)
    return hit[:limit]


def detect_gap_themes(query: str, resolved: list[str]) -> list[str]:
    """query 点名了但无板块多日数据的题材（用于显式缺口声明）。

    只匹配 _GAP_THEME_ALIASES 小白名单；且已被 resolved 覆盖的不再重复列为缺口。
    """
    text = re.sub(r"\s+", "", str(query or ""))
    covered = "".join(resolved)
    gaps: list[str] = []
    for canonical, aliases in _GAP_THEME_ALIASES.items():
        if canonical in covered:
            continue
        if any(alias in text for alias in aliases):
            gaps.append(canonical)
    return gaps


def _trend_tag(first: float | None, last: float | None) -> str:
    if first is None or last is None or first == 0:
        return "—"
    ratio = last / first
    if ratio >= 1.05:
        return f"放量(×{ratio:.2f})"
    if ratio <= 0.95:
        return f"缩量(×{ratio:.2f})"
    return f"持平(×{ratio:.2f})"


def _fetch_theme_trend(con: Any, theme: str, window: int) -> dict[str, Any] | None:
    """单题材的多日趋势 + 拥挤度分位。题材在板块表无行时返回 None。"""
    rows = con.execute(
        f"""
        select trade_date, pct_chg, diff_ratio, amount
        from fact_sector_daily
        where sector_name = ?
        order by trade_date desc
        limit {int(window)}
        """,
        [theme],
    ).fetchall()
    if not rows:
        return None
    rows = list(reversed(rows))  # 升序（旧→新）
    amounts = [float(r[3]) for r in rows if r[3] is not None]
    pcts = [float(r[1]) for r in rows if r[1] is not None]
    diffs = [float(r[2]) for r in rows if r[2] is not None]
    double_red_days = sum(1 for r in rows if is_double_red(r[1], r[2], r[3]))
    first_amt = amounts[0] if amounts else None
    last_amt = amounts[-1] if amounts else None
    avg_pct = sum(pcts) / len(pcts) if pcts else None
    avg_diff = sum(diffs) / len(diffs) if diffs else None

    # 拥挤度分位：最新成交额在自身 trailing-60 日成交额分布里的百分位。
    hist = con.execute(
        f"""
        select amount from fact_sector_daily
        where sector_name = ? and amount is not null
        order by trade_date desc limit {CROWDING_LOOKBACK}
        """,
        [theme],
    ).fetchall()
    hist_amts = sorted(float(r[0]) for r in hist)
    crowding_pct: float | None = None
    if hist_amts and last_amt is not None:
        below = sum(1 for a in hist_amts if a <= last_amt)
        crowding_pct = round(100.0 * below / len(hist_amts), 1)

    # 涨停热度趋势（可选，题材可能在热度表无行）。
    heat = con.execute(
        f"""
        select trade_date, limit_up_count, rank
        from fact_theme_limit_heat_daily
        where sector_name = ?
        order by trade_date desc limit {int(window)}
        """,
        [theme],
    ).fetchall()
    heat_trend = None
    if heat:
        heat_rows = list(reversed(heat))
        first_lu = heat_rows[0][1]
        last_lu = heat_rows[-1][1]
        last_rank = heat_rows[-1][2]
        heat_trend = (first_lu, last_lu, last_rank)

    return {
        "theme": theme,
        "days": len(rows),
        "double_red_days": double_red_days,
        "amount_trend": _trend_tag(first_amt, last_amt),
        "avg_pct": avg_pct,
        "avg_diff": avg_diff,
        "crowding_pct": crowding_pct,
        "heat_trend": heat_trend,
        "first_date": str(rows[0][0]),
        "last_date": str(rows[-1][0]),
    }


def _fmt(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def load_midterm_trend_artifact(
    query: str,
    anchored_theme: str | None,
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
) -> MidtermTrendArtifact:
    db_path = (
        Path(market_db_path).expanduser()
        if market_db_path
        else DEFAULT_MARKET_DB_PATH
    )
    if not db_path.exists():
        return MidtermTrendArtifact(
            window,
            (),
            (),
            degrade_reason="D6 中期趋势库不存在",
        )
    try:
        import duckdb  # type: ignore
    except Exception:
        return MidtermTrendArtifact(
            window,
            (),
            (),
            degrade_reason="D6 中期趋势依赖不可用",
        )
    try:
        con = retrieval_cache.connect_readonly(db_path)
    except Exception:
        return MidtermTrendArtifact(
            window,
            (),
            (),
            degrade_reason="D6 中期趋势库不可读",
        )
    try:
        themes = resolve_query_themes(con, query, anchored_theme)
        trends: list[dict[str, Any]] = []
        missing: list[str] = []
        for theme in themes:
            trend = _fetch_theme_trend(con, theme, window)
            if trend is None:
                missing.append(theme)
            else:
                trends.append(trend)
        missing.extend(
            theme
            for theme in detect_gap_themes(query, themes)
            if theme not in missing
        )
        reason = None
        if not trends:
            reason = "D6 未找到可用的题材中期趋势数据"
        return MidtermTrendArtifact(
            window,
            tuple(trends),
            tuple(missing),
            degrade_reason=reason,
        )
    except Exception:
        return MidtermTrendArtifact(
            window,
            (),
            (),
            degrade_reason="D6 中期趋势查询失败",
        )
    finally:
        try:
            con.close()
        except Exception:
            pass


def midterm_trend_block_for_llm(
    query: str,
    anchored_theme: str | None,
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
) -> str:
    """把多日趋势 + 拥挤度分位渲染成带 [D6] 引用编号的确定性数据块（空串=未取到）。"""
    artifact = load_midterm_trend_artifact(
        query,
        anchored_theme,
        market_db_path,
        window,
    )
    if not artifact.available:
        return ""
    trends = list(artifact.trends)
    missing = list(artifact.missing_themes)
    try:
        lines = ["## 多日/中期趋势数据块 [D6]"]
        lines.append(
            f"- 查询口径：近 {window} 个交易日（{trends[0]['first_date']} ~ {trends[0]['last_date']}），"
            "本地 DuckDB fact_sector_daily / fact_theme_limit_heat_daily 参数化直查，非 LLM 生成。"
        )
        lines.append(
            "- 拥挤度分位口径：该题材最新成交额在自身近 "
            f"{CROWDING_LOOKBACK} 日成交额分布里的百分位（越高=越拥挤，中期赔率相应打折）。"
        )
        header = "| 题材 | 覆盖天数 | 近N日双红天数 | 成交额趋势(首→末) | 近N日均涨% | 边际量均值% | 涨停热度(首→末,最新rank) | 拥挤度分位 |"
        sep = "|" + "---|" * 8
        lines.append("")
        lines.append(header)
        lines.append(sep)
        for t in trends:
            if t["heat_trend"]:
                first_lu, last_lu, last_rank = t["heat_trend"]
                heat_text = f"{first_lu}→{last_lu}，rank{last_rank}"
            else:
                heat_text = "—"
            crowd = f"{t['crowding_pct']}%" if t["crowding_pct"] is not None else "—"
            lines.append(
                f"| {t['theme']} | {t['days']} | {t['double_red_days']} | {t['amount_trend']} | "
                f"{_fmt(t['avg_pct'])} | {_fmt(t['avg_diff'])} | {heat_text} | {crowd} |"
            )
        lines.append("")
        if missing:
            lines.append(
                "- 数据缺口：" + "、".join(missing) + " 在板块日行情表无独立行（可能是跨板块分散题材），"
                "该题材的多日趋势无法给出，禁止用当日或其他来源外推。"
            )
        lines.append(
            "- 使用要求：本块用于回答「中期赔率/配置价值/未来数月」类问题。"
            "**当日强度 ≠ 中期赔率**：某题材当日双红/涨停领先，但若近 N 日双红天数稀少、成交额缩量、"
            "拥挤度分位偏高（如 ≥80%），说明是短期脉冲而非中期趋势，中期赔率应下调；"
            "反之双红天数多、放量、拥挤度分位不高，才支持中期占优。必须结合本块多日证据判断，"
            "不得只凭当日 [D4]/[S] 截面给中期结论。缺口题材只能声明缺数。"
        )
        return "\n".join(lines)
    except Exception:
        return ""
