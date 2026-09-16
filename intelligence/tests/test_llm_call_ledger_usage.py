"""判官侧 token 用量记进 LLMCallLedger（INDEX #23）。

钉住的契约：

1. ``token_usage_counts`` 双命名取值（prompt/completion 与 input/output），bool 不算数；
2. ``_post_chat`` 读响应顶层 usage → 记录带 ``usage_source=api``；缺 usage 记 None 不抛；
3. grok CLI：payload 带 usage → ``cli``；不带 → 字符估算且**必带** ``estimated`` 标记，
   ``estimated_share > 0``；``_extract_text`` 行为不变；
4. ``summary()`` 合计 = 各 record 之和，``tokens_by_purpose.judge`` 只含判官调用；
5. ``call_purpose`` ContextVar 嵌套不串；
6. verifier → complete → _post_chat 这条真实链路上，判官记录带 ``purpose=judge``；
7. adapter 的 ``metrics.judge_usage`` 差分与来源合并规则。
"""

from __future__ import annotations

import json
import subprocess

import pytest

from intelligence.runtime import continuous_turn_adapter
from intelligence.services import grok_cli_judge, llm_refine, llm_usage
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_episode_semantic_verifier import _structural

JUDGE_JSON = '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}'
JUDGE_MESSAGES = [
    {"role": "system", "content": "你是判官，只输出 JSON。"},
    {"role": "user", "content": '{"sentences":[{"index":0,"text":"市场当前偏弱。"}]}'},
]


class _FakeHttpResponse:
    def __init__(self, body: dict) -> None:
        self._body = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def _http_provider(name: str = "judge") -> llm_refine.LLMProvider:
    return llm_refine.LLMProvider(name, "secret", "https://judge.invalid/v1", "glm-5.2")


def _cli_provider() -> llm_refine.LLMProvider:
    return llm_refine.LLMProvider(
        "grok-cli-judge", "", grok_cli_judge.CLI_GROK_URL, "grok-4.6", transport="cli"
    )


def _install_http(monkeypatch: pytest.MonkeyPatch, body: dict) -> None:
    monkeypatch.setattr(
        llm_refine.urllib.request,
        "urlopen",
        lambda request, timeout=0.0: _FakeHttpResponse(body),
    )


def _install_cli(monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
    monkeypatch.setattr(
        grok_cli_judge, "resolve_grok_binary", lambda env=None: "/fake/grok"
    )

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout=json.dumps(payload), stderr=""
        )

    original = grok_cli_judge.complete_grok_cli
    monkeypatch.setattr(
        grok_cli_judge,
        "complete_grok_cli",
        lambda provider, messages, timeout: original(
            provider, messages, timeout, runner=fake_run
        ),
    )


# ── 1. 双命名取值 ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "usage, expected",
    [
        ({"prompt_tokens": 1222, "completion_tokens": 286}, (1222, 286)),
        ({"input_tokens": 19326, "output_tokens": 970}, (19326, 970)),
        # 两套都在时 input/output 优先（与 runtime 原逻辑一致）。
        ({"input_tokens": 5, "prompt_tokens": 9, "output_tokens": 1, "completion_tokens": 7}, (5, 1)),
        ({"prompt_tokens": True, "completion_tokens": -1}, (None, None)),
        ({}, (None, None)),
        (None, (None, None)),
        ("not-a-mapping", (None, None)),
    ],
)
def test_token_usage_counts_dual_naming(usage, expected) -> None:
    assert llm_usage.token_usage_counts(usage) == expected


def test_runtime_message_token_usage_delegates_to_services() -> None:
    from intelligence.runtime.glm_agent_runtime import _message_token_usage

    assert _message_token_usage({"_usage": {"prompt_tokens": 3, "completion_tokens": 2}}) == (3, 2)
    assert _message_token_usage({"usage": {"input_tokens": 4, "output_tokens": 1}}) == (4, 1)
    assert _message_token_usage({}) == (None, None)


# ── 2. API 判官：_post_chat 读 usage ───────────────────────────────────


@pytest.mark.parametrize(
    "usage, expected",
    [
        ({"prompt_tokens": 1222, "completion_tokens": 286}, (1222, 286)),
        ({"input_tokens": 1500, "output_tokens": 40}, (1500, 40)),
    ],
)
def test_post_chat_records_usage_from_either_naming(monkeypatch, usage, expected) -> None:
    _install_http(
        monkeypatch,
        {"choices": [{"message": {"content": JUDGE_JSON}}], "usage": usage},
    )
    with llm_refine.call_ledger_scope() as ledger:
        content = llm_refine._post_chat(_http_provider(), JUDGE_MESSAGES, timeout=5.0)
    assert content == JUDGE_JSON
    assert len(ledger.records) == 1
    record = ledger.records[0]
    assert (record.input_tokens, record.output_tokens) == expected
    assert record.usage_source == llm_usage.USAGE_SOURCE_API
    assert record.status == "success"


def test_post_chat_without_usage_records_none_and_does_not_raise(monkeypatch) -> None:
    _install_http(monkeypatch, {"choices": [{"message": {"content": JUDGE_JSON}}]})
    with llm_refine.call_ledger_scope() as ledger:
        content = llm_refine._post_chat(_http_provider(), JUDGE_MESSAGES, timeout=5.0)
    assert content == JUDGE_JSON
    record = ledger.records[0]
    assert record.input_tokens is None and record.output_tokens is None
    # 没有用量就没有来源：读者靠 usage_source 是否存在判「有没有」。
    assert record.usage_source is None
    summary = ledger.summary()
    assert summary["input_tokens_total"] == 0
    assert summary["estimated_share"] == 0.0
    assert "input_tokens" not in summary["records"][0]
    assert "usage_source" not in summary["records"][0]


# ── 3. CLI 判官：有 usage → cli；无 usage → estimated ───────────────────


def test_cli_payload_with_usage_records_cli_source(monkeypatch) -> None:
    # 生产 grok 1.0.5 的真实 payload 形状（2026-09-05 探针，见 llm_usage docstring）。
    payload = {
        "text": JUDGE_JSON,
        "stopReason": "end_turn",
        "usage": {
            "input_tokens": 19326,
            "cache_read_input_tokens": 128,
            "cache_creation_input_tokens": 0,
            "output_tokens": 970,
            "reasoning_tokens": 858,
            "total_tokens": 20424,
        },
        "modelUsage": {
            "grok-4.6-build": {"inputTokens": 19326, "outputTokens": 970, "modelCalls": 1}
        },
    }
    _install_cli(monkeypatch, payload)
    with llm_refine.call_ledger_scope() as ledger:
        with llm_refine.provider_override(_cli_provider()):
            content, used, reason = llm_refine.complete(JUDGE_MESSAGES, timeout=20)
    assert reason == "" and used is not None
    assert type(content) is str, "对外契约仍是纯 str"
    assert json.loads(content)["passed"] is True
    record = ledger.records[0]
    assert (record.input_tokens, record.output_tokens) == (19326, 970)
    assert record.usage_source == llm_usage.USAGE_SOURCE_CLI
    assert ledger.summary()["estimated_share"] == 0.0


def test_cli_payload_model_usage_fallback() -> None:
    payload = {
        "text": JUDGE_JSON,
        "modelUsage": {
            "grok-a": {"inputTokens": 100, "outputTokens": 10},
            "grok-b": {"inputTokens": 50, "outputTokens": 5},
        },
    }
    assert llm_usage.cli_payload_token_usage(payload) == (150, 15)
    assert llm_usage.cli_payload_token_usage({"text": JUDGE_JSON}) == (None, None)
    assert llm_usage.cli_payload_token_usage({"passed": True}) == (None, None)
    assert llm_usage.cli_payload_token_usage("raw") == (None, None)


def test_cli_payload_without_usage_falls_back_to_estimate_with_marker(monkeypatch) -> None:
    _install_cli(monkeypatch, {"text": JUDGE_JSON, "stopReason": "end_turn"})
    with llm_refine.call_ledger_scope() as ledger:
        with llm_refine.provider_override(_cli_provider()):
            content, _used, reason = llm_refine.complete(JUDGE_MESSAGES, timeout=20)
    assert reason == ""
    record = ledger.records[0]
    assert record.usage_source == llm_usage.USAGE_SOURCE_ESTIMATED
    expected = llm_usage.estimate_token_usage(JUDGE_MESSAGES, content)
    assert (record.input_tokens, record.output_tokens) == expected
    assert record.input_tokens > 0 and record.output_tokens > 0
    summary = ledger.summary()
    assert summary["estimated_share"] > 0
    assert summary["records"][0]["usage_source"] == "estimated"


def test_plain_str_test_double_still_gets_estimated_marker(monkeypatch) -> None:
    """既有测试把 complete_grok_cli 换成回裸 str 的 lambda——照样记账、照样标 estimated。"""

    monkeypatch.setattr(
        grok_cli_judge, "complete_grok_cli", lambda *_args, **_kwargs: JUDGE_JSON
    )
    with llm_refine.call_ledger_scope() as ledger:
        with llm_refine.provider_override(_cli_provider()):
            content, _used, reason = llm_refine.complete(JUDGE_MESSAGES, timeout=20)
    assert reason == "" and content == JUDGE_JSON
    assert ledger.records[0].usage_source == "estimated"


def test_extract_text_behaviour_unchanged_with_or_without_usage() -> None:
    with_usage = json.dumps(
        {"text": f"```json\n{JUDGE_JSON}\n```", "usage": {"input_tokens": 1, "output_tokens": 2}}
    )
    without_usage = json.dumps({"text": f"```json\n{JUDGE_JSON}\n```"})
    assert grok_cli_judge._extract_text(with_usage) == JUDGE_JSON
    assert grok_cli_judge._extract_text(without_usage) == JUDGE_JSON
    direct = json.dumps({"passed": False, "rejected_sentence_indexes": [1], "issues": ["x"]})
    assert json.loads(grok_cli_judge._extract_text(direct))["passed"] is False
    with pytest.raises(grok_cli_judge.GrokCliEmptyResponse):
        grok_cli_judge._extract_text("   ")
    with pytest.raises(grok_cli_judge.GrokCliInvalidJson):
        grok_cli_judge._extract_text("{not json")


def test_estimate_is_cjk_weighted_and_never_negative() -> None:
    zh = llm_usage.estimate_token_count("中文" * 130)  # 260 个汉字
    en = llm_usage.estimate_token_count("a" * 260)
    assert zh == 200 and en == 52, "同字符数下中文估算 token 更多（1.3 vs 5.0 字符/token）"
    assert llm_usage.estimate_token_count("") == 0
    assert llm_usage.estimate_token_usage([], None) == (0, 0)
    # 校准点：2026-09-05 判官提示词 2951 字符（中文 1142 / 其他 1809）→ GLM 实测 1222。
    prompt = "中" * 1142 + "a" * 1809
    estimate = llm_usage.estimate_token_count(prompt)
    assert abs(estimate - 1222) / 1222 < 0.03


# ── 4. summary 合计与按 purpose 分组 ────────────────────────────────────


def _record(**overrides) -> llm_refine.LLMCallRecord:
    base = dict(
        caller="chat", provider="p", model="m", status="success", elapsed_ms=1
    )
    base.update(overrides)
    return llm_refine.LLMCallRecord(**base)


def test_summary_totals_and_by_purpose_from_synthetic_sequence() -> None:
    ledger = llm_refine.LLMCallLedger()
    ledger.record(
        _record(
            caller="chat_tools",
            input_tokens=37_000,
            output_tokens=1_400,
            usage_source="api",
            purpose=None,  # 写手：未标注
        )
    )
    ledger.record(
        _record(
            input_tokens=19_326,
            output_tokens=970,
            usage_source="cli",
            purpose="judge",
        )
    )
    ledger.record(_record(status="failed", reason="timeout", purpose="judge"))
    summary = ledger.summary()
    assert summary["input_tokens_total"] == 37_000 + 19_326
    assert summary["output_tokens_total"] == 1_400 + 970
    assert summary["input_tokens_total"] == sum(
        record.input_tokens or 0 for record in ledger.records
    )
    by_purpose = summary["tokens_by_purpose"]
    assert by_purpose["judge"] == {"calls": 2, "input_tokens": 19_326, "output_tokens": 970}
    assert by_purpose[llm_refine.UNLABELLED_PURPOSE] == {
        "calls": 1,
        "input_tokens": 37_000,
        "output_tokens": 1_400,
    }
    assert summary["estimated_share"] == 0.0
    records = summary["records"]
    assert records[1]["purpose"] == "judge" and records[1]["usage_source"] == "cli"
    assert "purpose" not in records[0]
    assert "input_tokens" not in records[2]
    # 老键一字不变
    assert summary["call_count"] == 3 and summary["failure_count"] == 1


def test_estimated_share_counts_only_records_with_usage() -> None:
    ledger = llm_refine.LLMCallLedger()
    ledger.record(_record(input_tokens=10, output_tokens=1, usage_source="api"))
    ledger.record(_record(input_tokens=20, output_tokens=2, usage_source="estimated"))
    ledger.record(_record(status="failed", reason="http_500"))
    assert ledger.summary()["estimated_share"] == 0.5


# ── 5. purpose ContextVar 嵌套 ─────────────────────────────────────────


def test_call_purpose_nesting_does_not_leak(monkeypatch) -> None:
    _install_http(
        monkeypatch,
        {
            "choices": [{"message": {"content": JUDGE_JSON}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        },
    )
    provider = _http_provider()
    with llm_refine.call_ledger_scope() as ledger:
        assert llm_refine.current_call_purpose() is None
        llm_refine._post_chat(provider, JUDGE_MESSAGES, timeout=5.0)  # 未标注
        with llm_refine.call_purpose("judge"):
            llm_refine._post_chat(provider, JUDGE_MESSAGES, timeout=5.0)
            with llm_refine.call_purpose("writer"):  # 判官作用域里的修复轮写手调用
                llm_refine._post_chat(provider, JUDGE_MESSAGES, timeout=5.0)
            llm_refine._post_chat(provider, JUDGE_MESSAGES, timeout=5.0)
        assert llm_refine.current_call_purpose() is None
        llm_refine._post_chat(provider, JUDGE_MESSAGES, timeout=5.0)
    assert [record.purpose for record in ledger.records] == [
        None,
        "judge",
        "writer",
        "judge",
        None,
    ]
    by_purpose = ledger.summary()["tokens_by_purpose"]
    assert by_purpose["judge"]["calls"] == 2 and by_purpose["judge"]["input_tokens"] == 20
    assert by_purpose["writer"]["calls"] == 1


def test_call_purpose_resets_on_exception() -> None:
    with pytest.raises(RuntimeError):
        with llm_refine.call_purpose("judge"):
            raise RuntimeError("boom")
    assert llm_refine.current_call_purpose() is None


# ── 6. verifier 真实链路：判官记录带 purpose=judge ───────────────────────


def test_verifier_judge_call_is_labelled_judge_end_to_end(monkeypatch) -> None:
    frame, structural = _structural("市场当前偏弱。")
    provider = _http_provider("judge")
    monkeypatch.setattr(llm_refine, "judge_provider_chain", lambda: (provider,))
    _install_http(
        monkeypatch,
        {
            "choices": [{"message": {"content": JUDGE_JSON}}],
            "usage": {"prompt_tokens": 1222, "completion_tokens": 286},
        },
    )
    with llm_refine.call_ledger_scope() as ledger:
        result = SemanticEpisodeVerifier().verify(
            frame=frame,
            structurally_verified=structural,
            deadline=ResearchDeadline.from_timeout(60),
        )
    assert result.judge_status == "passed"
    judge_records = [record for record in ledger.records if record.purpose == "judge"]
    assert len(judge_records) == 1
    assert (judge_records[0].input_tokens, judge_records[0].output_tokens) == (1222, 286)
    assert judge_records[0].usage_source == "api"
    assert all(record.purpose == "judge" for record in ledger.records), (
        "本例只有判官调用，不该出现其他标签"
    )
    # 作用域退出后不残留
    assert llm_refine.current_call_purpose() is None


# ── 7. adapter metrics.judge_usage 差分与来源合并 ─────────────────────────


def test_adapter_judge_usage_diffs_from_attempts_before() -> None:
    with llm_refine.call_ledger_scope() as ledger:
        # 上一轮 turn 留下的判官记录——不该算进本轮
        ledger.record(_record(input_tokens=999, output_tokens=9, usage_source="cli", purpose="judge"))
        attempts_before = continuous_turn_adapter._ledger_attempt_count()
        ledger.record(_record(caller="chat_tools", input_tokens=37_000, output_tokens=1_400, usage_source="api"))
        ledger.record(_record(input_tokens=19_326, output_tokens=970, usage_source="cli", purpose="judge"))
        ledger.record(_record(input_tokens=18_000, output_tokens=900, usage_source="cli", purpose="judge"))
        usage = continuous_turn_adapter._ledger_judge_usage(attempts_before)
    assert usage == {
        "calls": 2,
        "input_tokens": 19_326 + 18_000,
        "output_tokens": 970 + 900,
        "usage_source": "cli",
    }


@pytest.mark.parametrize(
    "sources, expected",
    [
        (["cli", "cli"], "cli"),
        (["api"], "api"),
        (["cli", "estimated"], "estimated"),  # 任一估算 → 整块标估算
        (["cli", "api"], "mixed"),  # 主判官 CLI + 备胎 API 都是真实值
        ([None], None),  # 判官调了但没拿到用量
    ],
)
def test_adapter_judge_usage_source_merge_rules(sources, expected) -> None:
    with llm_refine.call_ledger_scope() as ledger:
        for source in sources:
            ledger.record(
                _record(
                    input_tokens=None if source is None else 10,
                    output_tokens=None if source is None else 1,
                    usage_source=source,
                    purpose="judge",
                )
            )
        usage = continuous_turn_adapter._ledger_judge_usage(0)
    assert usage["calls"] == len(sources)
    assert usage["usage_source"] == expected
    if expected is None:
        assert usage["input_tokens"] is None and usage["output_tokens"] is None


def test_adapter_judge_usage_without_ledger_or_judge_calls_is_zero_shape() -> None:
    assert continuous_turn_adapter._ledger_judge_usage(0) == {
        "calls": 0,
        "input_tokens": None,
        "output_tokens": None,
        "usage_source": None,
    }
    with llm_refine.call_ledger_scope() as ledger:
        ledger.record(_record(caller="chat_tools", input_tokens=5, output_tokens=1, usage_source="api"))
        usage = continuous_turn_adapter._ledger_judge_usage(0)
    assert usage["calls"] == 0 and usage["usage_source"] is None


def test_episode_metrics_carries_judge_usage(monkeypatch) -> None:
    with llm_refine.call_ledger_scope() as ledger:
        before = continuous_turn_adapter._ledger_attempt_count()
        ledger.record(_record(input_tokens=100, output_tokens=10, usage_source="estimated", purpose="judge"))
        metrics = continuous_turn_adapter._episode_metrics(
            None,
            attempts_before=before,
            structural_status="completed",
            semantic_status="passed",
        )
    assert metrics["judge_usage"] == {
        "calls": 1,
        "input_tokens": 100,
        "output_tokens": 10,
        "usage_source": "estimated",
    }
    assert metrics["provider_attempts"] == 1
