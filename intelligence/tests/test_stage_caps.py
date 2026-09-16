from __future__ import annotations

from intelligence.runtime.episode_tool_batch import tool_batch_timeout_seconds
from intelligence.services.episode_semantic_verifier import (
    DEFAULT_JUDGE_TIMEOUT_SECONDS,
    complete_judge_attempt_seconds,
    judge_attempt_seconds,
    semantic_judge_window_seconds,
)
from intelligence.services.research_contract import (
    ResearchPolicy,
    apply_env_ceiling,
    derive_stage_caps,
)


def test_derive_stage_caps_pins_current_tier_table() -> None:
    table = {
        "quick": derive_stage_caps(ResearchPolicy.for_tier("quick")),
        "standard": derive_stage_caps(ResearchPolicy.for_tier("standard")),
        "deep": derive_stage_caps(ResearchPolicy.for_tier("deep")),
    }
    assert table["quick"].tool_batch_seconds == 10.0
    assert table["standard"].tool_batch_seconds == 70.0
    assert table["deep"].tool_batch_seconds == 192.0
    assert table["deep"].judge_window_seconds == 50.0
    for tier, caps in table.items():
        policy = ResearchPolicy.for_tier(tier)
        assert caps.tool_batch_seconds + policy.synthesis_reserve == policy.total_seconds


def test_deep_caps_reproduce_arm_c_floors() -> None:
    caps = derive_stage_caps(ResearchPolicy.for_tier("deep"))
    assert caps.judge_window_seconds >= 25.0
    assert caps.tool_batch_seconds >= 60.0
    assert complete_judge_attempt_seconds(DEFAULT_JUDGE_TIMEOUT_SECONDS) == 50.0
    assert min(DEFAULT_JUDGE_TIMEOUT_SECONDS, caps.judge_window_seconds) == 50.0


def test_standard_caps_stay_inside_total_and_protect_reserve() -> None:
    policy = ResearchPolicy.for_tier("standard")
    caps = derive_stage_caps(policy)
    assert policy.synthesis_reserve == 20.0
    assert caps.tool_batch_seconds + policy.synthesis_reserve == policy.total_seconds


def test_standard_judge_window_floor_covers_r06_terra_p95() -> None:
    """R-06 / R-10: window floor stays 50; 08-20 first attempt uses the window.

    Live asked=5.208 (retry half-window). Judge-shaped terra N=8 p95=10.75.
    08-20 grok compact N=5 tail=46.7, so first = min(cap, window)=50, not
    window×0.5. Do not steal synthesis reserve or raise T / repair cap /
    tool_batch / quick / deep.
    """

    standard = derive_stage_caps(ResearchPolicy.for_tier("standard"))
    quick = derive_stage_caps(ResearchPolicy.for_tier("quick"))
    deep = derive_stage_caps(ResearchPolicy.for_tier("deep"))
    assert standard.tool_batch_seconds == 70.0
    assert standard.judge_window_seconds == 50.0
    assert min(DEFAULT_JUDGE_TIMEOUT_SECONDS, standard.judge_window_seconds) == 50.0
    assert quick.judge_window_seconds < 25.0
    assert deep.judge_window_seconds == 50.0


def test_max_tier_judge_caps_pin_measured_grok_latency(monkeypatch) -> None:
    """max 档判官：单次 75s、窗 150s = 两次完整尝试；其余档位一字不变。

    2026-09-07 用两发 judge=unavailable 的真实 13.3K/13.6K 载荷重放 grok-4.6
    n=6：p50 52.0s / max 60.6s，4/6 超过 50s 帽；给足时 6/6 有效。50s 在 max 档
    载荷上是中位数即超时，75 = max + 约 24% 余量；窗两倍于帽，首发超时后仍剩
    一次完整尝试。
    """

    monkeypatch.delenv("ASK_SEMANTIC_JUDGE_WINDOW", raising=False)
    maximum = derive_stage_caps(ResearchPolicy.for_tier("max"))
    assert maximum.judge_attempt_seconds == 75.0
    assert maximum.judge_window_seconds == 150.0
    assert maximum.judge_window_seconds == 2 * maximum.judge_attempt_seconds
    assert maximum.tool_batch_seconds == 540.0

    for tier in ("quick", "standard", "deep"):
        caps = derive_stage_caps(ResearchPolicy.for_tier(tier))
        assert caps.judge_attempt_seconds is None, tier
    assert derive_stage_caps(ResearchPolicy.for_tier("standard")).judge_window_seconds == 50.0
    assert derive_stage_caps(ResearchPolicy.for_tier("deep")).judge_window_seconds == 50.0

    max_policy = ResearchPolicy.for_tier("max")
    assert judge_attempt_seconds(DEFAULT_JUDGE_TIMEOUT_SECONDS, max_policy) == 75.0
    # 档位值是地板不是天花板：显式配置得更高时沿用配置。
    assert judge_attempt_seconds(90.0, max_policy) == 90.0
    assert judge_attempt_seconds(DEFAULT_JUDGE_TIMEOUT_SECONDS, ResearchPolicy.for_tier("standard")) == 50.0
    assert complete_judge_attempt_seconds(DEFAULT_JUDGE_TIMEOUT_SECONDS, max_policy) == 75.0
    assert semantic_judge_window_seconds(max_policy) == 150.0


def test_env_ceiling_can_only_lower_derived_cap(monkeypatch) -> None:
    monkeypatch.delenv("ASK_TOOL_BATCH_TIMEOUT", raising=False)
    derived = derive_stage_caps(ResearchPolicy.for_tier("standard")).tool_batch_seconds
    assert derived != 30.0
    assert apply_env_ceiling(derived, "ASK_TOOL_BATCH_TIMEOUT") == derived
    monkeypatch.setenv("ASK_TOOL_BATCH_TIMEOUT", "5")
    assert apply_env_ceiling(derived, "ASK_TOOL_BATCH_TIMEOUT") == 5.0
    monkeypatch.setenv("ASK_TOOL_BATCH_TIMEOUT", "999")
    assert apply_env_ceiling(derived, "ASK_TOOL_BATCH_TIMEOUT") == derived


def test_timeout_helpers_use_derived_caps_not_literals(monkeypatch) -> None:
    monkeypatch.delenv("ASK_TOOL_BATCH_TIMEOUT", raising=False)
    monkeypatch.delenv("ASK_SEMANTIC_JUDGE_WINDOW", raising=False)
    deep = ResearchPolicy.for_tier("deep")
    assert tool_batch_timeout_seconds(deep) == 192.0
    assert semantic_judge_window_seconds(deep) == 50.0
    monkeypatch.setenv("ASK_TOOL_BATCH_TIMEOUT", "60")
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE_WINDOW", "40")
    assert tool_batch_timeout_seconds(deep) == 60.0
    assert semantic_judge_window_seconds(deep) == 40.0
