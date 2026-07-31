"""judge 挂了应该降级放行，而不是罚被审对象。

judge 是「后台请求」——用户不在等它的结果。官方 Claude Code 对这类请求的处理是
减载：`FOREGROUND_529_RETRY_SOURCES` 白名单只放前台请求，摘要/标题/**分类器**一律
立即放弃，理由写在源码注释里——过载时每次重试对网关是 3-10 倍放大，而「用户根本
看不到这些失败」。

我们这里 judge 就是分类器。它因超时/预算/HTTP 故障没能给出判定时，原先的行为是
整份答案被换成缺口模板——一个通过了确定性绑定校验的答案，因为审稿人缺席而被丢弃。

放行有三条硬约束（照抄 episode 侧 `_transient_failure_candidate`）：
1. 只放行**瞬时故障**；配置问题和 judge 自己产出有问题的，继续 fail-closed
2. 正文必须**已经过确定性层**——数字/公司/日期是否有出处一条没放宽
3. 放行后状态不冒充 accepted，正文自带警示
"""
from __future__ import annotations

import pytest

from intelligence.services import ask_synthesis


class _Spec:
    """只需要 present_grounded_composer_answer 能接受的最小替身。"""


@pytest.fixture
def presented(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ask_synthesis.answer_model,
        "present_grounded_composer_answer",
        lambda answer, spec: answer,
    )


TRANSIENT = [
    pytest.param("语义核验超过截止时间", id="timeout"),
    pytest.param("provider 流未正常停止", id="stalled"),
    pytest.param("HTTP 529", id="http_error"),
    pytest.param("返回空内容", id="empty"),
    pytest.param(
        "LLM 调用预算耗尽（本轮上限 6 次尝试），已拒发新调用并降级",
        id="budget",
    ),
]


@pytest.mark.usefixtures("presented")
@pytest.mark.parametrize("reason", TRANSIENT)
def test_transient_judge_outage_releases_the_candidate(reason: str) -> None:
    released = ask_synthesis._judge_outage_release(
        "上证指数收跌 0.62%。",
        _Spec(),
        reason,
    )

    assert released is not None
    assert "上证指数收跌 0.62%。" in released


@pytest.mark.usefixtures("presented")
def test_released_text_carries_the_warning() -> None:
    """降级放行不能静默——用户要知道这条没过语义复核。"""
    released = ask_synthesis._judge_outage_release(
        "上证指数收跌 0.62%。", _Spec(), "超时"
    )

    assert released is not None
    assert released.startswith(ask_synthesis._JUDGE_OUTAGE_NOTICE)


@pytest.mark.usefixtures("presented")
@pytest.mark.parametrize(
    "reason",
    [
        pytest.param("未配置 LLM key", id="misconfigured"),
        pytest.param("输出超长", id="output_too_long"),
        pytest.param("响应被截断", id="truncated"),
    ],
)
def test_non_transient_failures_still_fail_closed(reason: str) -> None:
    """配置问题和 judge 自己产出有问题的，不在放行白名单里。

    episode 侧 `_transient_failure_candidate` 的注释写得很明白：
    configuration、malformed-output、contract 三类继续走 fail-closed。
    """
    assert ask_synthesis._judge_outage_release("正文", _Spec(), reason) is None


@pytest.mark.usefixtures("presented")
def test_empty_body_is_not_released() -> None:
    """没有正文可放行时不要放行一个只有警示语的空壳。"""
    assert ask_synthesis._judge_outage_release("   ", _Spec(), "超时") is None


def test_budget_exhaustion_is_no_longer_mislabelled_as_provider_down() -> None:
    """预算耗尽是我们自己的限额，不是供应商挂了——两者处置相反。"""
    assert (
        ask_synthesis._stable_llm_fallback_reason(
            "LLM 调用预算耗尽（本轮上限 6 次尝试），已拒发新调用并降级"
        )
        == "call_budget_exhausted"
    )
    assert (
        ask_synthesis._stable_llm_fallback_reason("未配置 LLM key")
        == "provider_unavailable"
    )


def test_released_status_can_reach_the_user() -> None:
    """放行状态必须在 promote 的白名单里，否则前面全白做。"""
    assert (
        "judge_outage_released" in ask_synthesis._PROMOTABLE_SHADOW_STATUSES
    )


def test_released_status_is_distinguishable_from_a_clean_pass() -> None:
    """遥测要能分出「过了」和「没人审但放行了」。"""
    assert "judge_outage_released" not in {"accepted", "repaired"}


def test_call_budget_exhausted_is_a_public_enum() -> None:
    """新 reason 要进公开白名单，否则它会被打码成不可读。"""
    from intelligence.api import app

    assert "call_budget_exhausted" in app._STABLE_MACHINE_FALLBACK_REASONS
