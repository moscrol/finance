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
    - **后续终点只报事实**：每段类比窗口之后 5/10/20 交易日的指数累计涨跌、
      日均涨停、最高连板、日均双红题材数——全部来自库内逐日行，非 LLM 生成。
    - 缺数（库不可用/历史太短/维度缺失）显式声明，禁止外推。
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from intelligence.paths import default_market_db_path
from intelligence.services import retrieval_cache
from intelligence.services import reading_baseline
# 取数层 2026-09-05 下沉到 market_feature_store（赚钱效应 regime 与 D10 共用），
# 这里 re-export 保住既有 import 路径与 `_AUX_QUERIES` 的棘轮测试。
from market_feature_store.market_regime_vectors import (  # noqa: F401
    _AUX_QUERIES,
    FEATURES,
    load_market_regime_vector_result,
    load_market_regime_vectors,
)

DEFAULT_MARKET_DB_PATH = default_market_db_path()

DEFAULT_WINDOW = 20
STRIDE = 5
TOP_K = 3
FORWARD_HORIZONS = (5, 10, 20)
MIN_HISTORY_MULTIPLE = 3  # 与 D8 一致：历史至少 3 个窗口长度才谈得上找类比

# 展示层用的中文标签（渲染当前/历史窗口摘要时用原始量纲，可读性优先）
_DISPLAY_FEATURES: tuple[tuple[str, str, str], ...] = (
    ("total_amount", "成交额", "亿"),
    ("limit_up", "涨停", "家"),
    ("max_boards", "最高连板", "板"),
    ("double_red_theme_count", "双红题材", "个"),
    ("sh_deviation_pct", "偏离度", "%"),
)

_MIN_FEATURE_COVERAGE = 0.6  # 非空日下限为 max(1, int(n * 此值))；整数截断，不向上取整
_DELTA_WEIGHT = 0.5          # 首尾段变化项相对全窗均值项的权重
_STD_EPSILON = 1e-9
END_SEGMENT_EPSILON = 0.3  # 沿用 river 首尾段方向界线，不改变签名或距离


def end_segment_direction(delta: float | None) -> str | None:
    """首尾段差的类别；闭区间[-0.3, 0.3]近零，未知/非有限值不分类。"""
    if delta is None or not math.isfinite(delta):
        return None
    return "increase" if delta > END_SEGMENT_EPSILON else ("decrease" if delta < -END_SEGMENT_EPSILON else "near_zero")


def direction_relation_label(relation: str | None) -> str | None:
    """模型摘要用一一对应的中文类别；完整对象保留原英文类别，None仍未知。"""
    return {
        "same": "同向", "opposite": "反向",
        "one_near_zero": "一方近零", "both_near_zero": "双方近零",
    }[relation] if relation is not None else None


def end_segment_direction_relation(a: float | None, b: float | None) -> str | None:
    """只比较同一维的两个未舍入首尾段差，不认证持续路径或距离贡献。"""
    left, right = end_segment_direction(a), end_segment_direction(b)
    if left is None or right is None:
        return None
    if left == right:
        return "both_near_zero" if left == "near_zero" else "same"
    return "one_near_zero" if "near_zero" in (left, right) else "opposite"


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
    segments: dict[str, dict[str, float | int | None]] = field(default_factory=dict, compare=False)
    window_days: int | None = field(default=None, compare=False)

    def to_payload(self) -> dict[str, Any]:
        return {
            "representation": "mean_and_end_segments",
            "path_evidence": "not_provided",
            "window_days": self.window_days,
            "eligibility": signature_eligibility(self.window_days) if self.window_days is not None else None,
            "features": {
                f: {**self.segments.get(f, {}), "z_mean": m, "end_segment_delta": t}
                for f, (m, t) in self.stats.items()
            },
        }

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
    # 兼容旧字段/标记；strict 只核对基表记录时间，不认证辅表或逐日历史可知性。
    knowledge_cutoff: str | None = None
    pit_grade: str | None = None
    # missing_features 保留旧的全局退出列表；具体原因以以下互斥字段为准。
    query_failed_features: tuple[str, ...] = ()
    empty_features: tuple[str, ...] = ()
    constant_features: tuple[str, ...] = ()
    active_features: tuple[str, ...] = ()
    current_signature_features: tuple[str, ...] = ()
    current_missing_features: tuple[str, ...] = ()
    current_feature_counts: dict[str, int] = field(default_factory=dict)
    current_window: tuple[str, str] | None = None
    standardization_window: tuple[str, str] | None = None
    current_signature: RegimeSignature | None = None
    selection: dict[str, Any] = field(default_factory=dict)
    feature_observations: dict[str, dict[str, Any]] = field(default_factory=dict)
    current_summary_coverage: dict[str, Any] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return bool(self.analogs)

    def model_payload(self) -> dict[str, Any]:
        """列名共享的表形投影；值与身份均来自同一结果，不解析展示文本。"""
        signatures = [("current", self.current_signature.to_payload() if self.current_signature else None)]
        summaries = [("current", self.current_summary, self.current_summary_coverage)]
        candidates = {}
        relations = {}
        forward_rows = []
        forward_columns = ["window_id", "horizon", "start_date", "end_date", "sh_index_cum_pct",
                           "avg_limit_up", "max_boards", "avg_double_red_themes",
                           "index_days", "limit_up_days", "boards_days", "double_red_days"]
        for a in self.analogs:
            wid = a.get("window_id", f"d10:{a['start_date']}:{a['end_date']}")
            signatures.append((wid, a.get("signature")))
            relations[wid] = a.get("direction_relations", {})
            summaries.append((wid, a.get("raw_summary", {}), a.get("raw_summary_coverage", {})))
            candidates[wid] = {k: a[k] for k in ("distance", "shared_dims", "active_dims", "missing_features",
                                                "pit_grade") if k in a}
            for horizon, fwd in a["forwards"].items():
                counts = fwd.get("observed_days", {}) if fwd else {}
                forward_rows.append([wid, horizon,
                    *[fwd.get(k) if fwd else None for k in forward_columns[2:8]],
                    *[counts.get(k) for k in ("sh_index_pct_chg", "limit_up", "max_boards", "double_red_theme_count")]])
        readings = signature_table(signatures)
        readings["columns"].append("direction_relation")
        for wid, rows in readings["windows"].items():
            for row in rows:
                row.append(direction_relation_label(relations.get(wid, {}).get(row[0])))
        summary_readings = raw_summary_table(summaries)
        # 原值均值及分母已经在签名表的，不重复发送；只补签名之外的展示维。
        for wid, rows in summary_readings["windows"].items():
            signed = {row["feature"]: (row["raw_mean"], row["non_null_days"])
                      for values in readings["windows"].get(wid, [])
                      for row in [{**readings["defaults"], **dict(zip(readings["columns"], values, strict=True))}]}
            summary_readings["windows"][wid] = [row for row in rows if signed.get(row[0]) != tuple(row[1:])]
        summary_readings["scope"] = "signature_supplement"
        payload = rounded_readout({
            "set": "d10", "current_window": self.current_window,
            "fit_window": self.standardization_window,
            "cutoff": self.knowledge_cutoff, "pit_grade": self.pit_grade,
            "selection": {**self.selection, "displayed_count": len(self.analogs)},
            "raw_summaries": summary_readings,
            "current_missing_features": self.current_missing_features,
            "current_gap_days": {f: self.current_feature_counts.get(f) for f in self.current_missing_features},
            "candidates": candidates,
            "forwards": {"columns": forward_columns, "rows": forward_rows},
            "candidate_relations": self.to_payload()["candidate_relations"],
            "signatures": readings,
            "feature_observations": observation_table(self.feature_observations),
        })
        payload = labeled_readout(payload, _FEATURE_LABELS)
        payload["feature_keys"] = {v: k for k, v in _FEATURE_LABELS.items()}
        return bind_model_windows(payload, [
            (a.get("window_id", f"d10:{a['start_date']}:{a['end_date']}"), a["start_date"], a["end_date"])
            for a in self.analogs
        ])

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "knowledge_cutoff": self.knowledge_cutoff,
            "pit_grade": self.pit_grade,
            "window": self.window,
            "available": self.available,
            "current_summary": dict(self.current_summary),
            "current_summary_coverage": self.current_summary_coverage,
            "analogs": list(self.analogs),
            "missing_features": list(self.missing_features),
            "query_failed_features": list(self.query_failed_features),
            "empty_features": list(self.empty_features),
            "constant_features": list(self.constant_features),
            "active_features": list(self.active_features),
            "current_signature_features": list(self.current_signature_features),
            "current_missing_features": list(self.current_missing_features),
            "current_feature_counts": dict(self.current_feature_counts),
            "current_window": self.current_window,
            "standardization_window": self.standardization_window,
            "degrade_reason": self.degrade_reason,
            "current_signature": self.current_signature.to_payload() if self.current_signature else None,
            "selection": {**self.selection, "displayed_count": len(self.analogs)},
            "candidate_relations": window_relations([
                (a["window_id"], a["start_date"], a["end_date"]) for a in self.analogs
                if "window_id" in a
            ]),
            "feature_observations": self.feature_observations,
        }


def bind_model_windows(payload: dict[str, Any], windows: list[tuple[str, str, str]]) -> dict[str, Any]:
    """模型投影内用局部引用连表，日期只存一次；不是跨候选集的名次或全局ID。"""
    refs = {wid: f"{payload['set']}.{i + 1}" for i, (wid, _, _) in enumerate(windows)}
    payload["windows"] = {refs[wid]: [start, end] for wid, start, end in windows}
    payload["candidates"] = {refs[wid]: values for wid, values in payload["candidates"].items()}
    for name in ("signatures", "raw_summaries"):
        if name not in payload:
            continue
        for key in ("windows", "window_days"):
            payload[name][key] = {refs.get(wid, wid): values for wid, values in payload[name][key].items()}
    for row in payload.get("forwards", {}).get("rows", []):
        row[0] = refs[row[0]]
    candidates = payload["candidates"]
    columns = list(dict.fromkeys(k for c in candidates.values() for k in c))
    payload["candidates"] = {
        "columns": columns, "windows": {ref: [c.get(k) for k in columns] for ref, c in candidates.items()},
    }
    for pair in payload["candidate_relations"]:
        pair["a"], pair["b"] = refs[pair["a"]], refs[pair["b"]]
    return payload


def labeled_readout(payload: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    """只翻译合同中声明为特征键的位置，不能替换schema键/窗口身份/显示名。"""
    def names(values):
        return [labels.get(v, v) for v in values]

    def keys(values):
        return {labels.get(k, k): v for k, v in values.items()}

    for name in ("signatures", "raw_summaries"):
        for rows in payload.get(name, {}).get("windows", {}).values():
            for row in rows:
                row[0] = labels.get(row[0], row[0])
    observations = payload["feature_observations"]
    observations["features"] = keys(observations["features"])
    observations["overrides"] = {field: keys(values) for field, values in observations.get("overrides", {}).items()}
    payload["current_missing_features"] = names(payload["current_missing_features"])
    if "current_gap_days" in payload:
        payload["current_gap_days"] = keys(payload["current_gap_days"])
    for candidate in payload["candidates"].values():
        for key in ("missing_features", "only_current", "only_candidate"):
            if key in candidate:
                candidate[key] = names(candidate[key])
    structure = payload.get("dimension_structure")
    if structure:
        structure["groups"] = [names(group) for group in structure["groups"]]
        structure["undetermined"] = [[*names(pair[:2]), pair[2]] for pair in structure["undetermined"]]
    return payload


def rounded_readout(value: Any) -> Any:
    """只在对外显示时舍入；不回写计算对象或改变分类。"""
    if isinstance(value, float):
        rounded = round(value, 3)
        return int(rounded) if rounded.is_integer() else rounded
    if isinstance(value, dict):
        return {k: rounded_readout(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [rounded_readout(v) for v in value]
    return value


def raw_summary_table(
    summaries: list[tuple[str, dict[str, float | None], dict[str, Any]]],
) -> dict[str, Any]:
    """均值及同一组原值行的分母一起投影；旧原件缺计数时保持未知。"""
    return {
        "aggregation": "mean_over_non_null",
        "columns": ["feature", "raw_mean", "non_null_days"],
        "window_days": {wid: coverage.get("input_days") for wid, _, coverage in summaries},
        "windows": {wid: [[feature, mean, coverage.get("non_null_days", {}).get(feature)]
                          for feature, mean in summary.items()]
                    for wid, summary, coverage in summaries},
    }


def signature_eligibility(window_days: int) -> dict[str, int]:
    """签名实际使用的整数准入门槛；部分覆盖可准入，不要求每段完整。"""
    return {
        "min_non_null_days": max(1, int(window_days * _MIN_FEATURE_COVERAGE)),
        "segment_days": max(1, window_days // 3),
        "min_head_days": 1, "min_tail_days": 1,
    }


def signature_table(signatures: list[tuple[str, dict[str, Any] | None]]) -> dict[str, Any]:
    """投影摘要与覆盖；完全相同的计数列提为defaults，不根据窗口长度猜值。"""
    columns = ["feature", "raw_mean", "z_mean", "end_segment_delta", "non_null_days", "head_days", "tail_days"]
    values = [v for _, signature in signatures if signature for v in signature["features"].values()]
    defaults = {key: values[0].get(key) for key in columns[4:]
                if len(values) >= 2 and all(v.get(key) == values[0].get(key) for v in values)}
    columns = [key for key in columns if key not in defaults]
    return {
        "representation": "mean_and_end_segments", "path_evidence": "not_provided",
        "defaults": defaults,
        "omitted": ["head_tail_level_means", "daily_path"],
        "window_days": {wid: signature.get("window_days") for wid, signature in signatures if signature},
        "eligibility_by_window_days": {str(signature["window_days"]): signature.get("eligibility")
                                       for _, signature in signatures
                                       if signature and signature.get("window_days") is not None
                                       and signature.get("eligibility") is not None},
        "columns": columns,
        "windows": {wid: [[feature, *[values.get(k) for k in columns[1:]]]
                          for feature, values in signature["features"].items()]
                    for wid, signature in signatures if signature},
    }


def observation_table(observations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """重复状态列提为默认值+逐特征例外；None也原样保存，不按状态猜覆盖。"""
    columns = ["source", "unit", "non_null_days"]
    defaults = {}
    overrides = {}
    for key in ("read_status", "comparison_status", "missing_policy"):
        values = [o.get(key) for o in observations.values()]
        if not values:
            continue
        defaults[key] = max(dict.fromkeys(values), key=values.count)
        different = {f: o.get(key) for f, o in observations.items() if o.get(key) != defaults[key]}
        if different:
            overrides[key] = different
    return {"input_days": next(iter(observations.values()), {}).get("input_days"), "columns": columns,
            "defaults": defaults, "overrides": overrides,
            "features": {f: [o.get(k) for k in columns] for f, o in observations.items()}}


def window_relations(windows: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
    """本次结果内具名闭区间的逐对交集；不推断统计独立。"""
    return [
        {"a": aid, "b": bid, "overlap": max(a0, b0) <= min(a1, b1)}
        for i, (aid, a0, a1) in enumerate(windows)
        for bid, b0, b1 in windows[i + 1:]
    ]


def standardize_vectors(
    vectors: list[dict[str, Any]],
    features: tuple[str, ...] = FEATURES,
) -> tuple[list[dict[str, float | None]], list[str]]:
    """兼容二元返回：全空/近常量都退出，z 行保留 None；退出不等于表无数据。"""
    rows, reasons = _standardize_vectors_with_reasons(vectors, features)
    return rows, list(reasons)


def _standardize_vectors_with_reasons(
    vectors: list[dict[str, Any]],
    features: tuple[str, ...] = FEATURES,
) -> tuple[list[dict[str, float | None]], dict[str, str]]:
    """同一标准化计算保留退出原因；只描述实际输入范围，不推断源表是否存在。"""
    reasons: dict[str, str] = {}
    stats: dict[str, tuple[float, float]] = {}
    for feat in features:
        values = [float(row[feat]) for row in vectors if row.get(feat) is not None]
        if not values:
            reasons[feat] = "empty"
            continue
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        std = var ** 0.5
        if std < _STD_EPSILON:
            reasons[feat] = "constant"
            continue
        stats[feat] = (mean, std)
    z_rows: list[dict[str, float | None]] = []
    for row in vectors:
        z_row: dict[str, float | None] = {}
        for feat, (mean, std) in stats.items():
            raw = row.get(feat)
            z_row[feat] = None if raw is None else (float(raw) - mean) / std
        z_rows.append(z_row)
    return z_rows, reasons


def window_signature(
    z_rows: list[dict[str, float | None]],
    features: tuple[str, ...] = FEATURES,
    *,
    raw_rows: list[dict[str, Any]] | None = None,
) -> RegimeSignature:
    """窗口签名：每维（z 均值, z 末段均值−首段均值）；覆盖率不足的维不进签名。"""
    n = len(z_rows)
    if raw_rows is not None and len(raw_rows) != n:
        raise ValueError("原值与标准化行必须逐日对应")
    requirements = signature_eligibility(n)
    seg = requirements["segment_days"]
    stats: dict[str, tuple[float, float]] = {}
    segments: dict[str, dict[str, float | int | None]] = {}
    for feat in features:
        values = [(i, row[feat]) for i, row in enumerate(z_rows) if row.get(feat) is not None]
        if len(values) < requirements["min_non_null_days"]:
            continue
        vals = [v for _, v in values]
        mean = sum(vals) / len(vals)
        head = [v for i, v in values if i < seg]
        tail = [v for i, v in values if i >= n - seg]
        if len(head) < requirements["min_head_days"] or len(tail) < requirements["min_tail_days"]:
            continue
        head_mean, tail_mean = sum(head) / len(head), sum(tail) / len(tail)
        stats[feat] = (mean, tail_mean - head_mean)
        segments[feat] = {
            "head_mean": head_mean, "tail_mean": tail_mean,
            "non_null_days": len(vals), "window_days": n,
            "head_days": len(head), "tail_days": len(tail), "segment_days": seg,
        }
        if raw_rows is not None:
            for key, rows in (("raw_mean", raw_rows), ("raw_head_mean", raw_rows[:seg]),
                              ("raw_tail_mean", raw_rows[n - seg:])):
                raw = [float(r[feat]) for r in rows if r.get(feat) is not None]
                segments[feat][key] = sum(raw) / len(raw) if raw else None
    return RegimeSignature(stats, segments, window_days=n)


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
    """兼容原有值读取；生产对象同时携带下面同源计算的分母。"""
    return _raw_window_summary_with_coverage(rows, features)[0]


def _raw_window_summary_with_coverage(
    rows: list[dict[str, Any]],
    features: tuple[tuple[str, str, str], ...] = _DISPLAY_FEATURES,
) -> tuple[dict[str, float | None], dict[str, Any]]:
    """展示维独立于标准化准入；常量/缺维的原值观测不能随签名退出丢失。"""
    summary: dict[str, float | None] = {}
    counts: dict[str, int] = {}
    for feat, _, _ in features:
        vals = [float(r[feat]) for r in rows if r.get(feat) is not None]
        summary[feat] = (sum(vals) / len(vals)) if vals else None
        counts[feat] = len(vals)
    return summary, {"input_days": len(rows), "non_null_days": counts}


def _forward_facts(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any] | None:
    """后续 horizon 个输入交易日的终点及摘要；行数不足None，缺日收益不跳过。"""
    if len(rows) < horizon:
        return None
    seg = rows[:horizon]
    pcts = [float(r["sh_index_pct_chg"]) for r in seg if r.get("sh_index_pct_chg") is not None]
    cum: float | None = None
    if len(pcts) == horizon:
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
        "horizon": horizon,
        "start_date": seg[0].get("trade_date"), "end_date": seg[-1].get("trade_date"),
        "observed_days": {
            "sh_index_pct_chg": len(pcts), "limit_up": len(limit_ups),
            "max_boards": len(boards), "double_red_theme_count": len(double_red),
        },
        "sh_index_cum_pct": cum,
        "avg_limit_up": (sum(limit_ups) / len(limit_ups)) if limit_ups else None,
        "max_boards": max(boards) if boards else None,
        "avg_double_red_themes": (sum(double_red) / len(double_red)) if double_red else None,
    }


def window_pit_grade(rows: list[dict[str, Any]]) -> str | None:
    """一段逐日向量的 PIT 档位：每行都 strict 才 strict；任一行 trade_date_only 整段降档；行上没带 → None。"""
    grades = [r.get("pit_grade") for r in rows]
    if not rows or any(g is None for g in grades):
        return None
    return "strict" if all(g == "strict" for g in grades) else "trade_date_only"


def find_regime_analogs(
    vectors: list[dict[str, Any]],
    window: int = DEFAULT_WINDOW,
    stride: int = STRIDE,
    top_k: int = TOP_K,
) -> tuple[RegimeSignature | None, list[dict[str, Any]], list[str]]:
    """vectors 为升序全历史每日情绪向量（含 trade_date 键）。

    返回（当前窗口签名, 最相似的 K 段互不重叠历史窗口, 全局退出特征名，含常量）。
    历史窗口须与当前窗口不重叠；每段带后续 5/10/20 日事实。
    """
    n = len(vectors)
    if n < window * MIN_HISTORY_MULTIPLE:
        return None, [], []
    z_rows, dropped = standardize_vectors(vectors)
    return _find_regime_analogs(vectors, z_rows, dropped, window=window, stride=stride, top_k=top_k)


def _find_regime_analogs(
    vectors: list[dict[str, Any]],
    z_rows: list[dict[str, float | None]],
    dropped: list[str],
    *,
    window: int,
    stride: int = STRIDE,
    top_k: int = TOP_K,
    selection: dict[str, Any] | None = None,
) -> tuple[RegimeSignature | None, list[dict[str, Any]], list[str]]:
    """共享一次标准化后的匹配；在生产候选的同一循环记录范围，不二次复算。"""
    if selection is not None:
        selection.update(strategy="distance_greedy_nonoverlap", requested_top=top_k,
                         stride=stride, window_days=window, generated_count=0, comparable_count=0,
                         generation="range(0,n-2*window,stride); stop exclusive")
    n = len(vectors)
    if n < window * MIN_HISTORY_MULTIPLE:
        return None, [], dropped
    current = window_signature(z_rows[n - window:], raw_rows=vectors[n - window:])
    if not current.stats:
        return None, [], dropped
    total_dims = len(FEATURES) - len(dropped)
    candidates: list[tuple[float, int]] = []
    for start in range(0, n - 2 * window, stride):
        if selection is not None:
            selection["generated_count"] += 1
        sig = window_signature(z_rows[start:start + window])
        d = signature_distance(current, sig, total_dims)
        if d is not None:
            candidates.append((d, start))
    candidates.sort()
    if selection is not None:
        selection["comparable_count"] = len(candidates)
    picked: list[dict[str, Any]] = []
    used: list[tuple[int, int]] = []
    for d, start in candidates:
        end = start + window
        if any(not (end <= s or start >= e) for s, e in used):
            continue
        seg = vectors[start:end]
        candidate = window_signature(z_rows[start:end], raw_rows=seg)
        shared = [f for f in current.stats if f in candidate.stats]
        forwards: dict[int, dict[str, Any] | None] = {
            h: _forward_facts(vectors[end:], h) for h in FORWARD_HORIZONS
        }
        summary, coverage = _raw_window_summary_with_coverage(seg)
        picked.append(
            {
                "window_id": f"d10:{seg[0]['trade_date']}:{seg[-1]['trade_date']}",
                "signature": candidate.to_payload(),
                "direction_relations": {
                    f: end_segment_direction_relation(current.stats[f][1], candidate.stats[f][1])
                    for f in shared
                },
                "start_date": str(seg[0]["trade_date"]),
                "end_date": str(seg[-1]["trade_date"]),
                "distance": round(d, 3),
                "shared_features": shared,
                "shared_dims": len(shared),
                "active_dims": total_dims,
                "missing_features": [f for f in FEATURES if f not in dropped and f not in candidate.stats],
                "raw_summary": summary,
                "raw_summary_coverage": coverage,
                "forwards": forwards,
                # 段级 PIT：窗内任一天不是 strict 整段降档（#35；污点传播）。向量没带 pit_grade 时为 None。
                "pit_grade": window_pit_grade(seg),
            }
        )
        used.append((start, end))
        if len(picked) >= top_k:
            break
    return current, picked, dropped


# ---------------------------------------------------------------------------
# 取数层（FEATURES / _AUX_QUERIES / load_market_regime_vectors）已下沉到
# market_feature_store.market_regime_vectors，本模块顶部 re-export；这里只留装配。
# ---------------------------------------------------------------------------


def load_market_regime_artifact(
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
    as_of: date | str | None = None,
    knowledge_cutoff: date | str | None = None,
) -> MarketRegimeArtifact:
    """``knowledge_cutoff`` 缺省 = ``as_of``（站在 as_of 那天回看）；两者都空 → 不判 PIT（``pit_grade=None``，老路径）。"""
    cutoff = knowledge_cutoff if knowledge_cutoff is not None else as_of
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
        loaded = load_market_regime_vector_result(con, as_of=as_of, knowledge_cutoff=cutoff)
        vectors = loaded.vectors
        if not vectors:
            return MarketRegimeArtifact(
                window, {}, (), FEATURES,
                query_failed_features=loaded.query_failed_features,
                degrade_reason=("D10 fact_market_daily 查询失败（表/列缺失或读取失败）"
                                if loaded.status == "query_failed" else "D10 fact_market_daily 截止范围内无行"),
            )
        z_rows, reasons = _standardize_vectors_with_reasons(vectors)
        selection: dict[str, Any] = {}
        current, analogs, dropped = _find_regime_analogs(
            vectors, z_rows, list(reasons), window=window, selection=selection,
        )
        failed = loaded.query_failed_features
        all_missing = tuple(dict.fromkeys([*failed, *dropped]))
        active = tuple(f for f in FEATURES if f not in reasons)
        current_stats = window_signature(z_rows[-window:]).stats
        diagnostics = {
            "current_signature": current,
            "selection": selection,
            "feature_observations": {
                f: {
                    "source": _FEATURE_SOURCES[f], "unit": _FEATURE_UNITS[f],
                    "read_status": "query_failed" if f in failed else "queried",
                    "non_null_days": sum(r.get(f) is not None for r in vectors),
                    "input_days": len(vectors),
                    "comparison_status": "query_failed" if f in failed else reasons.get(f, "active"),
                    "missing_policy": ("无分组为缺失；不证明完整题材宇宙覆盖"
                                       if f == "double_red_theme_count" else "null_unknown"),
                } for f in FEATURES
            },
            "query_failed_features": failed,
            "empty_features": tuple(f for f, reason in reasons.items() if reason == "empty" and f not in failed),
            "constant_features": tuple(f for f, reason in reasons.items() if reason == "constant"),
            "active_features": active,
            "current_signature_features": tuple(current_stats),
            "current_missing_features": tuple(f for f in active if f not in current_stats),
            "current_feature_counts": {f: sum(r.get(f) is not None for r in vectors[-window:]) for f in active},
            "current_window": (str(vectors[max(0, len(vectors) - window)]["trade_date"]), str(vectors[-1]["trade_date"])),
            "standardization_window": (str(vectors[0]["trade_date"]), str(vectors[-1]["trade_date"])),
        }
        if current is None or not analogs:
            return MarketRegimeArtifact(
                window, {}, (), all_missing,
                degrade_reason="D10 历史不足或无可比情绪窗口", **diagnostics,
            )
        current_pit = window_pit_grade(vectors[-window:])
        analog_pits = [a.get("pit_grade") for a in analogs]
        overall: str | None
        if current_pit is None or any(p is None for p in analog_pits):
            overall = None
        else:
            overall = "strict" if current_pit == "strict" and all(p == "strict" for p in analog_pits) else "trade_date_only"
        summary, coverage = _raw_window_summary_with_coverage(vectors[-window:])
        return MarketRegimeArtifact(
            window,
            summary,
            tuple(analogs),
            all_missing,
            knowledge_cutoff=(str(cutoff)[:10] if cutoff is not None else None),
            pit_grade=overall,
            current_summary_coverage=coverage,
            **diagnostics,
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


def _fwd_text(fwd: dict[str, Any] | None, *, horizon: int) -> str:
    if fwd is None:
        return "—"
    coverage = fwd.get("observed_days", {}).get("sh_index_pct_chg")
    gap = f"；日收益覆盖{coverage}/{horizon}，完整终点不可计算" if coverage is not None and coverage < horizon else ""
    return (
        f"上证指数累计终点收益{_fmt(fwd['sh_index_cum_pct'], 2)}%（后续{horizon}交易日{gap}）"
        f"/日均涨停{_fmt(fwd['avg_limit_up'], 0)}家"
        f"/最高{_fmt(fwd['max_boards'], 0)}板/日均双红{_fmt(fwd['avg_double_red_themes'], 1)}个"
    )


_FEATURE_SOURCES = {
    **{f: f"fact_market_daily.{f}" for f in FEATURES if f not in _AUX_QUERIES},
    "max_boards": "fact_limit_advance_daily.boards:MAX",
    "double_red_theme_count": "fact_sector_daily:WHERE DOUBLE_RED_SQL再逐日COUNT",
    "top1_theme_share": "fact_theme_limit_heat_daily.market_share:MAX (all ranks)",
    "new_high_count": "fact_stock_high_daily:COUNT GROUP BY trade_date",
}

_FEATURE_UNITS = {
    "total_amount": "亿元", "advancers": "家", "limit_up": "家", "limit_down": "家",
    "sh_deviation_pct": "%", "sh_index_pct_chg": "%", "max_boards": "板",
    "double_red_theme_count": "个", "top1_theme_share": "源字段market_share，未核验比例尺度",
    "new_high_count": "家",
}

_FEATURE_LABELS = {
    "total_amount": "成交额",
    "advancers": "涨家数",
    "limit_up": "涨停数",
    "limit_down": "跌停数",
    "sh_deviation_pct": "偏离度",
    "sh_index_pct_chg": "指数日涨跌",
    "max_boards": "连板高度",
    "double_red_theme_count": "双红题材数",
    "top1_theme_share": "首题材涨停份额",
    "new_high_count": "新高家数",
}


class _ReadoutDumper(yaml.SafeDumper):
    def choose_scalar_style(self):
        # YAML normalizes unescaped NEL; quote Unicode line separators so
        # labels and source strings survive a JSON -> YAML -> JSON round trip.
        if any(char in self.event.value for char in ("\x85", "\u2028", "\u2029")):
            return '"'
        return super().choose_scalar_style()

    def write_indicator(self, indicator, need_whitespace, whitespace=False, indention=False):
        # Flow collections permit adjacent entries: [a,b]. Keep YAML's
        # scalar quoting/type rules, only omit the optional comma space.
        super().write_indicator(indicator, need_whitespace, whitespace or indicator == ",", indention)


def model_readout_block(payload: dict[str, Any]) -> str:
    """Lossless flow YAML avoids quoting every JSON key again inside a claim string."""
    json.dumps(payload, ensure_ascii=False, allow_nan=False)
    text = yaml.dump(payload, Dumper=_ReadoutDumper, allow_unicode=True, default_flow_style=True,
                     sort_keys=False, width=100_000).rstrip()
    return f"```yaml\n{text}\n```"


def regime_block_for_llm(
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
    as_of: date | str | None = None,
) -> str:
    """把市场情绪环境类比渲染成带 [D10] 引用编号的确定性数据块（空串=未取到）。"""
    artifact = load_market_regime_artifact(market_db_path, window=window, as_of=as_of)
    if not artifact.available:
        return ""
    return "\n".join([
        "## 市场情绪环境类比块 [D10]",
        *reading_baseline.block_rule_lines("D10"),
        "- 后续5交易日/后续10交易日/后续20交易日按输入序列，未证源日完整；sh_index_cum_pct=上证终点收益%(日收益须齐全)，其余=非空日均涨停/最高板/日均双红。"
        "终点收益不描述区间内的涨跌路径；同期限非缺失终点收益大于0可报样本频率分子/分母，显示0不猜原值正负，不是概率预测。",
        "- 两表共用读法：fit_window含当前窗，非留出；z非绝对占比高低/冷暖，首题材份额非全题材集中度。"
        "raw_mean/z_mean=非空原值/z均值，end_segment_delta=末减首三分之一z均值，非路径；*_days=非空分母，window_days=输入数。"
        "eligibility_by_window_days给段长/门槛，部分首尾段覆盖可准入；raw_summaries补签名外均值/分母。",
        f"- direction_relation按未舍入首尾差±{END_SEGMENT_EPSILON}(含边界近零)对current共有维分类，null未比较；非贡献档。",
        "- defaults/overrides=默认/例外；query_failed查询失败/empty范围无非空/constant近常量退出(std<1e-9)/active可标准化。"
        "全局退出不进分母，窗口缺维用共有维覆盖惩罚；current_gap_days=缺维非空数；null_unknown未知，queried不证全源覆盖，不补零。",
        "- 选择规则/规模见selection；windows为本块闭区间，交集不证独立；显示3位。",
        "- PIT仅核fact_market_daily.updated_at对本cutoff，strict不等于逐日历史可知，辅表未核；trade_date_only可能晚于截止、缺失或不可解析，不能区分首次迟入库与覆盖修订，不授予回放/校准资格。",
        model_readout_block(artifact.model_payload()),
    ])
