"""环境剧本:让「簇」变成「概念」—— 把压缩环闭上。

断在哪
------
``river_window.cluster_windows`` 能把区间聚成簇,但 ``Cluster.to_dict()`` 只输出
``size`` / ``labels`` / ``raw_means`` —— **簇是一堆数字,没有名字**。于是:

    窗口 → 特征 → 距离 → 聚类 → 簇 ──╳── 命名 → 词表 → 下次直接用这个词读盘

下次读盘还得从头算一遍距离。**没有任何东西被压缩下来、被复用。**

本模块把满足探索性门槛的簇记为环境剧本，供后续匹配和回溯。

命名的门槛
----------
**不是所有簇都配有名字。**样本内可分不代表可泛化，命名会让人更容易过度解释噪声。
所以本模块的重点**不是**造对象,是造**那道闸**:

1. **留出法**:簇在训练段上切,解释力在**从未参与切簇**的留出段上算。
   否则 K 调大就能把簇内离散度压到 0 —— 那是过拟合,不是深刻。
2. **置换零假设**:把后续事实在窗口之间**随机打乱**重算多次,得到「随机分簇能拿到
   多少解释力」的分布。**小样本上任何聚类都会显出表面解释力**,不跟这个分布比
   就是自欺。观测值必须落在零分布的尾部才算数。
3. **最小成员数**:两三个窗口凑出来的「规律」不命名。

过不了闸的簇**明确标记为不命名,并写出是哪一条没过**。

不编概率
--------
后续事实一律报 **样本数 + 实际值分位 + 复现次数**(「7 次里有 5 次为正」),
不把历史复现次数转述为概率预测。

纪律
----
- **纯函数。**不连库、不取数、不写文件。后续事实由调用方给 —— 它带 PIT 责任,
  不该在这里偷偷再开一条取数路径。
- **确定性。**置换检验用固定种子;簇 ID 由内容哈希决定,同样的输入永远同样的 ID。
- **可回溯。**每个剧本带成员窗口、判别签名、生效特征集、门限读数。
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from intelligence.services.market_regime_analogs import RegimeSignature, signature_distance
from intelligence.services.river_lens import DimensionStructure

#: 少于这么多成员的簇不命名 —— 两三个窗口凑出来的不是规律。
MIN_MEMBERS = 4
#: 观测解释力必须超过置换零分布的这个分位,才算「不是随机能拿到的」。
NULL_PERCENTILE = 95.0
#: 置换次数。固定种子,可重算。
N_PERMUTATIONS = 500
PERMUTATION_SEED = 20260108


# --------------------------------------------------------------------------- #
# 1. 解释力:这组簇有没有让后续事实变得更可解释
# --------------------------------------------------------------------------- #
def explanatory_power(
    assignments: Mapping[str, int],
    outcomes: Mapping[str, float],
) -> float | None:
    """``1 − 簇内离散度 ÷ 全体离散度``。只用两边都有的窗口。

    返回 None 表示样本不足或输入非法。簇均值在同一留出集上计算，
    所以这是簇间差异诊断，不是用训练期参数预测留出期的预测 R²。
    """

    keys = [k for k in assignments if k in outcomes]
    if len(keys) < 2:
        return None
    vals = [outcomes[k] for k in keys]
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in vals):
        return None
    # 同比例缩放不改变解释力，避免有限大数的平方/求和溢出为 NaN。
    scale = max(abs(v) for v in vals)
    if scale == 0:
        return None
    normalized = {k: outcomes[k] / scale for k in keys}
    vals = list(normalized.values())
    mean = sum(vals) / len(vals)
    total = sum((v - mean) ** 2 for v in vals)
    if total <= 0:
        return None
    within = 0.0
    by: dict[int, list[float]] = {}
    for k in keys:
        by.setdefault(assignments[k], []).append(normalized[k])
    for group in by.values():
        if not group:
            continue
        m = sum(group) / len(group)
        within += sum((v - m) ** 2 for v in group)
    return 1.0 - within / total


def permutation_null(
    assignments: Mapping[str, int],
    outcomes: Mapping[str, float],
    *,
    n: int = N_PERMUTATIONS,
    seed: int = PERMUTATION_SEED,
) -> list[float]:
    """把后续事实在窗口之间随机打乱,重算解释力 —— 「随机分簇能拿到多少」。

    **没有这个分布,解释力这个数就没有意义。**簇越多、样本越小,
    表面解释力越高;不跟随机比,任何聚类看起来都「有解释力」。
    """

    keys = [k for k in assignments if k in outcomes]
    if len(keys) < 2:
        return []
    vals = [outcomes[k] for k in keys]
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in vals):
        return []
    rng = random.Random(seed)
    out: list[float] = []
    for _ in range(n):
        shuffled = vals[:]
        rng.shuffle(shuffled)
        fake = {k: v for k, v in zip(keys, shuffled)}
        p = explanatory_power(assignments, fake)
        if p is not None:
            out.append(p)
    return sorted(out)


@dataclass(frozen=True)
class Gate:
    """命名闸的读数。``passed`` 为真才允许铸造剧本。"""

    observed: float | None
    null_p95: float | None
    null_median: float | None
    n_holdout: int
    n_clusters: int
    reasons: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.reasons

    @property
    def beats_random(self) -> bool | None:
        if self.observed is None or self.null_p95 is None:
            return None
        return self.observed > self.null_p95

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "observed_explanatory_power": None if self.observed is None else round(self.observed, 4),
            "null_p95": None if self.null_p95 is None else round(self.null_p95, 4),
            "null_median": None if self.null_median is None else round(self.null_median, 4),
            "beats_random": self.beats_random,
            "n_holdout_windows": self.n_holdout,
            "n_clusters": self.n_clusters,
            "blocking_reasons": list(self.reasons),
            "method": (
                "解释力 = 1 − 簇内离散度/全体离散度，**在从未参与切簇的留出段上算**；"
                "并与『把后续事实随机打乱』的置换零分布比较（固定种子，可重算）。"
                "观测值须高于零分布 p95。这是探索性诊断；窗口独立性、时序自相关、"
                "标准化拟合范围及后续事实截止仍由调用方验证，不是预测有效性证明。"
            ),
        }


def evaluate_gate(
    holdout_assignments: Mapping[str, int],
    holdout_outcomes: Mapping[str, float],
    *,
    min_members: int = MIN_MEMBERS,
    null_percentile: float = NULL_PERCENTILE,
) -> Gate:
    """在**留出段**上评一组簇配不配有名字。

    这是独立窗口假设下的探索性诊断，不是时序泛化证明。调用方还须隔离重叠窗口、
    后续事实区间和标准化拟合区间；逐窗口置换未控制自相关，不能据此宣称预测有效。
    """

    if min_members < 2 or not 0 < null_percentile < 100:
        raise ValueError("min_members 必须至少为 2，null_percentile 必须在 (0, 100) 内")
    keys = [k for k in holdout_assignments if k in holdout_outcomes]
    sizes: dict[int, int] = {}
    for k in keys:
        sizes[holdout_assignments[k]] = sizes.get(holdout_assignments[k], 0) + 1

    reasons: list[str] = []
    invalid = [k for k in keys if not isinstance(holdout_outcomes[k], (int, float))
               or isinstance(holdout_outcomes[k], bool) or not math.isfinite(holdout_outcomes[k])]
    if invalid:
        reasons.append(f"后续事实必须为有限数值，非法窗口：{invalid[:5]}")
    small = {c: n for c, n in sizes.items() if n < min_members}
    if small:
        reasons.append(f"留出簇成员不足（每簇至少 {min_members}）：{small}")
    if len(keys) < min_members * 2:
        reasons.append(
            f"留出段只有 {len(keys)} 个窗口，不足以评判（至少 {min_members * 2}）"
        )
    if len(sizes) < 2:
        reasons.append("留出段上只落进了一个簇，无从比较")

    obs = explanatory_power(holdout_assignments, holdout_outcomes)
    null = permutation_null(holdout_assignments, holdout_outcomes)
    p95 = None
    med = None
    if null:
        i = min(len(null) - 1, int(null_percentile / 100.0 * (len(null) - 1)))
        p95 = null[i]
        med = null[len(null) // 2]

    if obs is None:
        reasons.append("解释力无法计算（后续事实无差异或样本不足）")
    elif p95 is None:
        reasons.append("置换零分布不可计算，不命名")
    elif obs <= p95:
        reasons.append(
            f"解释力 {obs:.3f} 未超过随机分簇的 p95（{p95:.3f}）"
            "——这组簇没有提供随机分组拿不到的信息"
        )
    return Gate(obs, p95, med, len(keys), len(sizes), tuple(reasons))


# --------------------------------------------------------------------------- #
# 2. 环境剧本:过了闸的簇才有名字
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ForwardFacts:
    """后续事实。**只有事实和复现次数,没有概率。**"""

    n: int
    median: float | None
    p25: float | None
    p75: float | None
    positive: int
    negative: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_samples": self.n,
            "median": self.median,
            "p25": self.p25,
            "p75": self.p75,
            "positive_count": self.positive,
            "negative_count": self.negative,
            "statement": (
                f"历史上落入本剧本的 {self.n} 个窗口中，后续为正 {self.positive} 次、"
                f"为负 {self.negative} 次，中位 {self.median}。"
                "**这是小样本历史事实，不是概率。**"
            ),
        }


def _facts(values: Sequence[float]) -> ForwardFacts:
    vs = sorted(values)
    if not vs:
        return ForwardFacts(0, None, None, None, 0, 0)

    def q(p: float) -> float:
        if len(vs) == 1:
            return vs[0]
        i = p * (len(vs) - 1)
        lo, hi = int(i), min(int(i) + 1, len(vs) - 1)
        return round(vs[lo] + (vs[hi] - vs[lo]) * (i - lo), 4)

    return ForwardFacts(
        n=len(vs),
        median=q(0.5),
        p25=q(0.25),
        p75=q(0.75),
        positive=sum(1 for v in vs if v > 0),
        negative=sum(1 for v in vs if v < 0),
    )


@dataclass(frozen=True)
class RegimeScript:
    """一个被命名的簇。**这就是从「地图」跳到「坐标系」的那一步。**"""

    script_id: str
    auto_label: str
    centroid: RegimeSignature
    members: tuple[str, ...]
    forward: ForwardFacts
    divergence: tuple[tuple[str, float], ...]  # 簇内分歧最大的维（防刻舟求剑）
    features: tuple[str, ...]
    gate: Gate
    human_name: str | None = None
    training_radius: float | None = None  # 训练成员到质心的最大距离，非概率边界

    @property
    def name(self) -> str:
        return self.human_name or self.auto_label

    def to_dict(self) -> dict[str, Any]:
        return {
            "script_id": self.script_id,
            "name": self.name,
            "auto_label": self.auto_label,
            "human_name": self.human_name,
            "members": list(self.members),
            "centroid_z": {
                f: {"z_mean": round(m, 3), "z_trend": round(t, 3)}
                for f, (m, t) in sorted(self.centroid.stats.items())
            },
            "forward_facts": self.forward.to_dict(),
            "internal_divergence": [
                {"feature": f, "stdev_z": round(s, 3)} for f, s in self.divergence
            ],
            "features": list(self.features),
            "training_radius": self.training_radius,
            "gate": self.gate.to_dict(),
        }


def _auto_label(centroid: RegimeSignature, labels: Mapping[str, str]) -> str:
    """从质心自动生成一句**描述**(不是起名字 —— 起名字是人的事)。"""

    items = sorted(centroid.stats.items(), key=lambda kv: -abs(kv[1][0]))[:3]
    parts = []
    for f, (m, t) in items:
        nm = labels.get(f, f)
        lvl = "高" if m > 0.5 else ("低" if m < -0.5 else "中")
        trend = "走强" if t > 0.3 else ("走弱" if t < -0.3 else "平")
        parts.append(f"{nm}{lvl}{trend}")
    return " / ".join(parts) if parts else "（无可描述维度）"


def _centroid(sigs: Sequence[RegimeSignature]) -> tuple[RegimeSignature, dict[str, float]]:
    """簇质心 + 逐维的簇内标准差(分歧度)。缺维只在有值的成员上求。"""

    acc: dict[str, list[tuple[float, float]]] = {}
    for s in sigs:
        for f, (m, t) in s.stats.items():
            acc.setdefault(f, []).append((m, t))
    stats: dict[str, tuple[float, float]] = {}
    spread: dict[str, float] = {}
    for f, pairs in acc.items():
        ms = [p[0] for p in pairs]
        ts = [p[1] for p in pairs]
        mu = sum(ms) / len(ms)
        stats[f] = (mu, sum(ts) / len(ts))
        spread[f] = (sum((m - mu) ** 2 for m in ms) / len(ms)) ** 0.5
    return RegimeSignature(stats), spread


def mint_scripts(
    *,
    train: Mapping[str, RegimeSignature],
    train_assignments: Mapping[str, int],
    holdout_assignments: Mapping[str, int],
    holdout_outcomes: Mapping[str, float],
    train_outcomes: Mapping[str, float] | None = None,
    features: Sequence[str],
    labels: Mapping[str, str] | None = None,
    structure: DimensionStructure | None = None,
    min_members: int = MIN_MEMBERS,
) -> tuple[list[RegimeScript], Gate]:
    """过闸才铸造剧本。**闸不过 ⇒ 返回空列表 + 说明为什么。**

    ``train_*`` 用来定义剧本(质心、成员);``holdout_*`` **只**用来评闸 ——
    留出段从不参与切簇,所以它上面的解释力才是真读数。
    """

    overlap = set(train) & set(holdout_assignments)
    if overlap:
        raise ValueError(f"训练与留出窗口重叠：{sorted(overlap)[:5]}")
    if set(train_assignments) != set(train):
        raise ValueError("训练签名与训练分组的窗口必须一致")
    unknown = set(holdout_assignments.values()) - set(train_assignments.values())
    if unknown:
        raise ValueError(f"留出段引用了不存在的训练簇：{sorted(unknown)}")
    gate = evaluate_gate(
        holdout_assignments, holdout_outcomes, min_members=min_members
    )
    if not gate.passed:
        return [], gate

    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
           for k, v in (train_outcomes or {}).items() if k in train):
        raise ValueError("训练后续事实必须为有限数值")
    if not features or len(features) != len(set(features)):
        raise ValueError("features 必须非空且不能重复")
    for sig in train.values():
        if not set(sig.stats) <= set(features) or any(
            not math.isfinite(v) for pair in sig.stats.values() for v in pair
        ):
            raise ValueError("训练签名须为有限数值且只能包含已声明特征")
    lb = labels or {}
    outs = dict(train_outcomes or {})
    outs.update(holdout_outcomes)

    by: dict[int, list[str]] = {}
    for w, c in train_assignments.items():
        if w in train:
            by.setdefault(c, []).append(w)

    scripts: list[RegimeScript] = []
    for cid in sorted(by):
        members = tuple(sorted(by[cid]))
        held = [w for w, c in holdout_assignments.items() if c == cid and w in holdout_outcomes]
        if len(members) < min_members or len(held) < min_members:
            continue  # 全局闸过了，不代表无留出支持的训练簇也得到验证。
        cen, spread = _centroid([train[w] for w in members])
        distances = [signature_distance(train[w], cen, len(features)) for w in members]
        radius = max((d for d in distances if d is not None), default=None)
        # 后续事实:训练段成员 + 留出段落进本簇的窗口,都算 —— 它们都是本剧本的历史实例
        vals = [outs[w] for w in members if w in outs]
        vals += [holdout_outcomes[w] for w in held]
        feats = tuple(sorted(cen.stats))
        payload = json.dumps(
            {"c": {f: [round(v, 6) for v in cen.stats[f]] for f in feats},
             "m": list(members), "f": list(features)},
            ensure_ascii=False, sort_keys=True,
        )
        scripts.append(
            RegimeScript(
                script_id="rs-" + hashlib.sha256(payload.encode()).hexdigest()[:12],
                auto_label=_auto_label(cen, lb),
                centroid=cen,
                members=members,
                forward=_facts(vals),
                divergence=tuple(
                    sorted(spread.items(), key=lambda kv: -kv[1])[:3]
                ),
                features=tuple(features),
                gate=gate,
                training_radius=radius,
            )
        )
    return scripts, gate


# --------------------------------------------------------------------------- #
# 3. 复用:下次读盘不用从头算
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Match:
    script: RegimeScript | None
    distance: float | None
    runner_up: tuple[str, float] | None
    confident: bool
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "script_id": None if self.script is None else self.script.script_id,
            "name": None if self.script is None else self.script.name,
            "distance": None if self.distance is None else round(self.distance, 3),
            "runner_up": (
                None if self.runner_up is None
                else {"script_id": self.runner_up[0], "distance": round(self.runner_up[1], 3)}
            ),
            "confident": self.confident,
            "note": self.note,
            "forward_facts": None if self.script is None else self.script.forward.to_dict(),
        }


def match_script(
    sig: RegimeSignature,
    scripts: Sequence[RegimeScript],
    *,
    total_dims: int,
    margin: float = 0.25,
) -> Match:
    """当前窗口落进哪个剧本。**这一步才是「压缩被复用」。**

    ``confident`` 同时要求落在训练样本半径内，且领先第二名 ``margin``。
    这只是经验支持范围，不是概率置信度；相对领先不能证明绝对接近。
    """

    if not scripts:
        return Match(None, None, None, False, "没有已命名的剧本 —— 闸没过或还没铸造。")
    scored = []
    for s in scripts:
        d = signature_distance(sig, s.centroid, total_dims)
        if d is not None:
            scored.append((d, s))
    if not scored:
        return Match(None, None, None, False, "与所有剧本都没有共有维度,无法比较。")
    scored.sort(key=lambda x: (x[0], x[1].script_id))
    best_d, best = scored[0]
    if len(scored) == 1:
        return Match(best, best_d, None, False, "只有一个剧本可比；缺少对照，不能确认归属。")
    second_d, second = scored[1]
    if best.training_radius is None or best_d > best.training_radius + 1e-12:
        return Match(best, best_d, (second.script_id, second_d), False,
                     "超出训练成员的距离支持范围（或缺少训练半径），归属不明确；只报最近候选。")
    rel = (second_d - best_d) / second_d if second_d > 0 else 0.0
    if rel >= margin:
        note = f"在训练距离支持范围内且领先第二名 {rel:.0%}；这是经验匹配，不是概率置信度。"
        ok = True
    else:
        note = (
            f"只领先第二名 {rel:.0%}（< {margin:.0%}）——**归属不明确**，"
            "当前环境介于两个剧本之间，应同时读两者的后续事实,不要只报第一名。"
        )
        ok = False
    return Match(best, best_d, (second.script_id, second_d), ok, note)


# --------------------------------------------------------------------------- #
# 4. 给 agent 的那一块
# --------------------------------------------------------------------------- #
def scripts_block(
    scripts: Sequence[RegimeScript],
    gate: Gate,
    *,
    match: Match | None = None,
    labels: Mapping[str, str] | None = None,
    name: str = "SCRIPT",
) -> str:
    lb = labels or {}
    out = [f"## 环境剧本 [{name}]"]
    out.append(
        "- 口径：区间在训练段上聚类 → **在从未参与切簇的留出段上**评解释力 → "
        "与随机分簇的置换零分布比较 → 过闸的簇才铸造成剧本。"
    )

    g = gate.to_dict()
    out.append("- 限制：探索性诊断；窗口重叠、自相关、标准化拟合区间和后续事实截止由调用方验证，不是预测有效性证明。")
    out.append("")
    out.append("### ① 命名闸")
    out.append(
        f"- 留出段解释力 **{g['observed_explanatory_power']}** ｜ "
        f"随机分簇 p95 = {g['null_p95']}（中位 {g['null_median']}）｜ "
        f"留出窗口 {g['n_holdout_windows']} 个 ｜ 簇 {g['n_clusters']} 个"
    )
    if gate.passed:
        out.append("- ✅ **过闸**：解释力高于随机分簇能拿到的水平，这组簇值得有名字。")
    else:
        out.append("- ❌ **未过闸,不命名**。原因：")
        for r in gate.reasons:
            out.append(f"  - {r}")
        out.append(
            "- 这是**诚实的空结果**：当前维度/样本下聚不出有解释力的结构。"
            "给它起名字就是给噪声起名字。**先补维度或补样本,不要调参数凑过闸。**"
        )
        return "\n".join(out)

    out.append("")
    out.append("### ② 已命名的剧本")
    out.append("| ID | 描述 | 成员 | 后续事实（复现次数） | 簇内最大分歧维 |")
    out.append("|---|---|---|---|---|")
    for s in scripts:
        f = s.forward
        fact = (
            f"{f.n} 次：正 {f.positive} / 负 {f.negative}，中位 {f.median}"
            if f.n else "—"
        )
        dv = "、".join(f"{lb.get(k, k)} σ{v:.1f}" for k, v in s.divergence) or "—"
        out.append(f"| `{s.script_id}` | {s.name} | {len(s.members)} | {fact} | {dv} |")

    if match is not None:
        out.append("")
        out.append("### ③ 当前落在哪个剧本")
        m = match.to_dict()
        if match.script is None:
            out.append(f"- {match.note}")
        else:
            out.append(f"- **{m['name']}**（`{m['script_id']}`，距离 {m['distance']}）")
            out.append(f"- {match.note}")
            out.append(f"- {match.script.forward.to_dict()['statement']}")

    out.append("")
    out.append(
        "- **簇内分歧维要读出来**：同一个剧本里的窗口在这些维上差别最大，"
        "它们正是「这次可能不一样」的位置。相同剧本不等于相同行情。"
    )
    out.append(
        "- 使用要求:后续事实是**小样本历史事实,不是概率预测**。"
        "禁止把复现次数说成概率;剧本只由上述维度定义,不含基本面/政策/外部事件。"
    )
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# 5. 整条链路:窗口 → 聚类 → 过闸 → 铸造剧本
# --------------------------------------------------------------------------- #
def build_scripts(
    *,
    signatures: Mapping[str, RegimeSignature],
    outcomes: Mapping[str, float],
    order: Sequence[str],
    features: Sequence[str],
    cluster_threshold: float = 1.0,
    train_ratio: float = 0.7,
    labels: Mapping[str, str] | None = None,
    min_members: int = MIN_MEMBERS,
) -> tuple[list[RegimeScript], Gate, dict[str, Any]]:
    """从一组窗口签名直接走到剧本。``order`` 必须是**时间升序**的窗口名。

    **切分按时间,不按随机。**时间序列上随机切会让同一段行情同时出现在训练和留出里,
    留出段就不再是「没见过的未来」—— 那样算出来的解释力是漏出来的,不是挣来的。

    聚类:平均连接层次聚类,与 ``river_window.cluster_windows`` 同款口径
    (距离来自 ``signature_distance``,合并顺序确定)。留出窗口**不参与切簇**,
    只按最近质心归入已有簇。
    """

    if min_members < 2:
        raise ValueError("min_members 必须至少为 2")
    if len(order) != len(set(order)):
        raise ValueError("order 中有重复窗口，训练与留出不能复用同一实例")
    if set(order) != set(signatures):
        raise ValueError("order 必须逐一列出所有签名窗口，不能缺失或多出")
    if not 0 < train_ratio < 1 or not math.isfinite(cluster_threshold) or cluster_threshold < 0:
        raise ValueError("train_ratio 必须在 (0, 1) 内，cluster_threshold 必须是非负有限数")
    if not features or len(features) != len(set(features)):
        raise ValueError("features 必须非空且不能重复")
    for w, sig in signatures.items():
        if not set(sig.stats) <= set(features):
            raise ValueError(f"窗口 {w} 含未声明的特征")
        if any(not math.isfinite(v) for pair in sig.stats.values() for v in pair):
            raise ValueError(f"窗口 {w} 的签名不是有限数值")
    seq = list(order)
    if len(seq) < min_members * 3:
        return [], Gate(None, None, None, 0, 0,
                        (f"窗口总数 {len(seq)} 太少，无法时间切分后评判",)), {}

    cut = max(min_members, int(len(seq) * train_ratio))
    train_keys, hold_keys = seq[:cut], seq[cut:]
    total_dims = len(features)

    # ── 训练段聚类（平均连接，确定性） ──
    groups: list[list[str]] = [[k] for k in train_keys]
    def avg(ga: list[str], gb: list[str]) -> float | None:
        ds = [
            d for a in ga for b in gb
            if (d := signature_distance(signatures[a], signatures[b], total_dims)) is not None
        ]
        return sum(ds) / len(ds) if ds else None

    while len(groups) > 1:
        best: tuple[float, int, int] | None = None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                a = avg(groups[i], groups[j])
                if a is not None and (best is None or a < best[0] - 1e-12):
                    best = (a, i, j)
        if best is None or best[0] > cluster_threshold:
            break
        _, i, j = best
        groups[i] = sorted(groups[i] + groups[j])
        groups.pop(j)

    groups.sort(key=lambda g: (-len(g), g[0]))
    train_assign = {w: ci for ci, g in enumerate(groups) for w in g}

    # ── 留出段：只归类，不参与切簇 ──
    centroids = {ci: _centroid([signatures[w] for w in g])[0] for ci, g in enumerate(groups)}
    hold_assign: dict[str, int] = {}
    for w in hold_keys:
        scored = [
            (d, ci) for ci, c in centroids.items()
            if (d := signature_distance(signatures[w], c, total_dims)) is not None
        ]
        if scored:
            hold_assign[w] = min(scored)[1]

    scripts, gate = mint_scripts(
        train={w: signatures[w] for w in train_keys},
        train_assignments=train_assign,
        holdout_assignments=hold_assign,
        holdout_outcomes={w: outcomes[w] for w in hold_keys if w in outcomes},
        train_outcomes={w: outcomes[w] for w in train_keys if w in outcomes},
        features=features,
        labels=labels,
        min_members=min_members,
    )
    split = {
        "split": "按时间，非随机（随机切会让同段行情同时进训练和留出，解释力是漏出来的）",
        "n_windows": len(seq),
        "train": [train_keys[0], train_keys[-1]] if train_keys else [],
        "holdout": [hold_keys[0], hold_keys[-1]] if hold_keys else [],
        "n_train_clusters": len(groups),
        "cluster_threshold": cluster_threshold,
    }
    return scripts, gate, split
