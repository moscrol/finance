from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import replace
from datetime import datetime
from subprocess import CompletedProcess

import pytest

from intelligence.services import grok_cli_judge, llm_refine


PROVIDER = llm_refine.LLMProvider("fixture", "secret", "https://example.invalid/v1", "requested")
MESSAGES = [{"role": "user", "content": "question"}]


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Response:
    def __init__(self, body: object, *, headers: dict | None = None) -> None:
        self.body = json.dumps(body).encode() if not isinstance(body, bytes) else body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.body

    def __iter__(self):
        return iter(self.body.splitlines(keepends=True))

    def close(self):
        return None


def body(content="answer", **extra):
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}], **extra}


def sse(*events):
    return ("".join(f"data: {json.dumps(event)}\n" for event in events) + "data: [DONE]\n").encode()


def test_http_fallback_preserves_failed_attempt_and_selects_returned_content(monkeypatch):
    second = replace(PROVIDER, model="second", base_url="https://other.invalid/v1")
    calls = []

    def urlopen(request, timeout=0.0, **_kwargs):
        calls.append(json.loads(request.data))
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 503, "error model=not-proof", {}, None)
        return Response(body(" final\n", model="reported", id="response-2"), headers={"x-request-id": "request-2"})

    monkeypatch.setattr(llm_refine, "detect_providers", lambda *_: (PROVIDER, second))
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", urlopen)
    with llm_refine.call_ledger_scope(max_calls=2) as ledger:
        with llm_refine.call_provenance_scope("judge-one", "judge") as context:
            content, used, reason = llm_refine.complete(MESSAGES)
        records = ledger.records_for_call("judge-one")
    assert (content, used, reason) == (" final\n", second, "")
    assert len(records) == 2
    failed, succeeded = records
    assert failed["status"] == "failed" and failed["reported_model"] is None
    assert failed["identity_state"] == "unreported"
    assert failed["attempt_id"] != succeeded["attempt_id"] == context.selected_attempt_id
    assert succeeded["reported_model"] == "reported"
    assert succeeded["requested_model"] == calls[1]["model"]
    assert succeeded["request_sha256"] == canonical_hash(calls[1]["messages"])
    assert succeeded["result_sha256"] == text_hash(content)
    assert succeeded["response_id"] == "response-2" and succeeded["request_id"] == "request-2"
    assert succeeded["transport"] == "http" and succeeded["phase"] == "judge"
    assert datetime.fromisoformat(succeeded["started_at"]) <= datetime.fromisoformat(succeeded["completed_at"])
    assert json.loads(json.dumps(records)) == records
    records[0]["status"] = "tampered"
    assert ledger.records_for_call("judge-one")[0]["status"] == "failed"


def test_success_without_structured_model_never_uses_requested_model(monkeypatch):
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", lambda *_a, **_k: Response(body("I am requested")))
    with llm_refine.call_ledger_scope() as ledger, llm_refine.call_provenance_scope("unknown", "judge") as context:
        llm_refine._post_chat(PROVIDER, MESSAGES, 5)
    record = ledger.records_for_call("unknown")[0]
    assert record["identity_state"] == "unreported"
    assert record["reported_model"] is None
    assert context.selected_attempt_id == record["attempt_id"]


def test_nested_ledger_reuses_budget_and_rejected_call_has_no_attempt(monkeypatch):
    calls = []
    monkeypatch.setattr(llm_refine, "detect_providers", lambda *_: (PROVIDER,))
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", lambda *_a, **_k: calls.append(1) or Response(body(model="served")))
    with llm_refine.call_ledger_scope(max_calls=1) as ledger:
        with llm_refine.call_ledger_scope(max_calls=99, reuse_existing=True) as nested:
            assert nested is ledger
            with llm_refine.call_provenance_scope("first", "writer"):
                llm_refine.complete(MESSAGES)
        with llm_refine.call_provenance_scope("rejected", "judge") as context:
            assert llm_refine.complete(MESSAGES)[0] is None
        assert context.selected_attempt_id is None and context.identity_state == "not_called"
        assert ledger.records_for_call("rejected") == []
        assert ledger.summary()["reserved_count"] == 1
    assert len(calls) == 1


def test_endpoint_identifier_cannot_expose_url_credentials_or_path():
    first = replace(PROVIDER, base_url="HTTPS://user:password@Example.Invalid:443/private/token/?key=secret#fragment")
    second = replace(PROVIDER, base_url="https://example.invalid/private/token")
    identifier = llm_refine.provider_endpoint_id(first)
    assert identifier == llm_refine.provider_endpoint_id(second)
    assert len(identifier) == 64 and set(identifier) <= set("0123456789abcdef")
    assert identifier != llm_refine.provider_endpoint_id(PROVIDER)


@pytest.mark.parametrize("metadata", [{}, {"model": "grok-reported", "id": "cli-response", "request_id": "cli-request"}])
def test_cli_retains_only_structured_identity_and_output_binding(monkeypatch, metadata):
    original = grok_cli_judge.complete_grok_cli
    monkeypatch.setenv("LLM_JUDGE_GROK_BIN", "/fixture/grok")

    def runner(argv, **_kwargs):
        return CompletedProcess(argv, 0, stdout=json.dumps({"text": '{"passed":true}', **metadata}), stderr="")

    monkeypatch.setattr(grok_cli_judge, "complete_grok_cli", lambda *a, **k: original(*a, **k, runner=runner))
    provider = replace(PROVIDER, base_url="cli://grok", transport="cli", model="grok-requested")
    with llm_refine.call_ledger_scope() as ledger, llm_refine.call_provenance_scope("cli", "judge") as context:
        content = llm_refine._complete_cli_judge(provider, MESSAGES, 5)
    record = ledger.records_for_call("cli")[0]
    assert record["reported_model"] == metadata.get("model")
    assert record["identity_state"] == ("reported" if metadata else "unreported")
    assert record["result_sha256"] == text_hash(content)
    assert record["transport"] == "cli"
    assert record["response_id"] == metadata.get("id")
    assert record["request_id"] == metadata.get("request_id")
    assert context.selected_attempt_id == record["attempt_id"]


@pytest.mark.parametrize("kind", ["synthesis", "tools", "tools_stream", "synthesis_stream"])
def test_writer_transports_record_identity_and_detect_stream_conflict(monkeypatch, kind):
    streaming = "stream" in kind
    wire = sse(
        {"model": "first", "id": "stream-response", "choices": [{"delta": {"content": "an"}}]},
        {"model": "second", "choices": [{"delta": {"content": "swer"}, "finish_reason": "stop"}]},
    ) if streaming else body(model="served")
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", lambda *_a, **_k: Response(wire))
    with llm_refine.call_ledger_scope() as ledger, llm_refine.call_provenance_scope("writer", "writer"):
        if kind == "synthesis":
            llm_refine._post_chat_synthesis(PROVIDER, MESSAGES, 5, 0, 100, 100)
        elif kind == "tools":
            llm_refine._post_chat_message(PROVIDER, MESSAGES, 5)
        elif kind == "tools_stream":
            llm_refine._post_chat_message_stream(PROVIDER, MESSAGES, 5, 0, [], None, False, lambda _: None)
        else:
            llm_refine._post_chat_stream(PROVIDER, MESSAGES, 5, 0, lambda _: None, None, None, llm_refine.Deadline.from_timeout(5), 100, 100)
    record = ledger.records_for_call("writer")[0]
    assert record["reported_model"] == ("first" if streaming else "served")
    assert record["identity_conflict"] is streaming
    assert record["result_sha256"] == text_hash("answer")


def test_concurrent_calls_select_own_attempt_when_completion_order_is_reversed(monkeypatch):
    both_started = threading.Barrier(2)
    second_done = threading.Event()

    def urlopen(request, timeout=0.0, **_kwargs):
        name = json.loads(request.data)["messages"][0]["content"]
        both_started.wait(timeout=3)
        if name == "one":
            assert second_done.wait(timeout=3)
        else:
            second_done.set()
        return Response(body(name, model=f"model-{name}"))

    monkeypatch.setattr(llm_refine, "detect_providers", lambda *_: (PROVIDER,))
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", urlopen)

    def run(name):
        with llm_refine.call_provenance_scope(name, "judge") as context:
            content, _, _ = llm_refine.complete([{"role": "user", "content": name}])
        return name, content, context.selected_attempt_id

    with llm_refine.call_ledger_scope(max_calls=2) as ledger, ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(copy_context().run, run, name) for name in ("one", "two")]
        results = [future.result(timeout=5) for future in futures]
    for name, content, selected in results:
        [record] = ledger.records_for_call(name)
        assert record["attempt_id"] == selected
        assert record["reported_model"] == f"model-{name}"
        assert record["result_sha256"] == text_hash(content)


def test_async_scopes_and_nested_calls_restore_parent_context(monkeypatch):
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", lambda *_a, **_k: Response(body(model="served")))

    async def run(name):
        with llm_refine.call_provenance_scope(name, "judge") as context:
            await asyncio.sleep(0)
            llm_refine._post_chat(PROVIDER, MESSAGES, 5)
        return name, context.selected_attempt_id

    async def gather():
        return await asyncio.gather(run("one"), run("two"))

    with llm_refine.call_ledger_scope() as ledger, llm_refine.call_provenance_scope("outer", "writer") as outer:
        results = asyncio.run(gather())
        assert outer.selected_attempt_id is None
        llm_refine._post_chat(PROVIDER, MESSAGES, 5)
    for name, selected in results:
        assert ledger.records_for_call(name)[0]["attempt_id"] == selected
    assert ledger.records_for_call("outer")[0]["attempt_id"] == outer.selected_attempt_id


def test_json_retry_keeps_first_success_with_unknown_identity(monkeypatch):
    responses = iter([body("not judge JSON"), body('{"score": 4}', model="served")])
    monkeypatch.setattr(llm_refine, "detect_providers", lambda *_: (PROVIDER,))
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", lambda *_a, **_k: Response(next(responses)))
    repaired = [*MESSAGES, {"role": "user", "content": "Return JSON only"}]
    with llm_refine.call_ledger_scope() as ledger, llm_refine.call_provenance_scope("retry", "judge") as context:
        assert llm_refine.complete(MESSAGES)[0] == "not judge JSON"
        assert llm_refine.complete(repaired)[0] == '{"score": 4}'
    first, last = ledger.records_for_call("retry")
    assert first["status"] == "success" and first["identity_state"] == "unreported"
    assert first["attempt_id"] != last["attempt_id"] == context.selected_attempt_id
    assert first["request_sha256"] == canonical_hash(MESSAGES)
    assert last["request_sha256"] == canonical_hash(repaired)


def test_no_active_ledger_cannot_claim_collected_success(monkeypatch):
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", lambda *_a, **_k: Response(body(model="served")))
    assert llm_refine.current_call_ledger() is None
    with llm_refine.call_provenance_scope("missing-ledger", "judge") as context:
        assert llm_refine._post_chat(PROVIDER, MESSAGES, 5) == "answer"
    assert context.selected_attempt_id is None


def test_failed_cli_attempt_is_preserved_without_credential_text(monkeypatch):
    monkeypatch.setenv("LLM_JUDGE_GROK_BIN", "/fixture/grok")
    original = grok_cli_judge.complete_grok_cli
    monkeypatch.setattr(grok_cli_judge, "complete_grok_cli", lambda *a, **k: original(
        *a, **k, runner=lambda argv, **_: CompletedProcess(argv, 1, stdout="", stderr="secret output")
    ))
    provider = replace(PROVIDER, base_url="cli://grok", transport="cli")
    with llm_refine.call_ledger_scope() as ledger, llm_refine.call_provenance_scope("cli-fail", "judge") as context:
        with pytest.raises(grok_cli_judge.GrokCliExit):
            llm_refine._complete_cli_judge(provider, MESSAGES, 5)
    [record] = ledger.records_for_call("cli-fail")
    assert record["status"] == "failed" and record["reported_model"] is None
    assert record["identity_state"] == "unreported" and record["reason"] == "grok_cli_exit"
    assert context.selected_attempt_id is None and "secret" not in json.dumps(record)


def test_tool_response_hash_binds_tool_arguments_as_well_as_content(monkeypatch):
    result = {"role": "assistant", "content": None, "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "lookup", "arguments": '{"ticker":"A"}'}}]}
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", lambda *_a, **_k: Response({"model": "served", "choices": [{"message": result}]}))
    with llm_refine.call_ledger_scope() as ledger, llm_refine.call_provenance_scope("tools", "writer"):
        llm_refine._post_chat_message(PROVIDER, MESSAGES, 5)
    [record] = ledger.records_for_call("tools")
    assert record["result_hash_kind"] == "tool_message_canonical_json"
    assert record["result_sha256"] == canonical_hash({"content": None, "tool_calls": result["tool_calls"]})


def test_http_failure_keeps_request_id_but_ignores_error_page_identity(monkeypatch):
    def urlopen(*_a, **_k):
        raise urllib.error.HTTPError(PROVIDER.base_url, 503, "served model=untrusted", {"x-request-id": "failed-request"}, None)

    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", urlopen)
    with llm_refine.call_ledger_scope() as ledger, llm_refine.call_provenance_scope("http-fail", "judge"):
        with pytest.raises(urllib.error.HTTPError):
            llm_refine._post_chat(PROVIDER, MESSAGES, 5)
    [record] = ledger.records_for_call("http-fail")
    assert record["request_id"] == "failed-request"
    assert record["reported_model"] is None
