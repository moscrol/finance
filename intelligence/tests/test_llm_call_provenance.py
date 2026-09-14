"""逐次调用的身份证据（plans/2026-09-14-judge-calibration-validity.md §3.1，V9/V10/V12）。

假 HTTP / 假 SSE，不打真模型。钉住四条合同：

1. **请求身份与响应自报身份是两个字段**，响应没报就是 ``unreported``，
   不回填 ``provider.model``（``_served_model_from_body`` 的既有规则）。
2. **每次实际派发一个 attempt_id**，provider 轮换与重试各自成条，不靠列表位置关联。
3. **流式分块报告不同模型时记冲突**，不取第一个掩盖后续变化。
4. **预算拒发是 ``not_called``**，不伪造一次已花费的 attempt。
"""

from __future__ import annotations

import json
from unittest import mock

import pytest

from intelligence.eval import judge_validity
from intelligence.services import llm_refine

PROVIDER = llm_refine.LLMProvider(
    name="zhipu",
    api_key="test-key",
    base_url="https://example.invalid/v4",
    model="glm-5.2",
)
PROVIDER_B = llm_refine.LLMProvider(
    name="openrouter",
    api_key="test-key-b",
    base_url="https://example.invalid/v1",
    model="gpt-4.1-mini",
)


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self._lines = body.splitlines(keepends=True)

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def __iter__(self):
        return iter(self._lines)

    def read(self) -> bytes:
        return self._body


def _chat_body(*, model: str | None, content: str = "ok") -> bytes:
    payload: dict = {"choices": [{"message": {"role": "assistant", "content": content}}]}
    if model is not None:
        payload["model"] = model
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _sse(*events: object) -> bytes:
    lines = [f"data: {json.dumps(event, ensure_ascii=False)}\n" for event in events]
    lines.append("data: [DONE]\n")
    return "".join(lines).encode("utf-8")


def _chunk(piece: str, *, model: str | None = None) -> dict:
    event: dict = {"choices": [{"delta": {"content": piece}}]}
    if model is not None:
        event["model"] = model
    return event


def _post(provider: llm_refine.LLMProvider, body: bytes) -> dict:
    with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(body)):
        return llm_refine._post_chat_message(
            provider,
            [{"role": "user", "content": "明天你怎么看"}],
            timeout=30.0,
            temperature=0.0,
            tools=None,
            tool_choice=None,
            disable_thinking=True,
        )


def _stream(provider: llm_refine.LLMProvider, body: bytes) -> dict:
    with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(body)):
        return llm_refine._post_chat_message_stream(
            provider,
            [{"role": "user", "content": "明天你怎么看"}],
            timeout=30.0,
            temperature=0.0,
            tools=None,
            tool_choice=None,
            disable_thinking=True,
            on_content_delta=lambda _piece: None,
        )


# --------------------------------------------------------------------------- #
# 身份状态三态
# --------------------------------------------------------------------------- #


def test_响应自报模型时记reported并与请求值分列():
    with llm_refine.call_ledger_scope() as ledger:
        _post(PROVIDER, _chat_body(model="glm-5.2-0930"))

    (record,) = ledger.records
    assert record.identity_state == llm_refine.IDENTITY_REPORTED
    assert record.reported_model == "glm-5.2-0930"
    # 请求值原样留着，但它不是身份证据
    assert record.requested_model == "glm-5.2"
    assert record.attempt_id


def test_响应没报模型时是unreported且不回填请求值():
    """中转不回该字段 = 「未回」，不是「等于我们请求的那个」。"""

    with llm_refine.call_ledger_scope() as ledger:
        _post(PROVIDER, _chat_body(model=None))

    (record,) = ledger.records
    assert record.identity_state == llm_refine.IDENTITY_UNREPORTED
    assert record.reported_model in (None, "")
    assert record.requested_model == "glm-5.2"


def test_失败的调用不从错误体取身份():
    """HTTP 错误页里的模型名不能证明评分身份（§3.1）。"""

    with llm_refine.call_ledger_scope() as ledger:
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError()):
            with pytest.raises(Exception):
                _post(PROVIDER, b"")

    (record,) = ledger.records
    assert record.status == "failed"
    assert record.identity_state == llm_refine.IDENTITY_UNREPORTED
    assert record.reported_model in (None, "")


# --------------------------------------------------------------------------- #
# V9：轮换、重试、流式冲突
# --------------------------------------------------------------------------- #


def test_V9a_provider轮换每次尝试各自成条且不串():
    with llm_refine.call_ledger_scope() as ledger:
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError()):
            with pytest.raises(Exception):
                _post(PROVIDER, b"")
        _post(PROVIDER_B, _chat_body(model="gpt-4.1-mini-2026"))

    first, second = ledger.records
    assert first.status == "failed" and second.status == "success"
    # attempt 身份各自独立：不靠列表位置关联
    assert first.attempt_id and second.attempt_id
    assert first.attempt_id != second.attempt_id
    # 身份不串：失败那条没有借到后面成功那条的模型
    assert first.reported_model in (None, "")
    assert second.reported_model == "gpt-4.1-mini-2026"
    assert first.requested_model == "glm-5.2"
    assert second.requested_model == "gpt-4.1-mini"


def test_V9b_流式分块换模型记冲突不取第一个():
    """后续分块报了另一个模型 = 身份冲突，必须留痕。

    改之前这里是 `if not served_model:` —— 只认第一个分块，换模型被静默掩盖。
    """

    body = _sse(
        _chunk("前", model="glm-5.2"),
        _chunk("后", model="gpt-5.6-sol"),
    )
    with llm_refine.call_ledger_scope() as ledger:
        _stream(PROVIDER, body)

    (record,) = ledger.records
    assert record.status == "success"
    assert record.identity_state == llm_refine.IDENTITY_REPORTED
    assert "gpt-5.6-sol" in record.reported_model_conflicts
    assert record.reported_model == "glm-5.2"


def test_V9b2_流式分块模型一致时不报冲突():
    body = _sse(_chunk("前", model="glm-5.2"), _chunk("后", model="glm-5.2"))
    with llm_refine.call_ledger_scope() as ledger:
        _stream(PROVIDER, body)

    (record,) = ledger.records
    assert record.reported_model_conflicts == ()
    assert record.reported_model == "glm-5.2"


def test_V9c_成功的身份冲突不被后续重试擦掉():
    """先一条带冲突的成功，再一条干净的成功——冲突那条原样还在。"""

    conflicted = _sse(_chunk("前", model="glm-5.2"), _chunk("后", model="gpt-5.6-sol"))
    clean = _sse(_chunk("再来", model="glm-5.2"))
    with llm_refine.call_ledger_scope() as ledger:
        _stream(PROVIDER, conflicted)
        _stream(PROVIDER, clean)

    first, second = ledger.records
    assert "gpt-5.6-sol" in first.reported_model_conflicts
    assert second.reported_model_conflicts == ()


# --------------------------------------------------------------------------- #
# V10 / V12：作用域与预算
# --------------------------------------------------------------------------- #


def test_V10_嵌套作用域复用外层台账不重置预算():
    with llm_refine.call_ledger_scope(max_calls=1) as outer:
        with llm_refine.call_ledger_scope(max_calls=99) as inner:
            assert inner is outer
            assert inner.max_calls == 1  # 内层的 99 不生效
        _post(PROVIDER, _chat_body(model="glm-5.2"))
        assert outer.over_budget()


def test_V12_预算拒发是not_called不伪造已花费的attempt():
    with llm_refine.call_ledger_scope(max_calls=1) as ledger:
        _post(PROVIDER, _chat_body(model="glm-5.2"))
        with pytest.raises(llm_refine.LLMCallBudgetExceeded):
            _post(PROVIDER, _chat_body(model="glm-5.2"))

    # 只有一条真花了钱的记录；被拒那次进 rejected_count，不进 records
    assert len(ledger.records) == 1
    assert ledger.rejected_count == 1
    assert ledger.records[0].identity_state == llm_refine.IDENTITY_REPORTED


def test_summary里带出身份字段可进收据():
    with llm_refine.call_ledger_scope() as ledger:
        _post(PROVIDER, _chat_body(model="glm-5.2-0930"))

    summary = ledger.summary()
    (row,) = summary["records"]
    assert row["identity_state"] == llm_refine.IDENTITY_REPORTED
    assert row["reported_model"] == "glm-5.2-0930"
    assert row["requested_model"] == "glm-5.2"
    assert row["attempt_id"]
    # 收据要能序列化
    json.dumps(summary, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# 跨层常量一致性
# --------------------------------------------------------------------------- #


def test_身份状态常量与eval层逐字一致():
    """``judge_validity`` 不得 import services，所以两边各存一份字面量。

    各存一份就会漂，而漂的时候 ``identity_state != "reported"`` 会让**所有**
    评分被判 unknown，或者反过来放行——两个方向都是静默的。这条测试把漂变成红。
    """

    assert llm_refine.IDENTITY_NOT_CALLED == judge_validity.IDENTITY_NOT_CALLED
    assert llm_refine.IDENTITY_UNREPORTED == judge_validity.IDENTITY_UNREPORTED
    assert llm_refine.IDENTITY_REPORTED == judge_validity.IDENTITY_REPORTED
