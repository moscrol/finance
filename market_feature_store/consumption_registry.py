"""数据消费 registry 的加载与一致性校验。

registry 是 YAML（``consumption_registry.yaml``），三个消费者：同步管线读
``plans``（哪一档跑哪些步骤）、agent 查询层读 ``recipes``（怎么联立、何时主动）、
人读整份当文档。本模块只负责两件事：

1. 把 YAML 读成结构化对象；
2. 校验它没有漂：档位名合法、引用的表在 ``schema.sql`` 里真的存在、
   计划里的每个步骤都归属某个数据族（infrastructure 步骤除外）。

与 ``run_review_sync.build_plan`` 的一致性不在这里做——那份代码在 skills/ 下，
由 ``tests/test_consumption_registry.py`` 把两边拼起来比对，registry 不反向依赖管线。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

import yaml

PACKAGE_DIR = Path(__file__).resolve().parent
REGISTRY_PATH = PACKAGE_DIR / "consumption_registry.yaml"
SCHEMA_PATH = PACKAGE_DIR / "schema.sql"

TIERS = ("A-replace", "B-identity", "C-daily", "D-derived")
RECIPE_STATUSES = ("live", "note", "pending-grilling")
PLANS = ("full", "cheap")

_DDL_OBJECT = re.compile(
    r"CREATE\s+(?:TABLE\s+IF\s+NOT\s+EXISTS|OR\s+REPLACE\s+VIEW|VIEW\s+IF\s+NOT\s+EXISTS|TABLE)\s+"
    r'"?([A-Za-z_][A-Za-z0-9_]*)"?',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Dataset:
    key: str
    label: str
    tables: tuple[str, ...]
    tier: str
    policy: str
    steps: dict[str, tuple[str, ...]] = field(default_factory=dict)
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class Recipe:
    key: str
    question: str
    status: str
    joins: tuple[str, ...]
    proactive: str
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class Registry:
    datasets: tuple[Dataset, ...]
    recipes: tuple[Recipe, ...]
    plans: dict[str, tuple[str, ...]]
    infrastructure_steps: tuple[str, ...]
    meta: dict
    tiers: dict[str, str]

    def steps_for(self, plan: str) -> tuple[str, ...]:
        if plan not in self.plans:
            raise KeyError(f"unknown plan {plan!r}; known: {', '.join(sorted(self.plans))}")
        return self.plans[plan]

    def dataset(self, key: str) -> Dataset:
        for ds in self.datasets:
            if ds.key == key:
                return ds
        raise KeyError(key)

    def datasets_for_step(self, step: str, plan: str) -> tuple[Dataset, ...]:
        return tuple(ds for ds in self.datasets if step in ds.steps.get(plan, ()))


def _as_tuple(value) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


def load_registry(path: Path = REGISTRY_PATH) -> Registry:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    datasets = []
    for item in data.get("datasets") or []:
        refresh = item.get("refresh") or {}
        steps_raw = item.get("steps") or {}
        datasets.append(
            Dataset(
                key=str(item["key"]),
                label=str(item.get("label") or item["key"]),
                tables=_as_tuple(item.get("tables")),
                tier=str(refresh.get("tier") or ""),
                policy=str(refresh.get("policy") or "").strip(),
                steps={str(k): _as_tuple(v) for k, v in steps_raw.items()},
                raw=item,
            )
        )
    recipes = []
    for item in data.get("recipes") or []:
        recipes.append(
            Recipe(
                key=str(item["key"]),
                question=str(item.get("question") or ""),
                status=str(item.get("status") or ""),
                joins=_as_tuple(item.get("joins")),
                proactive=str(item.get("proactive") or ""),
                raw=item,
            )
        )
    plans_raw = dict(data.get("plans") or {})
    infrastructure = _as_tuple(plans_raw.pop("infrastructure_steps", ()))
    plans = {str(k): _as_tuple(v) for k, v in plans_raw.items()}
    return Registry(
        datasets=tuple(datasets),
        recipes=tuple(recipes),
        plans=plans,
        infrastructure_steps=infrastructure,
        meta=dict(data.get("meta") or {}),
        tiers=dict(data.get("tiers") or {}),
    )


def schema_objects(path: Path = SCHEMA_PATH) -> set[str]:
    """schema.sql 里声明的表与视图名（VIEW 也算：registry 引用的是读口名）。"""
    text = Path(path).read_text(encoding="utf-8")
    return {m.group(1) for m in _DDL_OBJECT.finditer(text)}


def validate_registry(registry: Registry, *, schema_path: Path = SCHEMA_PATH) -> list[str]:
    """返回问题清单；空列表 = 通过。每条问题都写清是哪个键、期望什么。"""
    problems: list[str] = []
    declared = schema_objects(schema_path)

    keys = [ds.key for ds in registry.datasets]
    for dup in sorted({k for k in keys if keys.count(k) > 1}):
        problems.append(f"dataset key 重复: {dup}")

    known_tiers = set(TIERS)
    for ds in registry.datasets:
        if ds.tier not in known_tiers:
            problems.append(f"dataset {ds.key}: tier={ds.tier!r} 不在 {TIERS}")
        if not ds.policy:
            problems.append(f"dataset {ds.key}: refresh.policy 为空")
        for table in ds.tables:
            if table not in declared:
                problems.append(f"dataset {ds.key}: 表 {table} 不在 schema.sql 里")
        for plan, steps in ds.steps.items():
            if plan not in registry.plans:
                problems.append(f"dataset {ds.key}: steps 引用未知计划 {plan!r}")
                continue
            for step in steps:
                if step not in registry.plans[plan]:
                    problems.append(
                        f"dataset {ds.key}: 步骤 {step} 不在 plans.{plan} 里"
                    )

    for tier in registry.tiers:
        if tier not in known_tiers:
            problems.append(f"tiers 段出现未知档位 {tier!r}")

    for plan in PLANS:
        if plan not in registry.plans:
            problems.append(f"plans 缺少 {plan}")
    for plan, steps in registry.plans.items():
        seen: set[str] = set()
        for step in steps:
            if step in seen:
                problems.append(f"plans.{plan}: 步骤 {step} 重复")
            seen.add(step)
        owned = {
            step
            for ds in registry.datasets
            for step in ds.steps.get(plan, ())
        } | set(registry.infrastructure_steps)
        for step in steps:
            if step not in owned:
                problems.append(
                    f"plans.{plan}: 步骤 {step} 没有任何数据族认领（也不是 infrastructure）"
                )

    for recipe in registry.recipes:
        if recipe.status not in RECIPE_STATUSES:
            problems.append(f"recipe {recipe.key}: status={recipe.status!r} 不在 {RECIPE_STATUSES}")
        if not recipe.joins:
            problems.append(f"recipe {recipe.key}: joins 为空")
    return problems


def check_plan_against_pipeline(
    registry: Registry, pipeline_steps: dict[str, list[str]]
) -> list[str]:
    """把管线实际 build 出来的步骤名与 registry 的 plans 段逐项比对（含顺序）。"""
    problems: list[str] = []
    for plan, declared in registry.plans.items():
        actual = pipeline_steps.get(plan)
        if actual is None:
            problems.append(f"管线没有实现计划 {plan!r}")
            continue
        if tuple(actual) != tuple(declared):
            missing = [s for s in declared if s not in actual]
            extra = [s for s in actual if s not in declared]
            detail = []
            if missing:
                detail.append(f"registry 有、管线无: {', '.join(missing)}")
            if extra:
                detail.append(f"管线有、registry 无: {', '.join(extra)}")
            if not detail:
                detail.append("集合相同但顺序不同")
            problems.append(f"plans.{plan} 与管线不一致（{'；'.join(detail)}）")
    for plan in pipeline_steps:
        if plan not in registry.plans:
            problems.append(f"管线实现了 registry 未登记的计划 {plan!r}")
    return problems


def summarize(registry: Registry) -> str:
    """一屏概览：每个档位有哪些数据族、各计划多少步。"""
    lines = [f"consumption registry @ {registry.meta.get('updated', '?')}"]
    for tier in TIERS:
        members = [ds.key for ds in registry.datasets if ds.tier == tier]
        lines.append(f"  {tier:<11} {len(members):>2}  {', '.join(members)}")
    for plan, steps in registry.plans.items():
        lines.append(f"  plan {plan:<6} {len(steps):>2} 步: {' → '.join(steps)}")
    pending = [r.key for r in registry.recipes if r.status == "pending-grilling"]
    lines.append(
        f"  recipes {len(registry.recipes)}（pending-grilling: {', '.join(pending) or '-'}）"
    )
    return "\n".join(lines)
