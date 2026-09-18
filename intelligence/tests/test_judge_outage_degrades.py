"""judge 挂了应该降级放行，而不是罚被审对象。

judge 是「后台请求」——用户不在等它的结果。官方 Claude Code 对这类请求的处理是
减载：`FOREGROUND_529_RETRY_SOURCES` 白名单只放前台请求，摘要/标题/**分类器**一律
立即放弃，理由写在源码注释里——过载时每次重试对网关是 3-10 倍放大，而「用户根本
看不到这些失败」。

我们这里 judge 就是分类器。它因超时/预算/HTTP 故障没能给出判定时，原先的行为是
整份答案被换成缺口模板——一个通过了确定性绑定校验的答案，因为审稿人缺席而被丢弃。

保留有三条约束：
1. 复核故障只影响核验状态，不论瞬时故障、配置问题还是复核输出不合法，都不抹掉已有正文
2. 公开安全清洗继续执行，清洗后为空不能拿警示语冒充答案
3. 状态不冒充 accepted，正文带批注；本地预算和供应商故障仍分别归因
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
    assert released.startswith("上证指数收跌 0.62%。")
    assert "核验批注" in released and "未完成独立复核" in released
    assert "绑定已通过校验" not in released


@pytest.mark.usefixtures("presented")
@pytest.mark.parametrize(
    "reason",
    [
        pytest.param("未配置 LLM key", id="misconfigured"),
        pytest.param("输出超长", id="output_too_long"),
        pytest.param("响应被截断", id="truncated"),
    ],
)
def test_non_transient_review_failures_preserve_body_without_claiming_success(reason: str) -> None:
    released = ask_synthesis._judge_outage_release("正文", _Spec(), reason)
    assert released and released.startswith("正文")
    assert "未完成独立复核" in released
    assert "绑定已通过校验" not in released
    assert reason not in released


@pytest.mark.usefixtures("presented")
def test_empty_body_is_not_released() -> None:
    """没有正文可放行时不要放行一个只有警示语的空壳。"""
    assert ask_synthesis._judge_outage_release("   ", _Spec(), "超时") is None


class TestHttpStatusIsNotCollapsed:
    """保留正文不合并故障归因：请求错误、限速、过载仍是不同原因。"""

    @pytest.mark.parametrize("code", [429, 500, 502, 503, 529])
    def test_their_fault_is_releasable(self, code: int) -> None:
        cls = ask_synthesis._stable_llm_fallback_reason(
            f"LLM 合成 HTTP {code}，已降级为模板"
        )

        assert cls in ask_synthesis._TRANSIENT_JUDGE_REASONS

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 413, 422])
    def test_request_errors_are_not_classified_as_transient(self, code: int) -> None:
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
    """预算耗尽是自己的限额，不是供应商挂了，不能混记原因。"""
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
    """本地共享期限耗尽不归咎供应商；原稿保留也不谎称复核完成。"""

    def test_shared_deadline_exhaustion_retains_body_and_local_reason(self) -> None:
        reason = "LLM 合成超过共享截止时间，已降级为模板"

        assert (
            ask_synthesis._stable_llm_fallback_reason(reason)
            == "deadline_exhausted_local"
        )
        assert (
            "deadline_exhausted_local"
            not in ask_synthesis._TRANSIENT_JUDGE_REASONS
        )
        released = ask_synthesis._judge_outage_release("正文", _Spec(), reason)
        assert released and released.startswith("正文")
        assert "未完成独立复核" in released
        assert "复核服务超时" not in released

    def test_streaming_variant_classifies_the_same(self) -> None:
        """流式和非流式产出两句不同的串，别只堵一句。"""
        assert (
            ask_synthesis._stable_llm_fallback_reason(
                "LLM 流式合成超过共享截止时间，已降级为模板"
            )
            == "deadline_exhausted_local"
        )

    def test_provider_timeout_is_still_releasable(self) -> None:
        """供应商超时仍独立归因，不因原稿保留而改变原因分类。"""
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
        """保留既有诊断分组；展示策略不再由瞬时原因白名单决定。"""
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
