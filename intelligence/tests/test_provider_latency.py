"""修复轮窗口按生效 provider 取值的门禁。

守的是 2026-08-16 那次事故的形状：中转全站 5xx → 切 GLM 主链 → provider 层恢复
（模型/工具/证据全部正常），但两个修复轮各在整 30.0 秒超时，因为窗口是按中转
terra 的延迟地板硬编的常数。

判据不是「30 变大了」而是「**窗口随 provider 变**」——只断言某个具体数字，下次
换 provider 照样会重演。``_REPAIR_SECONDS_CAP`` 常数本身必须仍是 30。
"""

from __future__ import annotations

import pytest

from intelligence.services.provider_latency import (
    DEFAULT_REPAIR_SECONDS_CAP,
    ENV_OVERRIDE,
    GLM_MEASURED_P90_SECONDS,
    known_providers,
    provider_name_from,
    repair_seconds_cap_for,
)
from intelligence.services.repair_coordinator import (
    ProgressSnapshot,
    _REPAIR_SECONDS_CAP,
    build_repair_goal,
    grant_for_progress,
    grant_for_transient_model_retry,
)
from intelligence.services.research_contract import InMemoryRootBudgetLedger


def _progressed_snapshot() -> ProgressSnapshot:
    """一个「有进展」的快照，好让 should_reenter 放行、把断言 focus 在秒数上。"""

    return ProgressSnapshot(
        before_evidence_ids=(),
        after_evidence_ids=("e1",),
        before_covered_outputs=(),
        after_covered_outputs=("direct_assessment",),
        before_open_gaps=("direct_assessment",),
        after_open_gaps=(),
        independent_source_families=("kb",),
        before_evidence_source_families=(),
        after_evidence_source_families=(("e1", "kb"),),
        before_evidence_targets=(),
        after_evidence_targets=(("e1", ("direct_assessment",)),),
    )


def _goal(remaining_seconds: float = 300.0):
    return build_repair_goal(
        episode_id="ep-1",
        missing_outputs=("chain_mapping",),
        previous_progress=_progressed_snapshot(),
        remaining_calls=4,
        remaining_seconds=remaining_seconds,
        cycle=1,
    )


def _ledger(headroom: float = 1000.0) -> InMemoryRootBudgetLedger:
    """留足未分配余量的 root ledger。

    ``allocated_calls`` / ``allocated_seconds`` 都从 initial 值起算（初始额度即已分配），
    所以 initial 与 hard 相等 = 零余量，**两个维度任一没余量都会 fail-closed 拒掉**。
    生产同形：``initial = total - synthesis_reserve``、``hard = total``。
    这里把 initial 设 0，把整段 hard cap 都留作可铸余量，好让断言聚焦在秒数上。
    """

    return InMemoryRootBudgetLedger(
        episode_id="ep-1",
        initial_calls=0,
        hard_calls_cap=8,
        initial_seconds=0.0,
        hard_seconds_cap=headroom,
    )


def test_global_repair_cap_constant_stays_thirty() -> None:
    """R-21 / R-07：禁止把 30 调成新常数。窗随 p90，常数本身不动。"""

    assert _REPAIR_SECONDS_CAP == 30.0
    assert DEFAULT_REPAIR_SECONDS_CAP == 30.0


def test_relay_provider_keeps_thirty_second_window() -> None:
    """中转那条线不许变——它的 30s 有 R7/R21 的 5/5 成功收据背书。

    这条同时是「本次改动不拖慢其它路由」的机器判据：openai 路径取值不变，
    则非 GLM 路由的修复行为逐字节不变。
    """

    assert repair_seconds_cap_for("openai", env={}) == 30.0


def test_glm_provider_window_clears_measured_p90() -> None:
    """GLM 窗口必须盖过实测 p90=34.4s，否则重演 2026-08-16 的整 30s 超时。"""

    cap = repair_seconds_cap_for("zhipu", env={})
    assert cap > GLM_MEASURED_P90_SECONDS, (
        f"GLM 窗口 {cap}s 未盖过实测 p90 {GLM_MEASURED_P90_SECONDS}s"
    )


def test_window_varies_by_provider() -> None:
    """核心判据：窗口是 provider 的函数，不是常数。"""

    caps = {name: repair_seconds_cap_for(name, env={}) for name in known_providers()}
    assert len(set(caps.values())) > 1, f"窗口对所有 provider 相同，退化成常数了: {caps}"


@pytest.mark.parametrize("name", [None, "", "   ", "unknown-provider", "custom"])
def test_unknown_provider_falls_back_to_default(name: str | None) -> None:
    """未知 provider 落默认帽 = 改动前行为。fail-safe，不 raise、不给 0。"""

    assert repair_seconds_cap_for(name, env={}) == DEFAULT_REPAIR_SECONDS_CAP


def test_provider_name_is_case_insensitive() -> None:
    assert repair_seconds_cap_for("ZhiPu", env={}) == repair_seconds_cap_for(
        "zhipu", env={}
    )


def test_env_override_wins() -> None:
    assert repair_seconds_cap_for("openai", env={ENV_OVERRIDE: "55"}) == 55.0


@pytest.mark.parametrize("bad", ["", "   ", "abc", "0", "-5", "nan"])
def test_bad_env_override_is_ignored_not_fatal(bad: str) -> None:
    """配置写错不该把修复窗口静默压成 0 —— 那会让每个修复轮直接判死。"""

    cap = repair_seconds_cap_for("zhipu", env={ENV_OVERRIDE: bad})
    assert cap == repair_seconds_cap_for("zhipu", env={})
    assert cap > 0.0


def test_grant_uses_injected_cap_not_the_default() -> None:
    """端到端：注入 40s 帽，授予就该是 40s，而不是旧常数 30s。"""

    grant = grant_for_progress(
        _goal(remaining_seconds=300.0),
        _progressed_snapshot(),
        root_budget=_ledger(),
        research_tier="standard",
        seconds_cap=40.0,
    )
    assert grant is not None
    assert grant.seconds_granted == 40.0


def test_grant_without_cap_preserves_legacy_thirty() -> None:
    """不传 cap 的调用方行为逐字节不变。"""

    grant = grant_for_progress(
        _goal(remaining_seconds=300.0),
        _progressed_snapshot(),
        root_budget=_ledger(),
        research_tier="standard",
    )
    assert grant is not None
    assert grant.seconds_granted == 30.0


def test_remaining_still_binds_when_smaller_than_cap() -> None:
    """cap 只是上限：剩余不足时仍以剩余为准，fail-closed 语义不变。"""

    grant = grant_for_progress(
        _goal(remaining_seconds=12.0),
        _progressed_snapshot(),
        root_budget=_ledger(),
        research_tier="standard",
        seconds_cap=40.0,
    )
    assert grant is not None
    assert grant.seconds_granted == 12.0


@pytest.mark.parametrize("bad_cap", [0.0, -1.0])
def test_non_positive_cap_falls_back_instead_of_zero_window(bad_cap: float) -> None:
    """坏 cap 落默认帽，不铸 0 秒授予。"""

    grant = grant_for_progress(
        _goal(remaining_seconds=300.0),
        _progressed_snapshot(),
        root_budget=_ledger(),
        research_tier="standard",
        seconds_cap=bad_cap,
    )
    assert grant is not None
    assert grant.seconds_granted == 30.0


def test_transient_retry_uses_injected_cap() -> None:
    """23:05 复跑的第二发 TimeoutError 走的是 transient retry，也必须跟 p90。"""

    retry = grant_for_transient_model_retry(
        _goal(remaining_seconds=8.0),
        root_budget=_ledger(headroom=100.0),
        seconds_cap=40.0,
    )
    assert retry is not None
    assert retry.seconds_granted == 40.0


def test_transient_retry_without_cap_stays_thirty() -> None:
    retry = grant_for_transient_model_retry(
        _goal(remaining_seconds=8.0),
        root_budget=_ledger(headroom=100.0),
    )
    assert retry is not None
    assert retry.seconds_granted == 30.0


def test_provider_name_from_reads_runtime_chain_head() -> None:
    class _Prov:
        name = "zhipu"

    class _Runtime:
        _providers = (_Prov(),)

    assert provider_name_from(_Runtime()) == "zhipu"
    assert provider_name_from(object()) is None
