"""Keep stalled-read cancellation assertions in the ordinary test suite."""
from __future__ import annotations

from contextlib import contextmanager
import time

import pytest

from intelligence.services import llm_refine
from scripts.review_probes.diagnose_llm_timeout import local_endpoint
from scripts.review_probes.probe_stalled_cancellation import remove_forwarding, run_case


@pytest.mark.parametrize("path", ["wrapper", "tools_stream", "synthesis_stream"])
def test_stalled_read_cancellation_is_prompt(path):
    result = run_case(llm_refine, local_endpoint, path)
    assert result["passed"], result


@pytest.mark.parametrize("path", ["wrapper", "tools_stream", "synthesis_stream"])
def test_read_cancellation_waits_for_headers_even_when_open_is_slow(monkeypatch, path):
    original = llm_refine._open_deadline_http_response

    @contextmanager
    def slow_open(*args, **kwargs):
        time.sleep(0.4)
        with original(*args, **kwargs) as response:
            yield response

    monkeypatch.setattr(llm_refine, "_open_deadline_http_response", slow_open)
    result = run_case(llm_refine, local_endpoint, path)
    assert result["passed"], result
    assert result["requests"] == result["attempts"] == 1


@pytest.mark.parametrize("path", ["wrapper", "tools_stream", "synthesis_stream"])
def test_probe_detects_missing_cancellation_forwarding(monkeypatch, path):
    original = llm_refine._open_deadline_http_response
    mutant = remove_forwarding(original, llm_refine.__dict__)
    with monkeypatch.context() as context:
        context.setattr(llm_refine, "_open_deadline_http_response", mutant)
        result = run_case(llm_refine, local_endpoint, path)
    assert not result["passed"], result
    assert result["elapsed_seconds"] >= 1.0
    assert result["requests"] == result["attempts"] == 1
    assert llm_refine._open_deadline_http_response is original
