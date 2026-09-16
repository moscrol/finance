"""代码白名单上的纯 ``predict_fn(projection) -> p``（spec 03 §6）。

service 不动态加载代码；runner 只能从这张表取函数。每个 recipe 绑定一个内容哈希
（写进 ``ProbabilityForecast.probability_recipe_hash``），改配方 = 新 recipe_id + 新哈希。
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from intelligence.services.research_validation.baseline import TWO_BUCKET_RECIPE_HASH
from intelligence.services.research_validation.contracts import ContractError, is_probability

PredictFn = Callable[[Mapping[str, Any]], "float | None"]


def predict_two_bucket(projection: Mapping[str, Any]) -> float | None:
    """规则二桶：condition True/False → 对应桶的平滑概率；condition 未知 → None（不出预测）。"""
    condition = projection.get("condition")
    if condition is None:
        return None
    if not isinstance(condition, bool):
        raise ContractError(f"projection.condition 必须是 bool 或 None，得到 {condition!r}")
    bucket_p = projection.get("bucket_p")
    if not isinstance(bucket_p, Mapping):
        raise ContractError("projection.bucket_p 缺失")
    p = bucket_p.get("true" if condition else "false")
    if p is None:
        return None
    if not is_probability(p):
        raise ContractError(f"桶概率不是概率：{p!r}")
    return float(p)


RECIPES: dict[str, tuple[PredictFn, str]] = {
    "rule_two_bucket/v1": (predict_two_bucket, TWO_BUCKET_RECIPE_HASH),
}


def resolve_recipe(recipe_id: Any) -> tuple[PredictFn, str]:
    if recipe_id not in RECIPES:
        raise ContractError(f"recipe {recipe_id!r} 不在代码白名单 {sorted(RECIPES)}")
    return RECIPES[recipe_id]


__all__ = ["RECIPES", "PredictFn", "predict_two_bucket", "resolve_recipe"]
