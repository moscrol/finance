"""区间：把一段交易日折成六维特征，可回溯、可聚类。

三层能力对应三种问法：

- `river.slice_river`      单点：这一天这个实体，六维分别是什么 → **可回溯到主数据**
- `river_query`            横扫 / 纵扫：一天比全部实体、一批日子比基准
- 本模块                    **区间**：一段日子的六维特征是什么，哪些区间彼此相似

可回溯的含义（和单点一致，不降级）
--------------------------------
每个区间特征都带 `FeatureSpec`：它由哪张表哪一列、按什么规则算出来。所以任何一个
聚类结果都能往下拆到「哪些天 → 哪些行 → 哪张表」，不存在只在向量里存在的数。
`WindowFeatures.provenance` 就是这条链。

为什么不自己写距离和签名
------------------------
`market_regime_analogs` 已经有 `standardize_vectors` / `window_signature` /
`signature_distance`，而且处理缺维的方式是对的——**缺维不伪造、不补零，只从共有维
里算并按覆盖率惩罚**。本模块直接调它们，只把特征向量从「10 维全是盘面」扩到六个维度。
不建第二套距离。

聚类为什么用层次聚类而不是 k-means
----------------------------------
1. 距离是 `signature_distance` 给的，**不是欧氏空间里的点**（缺维会让维数不同），
   k-means 的质心没法定义；
2. 不需要预先指定 k——区间该分几类是读数不是输入；
3. 纯标准库，与 `stats.py` 的「无 scipy」一致。
平均连接 + 距离阈值切断，合并顺序对相同距离按索引升序定，保证可重算。

一个必须先看的现实
------------------
六个维度在历史上不是齐的（`scripts/river_pit_audit.py` 的读数）：资金轨的
`fact_theme_flow_daily` 只有 51 天、舆论从 2026-01 才开始。所以在长区间上，
这两维会被 `_MIN_FEATURE_COVERAGE` 判为缺失而**整维退出签名**——这是设计行为，
不是 bug。`WindowFeatures.dropped_dims` 会如实报出来，别把「维度退出」读成「维度为零」。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from intelligence.services.market_regime_analogs import (
    RegimeSignature,
    signature_distance,
    standardize_vectors,
    window_signature,
)
from intelligence.services.river import DEFAULT_DB, TRACKS, Track
# 双红阈值只许有一处真源（market_feature_store/signals.py）。写死字面量会被
# `test_double_red_single_source` 的棘轮拦下——那道门的意义是：口径改一处就全仓跟着改，
# 而不是让某个新模块悄悄钉死一份自己的定义。
from market_feature_store.signals import DOUBLE_RED_SQL


@dataclass(frozen=True)
class FeatureSpec:
    """一个特征的身份证：属于哪个维度、从哪来、怎么算的。回溯链的第一环。"""

    name: str
    track: Track
    source: str  # 表.列，或表 + 聚合规则
    rule: str
    label: str


# 六个维度都要有代表特征。选取原则：能从库里确定性算出、且是该维度的一等量。
FEATURES: tuple[FeatureSpec, ...] = (
    # 盘面
    FeatureSpec("total_amount", "market", "fact_market_daily.total_amount", "当日原值", "成交额"),
    FeatureSpec("advancers", "market", "fact_market_daily.advancers", "当日原值", "涨家数"),
    FeatureSpec("limit_up", "market", "fact_market_daily.limit_up", "当日原值", "涨停家数"),
    FeatureSpec(
        "sh_deviation_pct", "market", "fact_market_daily.sh_deviation_pct", "当日原值", "偏离度"
    ),
    # 题材
    FeatureSpec(
        "double_red_count",
        "theme",
        "fact_sector_daily",
        f"COUNT({DOUBLE_RED_SQL})：阈值真源是 market_feature_store/signals.py",
        "双红题材数",
    ),
    FeatureSpec(
        "top1_limit_share",
        "theme",
        "fact_theme_limit_heat_daily.market_share",
        "当日 rank=1 的题材涨停份额",
        "首题材份额",
    ),
    # 舆论
    FeatureSpec(
        "report_count_30d",
        "opinion",
        "fact_research_report_catalog.report_date",
        "近 30 日研报条数（滚动）；累计数被回填批次污染，故用滚动窗",
        "近30日研报",
    ),
    # 资金
    FeatureSpec(
        "theme_net_flow",
        "capital",
        "fact_theme_flow_daily.total_fund",
        "当日全题材净流入求和（DECIMAL 精确求和，避免并行浮点飘位）",
        "题材净流入",
    ),
    # 个股
    FeatureSpec(
        "new_high_1y",
        "stock",
        "fact_market_daily.stock_high_count_1y",
        "当日原值",
        "一年新高家数",
    ),
    # 判断
    FeatureSpec(
        "checkpoints_registered",
        "judgment",
        "checkpoints.jsonl",
        "当日登记的可证伪点条数；用户态文件，未提供路径时该维整体缺失",
        "登记判断数",
    ),
)

FEATURE_NAMES: tuple[str, ...] = tuple(f.name for f in FEATURES)
BY_NAME: dict[str, FeatureSpec] = {f.name: f for f in FEATURES}


@dataclass(frozen=True)
class WindowFeatures:
    """一个区间的六维签名 + 回溯链。"""

    start: str
    end: str
    n_days: int
    signature: RegimeSignature
    raw_means: dict[str, float | None]
    coverage: dict[str, float]  # 每维在窗口内的非空占比
    dropped_dims: tuple[str, ...]  # 覆盖率不足、整维退出签名的
    label: str = ""

    @property
    def provenance(self) -> list[dict[str, str]]:
        """签名里每一维的来源。聚类结果能靠它拆回到表和列。"""
        return [
            {
                "feature": name,
                "track": BY_NAME[name].track,
                "source": BY_NAME[name].source,
                "rule": BY_NAME[name].rule,
            }
            for name in sorted(self.signature.stats)
        ]

    @property
    def tracks_present(self) -> set[Track]:
        return {BY_NAME[n].track for n in self.signature.stats}

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "start": self.start,
            "end": self.end,
            "n_days": self.n_days,
            "dims": sorted(self.signature.stats),
            "tracks_present": sorted(self.tracks_present),
            "dropped_dims": list(self.dropped_dims),
            "coverage": {k: round(v, 3) for k, v in sorted(self.coverage.items())},
            "raw_means": {k: (None if v is None else round(v, 3)) for k, v in sorted(self.raw_means.items())},
            "provenance": self.provenance,
        }


# --------------------------------------------------------------------------- #
# 逐日特征向量
# --------------------------------------------------------------------------- #
def build_daily_vectors(
    *,
    db_path: str | Path | None = None,
    checkpoints_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """全历史逐日六维向量。缺数留 None，**不补零、不前向填充**。

    补零会把「这天没数据」变成「这天是 0」，在标准化之后是一个真实的极端值——
    资金轨只有 51 天，补零会造出 360 多天的假极值，聚类必然被它主导。
    """
    import duckdb

    db = Path(db_path or os.environ.get("MARKET_FEATURE_STORE_DB", DEFAULT_DB)).expanduser()
    if not db.exists():
        raise FileNotFoundError(f"数据库不存在：{db}（不自动创建）")

    con = duckdb.connect(str(db), read_only=True)
    try:
        base = con.execute(
            """
            SELECT CAST(trade_date AS DATE) AS d, total_amount, advancers, limit_up,
                   sh_deviation_pct, stock_high_count_1y
            FROM fact_market_daily ORDER BY trade_date
            """
        ).fetchall()
        double_red = dict(
            con.execute(
                f"""
                SELECT CAST(trade_date AS DATE),
                       COUNT(*) FILTER (WHERE {DOUBLE_RED_SQL})
                FROM fact_sector_daily GROUP BY 1
                """  # noqa: S608 - 谓词来自本仓常量，不接受外部输入
            ).fetchall()
        )
        top1 = dict(
            con.execute(
                """
                SELECT CAST(trade_date AS DATE), MAX(market_share)
                FROM fact_theme_limit_heat_daily WHERE rank = 1 GROUP BY 1
                """
            ).fetchall()
        )
        flow = {
            d: (None if v is None else float(v))
            for d, v in con.execute(
                """
                SELECT CAST(trade_date AS DATE), SUM(CAST(total_fund AS DECIMAL(18,4)))
                FROM fact_theme_flow_daily GROUP BY 1
                """
            ).fetchall()
        }
        reports = con.execute(
            "SELECT report_date, sector_tags, concept_tags FROM fact_research_report_catalog"
        ).fetchall()
    finally:
        con.close()

    report_days = sorted(r[0] for r in reports)
    checkpoints = _checkpoint_counts(checkpoints_path)

    rows: list[dict[str, Any]] = []
    for d, amount, adv, lu, dev, nh in base:
        rows.append(
            {
                "trade_date": str(d),
                "total_amount": amount,
                "advancers": adv,
                "limit_up": lu,
                "sh_deviation_pct": dev,
                "new_high_1y": nh,
                "double_red_count": double_red.get(d),
                "top1_limit_share": top1.get(d),
                "theme_net_flow": flow.get(d),
                "report_count_30d": _rolling_count(report_days, d, 30),
                "checkpoints_registered": checkpoints.get(str(d)) if checkpoints is not None else None,
            }
        )
    return rows


def _rolling_count(sorted_days: list[date], as_of: date, window: int) -> int | None:
    """近 ``window`` 日研报条数。as_of 早于全部研报时返回 None（没有数据 ≠ 零）。"""
    if not sorted_days or as_of < sorted_days[0]:
        return None
    return sum(1 for d in sorted_days if 0 <= (as_of - d).days < window)


def _checkpoint_counts(path: str | Path | None) -> dict[str, int] | None:
    """判断轨：逐日登记条数。未提供路径时返回 None → 该维整维缺失，不猜成 0。"""
    if path is None:
        return None
    p = Path(path)
    if not p.exists():
        return None
    counts: dict[str, int] = {}
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            day = str(rec.get("ts", ""))[:10]
            if day:
                counts[day] = counts.get(day, 0) + 1
    return counts


# --------------------------------------------------------------------------- #
# 区间特征
# --------------------------------------------------------------------------- #
def window_features(
    daily: list[dict[str, Any]],
    start: str,
    end: str,
    *,
    label: str = "",
    z_rows: list[dict[str, float | None]] | None = None,
) -> WindowFeatures | None:
    """把 ``[start, end]`` 折成一个可回溯的六维签名。区间内无交易日时返回 None。

    ``z_rows`` 由调用方传入以保证**所有窗口共用同一套标准化基准**——各窗口各自
    标准化会让距离失去可比性（每个窗口的 z 都以自己为中心）。
    """
    if z_rows is None:
        z_rows, _ = standardize_vectors(daily, FEATURE_NAMES)
    idx = [i for i, row in enumerate(daily) if start <= row["trade_date"] <= end]
    if not idx:
        return None
    sub_raw = [daily[i] for i in idx]
    sub_z = [z_rows[i] for i in idx]

    sig = window_signature(sub_z, FEATURE_NAMES)
    coverage = {
        name: sum(1 for r in sub_raw if r.get(name) is not None) / len(sub_raw)
        for name in FEATURE_NAMES
    }
    raw_means: dict[str, float | None] = {}
    for name in FEATURE_NAMES:
        vals = [float(r[name]) for r in sub_raw if r.get(name) is not None]
        raw_means[name] = (sum(vals) / len(vals)) if vals else None
    dropped = tuple(sorted(set(FEATURE_NAMES) - set(sig.stats)))
    return WindowFeatures(
        start=sub_raw[0]["trade_date"],
        end=sub_raw[-1]["trade_date"],
        n_days=len(sub_raw),
        signature=sig,
        raw_means=raw_means,
        coverage=coverage,
        dropped_dims=dropped,
        label=label or f"{start}~{end}",
    )


def windows_around(
    daily: list[dict[str, Any]],
    anchors: list[str],
    *,
    before: int = 0,
    after: int = 9,
    z_rows: list[dict[str, float | None]] | None = None,
) -> list[WindowFeatures]:
    """以一批锚点日（如 MA5 谷底确认日）为起点，各取一个交易日窗口。

    ``before``/``after`` 按**交易日**数而不是自然日——跨节假日时自然日会取到不同长度
    的窗口，让距离比较变成在比窗口长度。
    """
    if z_rows is None:
        z_rows, _ = standardize_vectors(daily, FEATURE_NAMES)
    pos = {row["trade_date"]: i for i, row in enumerate(daily)}
    out: list[WindowFeatures] = []
    for anchor in sorted(set(anchors)):
        i = pos.get(anchor)
        if i is None:
            continue
        lo, hi = max(0, i - before), min(len(daily) - 1, i + after)
        wf = window_features(
            daily, daily[lo]["trade_date"], daily[hi]["trade_date"], label=anchor, z_rows=z_rows
        )
        if wf is not None:
            out.append(wf)
    return out


# --------------------------------------------------------------------------- #
# 聚类
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Cluster:
    members: list[WindowFeatures]
    dropped: bool = False  # 与任何窗口都无共有维 → 无法比较，不塞进任何簇

    @property
    def size(self) -> int:
        return len(self.members)

    def to_dict(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "labels": [m.label for m in self.members],
            "tracks_present": sorted(set().union(*(m.tracks_present for m in self.members))) if self.members else [],
            "raw_means": _cluster_means(self.members),
        }


def _cluster_means(members: list[WindowFeatures]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for name in FEATURE_NAMES:
        vals = [m.raw_means[name] for m in members if m.raw_means.get(name) is not None]
        out[name] = round(sum(vals) / len(vals), 3) if vals else None  # type: ignore[arg-type]
    return out


def distance_matrix(windows: list[WindowFeatures]) -> list[list[float | None]]:
    """两两距离。``None`` 表示无共有维——不可比，不是「距离很远」。"""
    total = len(FEATURE_NAMES)
    n = len(windows)
    m: list[list[float | None]] = [[None] * n for _ in range(n)]
    for i in range(n):
        m[i][i] = 0.0
        for j in range(i + 1, n):
            d = signature_distance(windows[i].signature, windows[j].signature, total)
            m[i][j] = m[j][i] = d
    return m


def cluster_windows(
    windows: list[WindowFeatures], *, threshold: float = 1.0
) -> tuple[list[Cluster], list[WindowFeatures]]:
    """平均连接层次聚类，距离超过 ``threshold`` 就不再合并。

    返回 ``(簇, 无法比较的窗口)``。后者是与所有窗口都没有共有维的——**它们不是
    一个「其他」簇**，是压根没进比较，如实单列。

    合并顺序在距离相同时按 (i, j) 升序，保证同样输入得到同样结果。
    """
    n = len(windows)
    if n == 0:
        return [], []
    dm = distance_matrix(windows)
    comparable = [i for i in range(n) if any(dm[i][j] is not None for j in range(n) if j != i)]
    orphan = [windows[i] for i in range(n) if i not in comparable]

    groups: list[list[int]] = [[i] for i in comparable]
    while len(groups) > 1:
        best: tuple[float, int, int] | None = None
        for a in range(len(groups)):
            for b in range(a + 1, len(groups)):
                pairs = [
                    dm[i][j] for i in groups[a] for j in groups[b] if dm[i][j] is not None
                ]
                if not pairs:
                    continue
                avg = sum(pairs) / len(pairs)
                if best is None or avg < best[0]:
                    best = (avg, a, b)
        if best is None or best[0] > threshold:
            break
        _, a, b = best
        groups[a] = sorted(groups[a] + groups[b])
        groups.pop(b)

    clusters = [Cluster(members=[windows[i] for i in sorted(g)]) for g in groups]
    clusters.sort(key=lambda c: (-c.size, c.members[0].label))
    return clusters, orphan


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def render(clusters: list[Cluster], orphan: list[WindowFeatures], windows: list[WindowFeatures]) -> str:
    out: list[str] = []
    if windows:
        w = windows[0]
        present = sorted(w.tracks_present)
        out.append(
            f"窗口 {len(windows)} 个，各 {w.n_days} 个交易日；"
            f"进入签名的维度 {len(w.signature.stats)}/{len(FEATURE_NAMES)}"
        )
        out.append(f"  覆盖到的轨：{'、'.join(present)}（共 {len(TRACKS)} 条）")
        if w.dropped_dims:
            out.append(f"  ⚠ 退出签名的维度（窗口内覆盖率不足，不是取值为零）：{'、'.join(w.dropped_dims)}")
        out.append("")
    for i, c in enumerate(clusters, 1):
        means = _cluster_means(c.members)
        desc = "  ".join(
            f"{BY_NAME[k].label}={v:.0f}" for k, v in means.items() if v is not None and k in ("total_amount", "limit_up", "double_red_count", "new_high_1y")
        )
        out.append(f"簇 {i}（{c.size} 个窗口）  {desc}")
        out.append(f"    {'、'.join(m.label for m in c.members)}")
    if orphan:
        out.append("")
        out.append(f"无法比较（与所有窗口都无共有维）：{'、'.join(m.label for m in orphan)}")
    return "\n".join(out)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="时间长河：区间六维特征与聚类")
    ap.add_argument("anchors", nargs="+", help="锚点日列表，或 @文件（每行一个日期）")
    ap.add_argument("--before", type=int, default=0, help="锚点前几个交易日")
    ap.add_argument("--after", type=int, default=9, help="锚点后几个交易日")
    ap.add_argument("--threshold", type=float, default=1.0, help="层次聚类的距离切断阈值")
    ap.add_argument("--checkpoints", default=None, help="判断轨 checkpoints.jsonl 路径")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    anchors: list[str] = []
    for token in args.anchors:
        if token.startswith("@"):
            anchors.extend(
                line.strip()
                for line in Path(token[1:]).read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        else:
            anchors.append(token)

    daily = build_daily_vectors(checkpoints_path=args.checkpoints)
    z_rows, dropped_global = standardize_vectors(daily, FEATURE_NAMES)
    windows = windows_around(daily, anchors, before=args.before, after=args.after, z_rows=z_rows)
    clusters, orphan = cluster_windows(windows, threshold=args.threshold)
    if args.json:
        print(
            json.dumps(
                {
                    "globally_dropped_features": dropped_global,
                    "windows": [w.to_dict() for w in windows],
                    "clusters": [c.to_dict() for c in clusters],
                    "uncomparable": [w.label for w in orphan],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        if dropped_global:
            print(f"⚠ 全历史上就无信息、已整维剔除：{'、'.join(dropped_global)}\n")
        print(render(clusters, orphan, windows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
