"""ResearchProfile：不可变配置信封 + effective-config 收据。

来源：``docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md``
§7.5（ResearchProfile），实施顺序第 6 步；台账
``docs/handoffs/2026-08-15-dsh-absorption-p0-execution-handoff.md`` §5.3。

--------------------------------------------------------------------------
这一步是什么 / 不是什么
--------------------------------------------------------------------------

把散落的 Runtime、工具、预算、模式配置收成一份**不可变信封**，并给出
``dump_effective_config()`` 收据。覆盖必须显式声明、按字段 schema 校验；
默认行为**不是** dsh 的「替换整行，没写的字段消失」。

本模块**不发明第二份预算数字**。墙钟两阶段预算的唯一事实源仍是
``research_policy.GroundedBudgetProfile`` / ``grounded_deep``。Profile
**持有**那个对象（同一身份），``execution_policy()`` 从它派生
``ResearchExecutionPolicy``——这正是 conversation 入口今天手写的那三行。

下面这些钟走的是别的层，本轮**不抄进字段**，避免收据变成第三份口径：

- ``ResearchPolicy.for_tier``（generic owner 档位：30 / 90 / 240）
- ``ModeDecision.target_seconds``（90 / 240）
- ``_DEFAULT_CONTINUOUS_TURN_TIMEOUT_SECONDS``（api 层 120，可 env 覆盖）
- ``HeadlessBenchmarkBudgetProfile``（benchmark 脚本专用）

修复次数不存数字，从 ``max_repair_cycles_for_tier(research_tier)`` 派生。

--------------------------------------------------------------------------
与 spec 字面的有意偏离
--------------------------------------------------------------------------

1. **不复制 GroundedBudgetProfile 的字段。** spec 写 Profile 声明
   budget/deadline，但数字已经在 ``grounded_deep`` 上。再抄
   ``root_seconds`` 就是第二配置源——Step 1 收据已经点名禁止。
2. **allowed_tools / output_contract 默认为 None。** 现役权威在
   ``ResearchTaskContract`` / owner skill，不在本信封。写死一份名单
   会立刻和 Scope / owner 漂移。收据上标 ``source=contract|owner``。
3. **provider/model 默认为 None = ambient。** 生效模型的唯一口径是
   ``detect_providers()``（见 factory ``_effective_env_model`` 的教训）。
   Profile 不发明默认模型名。
4. **六份目录只填能引用到的现役事实。** 只有 ``deep-research`` 持有
   ``grounded_deep``；其余预算为 None，走 ``ResearchExecutionPolicy``
   既有默认（120 / 20）。不把 ModeGovernor 的 90s 写进 quick-research。

--------------------------------------------------------------------------
⚠ 接线状态
--------------------------------------------------------------------------

本轮只改 **conversation 入口** 那一处手写 ``ResearchExecutionPolicy``：
改走 ``profile_named("deep-research").execution_policy()``。
``AskOptions.grounded_budget_profile`` 仍直接持有 ``grounded_deep``，
不在本轮改——那是 ask 合成链，另轮再收。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from typing import Literal, Mapping, get_args

from intelligence.services.repair_coordinator import max_repair_cycles_for_tier
from intelligence.services.research_policy import (
    GroundedBudgetProfile,
    ResearchExecutionPolicy,
    grounded_deep,
)


RuntimeBackendName = Literal[
    "continuous_glm",
    "sdk_glm",
    "sdk_gpt",
    "codex_headless",
]
RUNTIME_BACKEND_NAMES: frozenset[str] = frozenset(get_args(RuntimeBackendName))
DEFAULT_RUNTIME_BACKEND: RuntimeBackendName = "continuous_glm"

ResearchTierName = Literal["quick", "standard", "deep"]
RESEARCH_TIER_NAMES: frozenset[str] = frozenset(get_args(ResearchTierName))

PROFILE_NAMES: frozenset[str] = frozenset(
    {
        "quick-research",
        "deep-research",
        "daily-review",
        "read-only",
        "benchmark",
        "headless",
    }
)

# 现役 continuous 路径的两段核验（structural → semantic），不是新想的链。
CONTINUOUS_VERIFIER_CHAIN: tuple[str, ...] = (
    "episode_verifier",
    "episode_semantic_verifier",
)

_OVERRIDE_FIELDS = frozenset(
    {
        "runtime_backend",
        "benchmark_only",
        "read_only",
        "provider",
        "model",
        "allowed_tools",
        "budget",
        "research_tier",
        "verifier_chain",
        "output_contract",
    }
)


class ResearchProfileError(ValueError):
    """覆盖字段未声明、schema 不合法，或目录里没有这个名字。"""


def _optional_str(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ResearchProfileError(f"{field_name} must be a string or None")
    cleaned = value.strip()
    if not cleaned:
        raise ResearchProfileError(f"{field_name} must be a non-empty string")
    return cleaned


def _optional_str_tuple(value: object, field_name: str) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, (tuple, list)):
        raise ResearchProfileError(f"{field_name} must be a sequence of strings or None")
    items = tuple(str(item).strip() for item in value)
    if any(not item for item in items):
        raise ResearchProfileError(f"{field_name} must contain non-empty strings")
    return items


def _required_str_tuple(value: object, field_name: str) -> tuple[str, ...]:
    items = _optional_str_tuple(value, field_name)
    if items is None:
        raise ResearchProfileError(f"{field_name} must be a sequence of strings")
    return items


@dataclass(frozen=True)
class ResearchProfile:
    """Immutable envelope over existing config objects.

    Budget numbers live on ``GroundedBudgetProfile``. This type only holds
    that object (or None) and derives ``ResearchExecutionPolicy`` from it.
    """

    name: str
    runtime_backend: RuntimeBackendName = DEFAULT_RUNTIME_BACKEND
    benchmark_only: bool = False
    read_only: bool = False
    provider: str | None = None
    model: str | None = None
    allowed_tools: tuple[str, ...] | None = None
    budget: GroundedBudgetProfile | None = None
    research_tier: ResearchTierName = "standard"
    verifier_chain: tuple[str, ...] = CONTINUOUS_VERIFIER_CHAIN
    output_contract: tuple[str, ...] | None = None
    declared_overrides: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.name not in PROFILE_NAMES:
            raise ResearchProfileError(
                f"unknown research profile: {self.name!r}; "
                f"known: {sorted(PROFILE_NAMES)}"
            )
        if self.runtime_backend not in RUNTIME_BACKEND_NAMES:
            raise ResearchProfileError(
                f"unsupported agent runtime backend: {self.runtime_backend}"
            )
        if self.research_tier not in RESEARCH_TIER_NAMES:
            raise ResearchProfileError(
                f"unknown research tier: {self.research_tier}"
            )
        if not isinstance(self.benchmark_only, bool):
            raise ResearchProfileError("benchmark_only must be boolean")
        if not isinstance(self.read_only, bool):
            raise ResearchProfileError("read_only must be boolean")
        if self.runtime_backend == "codex_headless" and not self.benchmark_only:
            raise ResearchProfileError(
                "codex_headless is benchmark-only; declare benchmark_only=True"
            )
        if self.budget is not None and not isinstance(
            self.budget, GroundedBudgetProfile
        ):
            raise ResearchProfileError(
                "budget must be GroundedBudgetProfile or None"
            )
        object.__setattr__(self, "provider", _optional_str(self.provider, "provider"))
        object.__setattr__(self, "model", _optional_str(self.model, "model"))
        object.__setattr__(
            self,
            "allowed_tools",
            _optional_str_tuple(self.allowed_tools, "allowed_tools"),
        )
        object.__setattr__(
            self,
            "output_contract",
            _optional_str_tuple(self.output_contract, "output_contract"),
        )
        object.__setattr__(
            self,
            "verifier_chain",
            _required_str_tuple(self.verifier_chain, "verifier_chain"),
        )
        overrides = _optional_str_tuple(
            self.declared_overrides, "declared_overrides"
        ) or ()
        unknown = [item for item in overrides if item not in _OVERRIDE_FIELDS]
        if unknown:
            raise ResearchProfileError(
                f"undeclared override fields: {unknown}"
            )
        object.__setattr__(self, "declared_overrides", overrides)

    def execution_policy(self) -> ResearchExecutionPolicy:
        """Derive the existing execution policy. No second budget struct."""

        if self.budget is None:
            return ResearchExecutionPolicy()
        return ResearchExecutionPolicy(
            max_elapsed_seconds=self.budget.root_seconds,
            synthesis_reserve_seconds=self.budget.synthesis_reserve_seconds,
            grounded_budget_profile=self.budget,
        )

    def override(self, **changes: object) -> ResearchProfile:
        """Typed merge: omitted fields stay; unknown names raise.

        This is the opposite of dsh's replace-row default. A partial
        override of ``runtime_backend`` must keep ``budget``.
        """

        unknown = sorted(set(changes) - _OVERRIDE_FIELDS)
        if unknown:
            raise ResearchProfileError(f"undeclared override fields: {unknown}")
        if not changes:
            return self
        validated = {key: changes[key] for key in changes}
        merged_overrides = tuple(
            dict.fromkeys((*self.declared_overrides, *validated))
        )
        return replace(self, declared_overrides=merged_overrides, **validated)

    def dump_effective_config(self) -> dict[str, object]:
        """spec §7.5 验收要求的那份收据。

        只报本信封持有或能从唯一事实源派生的东西。不把 ModeGovernor /
        ResearchPolicy.for_tier / continuous turn timeout 的数字抄进来。
        """

        policy = self.execution_policy()
        budget_dump: dict[str, object] | None
        if self.budget is None:
            budget_dump = None
        else:
            budget_dump = asdict(self.budget)
        return {
            "name": self.name,
            "runtime_backend": self.runtime_backend,
            "benchmark_only": self.benchmark_only,
            "read_only": self.read_only,
            "provider": self.provider,
            "provider_source": "profile" if self.provider else "ambient",
            "model": self.model,
            "model_source": "profile" if self.model else "ambient",
            "allowed_tools": (
                list(self.allowed_tools) if self.allowed_tools is not None else None
            ),
            "allowed_tools_source": (
                "profile" if self.allowed_tools is not None else "contract"
            ),
            "research_tier": self.research_tier,
            "repair_max_cycles": max_repair_cycles_for_tier(self.research_tier),
            "repair_max_cycles_source": "max_repair_cycles_for_tier",
            "grounded_budget_profile": budget_dump,
            "execution_policy": {
                "max_elapsed_seconds": policy.max_elapsed_seconds,
                "synthesis_reserve_seconds": policy.synthesis_reserve_seconds,
                "max_skill_calls": policy.max_skill_calls,
                "max_retries_per_skill": policy.max_retries_per_skill,
                "max_llm_calls": policy.max_llm_calls,
                "grounded_budget_profile_name": (
                    self.budget.name if self.budget is not None else None
                ),
            },
            "verifier_chain": list(self.verifier_chain),
            "output_contract": (
                list(self.output_contract)
                if self.output_contract is not None
                else None
            ),
            "output_contract_source": (
                "profile" if self.output_contract is not None else "owner"
            ),
            "declared_overrides": list(self.declared_overrides),
        }


def _profile(
    name: str,
    *,
    runtime_backend: RuntimeBackendName = DEFAULT_RUNTIME_BACKEND,
    benchmark_only: bool = False,
    read_only: bool = False,
    budget: GroundedBudgetProfile | None = None,
    research_tier: ResearchTierName = "standard",
) -> ResearchProfile:
    return ResearchProfile(
        name=name,
        runtime_backend=runtime_backend,
        benchmark_only=benchmark_only,
        read_only=read_only,
        budget=budget,
        research_tier=research_tier,
    )


RESEARCH_PROFILES: Mapping[str, ResearchProfile] = {
    "quick-research": _profile("quick-research", research_tier="quick"),
    "deep-research": _profile(
        "deep-research",
        budget=grounded_deep,
        research_tier="deep",
    ),
    "daily-review": _profile("daily-review"),
    "read-only": _profile("read-only", read_only=True),
    "benchmark": _profile("benchmark", benchmark_only=True, research_tier="deep"),
    "headless": _profile(
        "headless",
        runtime_backend="codex_headless",
        benchmark_only=True,
        research_tier="deep",
    ),
}


def profile_named(name: str) -> ResearchProfile:
    try:
        return RESEARCH_PROFILES[name]
    except KeyError:
        raise ResearchProfileError(
            f"unknown research profile: {name!r}; "
            f"known: {sorted(PROFILE_NAMES)}"
        ) from None


def profile_field_names() -> frozenset[str]:
    """Public dataclass fields. Tests use this to forbid copied budget keys."""

    return frozenset(item.name for item in fields(ResearchProfile))


__all__ = [
    "CONTINUOUS_VERIFIER_CHAIN",
    "DEFAULT_RUNTIME_BACKEND",
    "PROFILE_NAMES",
    "RESEARCH_PROFILES",
    "RESEARCH_TIER_NAMES",
    "RUNTIME_BACKEND_NAMES",
    "ResearchProfile",
    "ResearchProfileError",
    "ResearchTierName",
    "RuntimeBackendName",
    "profile_field_names",
    "profile_named",
]
