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
    pytest.param("provider 读取超时", id="provider_timeout"),
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


class TestHttpStatusIsNotCollapsed:
    """HTTP 不能塌成一类——429 和 400 的处置相反。

    产生点 ``llm_refine`` 写的是 ``LLM 合成 HTTP {code}``，它本来就知道是哪个码；
    分类器原先只判 ``"http" in normalized`` 就返回 provider_http_error，
    于是 **HTTP 400（我们自己请求构造错了）也会被当瞬时故障放行**。

    注意这条分界线跟 ch06b 的 ``shouldRetry`` 不同，因为问的不是同一个问题：
    它问「该不该重试」（401 该重试，可能是别的进程刷新了 token）；
    我们问「被审对象是不是无辜的」（401 之后每次都会失败，放行会变成常态）。
    """

    @pytest.mark.parametrize("code", [429, 500, 502, 503, 529])
    def test_their_fault_is_releasable(self, code: int) -> None:
        cls = ask_synthesis._stable_llm_fallback_reason(
            f"LLM 合成 HTTP {code}，已降级为模板"
        )

        assert cls in ask_synthesis._TRANSIENT_JUDGE_REASONS

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 413, 422])
    def test_our_fault_still_fails_closed(self, code: int) -> None:
        cls = ask_synthesis._stable_llm_fallback_reason(
            f"LLM 合成 HTTP {code}，已降级为模板"
        )

        assert cls == "provider_request_rejected"
        assert cls not in ask_synthesis._TRANSIENT_JUDGE_REASONS

    def test_rate_limit_and_overload_stay_distinguishable(self) -> None:
        """诊断要细：429 是我们被限速，5xx 是那边过载，遥测得分得开。"""
        assert (
            ask_synthesis._stable_llm_fallback_reason("LLM 合成 HTTP 429，已降级为模板")
            != ask_synthesis._stable_llm_fallback_reason(
                "LLM 合成 HTTP 529，已降级为模板"
            )
        )


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


class TestOurOwnDeadlineIsNotTheirOutage:
    """自家共享 deadline 走完 ≠ 供应商抖了一下。前者必须 fail-closed。

    这条分界线跟上面 HTTP 那组问的是同一个问题——「被审对象是不是无辜的」，
    但答案由**频率**决定：供应商抖动是例外，放行合理；自家预算不够是常态
    （2026-08-02 那批 23 轮里 15 轮撞的就是它），放行会从例外变成常态。

    真实代价：可见降级率会上升。那不是新增故障，是把原先静默放行的未核验答案
    换成显式降级——信息量没少，少的是假的确信。
    """

    def test_shared_deadline_exhaustion_fails_closed(self) -> None:
        reason = "LLM 合成超过共享截止时间，已降级为模板"

        assert (
            ask_synthesis._stable_llm_fallback_reason(reason)
            == "deadline_exhausted_local"
        )
        assert (
            "deadline_exhausted_local"
            not in ask_synthesis._TRANSIENT_JUDGE_REASONS
        )
        assert ask_synthesis._judge_outage_release("正文", _Spec(), reason) is None

    def test_streaming_variant_classifies_the_same(self) -> None:
        """流式和非流式产出两句不同的串，别只堵一句。"""
        assert (
            ask_synthesis._stable_llm_fallback_reason(
                "LLM 流式合成超过共享截止时间，已降级为模板"
            )
            == "deadline_exhausted_local"
        )

    def test_provider_timeout_is_still_releasable(self) -> None:
        """收紧的只是自家 deadline 这一类，供应商侧超时仍按瞬时故障处理。"""
        assert (
            ask_synthesis._stable_llm_fallback_reason("provider 读取超时")
            == "timeout"
        )
        assert "timeout" in ask_synthesis._TRANSIENT_JUDGE_REASONS

    def test_local_deadline_is_a_public_enum(self) -> None:
        from intelligence.api import app

        assert (
            "deadline_exhausted_local" in app._STABLE_MACHINE_FALLBACK_REASONS
        )

    def test_call_budget_exhaustion_is_deliberately_unchanged(self) -> None:
        """次数预算（LlmCallLedger）没跟着改——本轮没有证据说它也变成了常态。

        写成断言而不是注释：改动范围要能被读出来，下一个人想扩到这里得先删掉
        这条测试，那一刻他会看到上面这句话。
        """
        assert (
            "call_budget_exhausted" in ask_synthesis._TRANSIENT_JUDGE_REASONS
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
