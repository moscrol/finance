"""live 探针：run 目录一手证据、sidecar 起停约束、env 门控 LLM 上下文落盘。"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from intelligence.eval import live_probe as probe
from intelligence.services.ask_llm_context import (
    LLM_CONTEXT_FILENAME,
    llm_context_document,
    maybe_persist_llm_context,
    persist_enabled,
)
from intelligence.services.run_store import RunStore


STALE = "⚠️已被新证据取代"


def _write_run_dir(
    root: Path,
    *,
    with_llm_context: bool,
    stale_in_context: bool,
    stale_in_answer: bool,
) -> Path:
    run_dir = root / "run_fixture"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(
        json.dumps({"run_id": "run_fixture", "status": "completed"}),
        encoding="utf-8",
    )
    (run_dir / "report.json").write_text("{}", encoding="utf-8")
    answer = "长鑫收入按招股书口径很大。"
    if stale_in_answer:
        answer += STALE
    (run_dir / "answer.md").write_text(answer, encoding="utf-8")
    steps = [
        {
            "step_id": "s01",
            "name": "ask_retrieve_compose",
            "status": "completed",
            "started_at": "2026-08-17T22:00:00+08:00",
            "finished_at": "2026-08-17T22:02:10+08:00",
            "input_summary": "DRAM怎么看",
            "output_summary": "命中源：graph；引用 7 条",
        },
        {
            "step_id": "s02",
            "name": "render_artifacts",
            "status": "completed",
            "started_at": "2026-08-17T22:02:10+08:00",
            "finished_at": "2026-08-17T22:02:11+08:00",
            "output_summary": "answer.md + summary.json",
        },
    ]
    (run_dir / "trace.jsonl").write_text(
        "\n".join(json.dumps(step, ensure_ascii=False) for step in steps) + "\n",
        encoding="utf-8",
    )
    if with_llm_context:
        evidence = "[[晚间卖方研报20260518]] 长鑫 26Q1 收入"
        if stale_in_context:
            evidence += f" {STALE}"
        payload = {
            "prepared_synthesis_messages": [
                {"role": "system", "content": "你是研究助手"},
                {"role": "user", "content": evidence},
            ],
            "provider_traces": [
                {
                    "provider": "knowledge",
                    "capability": "evidence_index",
                    "status": "success",
                    "detail": "7 items",
                }
            ],
            "routed_modules": ["theme_radar"],
        }
        (run_dir / LLM_CONTEXT_FILENAME).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return run_dir


def test_inspect_grades_stale_marker_from_llm_context_not_answer(tmp_path: Path) -> None:
    run_dir = _write_run_dir(
        tmp_path,
        with_llm_context=True,
        stale_in_context=True,
        stale_in_answer=False,
    )
    inspection = probe.inspect_run_dir(run_dir)
    assert inspection.stale_marker_present is True
    assert inspection.evidence_grade == "llm_context"
    assert inspection.first_hand is True
    assert inspection.answer_mentions_stale is False
    assert LLM_CONTEXT_FILENAME in inspection.stale_marker_files
    assert "answer.md" not in inspection.stale_marker_files
    assert inspection.prompt_present is True
    assert "你是研究助手" in inspection.prompt_text
    assert inspection.steps[0]["step_id"] == "s01"
    assert inspection.steps[0]["name"] == "ask_retrieve_compose"
    assert inspection.tools[0]["provider"] == "knowledge"


def test_inspect_does_not_treat_answer_body_as_first_hand(tmp_path: Path) -> None:
    run_dir = _write_run_dir(
        tmp_path,
        with_llm_context=True,
        stale_in_context=False,
        stale_in_answer=True,
    )
    inspection = probe.inspect_run_dir(run_dir)
    assert inspection.answer_mentions_stale is True
    assert inspection.stale_marker_present is False
    assert inspection.first_hand is False
    assert inspection.evidence_grade == "absent"


def test_inspect_can_grade_trace_when_context_missing(tmp_path: Path) -> None:
    run_dir = _write_run_dir(
        tmp_path,
        with_llm_context=False,
        stale_in_context=False,
        stale_in_answer=False,
    )
    trace = run_dir / "trace.jsonl"
    trace.write_text(
        trace.read_text(encoding="utf-8")
        + json.dumps(
            {
                "step_id": "s01b",
                "name": "ask_retrieve_compose",
                "status": "completed",
                "output_summary": f"证据行含 {STALE}",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    inspection = probe.inspect_run_dir(run_dir)
    assert inspection.evidence_grade == "trace"
    assert inspection.first_hand is True
    assert "trace.jsonl" in inspection.stale_marker_files


def test_inspect_lists_trace_retrieval_when_provider_traces_missing(
    tmp_path: Path,
) -> None:
    run_dir = _write_run_dir(
        tmp_path,
        with_llm_context=False,
        stale_in_context=False,
        stale_in_answer=False,
    )
    steps = [
        json.loads(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    steps[0]["retrieval"] = {
        "sources": ["graph", "wiki"],
        "citation_counts": {"R": 8, "W": 17},
    }
    (run_dir / "trace.jsonl").write_text(
        "\n".join(json.dumps(step, ensure_ascii=False) for step in steps) + "\n",
        encoding="utf-8",
    )
    inspection = probe.inspect_run_dir(run_dir)
    assert inspection.tools[0]["sources"] == ["graph", "wiki"]
    assert inspection.tools[0]["citation_counts"] == {"R": 8, "W": 17}


def test_choose_port_skips_reserved_and_busy() -> None:
    busy = {8796, 8797}
    port = probe.choose_port(preferred=8792, is_busy=busy.__contains__)
    assert port == 8798
    assert port not in probe.RESERVED_PORTS


def test_assert_safe_to_start_blocks_live_lock(tmp_path: Path) -> None:
    lock = tmp_path / "finance-8792-live.lock"
    lock.write_text("held\n", encoding="utf-8")
    with pytest.raises(probe.ProbeBlocked, match="live.lock"):
        probe.assert_safe_to_start(lock_path=lock, port=8796, is_busy=lambda _port: False)


def test_assert_safe_to_start_blocks_busy_port() -> None:
    with pytest.raises(probe.ProbeBlocked, match="port 8796"):
        probe.assert_safe_to_start(
            lock_path=Path("/no/such/lock"),
            port=8796,
            is_busy=lambda port: port == 8796,
        )


def test_sidecar_zsh_overrides_grounded_and_does_not_exec_production_8792(
    tmp_path: Path,
) -> None:
    launcher = tmp_path / "start-finance-workbench"
    launcher.write_text("export FOO=1\nexec uvicorn --port 8792\n", encoding="utf-8")
    spec = probe.SidecarSpec(
        port=8796,
        repo_root=tmp_path / "repo",
        python=Path("/opt/venv/bin/python"),
        launcher=launcher,
        users_dir=tmp_path / "users",
        user="live-probe",
    )
    script = probe.sidecar_zsh(spec)
    assert "WORKBENCH_GROUNDED_PRESENTER=0" in script
    assert "WORKBENCH_PERSIST_LLM_CONTEXT=1" in script
    assert "RAG_WORKER_ENABLED=0" in script
    assert "--port 8796" in script
    assert "--port 8792" not in script
    assert "grep '^export '" in script
    assert "exec uvicorn" not in script.split("grep", 1)[0]


def test_llm_context_document_keeps_stale_marker_and_prompt() -> None:
    result = SimpleNamespace(
        prepared_synthesis_messages=[
            {"role": "user", "content": f"行 {STALE}"},
        ],
        synthesis_messages=[{"role": "assistant", "content": "见新证据"}],
        citations=[],
        warnings=["llm_fact_only_superseded_evidence"],
        provider_traces=[
            SimpleNamespace(
                provider="wiki",
                capability="rag",
                status="success",
                detail="",
            )
        ],
        llm_stream_telemetry={"structured_claim_count": 0},
        llm_provider="zhipu",
        llm_fallback_reason=None,
        routed_modules=["theme_radar"],
        wiki_rag_telemetry=None,
        synthesis_diagnostic=SimpleNamespace(state="composed", reason_code="ok"),
    )
    doc = llm_context_document(result)
    blob = json.dumps(doc, ensure_ascii=False)
    assert STALE in blob
    assert doc["llm_provider"] == "zhipu"
    assert doc["warnings"] == ["llm_fact_only_superseded_evidence"]


def test_persist_enabled_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKBENCH_PERSIST_LLM_CONTEXT", raising=False)
    assert persist_enabled() is False
    monkeypatch.setenv("WORKBENCH_PERSIST_LLM_CONTEXT", "1")
    assert persist_enabled() is True


def test_maybe_persist_writes_internal_artifact_only_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RunStore(root=tmp_path / "runs")
    run = store.create_run("DRAM怎么看", "ask")
    result = SimpleNamespace(
        prepared_synthesis_messages=[{"role": "user", "content": STALE}],
        synthesis_messages=None,
        citations=[],
        warnings=[],
        provider_traces=[],
        llm_stream_telemetry={},
        llm_provider="zhipu",
        llm_fallback_reason=None,
        routed_modules=[],
        wiki_rag_telemetry=None,
        synthesis_diagnostic=None,
    )
    monkeypatch.delenv("WORKBENCH_PERSIST_LLM_CONTEXT", raising=False)
    assert maybe_persist_llm_context(store, run.run_id, result) is None
    assert not (store.run_dir(run.run_id) / LLM_CONTEXT_FILENAME).exists()

    monkeypatch.setenv("WORKBENCH_PERSIST_LLM_CONTEXT", "1")
    path = maybe_persist_llm_context(store, run.run_id, result)
    assert path is not None
    assert path.is_file()
    assert STALE in path.read_text(encoding="utf-8")
    saved = store.load_run(run.run_id)
    artifact = next(item for item in saved.artifacts if item["path"] == LLM_CONTEXT_FILENAME)
    assert artifact["visibility"] == "internal"


def test_run_ask_persists_llm_context_when_env_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from intelligence.api import app as app_module
    from intelligence.services import ask as ask_svc
    from intelligence.services import followups as followups_svc
    from intelligence.services.ask import AskResult

    monkeypatch.setenv("WORKBENCH_PERSIST_LLM_CONTEXT", "1")

    def fake_answer(options):
        result = AskResult(
            query=options.query,
            trade_date="2026-08-14",
            matched_theme="DRAM",
            candidate_tier="watch",
            priority_score=80,
        )
        result.synthesis = "见新证据指针。"
        result.llm_provider = "zhipu"
        result.prepared_synthesis_messages = [
            {"role": "user", "content": f"边 {STALE}"},
        ]
        return result

    monkeypatch.setattr(ask_svc, "answer_query", fake_answer)
    monkeypatch.setattr(ask_svc, "render_answer", lambda result: result.synthesis or "")
    monkeypatch.setattr(
        followups_svc,
        "generate_followups",
        lambda *args, **kwargs: followups_svc.FollowupResult(),
    )

    store = RunStore(root=tmp_path / "runs")
    run = store.create_run("DRAM怎么看", "ask")
    request = app_module.CreateRunRequest(
        question="DRAM怎么看",
        task_type="ask",
        repo_root=tmp_path / "repo",
    )
    (tmp_path / "repo").mkdir()
    app_module._run_ask(store, run.run_id, request)
    path = store.run_dir(run.run_id) / LLM_CONTEXT_FILENAME
    assert path.is_file()
    assert STALE in path.read_text(encoding="utf-8")


def test_post_ask_and_wait_reads_run_id() -> None:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            assert body["question"] == "DRAM怎么看"
            assert body["user"] == "live-probe"
            assert body["compose"] is True
            payload = json.dumps({"run_id": "run_test", "status": "queued"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            payload = json.dumps(
                {"run_id": "run_test", "status": "completed"}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        run_id = probe.post_ask(base, question="DRAM怎么看", user="live-probe")
        assert run_id == "run_test"
        status = probe.wait_for_run(base, run_id, user="live-probe", timeout=2)
        assert status["status"] == "completed"
    finally:
        server.shutdown()
        server.server_close()


def test_degrade_counts_from_run_dir_split_unavailable_vs_content(
    tmp_path: Path,
) -> None:
    judge_dir = tmp_path / "judge"
    judge_dir.mkdir()
    (judge_dir / "run.json").write_text(
        json.dumps({"degrades": ["semantic judge leftover window"]}),
        encoding="utf-8",
    )
    (judge_dir / "report.json").write_text(
        json.dumps({"semantic_verifier": {"judge_status": "unavailable"}}),
        encoding="utf-8",
    )
    assert probe.degrade_counts_from_run_dir(judge_dir) == {
        "judge_unavailable_count": 1,
        "content_degraded_count": 0,
    }

    ask_dir = tmp_path / "ask"
    ask_dir.mkdir()
    (ask_dir / "run.json").write_text(
        json.dumps({"degrades": ["llm_unavailable_template_answer"]}),
        encoding="utf-8",
    )
    (ask_dir / "report.json").write_text(
        json.dumps({"judge_status": "not_applicable"}),
        encoding="utf-8",
    )
    assert probe.degrade_counts_from_run_dir(ask_dir) == {
        "judge_unavailable_count": 0,
        "content_degraded_count": 1,
    }


def test_port_is_listening_detects_bound_socket() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        assert probe.port_is_listening(port) is True
    finally:
        sock.close()
