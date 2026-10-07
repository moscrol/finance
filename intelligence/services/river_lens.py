"""多维对照镜头:把**空间**交给 agent,而不是把**排名**交给 agent。

为什么要有这个模块
------------------
``market_regime_analogs.regime_block_for_llm`` 递给 LLM 的是一张成品表:

    432 天 × 10 维
      → z 标准化 → 每窗每维 2 个数
      → 加权 L1（各维等权、_DELTA_WEIGHT 写死）
      → **塌成 1 个标量距离**
      → 排序取 top K
      → 每行只渲染 5 维的【窗口均值】，拼成一个字符串

于是 agent 拿到的是「已经做完的答案」。它**看不到**多维(只看到 5 个均值)、
**没法自己总结**(总结在它之前就用固定权重做完了)、**不能决定「类似」是什么意思**。

本模块不换算法、不换距离、不换权重 —— 那些都复用
``market_regime_analogs``(``standardize_vectors`` / ``window_signature`` /
``signature_distance``)。**它只负责把被压扁的那些东西重新摊开给 agent 看。**

三件被摊开的事
--------------
1. **维度结构**(``dimension_groups``)——提示历史上相关、可能冗余的维度。
   多维同时吻合不自动构成多份独立证据；相关分组也不证明组内等价或组间独立。

2. **距离的分解**(``decompose``)——不报一个标量,报**逐维的 Δz**,
   并分成「对齐的」和「分歧的」。agent 由此能说「在资金上像、在情绪上不像」。

3. **距离地形**(``landscape``)——top-K 之外候选的距离分布。
   显示最近窗口相对其他候选是否突出；绝对相似性仍须检查实际距离和逐维差异。

纪律
----
- **只读。**不建表、不写库。
- **不建第二套距离。**本模块算出的总距离与 ``signature_distance`` 逐位一致
  (有测试钉死),分解只是把同一个和式拆开。
- **PIT 透传。**本模块不自己取数,``daily`` 由调用方给;
  配套的 ``lens_from_db`` 强制 ``knowledge_cutoff``(沿用 ``river_window`` 的纪律)。
- **缺维不伪造。**沿用上游:只在共有维上比,按覆盖率惩罚;缺的维如实报。
- **特征集是参数。**默认用 ``river_window.FEATURES``(六轨),
  但接任何一组特征名都行 —— 教学标签接进来之后,**同一个工具直接量新的维度**。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Sequence

from intelligence.services.market_regime_analogs import (
    _DELTA_WEIGHT,
    RegimeSignature,
    signature_distance,
    standardize_vectors,
    window_signature,
)

#: 平均相关距离的聚类阈值，提示潜在冗余，不证明两维含义相同。
#: 可调；分组只是启发式摘要，不是统计独立维数估计。
DEFAULT_REDUNDANCY_R = 0.7

#: 均值差 + 加权趋势差不超过此值的维视为「对齐」（沿用原距离贡献）。
ALIGNED_DELTA = 0.5
#: 同一距离贡献不低于此值的维视为「分歧」——必须点名,防刻舟求剑。
DIVERGENT_DELTA = 1.5

#: 算相关至少要这么多对共同有值的观测,否则判为「证据不足」而不是「不相关」。
MIN_PAIRS_FOR_R = 30


# --------------------------------------------------------------------------- #
# 1. 维度结构:相关性与潜在冗余
# --------------------------------------------------------------------------- #
def pearson(
    rows: Sequence[dict[str, float | None]], a: str, b: str
) -> tuple[float | None, int]:
    """两维在历史上的皮尔逊相关。返回 (r, 共同有值的观测数)。

    成对完整:只用两边都非空的行。**不补零、不插值** —— 补出来的相关是假的。
    观测数不足或任一边为常量时返回 ``(None, n)``:那是**证据不足**,
    不能当成「不相关」,否则会把一对真冗余维放进不同的组。
    """

    pairs = [
        (float(r[a]), float(r[b]))
        for r in rows
        if r.get(a) is not None and r.get(b) is not None
    ]
    n = len(pairs)
    if n < MIN_PAIRS_FOR_R:
        return None, n
    ma = sum(p[0] for p in pairs) / n
    mb = sum(p[1] for p in pairs) / n
    va = sum((p[0] - ma) ** 2 for p in pairs)
    vb = sum((p[1] - mb) ** 2 for p in pairs)
    if va <= 0 or vb <= 0:
        return None, n
    cov = sum((p[0] - ma) * (p[1] - mb) for p in pairs)
    return cov / (va ** 0.5 * vb ** 0.5), n


@dataclass(frozen=True)
class DimensionGroup:
    """按平均相关距离合并的一组维；提示潜在冗余，不证明组内等价/组间独立。"""

    members: tuple[str, ...]
    max_abs_r: float | None  # 组内最强的那对相关（单成员组为 None）

    @property
    def size(self) -> int:
        return len(self.members)


@dataclass(frozen=True)
class DimensionStructure:
    groups: tuple[DimensionGroup, ...]
    pairs: tuple[tuple[str, str, float | None, int], ...]  # (a, b, r, n)
    undetermined: tuple[tuple[str, str, int], ...]  # 证据不足的对
    features: tuple[str, ...]

    @property
    def nominal_dims(self) -> int:
        return len(self.features)

    @property
    def effective_dims(self) -> int:
        """兼容名称，实际只计相关组数，不是统计意义的有效/独立维数。"""
        return len(self.groups)

    def group_of(self, feature: str) -> int | None:
        for i, g in enumerate(self.groups):
            if feature in g.members:
                return i
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "nominal_dims": self.nominal_dims,
            "effective_dims": self.effective_dims,
            "groups": [
                {"members": list(g.members), "max_abs_r": g.max_abs_r} for g in self.groups
            ],
            "undetermined_pairs": [
                {"a": a, "b": b, "n_pairs": n} for a, b, n in self.undetermined
            ],
            "note": (
                "相关分组提示潜在冗余，不表示组内每对特征都等价。"
                "读『几个维度都像』之前先看这张表。"
                "undetermined 是共同观测不足，按『证据不足』处理——"
                "未并组不等于已证明独立。组数只是相关阈值下的启发式摘要，不是统计独立维数。"
            ),
        }


def dimension_groups(
    z_rows: Sequence[dict[str, float | None]],
    features: Sequence[str],
    *,
    threshold: float = DEFAULT_REDUNDANCY_R,
) -> DimensionStructure:
    """把特征按历史相关性并组。**本模块最重要的输出。**

    用平均连接层次聚类(与 ``river_window.cluster_windows`` 同款),
    距离取 ``1 - |r|``,在 ``1 - threshold`` 处切断。合并顺序对相同距离
    按索引升序定,保证可重算。

    证据不足的对(共同观测 < ``MIN_PAIRS_FOR_R``)距离按 **1.0**(最远)处理 ——
    宁可少并组；未并组也必须保留证据不足提示，不能据此推断独立。
    """

    feats = tuple(features)
    pairs: list[tuple[str, str, float | None, int]] = []
    undetermined: list[tuple[str, str, int]] = []
    dist: dict[tuple[int, int], float] = {}
    for i in range(len(feats)):
        for j in range(i + 1, len(feats)):
            r, n = pearson(z_rows, feats[i], feats[j])
            pairs.append((feats[i], feats[j], r, n))
            if r is None:
                undetermined.append((feats[i], feats[j], n))
                dist[(i, j)] = 1.0
            else:
                dist[(i, j)] = 1.0 - abs(r)

    def d(i: int, j: int) -> float:
        return dist[(i, j)] if i < j else dist[(j, i)]

    clusters: list[list[int]] = [[i] for i in range(len(feats))]
    cut = 1.0 - threshold
    while len(clusters) > 1:
        best: tuple[float, int, int] | None = None
        for x in range(len(clusters)):
            for y in range(x + 1, len(clusters)):
                avg = sum(d(p, q) for p in clusters[x] for q in clusters[y]) / (
                    len(clusters[x]) * len(clusters[y])
                )
                if best is None or avg < best[0] - 1e-12:
                    best = (avg, x, y)
        if best is None or best[0] > cut:
            break
        _, x, y = best
        clusters[x] = sorted(clusters[x] + clusters[y])
        clusters.pop(y)

    groups: list[DimensionGroup] = []
    for members in sorted(clusters, key=lambda c: (-len(c), c[0])):
        names = tuple(feats[i] for i in members)
        rs = [
            abs(r)
            for a, b, r, _ in pairs
            if r is not None and a in names and b in names
        ]
        groups.append(DimensionGroup(names, max(rs) if rs else None))
    return DimensionStructure(tuple(groups), tuple(pairs), tuple(undetermined), feats)


# --------------------------------------------------------------------------- #
# 2. 距离的分解:像在哪、不像在哪
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DimDelta:
    feature: str
    group: int | None
    z_mean_a: float
    z_mean_b: float
    z_delta_a: float
    z_delta_b: float

    @property
    def d_mean(self) -> float:
        return self.z_mean_a - self.z_mean_b

    @property
    def d_trend(self) -> float:
        return self.z_delta_a - self.z_delta_b

    @property
    def contribution(self) -> float:
        """这一维对总距离和式的贡献,口径与 ``signature_distance`` 逐字一致。"""
        return abs(self.d_mean) + _DELTA_WEIGHT * abs(self.d_trend)

    @property
    def verdict(self) -> str:
        # 与距离用同一份均值 + 加权趋势贡献，不能把反向走势报成「对齐」。
        m = self.contribution
        if m <= ALIGNED_DELTA:
            return "对齐"
        if m >= DIVERGENT_DELTA:
            return "分歧"
        return "中间"


@dataclass(frozen=True)
class Decomposition:
    """一对窗口的逐维分解。``total`` 与 ``signature_distance`` 相等(有测试钉死)。"""

    total: float | None
    dims: tuple[DimDelta, ...]
    shared: tuple[str, ...]
    only_a: tuple[str, ...]
    only_b: tuple[str, ...]
    total_dims: int
    structure: DimensionStructure | None = None

    @property
    def aligned(self) -> tuple[DimDelta, ...]:
        return tuple(d for d in self.dims if d.verdict == "对齐")

    @property
    def divergent(self) -> tuple[DimDelta, ...]:
        return tuple(sorted(
            (d for d in self.dims if d.verdict == "分歧"),
            key=lambda d: -d.contribution,
        ))

    @property
    def aligned_groups(self) -> tuple[int, ...]:
        """对齐维落入的相关组；不等于独立证据的个数。"""
        return tuple(sorted({d.group for d in self.aligned if d.group is not None}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_distance": self.total,
            "total_dims": self.total_dims,
            "shared_dims": list(self.shared),
            "only_in_current": list(self.only_a),
            "only_in_candidate": list(self.only_b),
            "aligned_dims": [d.feature for d in self.aligned],
            "aligned_correlation_groups": len(self.aligned_groups),
            "divergent_dims": [
                {
                    "feature": d.feature,
                    "d_mean": round(d.d_mean, 3),
                    "d_trend": round(d.d_trend, 3),
                    "group": d.group,
                }
                for d in self.divergent
            ],
            "per_dim": [
                {
                    "feature": d.feature,
                    "group": d.group,
                    "z_current": round(d.z_mean_a, 3),
                    "z_candidate": round(d.z_mean_b, 3),
                    "d_mean": round(d.d_mean, 3),
                    "d_trend": round(d.d_trend, 3),
                    "contribution": round(d.contribution, 3),
                    "verdict": d.verdict,
                }
                for d in sorted(self.dims, key=lambda x: -x.contribution)
            ],
        }


def decompose(
    a: RegimeSignature,
    b: RegimeSignature,
    total_dims: int,
    *,
    structure: DimensionStructure | None = None,
) -> Decomposition:
    """把 ``signature_distance(a, b)`` 拆成逐维贡献。**不改口径,只拆和式。**"""

    shared = tuple(f for f in a.stats if f in b.stats)
    dims = tuple(
        DimDelta(
            feature=f,
            group=structure.group_of(f) if structure else None,
            z_mean_a=a.stats[f][0],
            z_mean_b=b.stats[f][0],
            z_delta_a=a.stats[f][1],
            z_delta_b=b.stats[f][1],
        )
        for f in shared
    )
    return Decomposition(
        total=signature_distance(a, b, total_dims),
        dims=dims,
        shared=shared,
        only_a=tuple(f for f in a.stats if f not in b.stats),
        only_b=tuple(f for f in b.stats if f not in a.stats),
        total_dims=total_dims,
        structure=structure,
    )


# --------------------------------------------------------------------------- #
# 3. 距离地形:top-K 之外长什么样
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Landscape:
    """候选距离的分布。

    **为什么不用「最近者的百分位」**:最近者按定义就是第 1 名,它的百分位恒等于 0,
    无论全历史是真有一个极像的窗口,还是两百个窗口一样不像。那个数没有信息量。

    要回答的是**「它比近端群体低多少个身位」**:
    ``standout = (p5 - nearest) / (p50 - p5)``。
    分母是「从近端到中位」的自然尺度,所以这个比值不随量纲变。
    """

    n: int
    quantiles: dict[str, float]
    nearest: float | None
    standout: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": self.n,
            "quantiles": {k: round(v, 3) for k, v in self.quantiles.items()},
            "nearest": None if self.nearest is None else round(self.nearest, 3),
            "standout": self.standout,
            "standout_definition": "(p5 - nearest) / (p50 - p5)；越大表示最近者越鹤立鸡群",
            "reading": self.reading,
        }

    @property
    def reading(self) -> str:
        """只解读候选中的相对排名，绝对相似性须另看逐维距离。"""
        if self.nearest is None:
            return "无候选窗口。"
        if self.standout is None:
            return (
                f"有 {self.n} 个候选，最近距离 {self.nearest:.2f}，但 p50−p5 为零，"
                "无法区分相对突出程度；不能据此断言没有相似窗口。"
            )
        s = self.standout
        if s >= 1.0:
            return (
                f"最近候选距离 {self.nearest:.2f}，比近端群体(p5={self.quantiles['p5']:.2f})"
                f"还低 {s:.1f} 个「近端→中位」身位——排名相对突出，但不证明绝对相似。"
            )
        if s >= 0.2:
            return (
                f"最近候选领先近端群体 {s:.1f} 个身位；这只描述相对排名，不证明绝对相似，"
                "应一并检查其他候选的逐维差异。"
            )
        return (
            f"最近候选只领先近端群体 {s:.2f} 个身位——**候选排名不突出**。"
            "这不能判断绝对相似：可能多个窗口都很像，也可能都不像。"
            "须检查实际距离和逐维差异，不能仅凭排名声称找到了对标。"
        )


def landscape(distances: Iterable[float | None]) -> Landscape:
    vals = sorted(d for d in distances if d is not None)
    if not vals:
        return Landscape(0, {}, None, None)

    def q(p: float) -> float:
        if len(vals) == 1:
            return vals[0]
        i = p * (len(vals) - 1)
        lo, hi = int(i), min(int(i) + 1, len(vals) - 1)
        return vals[lo] + (vals[hi] - vals[lo]) * (i - lo)

    nearest = vals[0]
    qs = {"p1": q(0.01), "p5": q(0.05), "p25": q(0.25), "p50": q(0.50), "p90": q(0.90)}
    spread = qs["p50"] - qs["p5"]
    standout = None if spread <= 0 else round((qs["p5"] - nearest) / spread, 3)
    return Landscape(n=len(vals), quantiles=qs, nearest=nearest, standout=standout)


# --------------------------------------------------------------------------- #
# 4. 装配:给 agent 的那一块
# --------------------------------------------------------------------------- #
@dataclass
class LensResult:
    structure: DimensionStructure
    current: RegimeSignature
    candidates: list[tuple[str, RegimeSignature, Decomposition]] = field(default_factory=list)
    landscape_: Landscape | None = None
    knowledge_cutoff: str | None = None
    dropped: tuple[str, ...] = ()
    labels: dict[str, str] = field(default_factory=dict)
    current_window: tuple[str, str] | None = None
    standardization_window: tuple[str, str] | None = None
    upstream_pit_counts: dict[str, int] = field(default_factory=dict)
    feature_sources: dict[str, str] = field(default_factory=dict)
    excluded_features: dict[str, str] = field(default_factory=dict)
    current_missing_features: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_cutoff": self.knowledge_cutoff,
            "current_window": self.current_window,
            "standardization_window": self.standardization_window,
            "upstream_pit_counts": dict(self.upstream_pit_counts),
            "feature_sources": dict(self.feature_sources),
            "excluded_features": dict(self.excluded_features),
            "current_missing_features": list(self.current_missing_features),
            "dimension_structure": self.structure.to_dict(),
            "dropped_features": list(self.dropped),
            "current_window_z": {
                f: {"z_mean": round(m, 3), "z_trend": round(t, 3)}
                for f, (m, t) in self.current.stats.items()
            },
            "landscape": self.landscape_.to_dict() if self.landscape_ else None,
            "candidates": [
                {"label": label, **dec.to_dict()} for label, _, dec in self.candidates
            ],
        }


def build_lens(
    daily: Sequence[dict[str, Any]],
    features: Sequence[str],
    *,
    current: tuple[str, str],
    candidates: Sequence[tuple[str, str, str]],
    knowledge_cutoff: str | None = None,
    threshold: float = DEFAULT_REDUNDANCY_R,
    labels: dict[str, str] | None = None,
    top: int = 5,
) -> LensResult:
    """``daily`` 是逐日向量(由调用方按 PIT 取好)。``candidates`` 是 (label, start, end)。

    **不自己取数** —— 取数带 PIT 责任,留在调用方(``river_window.build_daily_vectors``
    强制 ``knowledge_cutoff``)。本模块只做摊开。
    """

    z_rows, dropped = standardize_vectors(list(daily), tuple(features))
    live = tuple(f for f in features if f not in dropped)
    structure = dimension_groups(z_rows, live, threshold=threshold)

    def sig_of(start: str, end: str) -> RegimeSignature | None:
        idx = [i for i, r in enumerate(daily) if start <= r["trade_date"] <= end]
        if not idx:
            return None
        return window_signature([z_rows[i] for i in idx], live)

    cur = sig_of(*current)
    if cur is None:
        raise ValueError(f"当前窗口 {current} 内没有交易日")

    scored: list[tuple[float, str, RegimeSignature, Decomposition]] = []
    all_d: list[float | None] = []
    for label, s, e in candidates:
        sig = sig_of(s, e)
        if sig is None:
            continue
        dec = decompose(cur, sig, len(live), structure=structure)
        all_d.append(dec.total)
        if dec.total is not None:
            scored.append((dec.total, label, sig, dec))
    scored.sort(key=lambda x: (x[0], x[1]))

    pit_counts: dict[str, int] = {}
    for row in daily:
        grade = row.get("pit_grade")
        key = grade if grade in {"strict", "trade_date_only"} else "unknown"
        pit_counts[key] = pit_counts.get(key, 0) + 1
    days = [row["trade_date"] for row in daily]
    return LensResult(
        current_window=current,
        standardization_window=(min(days), max(days)),
        upstream_pit_counts=pit_counts,
        current_missing_features=tuple(f for f in live if f not in cur.stats),
        structure=structure,
        current=cur,
        candidates=[(lab, sg, dc) for _, lab, sg, dc in scored[:top]],
        landscape_=landscape(all_d),
        knowledge_cutoff=knowledge_cutoff,
        dropped=tuple(dropped),
        labels=labels or {},
    )


def lens_block(res: LensResult, *, name: str = "LENS") -> str:
    """渲染成递给 agent 的文本块。**给空间,不给排名。**"""

    L = res.labels
    def nm(f: str) -> str:
        return L.get(f, f)

    out: list[str] = [f"## 多维对照镜头 [{name}]"]
    out.append(
        "- 口径：逐特征对声明范围内的输入历史做 z 标准化后压成窗口签名（每维：z 均值 + z 首尾段变化），"
        "共有维加权 L1、按覆盖率惩罚。距离口径与 [D10] 同源，未改权重。"
    )
    if res.knowledge_cutoff:
        out.append(f"- 交易日截断：knowledge_cutoff={res.knowledge_cutoff}；日期截断不等于已证明当时可知。")
    if res.current_window:
        out.append(f"- 当前窗口：{res.current_window[0]}~{res.current_window[1]}。")
    if res.standardization_window:
        out.append(
            f"- 标准化拟合范围：{res.standardization_window[0]}~{res.standardization_window[1]}"
            "（含当前窗；这是截至站立日的横向比较，不是训练/留出验证）。"
        )
    counts = "、".join(f"{k}={v}" for k, v in sorted(res.upstream_pit_counts.items())) or "unknown"
    out.append(
        f"- 上游 PIT 日行标记：{counts}。判据相对本次 knowledge_cutoff，"
        "不等于每个历史交易日收盘时已知。仅保留取数层读数，未核验完整历史版本；"
        "trade_date_only / unknown 不得当作当时已知。即便标 strict，也不自动证明"
        "全部特征的发布时间与修订历史；本镜头不授予历史回放、方法校准或剧本命名资格。"
    )
    if res.dropped:
        out.append(
            f"- 整体缺失/常量维（已退出比较，不得臆补）：{'、'.join(nm(f) for f in res.dropped)}"
        )
    if res.current_missing_features:
        out.append("- 当前窗覆盖不足的维度：" + "、".join(nm(f) for f in res.current_missing_features))
    for feature, reason in sorted(res.excluded_features.items()):
        out.append(f"- 暂停比较 {feature}：{reason}")
    if res.feature_sources:
        out.extend(["", "### 特征来源（不是完整行级版本凭据）", "| 特征 | 来源与聚合口径 |", "|---|---|"])
        for feature, source in res.feature_sources.items():
            out.append(f"| {nm(feature)} ({feature}) | {source} |")

    st = res.structure
    out.append("")
    out.append(f"### ① 维度结构：名义 {st.nominal_dims} 维，实际 **{st.effective_dims}** 组")
    out.append(
        "> 分组提示历史相关性与潜在冗余，不证明组内等价或组间独立。"
        "读下面的「对齐维」之前先看相关性证据，不把多个维度默认当作独立证据。"
    )
    out.append("")
    out.append("| 组 | 成员 | 组内最高 \\|r\\| |")
    out.append("|---|---|---|")
    for i, g in enumerate(st.groups):
        r = "—" if g.max_abs_r is None else f"{g.max_abs_r:.2f}"
        out.append(f"| G{i} | {'、'.join(nm(m) for m in g.members)} | {r} |")
    if st.undetermined:
        pairs = "、".join(f"{nm(a)}×{nm(b)}(n={n})" for a, b, n in st.undetermined[:6])
        out.append("")
        out.append(
            f"- ⚠ 证据不足未能判断是否冗余的维对：{pairs}。"
            "**未并组 ≠ 已证明独立**，这些维的吻合不能当成独立证据。"
        )

    out.append("")
    out.append("### ② 当前窗口在各维上的位置（z = 相对声明拟合范围的位置）")
    out.append("| 维度 | 组 | z均值 | 窗口内趋势 |")
    out.append("|---|---|---|---|")
    for f, (m, t) in sorted(res.current.stats.items(), key=lambda kv: -abs(kv[1][0])):
        g = st.group_of(f)
        arrow = "↑" if t > 0.3 else ("↓" if t < -0.3 else "→")
        out.append(f"| {nm(f)} | G{g} | {m:+.2f} | {arrow} {t:+.2f} |")

    if res.landscape_:
        out.append("")
        out.append("### ③ 距离地形（top-K 之外长什么样）")
        ls = res.landscape_
        if ls.n:
            qs = ls.quantiles
            out.append(
                f"- 全部 {ls.n} 个候选窗口的距离分布："
                f"p1={qs['p1']:.2f} · p5={qs['p5']:.2f} · 中位={qs['p50']:.2f} · p90={qs['p90']:.2f}"
            )
            out.append(f"- **{ls.reading}**")

    out.append("")
    out.append("### ④ 候选窗口：像在哪、不像在哪")
    out.append("| 窗口 | 距离 | 对齐维 | **对齐相关组数** | 分歧维（均值/趋势 Δz） |")
    out.append("|---|---|---|---|---|")
    for label, _, dec in res.candidates:
        al = "、".join(nm(d.feature) for d in dec.aligned) or "—"
        dv = (
            "、".join(f"{nm(d.feature)} Δ均值{d.d_mean:+.1f}/趋势{d.d_trend:+.1f}" for d in dec.divergent[:3])
            or "—"
        )
        total = "—" if dec.total is None else f"{dec.total:.2f}"
        out.append(f"| {label} | {total} | {al} | **{len(dec.aligned_groups)}** | {dv} |")

    # 汇总表不能代替逐维读数：没有过阈值的中间维、缺维和覆盖分母同样要送达。
    for label, _, dec in res.candidates:
        out.extend(["", f"#### {label} · 逐维贡献"])
        out.append(
            f"- 共有维覆盖：{len(dec.shared)}/{dec.total_dims}；"
            f"候选缺维：{'、'.join(nm(f) for f in dec.only_a) or '无'}；"
            f"当前缺维：{'、'.join(nm(f) for f in dec.only_b) or '无'}。"
        )
        out.append("| 维度 | 当前z均值 | 候选z均值 | 当前趋势 | 候选趋势 | 距离和式贡献 | 判读 |")
        out.append("|---|---|---|---|---|---|---|")
        for d in sorted(dec.dims, key=lambda item: -item.contribution):
            out.append(
                f"| {nm(d.feature)} | {d.z_mean_a:+.2f} | {d.z_mean_b:+.2f} | "
                f"{d.z_delta_a:+.2f} | {d.z_delta_b:+.2f} | {d.contribution:.2f} | {d.verdict} |"
            )
    out.append(
        "- 候选之间可能重叠，数量不是独立复现次数。逐维贡献为均值差绝对值 + "
        f"{_DELTA_WEIGHT}×趋势差绝对值；总距离还含共有维数与覆盖率惩罚，显示数值已四舍五入。"
    )

    out.append("")
    out.append(
        "- **「对齐相关组数」只描述对齐维落在几个不同的相关组里**。"
        "同组可能存在冗余，但未并组不等于独立；不能仅凭组数断言哪个候选证据更强。"
        "对齐/分歧同时考虑均值与加权趋势，距离口径未变。"
    )
    out.append(
        "- **分歧维必须读出来**：相似窗口不是相同窗口。"
        "在分歧维上的差别,正是「这次为什么可能不一样」的位置。"
    )
    out.append(
        "- 使用要求：这些是**小样本历史事实,不是概率预测**。"
        "禁止把样本频率说成概率;相似度只基于上述维度,不含基本面/政策/外部事件差异。"
    )
    return "\n".join(out)


def lens_payload(res: LensResult) -> str:
    """同一份读数的 JSON 形态 —— 给需要结构化消费的调用方。"""

    return json.dumps(res.to_dict(), ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
# 5. 接真库 + 命令行:作为工具被调用
# --------------------------------------------------------------------------- #
def lens_from_db(
    *,
    knowledge_cutoff: str,
    as_of: str | None = None,
    window: int = 10,
    step: int = 5,
    top: int = 5,
    db_path: str | None = None,
    checkpoints_path: str | None = None,
    threshold: float = DEFAULT_REDUNDANCY_R,
) -> LensResult:
    """从市场库取六轨逐日向量,铺满候选窗口,产出镜头读数。**只读。**

    ``knowledge_cutoff`` 必填 —— 直接透传给 ``river_window.build_daily_vectors``,
    由它执行 PIT(有效时间截断 + 按 ``updated_at`` 判 ``pit_grade``)。
    本模块不自己绕过去取数,就是为了不另开一条可能漏 PIT 的路。

    候选窗口:在历史上每 ``step`` 个交易日铺一个长 ``window`` 的窗口,
    **与当前窗口有重叠的一律剔除**(自己跟自己像不是信息)。
    """

    from intelligence.services import river_window as rw

    if window < 1 or step < 1 or top < 1:
        raise ValueError("window、step、top 必须是正整数")
    if not 0 < threshold <= 1:
        raise ValueError("redundancy threshold 必须在 (0, 1] 内")
    cutoff_day = date.fromisoformat(knowledge_cutoff)
    asof_day = date.fromisoformat(as_of) if as_of else cutoff_day
    if asof_day > cutoff_day:
        raise ValueError("as_of 不能晚于 knowledge_cutoff")
    daily = rw.build_daily_vectors(
        knowledge_cutoff=knowledge_cutoff,
        db_path=db_path,
        checkpoints_path=checkpoints_path,
    )
    # as_of 早于 cutoff 时，候选与标准化基准也必须停在 as_of，不能混入目标窗之后的行情。
    daily = [r for r in daily if r["trade_date"] <= asof_day.isoformat()]
    if len(daily) < window * 2:
        raise ValueError(f"交易日不足：{len(daily)} 天，至少需要 {window * 2} 天")

    end_i = len(daily) - 1
    if as_of:
        hits = [i for i, r in enumerate(daily) if r["trade_date"] <= as_of]
        if not hits:
            raise ValueError(f"{as_of} 之前没有交易日")
        end_i = hits[-1]
    cur_lo = max(0, end_i - window + 1)
    current = (daily[cur_lo]["trade_date"], daily[end_i]["trade_date"])

    candidates: list[tuple[str, str, str]] = []
    for lo in range(0, len(daily) - window + 1, max(1, step)):
        hi = lo + window - 1
        if hi >= cur_lo and lo <= end_i:   # 与当前窗重叠 → 剔除
            continue
        candidates.append(
            (f"{daily[lo]['trade_date']}~{daily[hi]['trade_date']}",
             daily[lo]["trade_date"], daily[hi]["trade_date"])
        )

    result = build_lens(
        daily,
        rw.COMPARABLE_FEATURE_NAMES,
        current=current,
        candidates=candidates,
        knowledge_cutoff=knowledge_cutoff,
        threshold=threshold,
        labels={f.name: f.label for f in rw.FEATURES},
        top=top,
    )
    result.feature_sources = {f.name: f"{f.source}；{f.rule}" for f in rw.FEATURES}
    result.excluded_features = {
        f: "来源口径变化，标准化口径尚未统一；原值可展示但不进签名与距离"
        for f in sorted(rw.SUSPENDED_FEATURES)
    }
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="river-lens",
        description="多维对照镜头：把空间交给 agent，而不是把排名交给 agent。只读。",
    )
    ap.add_argument("--knowledge-cutoff", required=True,
                    help="站在哪天回看（必填，PIT）。只用该日及之前的行。")
    ap.add_argument("--as-of", default=None, help="当前窗口结束于哪天（默认 = cutoff 当天）")
    ap.add_argument("--window", type=int, default=10, help="窗口长度（交易日）")
    ap.add_argument("--step", type=int, default=5, help="候选窗口铺设步长（交易日）")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--db-path", default=None)
    ap.add_argument("--checkpoints", default=None)
    ap.add_argument("--redundancy-r", type=float, default=DEFAULT_REDUNDANCY_R,
                    help=f"平均相关距离的分组阈值，不证明等价或独立（默认 {DEFAULT_REDUNDANCY_R}）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 而不是给 agent 的文本块")
    args = ap.parse_args(argv)

    res = lens_from_db(
        knowledge_cutoff=args.knowledge_cutoff,
        as_of=args.as_of or args.knowledge_cutoff,
        window=args.window,
        step=args.step,
        top=args.top,
        db_path=args.db_path,
        checkpoints_path=args.checkpoints,
        threshold=args.redundancy_r,
    )
    print(lens_payload(res) if args.json else lens_block(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
