"""多维对照镜头:把**空间**交给 agent,而不是把**排名**交给 agent。

为什么要有这个模块
------------------
旧 ``market_regime_analogs.regime_block_for_llm`` 仅递给 LLM 成品表:

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

2. **距离的分解**(``decompose``)——逐维均值/首尾段差、贡献等级与方向关系分列。
   贡献小不保证同方向；首尾段摘要也不能恢复完整路径。

3. **距离地形**(``landscape``)——整个可比池的描述性距离分布。
   保留分位方法与候选规模，撤下未校准的突出类别，不认证绝对相似。

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
from pathlib import Path
from typing import Any, Iterable, Sequence

from intelligence.services.market_regime_analogs import (
    _DELTA_WEIGHT,
    END_SEGMENT_EPSILON,
    end_segment_direction,
    end_segment_direction_relation,
    direction_relation_label,
    RegimeSignature,
    signature_distance,
    signature_table,
    rounded_readout,
    observation_table,
    labeled_readout,
    bind_model_windows,
    model_readout_block,
    _standardize_vectors_with_reasons,
    window_relations,
    window_signature,
)

#: 平均相关距离的聚类阈值，提示潜在冗余，不证明两维含义相同。
#: 可调；分组只是启发式摘要，不是统计独立维数估计。
DEFAULT_REDUNDANCY_R = 0.7

#: 贡献等级只描述原距离和式，不判断同方向或路径相同。
LOW_CONTRIBUTION = 0.5
HIGH_CONTRIBUTION = 1.5
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
    def contribution_band(self) -> str:
        if self.contribution <= LOW_CONTRIBUTION:
            return "low"
        if self.contribution >= HIGH_CONTRIBUTION:
            return "high"
        return "middle"

    @property
    def direction_relation(self) -> str | None:
        return end_segment_direction_relation(self.z_delta_a, self.z_delta_b)


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
    def low_contribution(self) -> tuple[DimDelta, ...]:
        return tuple(d for d in self.dims if d.contribution_band == "low")

    @property
    def high_contribution(self) -> tuple[DimDelta, ...]:
        return tuple(sorted(
            (d for d in self.dims if d.contribution_band == "high"),
            key=lambda d: -d.contribution,
        ))

    @property
    def low_contribution_groups(self) -> tuple[int, ...]:
        """低贡献维落入的相关组；不等于独立证据的个数。"""
        return tuple(sorted({d.group for d in self.low_contribution if d.group is not None}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_distance": self.total,
            "total_dims": self.total_dims,
            "shared_dims": list(self.shared),
            "only_in_current": list(self.only_a),
            "only_in_candidate": list(self.only_b),
            "low_contribution_dims": [d.feature for d in self.low_contribution],
            "low_contribution_groups": len(self.low_contribution_groups),
            "high_contribution_dims": [
                {
                    "feature": d.feature,
                    "d_mean": round(d.d_mean, 3),
                    "d_trend": round(d.d_trend, 3),
                    "group": d.group,
                }
                for d in self.high_contribution
            ],
            "per_dim": [
                {
                    "feature": d.feature,
                    "group": d.group,
                    "z_current": round(d.z_mean_a, 3),
                    "z_candidate": round(d.z_mean_b, 3),
                    "d_mean": round(d.d_mean, 3),
                    "d_trend": round(d.d_trend, 3),
                    "current_end_segment_delta": d.z_delta_a,
                    "candidate_end_segment_delta": d.z_delta_b,
                    "current_direction": end_segment_direction(d.z_delta_a),
                    "candidate_direction": end_segment_direction(d.z_delta_b),
                    "direction_relation": d.direction_relation,
                    "contribution": d.contribution,
                    "contribution_band": d.contribution_band,
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
    """可比池距离的描述分布，不作突出程度或绝对相似性认证。

    standout 仅保留旧 Python 数值读取；其小n可达域未校准，退出对外投影。
    """

    n: int
    quantiles: dict[str, float]
    nearest: float | None

    @property
    def standout(self) -> float | None:
        """旧 Python 读取兼容；按需导出原公式，不存冗余字段，不进入模型投影。"""
        if self.nearest is None:
            return None
        spread = self.quantiles["p50"] - self.quantiles["p5"]
        return None if spread <= 0 else round((self.quantiles["p5"] - self.nearest) / spread, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": self.n,
            "quantiles": {k: round(v, 3) for k, v in self.quantiles.items()},
            "nearest": None if self.nearest is None else round(self.nearest, 3),
            "status": "available" if self.n else "no_candidates",
            "interpretation": "descriptive_only",
            "quantile_method": "linear_at_p_times_n_minus_1",
            "reading": self.reading,
        }

    @property
    def reading(self) -> str:
        if self.nearest is None:
            return "无候选窗口。"
        return (
            f"可比池{self.n}窗，最近距离{self.nearest:.3f}；p5为距离第5百分位，"
            "按升序位置0.05×(n−1)线性插值，不是第5名。"
            "仅描述本候选集的距离分布，无法区分经校准的突出类别，也不认证绝对相似。"
        )


def landscape(distances: Iterable[float | None]) -> Landscape:
    vals = sorted(d for d in distances if d is not None)
    if not vals:
        return Landscape(0, {}, None)

    def q(p: float) -> float:
        if len(vals) == 1:
            return vals[0]
        i = p * (len(vals) - 1)
        lo, hi = int(i), min(int(i) + 1, len(vals) - 1)
        return vals[lo] + (vals[hi] - vals[lo]) * (i - lo)

    nearest = vals[0]
    qs = {"p1": q(0.01), "p5": q(0.05), "p25": q(0.25), "p50": q(0.50), "p90": q(0.90)}
    return Landscape(n=len(vals), quantiles=qs, nearest=nearest)


# --------------------------------------------------------------------------- #
# 4. 装配:给 agent 的那一块
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LensCandidate:
    label: str
    start_date: str
    end_date: str
    signature: RegimeSignature
    decomposition: Decomposition

    @property
    def window_id(self) -> str:
        return f"river:{self.start_date}:{self.end_date}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id, "label": self.label,
            "start_date": self.start_date, "end_date": self.end_date,
            "signature": self.signature.to_payload(), **self.decomposition.to_dict(),
        }


@dataclass
class LensResult:
    structure: DimensionStructure
    current: RegimeSignature
    candidates: list[LensCandidate] = field(default_factory=list)
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
    current_gap_days: dict[str, int] = field(default_factory=dict)
    selection: dict[str, Any] = field(default_factory=dict)
    feature_observations: dict[str, dict[str, Any]] = field(default_factory=dict)

    def model_payload(self) -> dict[str, Any]:
        signatures = [("current", self.current.to_payload())]
        candidates = {}
        for candidate in self.candidates:
            wid, dec = candidate.window_id, candidate.decomposition
            signatures.append((wid, candidate.signature.to_payload()))
            candidates[wid] = {
                **({"label": candidate.label} if candidate.label != f"{candidate.start_date}~{candidate.end_date}" else {}),
                "distance": dec.total,
                "shared_dims": len(dec.shared), "active_dims": dec.total_dims,
                "only_current": dec.only_a, "only_candidate": dec.only_b,
                "low_contribution_groups": len(dec.low_contribution_groups),
            }
        readings = signature_table(signatures)
        readings["columns"] += ["contribution", "contribution_band", "direction_relation"]
        for row in readings["windows"]["current"]:
            row.extend([None, None, None])
        for candidate in self.candidates:
            dims = {d.feature: d for d in candidate.decomposition.dims}
            for row in readings["windows"][candidate.window_id]:
                dim = dims.get(row[0])
                row.extend([dim.contribution, dim.contribution_band, direction_relation_label(dim.direction_relation)]
                           if dim else [None, None, None])
        payload = rounded_readout({
            "set": "river", "current_window": self.current_window,
            "fit_window": self.standardization_window, "cutoff": self.knowledge_cutoff,
            "upstream_pit_counts": self.upstream_pit_counts,
            "selection": {**self.selection, "displayed_count": len(self.candidates)},
            "candidate_relations": window_relations([(c.window_id, c.start_date, c.end_date) for c in self.candidates]),
            "dimension_structure": {
                "groups": [g.members for g in self.structure.groups],
                "max_abs_r": [g.max_abs_r for g in self.structure.groups],
                "undetermined": self.structure.undetermined,
            },
            "current_missing_features": self.current_missing_features,
            "current_gap_days": {f: self.current_gap_days.get(f) for f in self.current_missing_features},
            "landscape": self.landscape_.to_dict() if self.landscape_ else None,
            "candidates": candidates, "signatures": readings,
            "feature_observations": observation_table(self.feature_observations),
        })
        # 部分label也须与未翻译键一起验唯一，防止x→y与原有y碰撞。
        features = tuple(self.feature_observations)
        labels = {f: self.labels.get(f, f) for f in features}
        if len(set(labels.values())) == len(features):
            payload = labeled_readout(payload, labels)
            payload["feature_keys"] = {v: k for k, v in labels.items()}
        return bind_model_windows(payload, [(c.window_id, c.start_date, c.end_date) for c in self.candidates])

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_cutoff": self.knowledge_cutoff,
            "current_window": self.current_window,
            "standardization_window": self.standardization_window,
            "upstream_pit_counts": dict(self.upstream_pit_counts),
            "feature_sources": dict(self.feature_sources),
            "excluded_features": dict(self.excluded_features),
            "current_missing_features": list(self.current_missing_features),
            "current_gap_days": dict(self.current_gap_days),
            "dimension_structure": self.structure.to_dict(),
            "dropped_features": list(self.dropped),
            "current_window_z": {
                f: {"z_mean": round(m, 3), "z_trend": round(t, 3)}
                for f, (m, t) in self.current.stats.items()
            },
            "landscape": self.landscape_.to_dict() if self.landscape_ else None,
            "current_signature": self.current.to_payload(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "selection": {**self.selection, "displayed_count": len(self.candidates)},
            "candidate_relations": window_relations([
                (c.window_id, c.start_date, c.end_date) for c in self.candidates
            ]),
            "feature_observations": self.feature_observations,
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

    if top < 1:
        raise ValueError("top 必须是正整数")
    identities = [(s, e) for _, s, e in candidates]
    if len(identities) != len(set(identities)):
        raise ValueError("重复候选窗口：日期身份不能由不同显示名重复计数")
    z_rows, reasons = _standardize_vectors_with_reasons(list(daily), tuple(features))
    dropped = list(reasons)
    live = tuple(f for f in features if f not in dropped)
    structure = dimension_groups(z_rows, live, threshold=threshold)

    def sig_of(start: str, end: str) -> RegimeSignature | None:
        idx = [i for i, r in enumerate(daily) if start <= r["trade_date"] <= end]
        if not idx:
            return None
        return window_signature([z_rows[i] for i in idx], live, raw_rows=[daily[i] for i in idx])

    cur = sig_of(*current)
    if cur is None:
        raise ValueError(f"当前窗口 {current} 内没有交易日")

    scored: list[LensCandidate] = []
    all_d: list[float | None] = []
    for label, s, e in candidates:
        sig = sig_of(s, e)
        if sig is None:
            continue
        dec = decompose(cur, sig, len(live), structure=structure)
        all_d.append(dec.total)
        if dec.total is not None:
            scored.append(LensCandidate(label, s, e, sig, dec))
    scored.sort(key=lambda c: (c.decomposition.total, c.label, c.start_date, c.end_date))

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
        current_gap_days={f: sum(r.get(f) is not None for r in daily if current[0] <= r["trade_date"] <= current[1])
                          for f in live if f not in cur.stats},
        structure=structure,
        current=cur,
        candidates=scored[:top],
        selection={
            "strategy": "distance_top_k_overlap_allowed", "requested_top": top,
            "generated_count": len(candidates), "comparable_count": len(scored),
            "generation": "caller_supplied_windows",
        },
        feature_observations={
            f: {"read_status": "caller_supplied", "non_null_days": sum(r.get(f) is not None for r in daily),
                "input_days": len(daily), "comparison_status": reasons.get(f, "active"),
                "missing_policy": "null_unknown"} for f in features
        },
        landscape_=landscape(all_d),
        knowledge_cutoff=knowledge_cutoff,
        dropped=tuple(dropped),
        labels=labels or {},
    )


def lens_block(res: LensResult, *, name: str = "LENS", shared_reading_rules: bool = False) -> str:
    """模型与人读同一份具名结果，数据只从 model_payload 投影一次。"""
    schema_rules = [
        "- fit_window含当前窗，非留出验证；raw_mean/z_mean为非空原值/z均值，end_segment_delta=末减首三分之一z均值，*_days非空数。"
        "首尾差近零≠逐日走平，无路径；signatures.defaults为各行相同计数；eligibility_by_window_days给段长/准入最少观测。",
        f"- direction_relation按未舍入首尾差±{END_SEGMENT_EPSILON}分类（含边界近零）："
        "同向/反向/一方近零/双方近零，null未比较。windows=本块引用→[起日,止日]。",
        "- feature_observations：defaults/overrides默认/例外；null_unknown未知，queried不证全源覆盖；"
        "current_gap_days缺维非空数；显示舍入3位。",
    ]
    if shared_reading_rules:
        schema_rules = ["- 签名/覆盖/缺维/方向/舍入口径沿用前块共同读法；首尾近零非逐日走平。"]
    return "\n".join([
        f"## 多维对照镜头 [{name}]",
        f"- knowledge_cutoff={res.knowledge_cutoff}仅截交易日，非历史可知。",
        *schema_rules,
        f"- 逐维贡献=abs(均值差)+{_DELTA_WEIGHT}×abs(首尾差之差)；总距离=贡献和×活动维数/共有维数²。"
        f"贡献low≤{LOW_CONTRIBUTION}、high≥{HIGH_CONTRIBUTION}，其余middle，不判断方向。",
        "- selection=生成/可比/展示数，top-K允许重叠；组数/交集不证统计独立。"
        "upstream_pit_counts仅对本cutoff，未核完整历史版本；strict非逐日可知，trade_date_only不证明重写。"
        "不是概率预测，不含基本面/政策差异，不授予回放/校准/剧本命名资格。",
        model_readout_block(res.model_payload()),
    ])


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
    result.selection.update(window_days=window, stride=step,
                            generation="stride_windows_excluding_current_overlap")
    result.feature_sources = {f.name: f"{f.source}；{f.rule}" for f in rw.FEATURES}
    for f in rw.FEATURES:
        observation = result.feature_observations.setdefault(f.name, {
            "non_null_days": sum(r.get(f.name) is not None for r in daily),
            "input_days": len(daily), "comparison_status": "suspended",
            "missing_policy": "null_unknown",
        })
        observation["read_status"] = (
            "queried" if f.name != "checkpoints_registered" else
            "not_requested" if checkpoints_path is None else
            "read" if Path(checkpoints_path).is_file() else "unavailable"
        )
        observation["unit"] = f.unit
        observation["source"] = f.source + (
            "；逐日COUNT FILTER DOUBLE_RED_SQL" if f.name == "double_red_count" else
            "；rank=1后MAX" if f.name == "top1_limit_share" else
            "；近30日滚动计数" if f.name == "report_count_30d" else
            "；单来源日SUM，混来源None" if f.name == "theme_net_flow" else ""
        )
        if f.name == "double_red_count":
            observation["missing_policy"] = "已观测源行内COUNT FILTER可为0；无源日为缺失；未证完整题材宇宙"
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
