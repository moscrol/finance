"""Real Pi subprocesses against a loopback-only model/tool stub; no paid API calls."""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import urllib.error

import pytest

from tests.pi_delivery_support import make_source

REPO = Path(__file__).resolve().parents[1]
PI = shutil.which("pi")
pytestmark = pytest.mark.skipif(PI is None, reason="Pi CLI required for subprocess integration tests")
SPEC = importlib.util.spec_from_file_location("pi_native_test_commands", REPO / "integrations/pi/run_native.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
MODEL = "glm-5.3-flash"


def complete(text="Complete test answer."):
    return {"role": "assistant", "content": text}


def tools(*calls, text=None):
    return {"role": "assistant", "content": text, "tool_calls": [
        {"index": i, "id": f"call-{i}", "type": "function",
         "function": {"name": name, "arguments": json.dumps(args)}}
        for i, (name, args) in enumerate(calls)
    ]}


@contextmanager
def endpoint(respond, *, model=MODEL):
    requests, errors = [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, body))
            try:
                result = respond(self.path, body)
            except Exception as error:
                errors.append(error)
                result = (400, {"error": {"message": str(error)}})
            if isinstance(result, tuple):
                code, data = result
                payload = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            elif self.path == "/tool":
                payload = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Connection", "close")
                self.end_headers()
                chunk = {"id": "stub", "object": "chat.completion.chunk", "created": 1, "model": model,
                         "choices": [{"index": 0, "delta": result, "finish_reason": None}]}
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
                reason = "tool_calls" if result.get("tool_calls") else "stop"
                chunk["choices"] = [{"index": 0, "delta": {}, "finish_reason": reason}]
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n").encode())
                self.wfile.flush()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests, errors
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def run_pi(tmp_path):
    root = tmp_path / "run"
    (root / "kit").mkdir(parents=True)
    shutil.copyfile(REPO / "integrations/pi/finance-mode.ts", root / "kit/finance-mode.ts")
    shutil.copyfile(REPO / "integrations/pi/delivery-prompts.json", root / "kit/delivery-prompts.json")
    skills = tmp_path / "skills"
    for name in runner.DEFAULT_SKILLS:
        (skills / name).mkdir(parents=True)
        shutil.copyfile(REPO / "skills" / name / "SKILL.md", skills / name / "SKILL.md")
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "settings.json").write_text(json.dumps({"retry": {"enabled": False},
        "compaction": {"enabled": False}, "cacheWarming": "off", "enableInstallTelemetry": False}))
    menu = {"case": "offline-test", "as_of": "2026-09-30", "authorized_tools": [
        {"name": "market_data", "parameters": {"mandatory_schema_marker": "use-the-frozen-cutoff"}}
    ]}
    menu_file = root / "menu.json"
    menu_file.write_text(json.dumps(menu))

    def run(url, *, second_look=False, subagents=False, preload=None, postload=None, delivery_style=None):
        mode = "delivery" if delivery_style else "research"
        menu_file.write_text(json.dumps({**menu, "authorized_tools": []} if delivery_style else menu))
        plan = {"pi_bin": PI, "code_root": str(tmp_path), "os_skill": "finance-mode",
                "app_skills": list(runner.DEFAULT_SKILLS[1:]), "model": MODEL, "thinking": "low",
                "subagents": subagents, "mode": mode}
        env = {**os.environ, "PI_CODING_AGENT_DIR": str(agent_dir),
               "FINANCE_PI_BRIDGE_URL": url, "FINANCE_PI_CASE": "offline-test", "FINANCE_PI_MODEL": MODEL,
               "FINANCE_PI_SKILL_ROOT": str(skills), "FINANCE_PI_OS_SKILL": "finance-mode",
               "FINANCE_PI_APP_SKILLS": ",".join(plan["app_skills"]), "FINANCE_PI_SUBAGENT_DEPTH": "0",
               "FINANCE_PI_SUBAGENTS": "1" if subagents else "0", "FINANCE_PI_BIN": PI,
               "FINANCE_PI_SECOND_LOOK": "1" if second_look else "0", "FINANCE_PI_MENU_FILE": str(menu_file),
               "FINANCE_PI_MODE": mode, "FINANCE_PI_DELIVERY_STYLE": delivery_style or "direct",
               "FINANCE_PI_DELIVERY_SKILL": "finance-market-review" if delivery_style else ""}
        command = runner.pi_command(plan, root, "Offline test only.")
        if preload is not None:
            index = command.index("-e")
            command[index:index] = ["-e", str(preload)]
        if postload is not None:
            index = command.index("--")
            command[index:index] = ["-e", str(postload)]
        process = subprocess.Popen(command, cwd=root / "kit",
                                   env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            out, err = process.communicate(timeout=25)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, 9)
            process.communicate(timeout=5)
            raise AssertionError("Pi did not settle within the offline test deadline") from None
        assert process.returncode == 0, err
        return [json.loads(line) for line in out.split("\n") if line.strip()]

    return run, skills


def _model_requests(requests):
    return [body for path, body in requests if path == "/v1/chat/completions"]


def test_real_entry_exposes_finance_tool_and_executes_skill_read(run_pi):
    run, skills = run_pi
    turns = 0

    def respond(path, body):
        nonlocal turns
        if path == "/tool":
            assert body == {"tool": "market_data", "args": {"as_of": "2026-09-30"}}
            return {"observation": {"status": "ok", "as_of": "2026-09-30"}}
        turns += 1
        if turns == 1:
            return tools(("read", {"path": str(skills / "finance-market-review/SKILL.md")}),
                         ("finance_call", {"tool": "market_data", "args": {"as_of": "2026-09-30"}}))
        return complete()

    with endpoint(respond) as (url, requests, errors):
        events = run(url)
    assert not errors
    published = _model_requests(requests)[0]["tools"]
    assert {t["function"]["name"] for t in published} == {"read", "finance_call"}
    finance = next(t["function"] for t in published if t["function"]["name"] == "finance_call")
    assert finance["parameters"]["properties"]["tool"]["enum"] == ["market_data"]
    results = [e for e in events if e["type"] == "tool_execution_end"]
    assert {e["toolName"] for e in results} == {"read", "finance_call"}
    assert all(not e["isError"] for e in results)
    assert len([r for r in requests if r[0] == "/tool"]) == 1


def test_dataset_name_cannot_be_used_as_a_financial_tool(run_pi):
    run, _ = run_pi
    turns = 0

    def respond(path, _body):
        nonlocal turns
        assert path != "/tool", "invalid tool name must be rejected before bridge transport"
        turns += 1
        if turns == 1:
            return tools(("finance_call", {"tool": "invented_dataset", "args": {}}))
        return complete()

    with endpoint(respond) as (url, _, errors):
        events = run(url)
    assert not errors
    result = next(e for e in events if e["type"] == "tool_execution_end")
    assert result["isError"] is True


def test_second_look_settles_after_exactly_one_continuation(run_pi):
    run, _ = run_pi
    calls = 0

    def respond(_path, _body):
        nonlocal calls
        calls += 1
        assert calls <= 3, "unbounded second-look continuation"
        return complete()

    with endpoint(respond) as (url, _, errors):
        events = run(url, second_look=True)
    assert not errors
    assert calls == 2
    assert events[-1]["type"] == "agent_settled"


OTHER_CONTINUATION_OWNER = """export default function (pi) {
    const key = Symbol.for("finance.pi.continuation-owner");
    const owner = globalThis[key];
    if (owner !== undefined) throw new Error(`Pi continuation already owned by ${owner}`);
    globalThis[key] = "reviewed-history";
    pi.on("session_shutdown", () => {
        if (globalThis[key] === "reviewed-history") delete globalThis[key];
    });
}
"""


@pytest.mark.parametrize("order", ["preload", "postload"])
@pytest.mark.parametrize("mode", ["second-look", "aligned"])
def test_financial_continuations_refuse_another_owner_before_model_call(run_pi, tmp_path, order, mode):
    run, _ = run_pi
    other = tmp_path / "other-owner.ts"
    other.write_text(OTHER_CONTINUATION_OWNER)
    settings = {"second_look": True} if mode == "second-look" else {"delivery_style": "aligned"}
    with endpoint(lambda _path, _body: complete()) as (url, requests, errors):
        with pytest.raises(AssertionError, match="continuation already owned"):
            run(url, **{order: other}, **settings)
    assert requests == [] and not errors


@pytest.mark.parametrize("delivery_style", [None, "direct"])
@pytest.mark.parametrize("order", ["preload", "postload"])
def test_no_followup_does_not_claim_continuation_ownership(run_pi, tmp_path, order, delivery_style):
    run, _ = run_pi
    other = tmp_path / "other-owner.ts"
    other.write_text(OTHER_CONTINUATION_OWNER)
    with endpoint(lambda _path, _body: complete()) as (url, requests, errors):
        events = run(url, **{order: other}, delivery_style=delivery_style)
    assert not errors and len(_model_requests(requests)) == 1
    assert events[-1]["type"] == "agent_settled"


def test_duplicate_same_named_continuation_cannot_stack(run_pi, tmp_path):
    run, _ = run_pi
    duplicate = tmp_path / "finance-mode-copy.ts"
    shutil.copyfile(REPO / "integrations/pi/finance-mode.ts", duplicate)
    shutil.copyfile(REPO / "integrations/pi/delivery-prompts.json", tmp_path / "delivery-prompts.json")
    with endpoint(lambda _path, _body: complete()) as (url, requests, _):
        with pytest.raises(AssertionError, match="continuation already owned by finance-mode"):
            run(url, delivery_style="aligned", postload=duplicate)
    assert requests == []


def test_continuation_owner_is_released_on_real_session_shutdown(run_pi, tmp_path):
    run, _ = run_pi
    observed = tmp_path / "shutdown-owner.json"
    watcher = tmp_path / "owner-watcher.ts"
    watcher.write_text('import {writeFileSync} from "node:fs";\n'
                       'export default function(pi) { pi.on("session_shutdown", () => {\n'
                       f'writeFileSync({json.dumps(str(observed))}, JSON.stringify({{owner: globalThis[Symbol.for("finance.pi.continuation-owner")] ?? null}}));\n'
                       '}); }\n')
    with endpoint(lambda _path, _body: complete()) as (url, requests, errors):
        run(url, second_look=True, postload=watcher)
    assert not errors and len(_model_requests(requests)) == 2
    assert json.loads(observed.read_text()) == {"owner": None}


@pytest.mark.parametrize("failure", [False, True])
def test_child_receives_schema_and_cutoff_and_failure_is_not_a_conclusion(run_pi, failure):
    run, _ = run_pi
    parent_turns = child_turns = 0
    child_requests = []

    def respond(path, body):
        nonlocal parent_turns, child_turns
        if path == "/tool":
            return {"observation": {"status": "ok"}}
        child = "finance-researcher" in json.dumps(body["messages"], ensure_ascii=False)
        if child:
            child_requests.append(body)
            child_turns += 1
            if child_turns == 1:
                return tools(("finance_call", {"tool": "market_data", "args": {}}),
                             text="I will look up the evidence next.")
            if failure:
                return 401, {"error": {"message": "offline simulated child failure"}}
            return complete("Child final evidence summary.")
        parent_turns += 1
        if parent_turns == 1:
            return tools(("spawn_sub_agent", {"skill": "finance-market-review", "title": "child",
                                              "task": "Research the assigned market."}))
        return complete()

    with endpoint(respond) as (url, _, errors):
        events = run(url, subagents=True)
    assert not errors
    assert child_turns == 2
    first = child_requests[0]
    assert {t["function"]["name"] for t in first["tools"]} == {"read", "finance_call"}
    user = json.dumps([m for m in first["messages"] if m["role"] == "user"])
    assert "mandatory_schema_marker" in user and "2026-09-30" in user
    results = [e for e in events if e["type"] == "tool_execution_end" and e["toolName"] == "spawn_sub_agent"]
    assert len(results) == 1
    assert results[0]["isError"] is failure
    text = json.dumps(results[0]["result"]["content"])
    if failure:
        assert "I will look up the evidence next." not in text
    else:
        assert "Child final evidence summary." in text


def test_read_guard_rejects_unmounted_files_and_symlink_escape(run_pi, tmp_path):
    run, skills = run_pi
    secret = tmp_path / "private.txt"
    secret.write_text("PRIVATE_MARKER_NOT_FOR_THE_MODEL")
    escape = skills / "finance-market-review/escape.txt"
    escape.symlink_to(secret)
    turns = 0

    def respond(_path, _body):
        nonlocal turns
        turns += 1
        return tools(("read", {"path": str(secret)}), ("read", {"path": str(escape)})) if turns == 1 else complete()

    with endpoint(respond) as (url, requests, errors):
        events = run(url)
    assert not errors
    results = [e for e in events if e["type"] == "tool_execution_end"]
    assert len(results) == 2 and all(e["isError"] for e in results)
    assert "PRIVATE_MARKER_NOT_FOR_THE_MODEL" not in json.dumps(requests)


def test_full_runner_bridge_and_pi_round_trip_is_offline(tmp_path, monkeypatch):
    import duckdb

    database = tmp_path / "source.duckdb"
    duckdb.connect(str(database)).close()
    question = tmp_path / "question.txt"
    question.write_text("Review the available prior research, with a fixed cutoff.")
    launcher = tmp_path / "launcher.sh"
    launcher.write_text("")
    root = tmp_path / "experiment"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        bridge_port = sock.getsockname()[1]
    # The repository is dirty during development; dirty-tree rejection has separate real-git tests.
    monkeypatch.setattr(runner, "require_clean_code", lambda _code: None)
    runner.PROCESSES.clear()
    turns = 0

    def respond(_path, body):
        nonlocal turns
        turns += 1
        assert body["model"] == MODEL
        assert body["temperature"] == 0
        if turns == 1:
            return tools(("finance_call", {"tool": "memory_lookup", "args": {"wrong": "fixture-prior"}}),
                         ("finance_call", {"tool": "memory_lookup", "args": {"query": "fixture-prior"}}))
        messages = [json.loads(m["content"]) for m in body["messages"] if m["role"] == "tool"]
        views = [message["observation"] for message in messages if "observation" in message]
        assert len(views) == 1
        assert "telemetry" not in views[0] and "trace" not in views[0]
        assert views[0]["status"] and isinstance(views[0]["ok"], bool)
        return complete()

    with endpoint(respond) as (url, requests, errors):
        monkeypatch.setenv("FORESIGHT_BUILTIN_LLM_API_KEY", "offline-fixture-key")
        monkeypatch.setenv("FORESIGHT_BUILTIN_LLM_BASE_URL", url + "/v1")
        assert runner.main(["prepare", "--root", str(root), "--db", str(database),
                            "--question-file", str(question), "--as-of", "2026-09-30",
                            "--today", "2026-10-09", "--rag-bindings", "off",
                            "--launcher", str(launcher), "--bridge-port", str(bridge_port),
                            "--pi-bin", PI, "--turn-seconds", "30", "--call-cap", "8"]) == 0
        assert runner.main(["run", "--root", str(root)]) == 0
    assert not errors
    result = json.loads((root / "RESULT.json").read_text())
    assert result["status"] == "completed"
    assert result["inputs_unchanged"] and result["processes_stopped"]
    assert result["arm"]["model_admission"] is True
    assert result["arm"]["physical_requests"] == len(requests) == 2
    assert result["arm"]["tools_used"] == ["memory_lookup"]
    assert result["arm"]["tool_calls"] == 2
    assert result["arm"]["tool_observations"] == 1
    assert result["arm"]["parent_tool_attempts"] == 2
    assert result["arm"]["parent_tool_errors"] == 1
    assert json.loads((root / "pi/completed-drafts.json").read_text()) == [
        {"stop_reason": "stop", "text": "Complete test answer."}]
    assert result["quality"] == "UNREVIEWED"
    assert (root / "pi/answer.md").read_text() == "Complete test answer."
    transport = (root / "pi-model-requests.jsonl").read_text() + (root / "pi-model-responses.jsonl").read_text()
    assert "offline-fixture-key" not in transport


@pytest.mark.parametrize("style,numeric,analysis_only,author_model,evidence_view", [
    ("direct", False, False, None, "raw"), ("aligned", False, False, None, "raw"),
    ("direct", True, False, None, "raw"), ("aligned", True, False, None, "raw"),
    ("direct", True, True, None, "raw"), ("direct", True, True, "explicit-author", "raw"),
    ("direct", True, True, "explicit-author", "factored"), ("aligned", False, False, None, "factored"),
])
def test_frozen_delivery_has_no_data_tools_and_stages_are_bounded(tmp_path, monkeypatch, style, numeric, analysis_only, author_model, evidence_view):
    source = make_source(tmp_path / "source", repeated_evidence=evidence_view == "factored")
    root = tmp_path / "delivery"
    launcher = tmp_path / "launcher.sh"
    launcher.write_text("")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monkeypatch.setattr(runner, "require_clean_code", lambda _code: None)
    runner.PROCESSES.clear()
    turns = 0

    def respond(_path, body):
        nonlocal turns
        turns += 1
        assert {tool["function"]["name"] for tool in body["tools"]} == {"read"}
        assert body["model"] == (author_model or MODEL)
        encoded = json.dumps(body, ensure_ascii=False)
        method = (REPO / "skills/finance-market-review/SKILL.md").read_text().partition("\n---\n")[2].strip()
        system = "\n".join(m["content"] for m in body["messages"] if m["role"] == "system")
        assert method in system
        assert "ADMITTED_FACT" in encoded
        assert ("frozen_numeric_checks_v1" in encoded) is numeric
        assert "PRIVATE_AUDIT_SENTINEL" not in encoded and "OLD_DRAFT_SENTINEL" not in encoded
        assert ("factored_public_evidence_v1" in encoded) is (evidence_view == "factored")
        if turns == 1:
            filename = "model-evidence.json" if evidence_view == "factored" else "evidence-packet.json"
            expected = json.loads((root / filename).read_text())
            assert json.dumps(expected, ensure_ascii=False) in "\n".join(
                message["content"] for message in body["messages"] if message["role"] == "user")
            if evidence_view == "factored":
                from intelligence.eval.factored_evidence import restore_packet
                original = json.loads((root / "evidence-packet.json").read_text())
                assert restore_packet(expected) == original
                public = expected["observations"][0]["result"]
                assert "evidence_common" in public and "observation_parts" in public
            with pytest.raises(urllib.error.HTTPError) as denied:
                runner.call(port, "/tool", {"tool": "finance_query", "args": {}})
            assert denied.value.code == 403
            with pytest.raises(urllib.error.HTTPError) as reset:
                runner.call(port, "/configure", {"mode": "research"})
            assert b"already configured" in reset.value.read()
            return tools(("read", {"path": str(REPO / "skills/finance-market-review/SKILL.md")}))
        if style == "aligned" and turns == 2:
            return complete("WORKING_TABLE: observed five of ten; scope is the supplied ten.")
        if style == "aligned":
            assert turns == 3 and "WORKING_TABLE" in encoded
        else:
            assert turns == 2
        return complete("FINAL_DELIVERY: FICTIONAL_NUMERIC_SENTINEL" if analysis_only else
                        "FINAL_DELIVERY: five of the supplied ten records match.")

    with endpoint(respond, model=author_model or MODEL) as (url, requests, errors):
        monkeypatch.setenv("FORESIGHT_BUILTIN_LLM_API_KEY", "offline-fixture-key")
        monkeypatch.setenv("FORESIGHT_BUILTIN_LLM_BASE_URL", url + "/v1")
        assert runner.main(["prepare", "--root", str(root), "--source-run", str(source),
                            "--delivery-style", style, "--delivery-skill", "finance-market-review",
                            "--evidence-view", evidence_view, "--launcher", str(launcher),
                            "--bridge-port", str(port), "--pi-bin", PI, "--turn-seconds", "40",
                            *(["--numeric-checks"] if numeric else []),
                            *(["--analysis-only"] if analysis_only else []),
                            *(["--author-model", author_model] if author_model else [])]) == 0
        assert not (root / "market_feature_store.duckdb").exists()
        assert runner.main(["run", "--root", str(root)]) == 0
    assert not errors
    result = json.loads((root / "RESULT.json").read_text())
    assert result["status"] == "completed"
    assert result["source_model"] == MODEL
    assert result["author_model"] == (author_model or MODEL)
    assert result["model_axis_changed"] is (author_model is not None)
    assert result["arm"]["data_tools_disabled"] is True
    assert result["arm"]["delivery_method_in_first_request"] is True
    assert result["arm"]["evidence_view_in_first_request"] is True
    assert result["evidence_view"] == evidence_view
    if evidence_view == "factored":
        view_record = json.loads((root / "evidence-view-receipt.json").read_text())
        assert view_record["roundtrip_equal"] is True
        assert view_record["view_bytes"] < view_record["original_bytes"]
    if numeric:
        assert result["arm"]["numeric_checks_in_first_request"] is True
        assert result["arm"]["numeric_checked_observations"] == 0, "untyped fixture prose must remain unsupported"
    assert result["arm"]["tool_calls"] == result["arm"]["tool_observations"] == 0
    assert result["arm"]["skill_reads"] == 1
    assert result["arm"]["completed_drafts"] == (2 if style == "aligned" else 1)
    assert result["arm"]["physical_requests"] == len(requests) == (3 if style == "aligned" else 2)
    assert result["inputs_unchanged"] and result["processes_stopped"]
    assert (root / "pi/answer.md").read_text().startswith("FINAL_DELIVERY")
    if analysis_only:
        facts = (root / "checked-facts.md").read_text()
        assert "FICTIONAL_NUMERIC_SENTINEL" not in facts
        assert "FICTIONAL_NUMERIC_SENTINEL" in (root / "pi/analysis.md").read_text()
        assert result["checked_facts_sha256"] == runner.digest(root / "checked-facts.md")
        assert result["quality"] == "UNREVIEWED"
        assert result["delivery_scope"] == "fixed_numeric_document_and_unreviewed_model_analysis"
