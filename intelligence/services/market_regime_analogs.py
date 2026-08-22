"""D10 市场情绪环境类比块：给一段区间的市场情绪结构，找历史上相似的情绪环境。

背景（为什么要这个块）：
    「看到这段区间的行情，找以往类似的情绪环境」——D8 只能做**题材级**类比
    （某题材自身历史），而情绪环境是**市场级**的：涨停潮/连板高度/涨家数/成交额/
    题材集中度共同构成的市场状态。本块做确定性版：**只列历史事实，不给概率**。

设计（沿用 D8 的纪律，见 2026-08-13 memory-analog-lifecycle 设计稿 §4）：
    - **确定性意图路由**：须同时命中「环境类词面」（情绪/盘面/市场环境/行情…）与
      「类比类词面」（类似/相似/对标/历史上…）才触发——单独问"今天情绪怎么样"
      或题材级类比（D8 的领地）都不触发。
    - **每日情绪向量**：成交额/涨家数/涨停/跌停/指数偏离度/指数涨跌/连板最高度/
      双红题材数/第一题材涨停份额/新高家数，全部来自主库现有表，无新数据源。
    - **z-score 标准化**：市场级特征跨年代量纲漂移大（成交额 8000 亿→2 万亿），
      固定尺度表会失效；改为每个特征对全历史做 z 标准化后再比距离。
      代价：相似=「相对自身历史的相似」，跨库不可直接搬距离值。
    - **窗口签名**：窗口内每维取（z 均值, z 首尾段变化），加权 L1 距离 + 缺维按
      覆盖率惩罚（某表缺数据的年代不伪造维度，只降权）。
    - **后续走法只报事实**：每段类比窗口之后 5/10/20 交易日的指数累计涨跌、
      日均涨停、最高连板、日均双红题材数——全部来自库内逐日行，非 LLM 生成。
    - 缺数（库不可用/历史太短/维度缺失）显式声明，禁止外推。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intelligence.paths import default_market_db_path
from intelligence.services import retrieval_cache
from market_feature_store.signals import DOUBLE_RED_SQL

DEFAULT_MARKET_DB_PATH = default_market_db_path()

DEFAULT_WINDOW = 20
STRIDE = 5
TOP_K = 3
FORWARD_HORIZONS = (5, 10, 20)
MIN_HISTORY_MULTIPLE = 3  # 与 D8 一致：历史至少 3 个窗口长度才谈得上找类比

# 每日情绪向量的特征维（键名 = loader 产出的字段名）
FEATURES: tuple[str, ...] = (
    "total_amount",            # 两市成交额（亿）
    "advancers",               # 涨家数
    "limit_up",                # 涨停家数
    "limit_down",              # 跌停家数
    "sh_deviation_pct",        # 上证对周均线偏离度（%）
    "sh_index_pct_chg",        # 上证日涨跌（%）
    "max_boards",              # 连板最高度
    "double_red_theme_count",  # 严格双红题材数（pct>0 & diff>10 & amount>500）
    "top1_theme_share",        # 第一题材涨停份额
    "new_high_count",          # 新高家数
)

# 展示层用的中文标签（渲染当前/历史窗口摘要时用原始量纲，可读性优先）
_DISPLAY_FEATURES: tuple[tuple[str, str, str], ...] = (
    ("total_amount", "成交额", "亿"),
    ("limit_up", "涨停", "家"),
    ("max_boards", "最高连板", "板"),
    ("double_red_theme_count", "双红题材", "个"),
    ("sh_deviation_pct", "偏离度", "%"),
)

_MIN_FEATURE_COVERAGE = 0.6  # 窗口内某维非空占比低于此值 → 该维视为缺失
_DELTA_WEIGHT = 0.5          # 趋势项（首尾段变化）相对水平项（均值）的权重
_STD_EPSILON = 1e-9

# 意图路由：环境词面 × 类比词面须同时命中
_ENV_TERMS = (
    "情绪",
    "盘面",
    "市场环境",
    "行情",
    "赚钱效应",
    "涨停潮",
    "这种市场",
)
_ANALOG_TERMS = (
    "类似",
    "类比",
    "相似",
    "对标",
    "历史上",
    "上一次",
    "上次",
    "先例",
    "以往",
    "过往",
    "历史经验",
)


def parse_regime_intent(query: str) -> bool:
    """确定性意图路由：环境词面与类比词面须同时命中才触发。

    「今天情绪怎么样」只有环境词 → 不触发（普通盘面问答）；
    「历史上信创类似走势」只有类比词 → 不触发（那是 D8 题材级的领地）。
    """
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return False
    return any(t in text for t in _ENV_TERMS) and any(t in text for t in _ANALOG_TERMS)


@dataclass(frozen=True)
class RegimeSignature:
    """单个窗口的情绪签名：feature → (z 均值, z 首尾段变化)；缺维不出现在 dict 里。"""

    stats: dict[str, tuple[float, float]]

    @property
    def dims(self) -> int:
        return len(self.stats)


@dataclass(frozen=True)
class MarketRegimeArtifact:
    window: int
    current_summary: dict[str, float | None]
    analogs: tuple[dict[str, Any], ...]
    missing_features: tuple[str, ...]
    evidence_id: str = "D10"
    degrade_reason: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.analogs)

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "window": self.window,
            "available": self.available,
            "current_summary": dict(self.current_summary),
            "analogs": list(self.analogs),
            "missing_features": list(self.missing_features),
            "degrade_reason": self.degrade_reason,
        }


def standardize_vectors(
    vectors: list[dict[str, Any]],
    features: tuple[str, ...] = FEATURES,
) -> tuple[list[dict[str, float | None]], list[str]]:
    """对全历史做逐特征 z 标准化；std≈0（常量维，无信息）或全空的维整体剔除。

    返回 (z 行列表, 被剔除/缺失的特征名列表)。z 行保留 None（当日缺数）。
    """
    dropped: list[str] = []
    stats: dict[str, tuple[float, float]] = {}
    for feat in features:
        values = [float(row[feat]) for row in vectors if row.get(feat) is not None]
        if not values:
            dropped.append(feat)
            continue
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        std = var ** 0.5
        if std < _STD_EPSILON:
            dropped.append(feat)
            continue
        stats[feat] = (mean, std)
    z_rows: list[dict[str, float | None]] = []
    for row in vectors:
        z_row: dict[str, float | None] = {}
        for feat, (mean, std) in stats.items():
            raw = row.get(feat)
            z_row[feat] = None if raw is None else (float(raw) - mean) / std
        z_rows.append(z_row)
    return z_rows, dropped


def window_signature(
    z_rows: list[dict[str, float | None]],
    features: tuple[str, ...] = FEATURES,
) -> RegimeSignature:
    """窗口签名：每维（z 均值, z 末段均值−首段均值）；覆盖率不足的维不进签名。"""
    n = len(z_rows)
    seg = max(1, n // 3)
    stats: dict[str, tuple[float, float]] = {}
    for feat in features:
        values = [(i, row[feat]) for i, row in enumerate(z_rows) if row.get(feat) is not None]
        if len(values) < max(1, int(n * _MIN_FEATURE_COVERAGE)):
            continue
        vals = [v for _, v in values]
        mean = sum(vals) / len(vals)
        head = [v for i, v in values if i < seg]
        tail = [v for i, v in values if i >= n - seg]
        if not head or not tail:
            continue
        delta = sum(tail) / len(tail) - sum(head) / len(head)
        stats[feat] = (mean, delta)
    return RegimeSignature(stats)


def signature_distance(
    a: RegimeSignature,
    b: RegimeSignature,
    total_dims: int,
) -> float | None:
    """双方共有维度的加权 L1 距离，除以维数后按覆盖率惩罚放大（缺维不伪造，只降权）。"""
    shared = [f for f in a.stats if f in b.stats]
    if not shared:
        return None
    acc = 0.0
    for feat in shared:
        am, ad = a.stats[feat]
        bm, bd = b.stats[feat]
        acc += abs(am - bm) + _DELTA_WEIGHT * abs(ad - bd)
    used = len(shared)
    return (acc / used) * (max(total_dims, 1) / used)


def _raw_window_summary(
    rows: list[dict[str, Any]],
    features: tuple[tuple[str, str, str], ...] = _DISPLAY_FEATURES,
) -> dict[str, float | None]:
    """展示用：窗口内各展示维的原始量纲均值（缺数维为 None）。"""
    summary: dict[str, float | None] = {}
    for feat, _, _ in features:
        vals = [float(r[feat]) for r in rows if r.get(feat) is not None]
        summary[feat] = (sum(vals) / len(vals)) if vals else None
    return summary


def _forward_facts(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any] | None:
    """类比窗口之后 horizon 日的市场实际走法（只报事实）。行数不足返回 None。"""
    if len(rows) < horizon:
        return None
    seg = rows[:horizon]
    pcts = [float(r["sh_index_pct_chg"]) for r in seg if r.get("sh_index_pct_chg") is not None]
    cum: float | None = None
    if len(pcts) >= max(1, int(horizon * _MIN_FEATURE_COVERAGE)):
        level = 1.0
        for p in pcts:
            level *= 1.0 + p / 100.0
        cum = (level - 1.0) * 100.0
    limit_ups = [float(r["limit_up"]) for r in seg if r.get("limit_up") is not None]
    boards = [float(r["max_boards"]) for r in seg if r.get("max_boards") is not None]
    double_red = [
        float(r["double_red_theme_count"])
        for r in seg
        if r.get("double_red_theme_count") is not None
    ]
    return {
        "sh_index_cum_pct": cum,
        "avg_limit_up": (sum(limit_ups) / len(limit_ups)) if limit_ups else None,
        "max_boards": max(boards) if boards else None,
        "avg_double_red_themes": (sum(double_red) / len(double_red)) if double_red else None,
    }


def find_regime_analogs(
    vectors: list[dict[str, Any]],
    window: int = DEFAULT_WINDOW,
    stride: int = STRIDE,
    top_k: int = TOP_K,
) -> tuple[RegimeSignature | None, list[dict[str, Any]], list[str]]:
    """vectors 为升序全历史每日情绪向量（含 trade_date 键）。

    返回（当前窗口签名, 最相似的 K 段互不重叠历史窗口, 整体缺失的特征名）。
    历史窗口须与当前窗口不重叠；每段带后续 5/10/20 日事实。
    """
    n = len(vectors)
    if n < window * MIN_HISTORY_MULTIPLE:
        return None, [], []
    z_rows, dropped = standardize_vectors(vectors)
    current = window_signature(z_rows[n - window:])
    if not current.stats:
        return None, [], dropped
    total_dims = len(FEATURES) - len(dropped)
    candidates: list[tuple[float, int]] = []
    for start in range(0, n - 2 * window, stride):
        sig = window_signature(z_rows[start:start + window])
        d = signature_distance(current, sig, total_dims)
        if d is not None:
            candidates.append((d, start))
    candidates.sort()
    picked: list[dict[str, Any]] = []
    used: list[tuple[int, int]] = []
    for d, start in candidates:
        end = start + window
        if any(not (end <= s or start >= e) for s, e in used):
            continue
        seg = vectors[start:end]
        forwards: dict[int, dict[str, Any] | None] = {
            h: _forward_facts(vectors[end:], h) for h in FORWARD_HORIZONS
        }
        picked.append(
            {
                "start_date": str(seg[0]["trade_date"]),
                "end_date": str(seg[-1]["trade_date"]),
                "distance": round(d, 3),
                "raw_summary": _raw_window_summary(seg),
                "forwards": forwards,
            }
        )
        used.append((start, end))
        if len(picked) >= top_k:
            break
    return current, picked, dropped


# ---------------------------------------------------------------------------
# 取数层：从主库现有表拼每日情绪向量。基表 fact_market_daily 缺失 → 整体降级；
# 辅表缺失 → 对应维度整体缺失（进 missing_features，匹配时按覆盖率降权）。
# ---------------------------------------------------------------------------

_AUX_QUERIES: dict[str, str] = {
    "max_boards": (
        "select trade_date, max(boards) from fact_limit_advance_daily group by trade_date"
    ),
    "double_red_theme_count": (
        "select trade_date, count(*) from fact_sector_daily "
        f"where {DOUBLE_RED_SQL} group by trade_date"
    ),
    "top1_theme_share": (
        "select trade_date, max(market_share) from fact_theme_limit_heat_daily group by trade_date"
    ),
    "new_high_count": (
        "select trade_date, count(*) from fact_stock_high_daily group by trade_date"
    ),
}


def load_market_regime_vectors(con: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """从只读连接拼每日情绪向量。返回 (升序向量列表, 缺失特征名列表)。"""
    try:
        base = con.execute(
            "select trade_date, total_amount, advancers, limit_up, limit_down, "
            "sh_deviation_pct, sh_index_pct_chg "
            "from fact_market_daily order by trade_date asc"
        ).fetchall()
    except Exception:
        return [], list(FEATURES)
    if not base:
        return [], list(FEATURES)
    missing: list[str] = []
    aux_maps: dict[str, dict[str, float]] = {}
    for feat, sql in _AUX_QUERIES.items():
        try:
            rows = con.execute(sql).fetchall()
        except Exception:
            missing.append(feat)
            continue
        aux_maps[feat] = {
            str(r[0]): float(r[1]) for r in rows if r[1] is not None
        }
    vectors: list[dict[str, Any]] = []
    for row in base:
        day = str(row[0])
        vec: dict[str, Any] = {
            "trade_date": day,
            "total_amount": row[1],
            "advancers": row[2],
            "limit_up": row[3],
            "limit_down": row[4],
            "sh_deviation_pct": row[5],
            "sh_index_pct_chg": row[6],
        }
        for feat in _AUX_QUERIES:
            vec[feat] = aux_maps.get(feat, {}).get(day) if feat in aux_maps else None
        vectors.append(vec)
    return vectors, missing


def load_market_regime_artifact(
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
) -> MarketRegimeArtifact:
    db_path = (
        Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    )
    if not db_path.exists():
        return MarketRegimeArtifact(
            window, {}, (), (), degrade_reason="D10 市场情绪类比库不存在"
        )
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return MarketRegimeArtifact(
            window, {}, (), (), degrade_reason="D10 市场情绪类比库不可读"
        )
    con = db_result.connection
    try:
        vectors, missing = load_market_regime_vectors(con)
        if not vectors:
            return MarketRegimeArtifact(
                window, {}, (), tuple(missing),
                degrade_reason="D10 fact_market_daily 无数据",
            )
        current, analogs, dropped = find_regime_analogs(vectors, window=window)
        all_missing = tuple(dict.fromkeys([*missing, *dropped]))
        if current is None or not analogs:
            return MarketRegimeArtifact(
                window, {}, (), all_missing,
                degrade_reason="D10 历史不足或无可比情绪窗口",
            )
        return MarketRegimeArtifact(
            window,
            _raw_window_summary(vectors[-window:]),
            tuple(analogs),
            all_missing,
        )
    except Exception:
        return MarketRegimeArtifact(
            window, {}, (), (), degrade_reason="D10 市场情绪类比查询失败"
        )
    finally:
        try:
            con.close()
        except Exception:
            pass


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _summary_text(summary: dict[str, float | None]) -> str:
    parts = []
    for feat, label, unit in _DISPLAY_FEATURES:
        value = summary.get(feat)
        if value is None:
            continue
        digits = 0 if feat in ("limit_up", "max_boards", "double_red_theme_count") else 1
        parts.append(f"{label}{_fmt(value, digits)}{unit}")
    return " · ".join(parts) if parts else "—"


def _fwd_text(fwd: dict[str, Any] | None) -> str:
    if fwd is None:
        return "—"
    return (
        f"指数{_fmt(fwd['sh_index_cum_pct'], 2)}%/日均涨停{_fmt(fwd['avg_limit_up'], 0)}家"
        f"/最高{_fmt(fwd['max_boards'], 0)}板/日均双红{_fmt(fwd['avg_double_red_themes'], 1)}个"
    )


_FEATURE_LABELS = {
    "total_amount": "成交额",
    "advancers": "涨家数",
    "limit_up": "涨停数",
    "limit_down": "跌停数",
    "sh_deviation_pct": "偏离度",
    "sh_index_pct_chg": "指数日涨跌",
    "max_boards": "连板高度",
    "double_red_theme_count": "双红题材数",
    "top1_theme_share": "题材集中度",
    "new_high_count": "新高家数",
}


def regime_block_for_llm(
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
) -> str:
    """把市场情绪环境类比渲染成带 [D10] 引用编号的确定性数据块（空串=未取到）。"""
    artifact = load_market_regime_artifact(market_db_path, window=window)
    if not artifact.available:
        return ""
    lines = ["## 市场情绪环境类比块 [D10]"]
    lines.append(
        f"- 口径：把最近 {window} 个交易日的市场情绪向量（成交额/涨家数/涨停/跌停/偏离度/"
        "指数涨跌/连板高度/双红题材数/题材集中度/新高家数，逐特征对全历史 z 标准化）"
        "压成窗口签名，在全历史滑窗中取加权距离最近的窗口，及其后续 5/10/20 日实际走法；"
        "本地 DuckDB 逐日行计算，非 LLM 生成。"
    )
    if artifact.missing_features:
        labels = "、".join(
            _FEATURE_LABELS.get(f, f) for f in artifact.missing_features
        )
        lines.append(
            f"- 数据缺口：{labels} 维缺失（对应表无数据），匹配时已按覆盖率降权，"
            "该缺口不得由其他来源臆补。"
        )
    lines.append("")
    lines.append(
        f"### 当前情绪环境（近 {window} 日均值）：{_summary_text(artifact.current_summary)}"
    )
    lines.append("| 历史相似窗口 | 距离 | 窗口内环境（均值） | 后续5日 | 后续10日 | 后续20日 |")
    lines.append("|" + "---|" * 6)
    for a in artifact.analogs:
        lines.append(
            f"| {a['start_date']}~{a['end_date']} | {a['distance']} | "
            f"{_summary_text(a['raw_summary'])} | "
            f"{_fwd_text(a['forwards'][5])} | {_fwd_text(a['forwards'][10])} | "
            f"{_fwd_text(a['forwards'][20])} |"
        )
    lines.append("")
    lines.append(
        "- 使用要求：历史类比是**小样本历史事实，不是概率预测**。只能表述为"
        "「历史上 X 段相似情绪窗口中，后续 N 日实际为…」，禁止把样本频率说成概率、"
        "禁止在样本外编情景；相似度只基于盘面情绪结构（z 标准化后的相对水平），"
        "不含基本面/政策/外部事件差异，须提示读者自行核对当时背景。"
    )
    return "\n".join(lines)
