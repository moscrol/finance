"""Real pi CLI against a scripted loopback peer, never a live model or Keychain.

Requires the macOS review runtime. Skips elsewhere are NOT admission evidence.
All PASS/STAGE_COMPLETE artifacts here are synthetic fixtures, not QC verdicts.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts.review_probes.prepare_pi_review_repair import ARCHIVE, STAGE_TOOLS, prepare

PI = Path("/opt/homebrew/bin/pi")


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


def load(path):
    return json.loads(path.read_text())


def test_content_binding_rejects_malformed_or_forged_submissions():
    script = """
import assert from 'node:assert/strict';
import { bindStageResult } from './scripts/review_probes/pi_review_protocol.mjs';
const identity = {stage: 'execute', axis: 'spec', revision: 'a'.repeat(40), baseline: 'b'.repeat(40)};
const raw = {observed: [], verdict: 'BLOCKED_INCOMPLETE_EVIDENCE'};
const bound = bindStageResult(raw, identity);
assert.deepEqual(bound, {...raw, ...identity, complete: true});
assert.equal(Object.hasOwn(raw, 'complete'), false);
for (const bad of [null, [], 'encoded', 42, false, {}]) {
  assert.throws(() => bindStageResult(bad, identity));
}
assert.throws(() => bindStageResult({note: 'x'.repeat(6000)}, identity), /delivery size/);
for (const field of ['stage', 'axis', 'revision', 'baseline', 'complete']) {
  assert.throws(() => bindStageResult({...raw, [field]: true}, identity), /controller identity/);
}
for (const [field, value] of [['stage', 'gateway'], ['axis', 'other'], ['revision', 'a'], ['baseline', 'b']]) {
  assert.throws(() => bindStageResult(raw, {...identity, [field]: value}), /controller identity/);
}
"""
    proc = subprocess.run(["node", "--input-type=module", "-e", script],
                          cwd=ARCHIVE.parents[2], capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stderr


def test_prepare_preserves_sealed_inputs_and_refuses_reuse(tmp_path):
    before = {p: p.read_bytes() for p in ARCHIVE.rglob("*") if p.is_file()}
    root = tmp_path / "fresh"
    receipt = prepare(root)
    assert receipt["status"] == "PREPARED_NOT_AUTHORIZED"
    assert receipt["real_model_requests"] == 0
    for axis in ("spec", "quality"):
        assert load(root / axis / "config.json")["stage_tools"] == STAGE_TOOLS
        assert not (root / axis / "gateway/receipt.json").exists()
        assert not (root / axis / "report").exists()
        assert not list((root / axis / "work/probes").iterdir())
        execute = (root / axis / "prompt-execute.md").read_text()
        assert "first two tool calls MUST be bash" in execute
        assert "control below exactly once" in execute and "author tests exactly once" in execute
        assert "Stage EXECUTE: first read" not in execute
        explore = (root / axis / "prompt-explore.md").read_text()
        assert "verify every called API signature" in explore
        assert "target trigger was reached" in explore
        assert "Exit nonzero" in explore
        for stage in ("explore", "execute", "report"):
            prompt = (root / axis / f"prompt-{stage}.md").read_text()
            assert "complete=true" not in prompt
            assert "controller-owned" in prompt
        extension = (root / axis / "review.mjs").read_text()
        assert "result: Type.Object({}" in extension
    with pytest.raises(FileExistsError):
        prepare(root)
    with pytest.raises(ValueError, match="sealed evidence"):
        prepare(ARCHIVE / "should-not-exist")
    assert before == {p: p.read_bytes() for p in before}


def test_prepare_fails_closed_on_changed_archive(tmp_path):
    archive = tmp_path / "archive"
    shutil.copytree(ARCHIVE, archive)
    with (archive / "spec/run_stage.py.txt").open("a") as stream:
        stream.write("\n# drift\n")
    with pytest.raises(ValueError, match="sealed input changed"):
        prepare(tmp_path / "fresh", archive)
    assert not (tmp_path / "fresh").exists()


@pytest.fixture
def runtime(tmp_path):
    if sys.platform != "darwin" or not PI.is_file():
        pytest.skip("real pi CLI and macOS sandbox required; not an admission receipt")
    root = tmp_path / "offline-repair-fixture"
    prepare(root)
    # Replaces the helper only in disposable test inputs. Never read live credentials.
    (root / "glm_credential.py").write_text("print('offline-fixture-no-credential')\n")
    tree = tmp_path / "candidate"
    tree.mkdir()
    env = {"HOME": str(tmp_path), "PATH": os.environ["PATH"], "GIT_CONFIG_NOSYSTEM": "1"}
    for args in (["init", "-q"], ["-c", "user.name=Fixture", "-c", "user.email=fixture@invalid",
                                 "commit", "-q", "--allow-empty", "-m", "offline fixture"]):
        subprocess.run(["git", "-C", str(tree), *args], env=env, check=True, capture_output=True)
    revision = subprocess.check_output(["git", "-C", str(tree), "rev-parse", "HEAD"], text=True).strip()
    for axis in ("spec", "quality"):
        folder = root / axis
        config = load(folder / "config.json")
        old_tree = config["tree"]
        config.update(tree=str(tree), author=str(tree), revision=revision, baseline=revision, python=sys.executable)
        dump(folder / "config.json", config)
        sandbox = folder / "tools.sb"
        sandbox.write_text(sandbox.read_text().replace(old_tree, str(tree)))
    return root


@pytest.fixture
def peer(tmp_path):
    state = {"requests": [], "reply": None, "errors": []}

    class Fake(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(payload)
            try:
                content = state["reply"](payload, len(state["requests"]))
                if not payload.get("stream"):
                    body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                tools = content if isinstance(content, list) else None
                delta = {"role": "assistant", **({"tool_calls": tools} if tools else {"content": content})}
                chunks = [
                    {"id": "offline", "object": "chat.completion.chunk", "model": "glm-5.3",
                     "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                    {"id": "offline", "object": "chat.completion.chunk", "model": "glm-5.3",
                     "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls" if tools else "stop"}]},
                ]
                body = "".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(body.encode())))
                self.end_headers()
                self.wfile.write(body.encode())
            except Exception as exc:
                state["errors"].append(repr(exc))
                self.send_error(500)

    # The archived provider is intentionally pinned. Never stop another owner's server.
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 19899), Fake)
    except OSError:
        pytest.skip("private 19899 already owned; cannot validate CLI integration")
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        dump(tmp_path / "peer-summary.json", {
            "fake_http_requests": len(state["requests"]), "real_model_requests": 0,
            "tool_menus": [[t["function"]["name"] for t in p.get("tools", [])] for p in state["requests"]],
            "errors": state["errors"],
        })
    assert not state["errors"], state["errors"]


def tool(name, params, index=0):
    return {"index": index, "id": f"call_{index}_{name}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(params)}}


def run(command, cwd, env=None):
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=35)


def gateway(runtime, *, menu_only=False):
    folder = runtime / "spec"
    out = folder / "gateway"
    (out / "commands").mkdir(parents=True)
    (folder / "work/gateway-fixture.txt").write_text("OFFLINE_RANDOM_29f1\n")
    env = {"HOME": str(runtime), "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
           "LANG": "C.UTF-8", "PI_CODING_AGENT_DIR": str(folder / "pi-config"),
           "PI_OFFLINE": "1", "PI_TELEMETRY": "0", "REVIEW_PHASE": "gateway",
           "REVIEW_OUTPUT_DIR": str(out)}
    command = [str(PI), "--provider", "glm-direct-review", "--model", "glm-5.3", "--thinking", "off",
               "--models", "glm-direct-review/glm-5.3", "--no-session", "--no-extensions",
               "-e", str(folder / "gateway.mjs"), "--no-skills", "--no-prompt-templates",
               "--no-context-files", "--no-themes", "--no-approve", "--offline", "--tools", "read,write",
               "--mode", "json", "-p"]
    if menu_only:
        stop = runtime / "stop-after-start.mjs"
        stop.write_text("export default pi => pi.on('session_start', () => process.exit(0));\n")
        command += ["-e", str(stop)]
    command += ["--", "Offline protocol fixture only."]
    proc = run(command, folder, env)
    (out / "cli-events.jsonl").write_text(proc.stdout)
    (out / "cli-stderr.log").write_text(proc.stderr)
    return proc, out


def test_real_cli_menu_startup_zero_requests(runtime, peer):
    proc, out = gateway(runtime, menu_only=True)
    assert proc.returncode == 0, proc.stderr
    assert load(out / "tool-menu.json")["status"] == "PASS"
    assert load(out / "gateway-state.json")["phase"] == "read"
    assert peer["requests"] == []


@pytest.mark.parametrize("mode", ["good", "parallel", "early_write", "bad_copy", "early_final", "bad_final", "read_error", "wrong_path", "wrong_range"])
def test_real_cli_gateway_protocol(runtime, peer, mode):
    folder = runtime / "spec"
    fixture = folder / "work/gateway-fixture.txt"
    echo = folder / "work/gateway-echo.txt"

    def reply(payload, number):
        if number == 1:
            if mode == "early_final":
                return "OFFLINE_RANDOM_29f1"
            target = folder / "config.json" if mode == "wrong_path" else fixture
            read = tool("read", {"path": str(target), "offset": 2 if mode == "wrong_range" else 1, "limit": 1})
            write = tool("write", {"path": str(echo), "content": "guessed"}, 1)
            if mode == "read_error":
                fixture.unlink()
            return [read, write] if mode == "parallel" else [write] if mode == "early_write" else [read]
        if number == 2:
            results = [m for m in payload["messages"] if m["role"] == "tool"]
            content = results[-1]["content"]
            assert content == "OFFLINE_RANDOM_29f1\n"
            return [tool("write", {"path": str(echo), "content": "bad" if mode == "bad_copy" else content})]
        assert number == 3
        return "wrong" if mode == "bad_final" else "OFFLINE_RANDOM_29f1"

    peer["reply"] = reply
    proc, out = gateway(runtime)
    state = load(out / "gateway-state.json")
    menus = [[t["function"]["name"] for t in p.get("tools", [])] for p in peer["requests"]]
    if mode == "good":
        assert proc.returncode == 0, proc.stderr
        assert state["phase"] == "complete", state
        assert menus == [["read"], ["write"], []]
        assert echo.read_bytes() == fixture.read_bytes()
    else:
        assert state["phase"] == "failed", (proc.stderr, state)
        assert len(menus) == (3 if mode == "bad_final" else 2 if mode == "bad_copy" else 1)
        if mode != "bad_final":
            assert not echo.exists()
    assert all(p["parallel_tool_calls"] is False for p in peer["requests"])
    assert not (out / "submission.json").exists()


def stage_fixture(runtime, stage, axis):
    folder = runtime / axis
    # Test-only fixtures satisfy the runner's prerequisite checks; not real admission.
    dump(folder / "gateway/receipt.json", {"status": "PASS", "synthetic_fixture": True})
    dump(folder / "sandbox-preflight-04/receipt.json", {"status": "PASS", "synthetic_fixture": True})
    if stage != "explore":
        dump(folder / ("explore" if stage == "execute" else "execute") / "execution.json",
             {"status": "STAGE_COMPLETE", "synthetic_fixture": True})
    probe = folder / "work/probes/offline.py"
    probe.write_text("# Synthetic plumbing fixture; not a product probe.\n")
    if stage == "report":
        (folder / "report-packet.md").write_text("Synthetic plumbing fixture only.\n")
    data = {"probe_files": [str(probe)], "verdict": "BLOCKED_INCOMPLETE_EVIDENCE",
            "claims": [{"id": f"C{i}", "status": "not_verified"} for i in range(1, 8)]}
    return folder, data


@pytest.mark.parametrize("stage", ["explore", "execute", "report"])
@pytest.mark.parametrize("axis", ["spec", "quality"])
def test_real_stage_runner_delivers_without_followup(runtime, peer, stage, axis):
    folder, data = stage_fixture(runtime, stage, axis)
    peer["reply"] = lambda *_: [tool("deliver_stage", {"result": data})]
    proc = run([sys.executable, "-B", str(folder / "run_stage.py"), stage], folder)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    out = folder / stage
    assert load(out / "tool-menu.json")["status"] == "PASS"
    execution = load(out / "execution.json")
    assert execution["status"] == "STAGE_COMPLETE", execution
    config = load(folder / "config.json")
    assert load(out / "submission.json") == {
        **data, "complete": True, "stage": stage, "axis": axis,
        "revision": config["revision"], "baseline": config["baseline"],
    }
    assert len(peer["requests"]) == 1
    assert {t["function"]["name"] for t in peer["requests"][0]["tools"]} == set(STAGE_TOOLS[stage])


@pytest.mark.parametrize("field,value", [
    ("stage", "EXECUTE"), ("stage", "execute"), ("axis", "quality"),
    ("revision", "0" * 40), ("baseline", "0" * 40),
    ("complete", True), ("complete", False), ("complete", "true"), ("complete", None),
])
def test_reviewer_identity_injection_stops_without_followup(runtime, peer, field, value):
    folder, data = stage_fixture(runtime, "execute", "spec")
    data[field] = value
    peer["reply"] = lambda *_: [tool("deliver_stage", {"result": data})]
    run([sys.executable, "-B", str(folder / "run_stage.py"), "execute"], folder)
    out = folder / "execute"
    assert load(out / "execution.json")["status"] == "BLOCKED_STAGE_OR_PROVIDER"
    assert "controller identity" in load(out / "controller-stop.json")["reason"]
    assert not (out / "submission.json").exists()
    assert len(peer["requests"]) == 1


@pytest.mark.parametrize("stage,missing", [
    ("explore", "probe_files"), ("report", "verdict"), ("report", "claims"),
])
def test_completion_does_not_replace_required_evidence(runtime, peer, stage, missing):
    folder, data = stage_fixture(runtime, stage, "spec")
    del data[missing]
    peer["reply"] = lambda *_: [tool("deliver_stage", {"result": data})]
    # The final reserved request has no repair/follow-up budget.
    extension = folder / "review.mjs"
    extension.write_text(extension.read_text().replace("let admitted = 0;", "let admitted = 16;"))
    run([sys.executable, "-B", str(folder / "run_stage.py"), stage], folder)
    assert load(folder / stage / "execution.json")["status"] == "BLOCKED_STAGE_OR_PROVIDER"
    assert not (folder / stage / "submission.json").exists()
    assert len(peer["requests"]) == 1


@pytest.mark.parametrize("require_reviewer_flag", [False, True])
def test_last_reserved_request_delivers_without_completion_flag(runtime, peer, require_reviewer_flag):
    folder, data = stage_fixture(runtime, "execute", "spec")
    extension = folder / "review.mjs"
    code = extension.read_text().replace("let admitted = 0;", "let admitted = 16;")
    if require_reviewer_flag:
        # Reinstall the 1405 schema defect in disposable inputs as a mutation witness.
        assert code.count("result: Type.Object({}") == 1
        code = code.replace("result: Type.Object({}", "result: Type.Object({ complete: Type.Literal(true) }")
    extension.write_text(code)
    peer["reply"] = lambda *_: [tool("deliver_stage", {"result": data})]
    proc = run([sys.executable, "-B", str(folder / "run_stage.py"), "execute"], folder)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    if require_reviewer_flag:
        assert load(folder / "execute/execution.json")["status"] == "BLOCKED_STAGE_OR_PROVIDER"
        assert not (folder / "execute/submission.json").exists()
        assert len(peer["requests"]) == 1
        return
    assert load(folder / "execute/execution.json")["status"] == "STAGE_COMPLETE"
    submission = load(folder / "execute/submission.json")
    assert submission["complete"] is True
    assert submission["verdict"] == "BLOCKED_INCOMPLETE_EVIDENCE"
    assert all(claim["status"] == "not_verified" for claim in submission["claims"])
    assert len(peer["requests"]) == 1
    assert [t["function"]["name"] for t in peer["requests"][0]["tools"]] == ["deliver_stage"]


@pytest.mark.parametrize("budget", ["reserved_used", "hard_limit", "deadline"])
def test_exhausted_stage_rejects_before_any_provider_request(runtime, peer, budget):
    folder, _ = stage_fixture(runtime, "execute", "spec")
    extension = folder / "review.mjs"
    original = extension.read_text()
    old, new = {
        "reserved_used": ("let reportAdmitted = false;", "let reportAdmitted = true;"),
        "hard_limit": ("let admitted = 0;", "let admitted = 24;"),
        "deadline": ("const started = clock();", "const started = clock() - 600001;"),
    }[budget]
    assert original.count(old) == 1
    extension.write_text(original.replace(old, new))
    run([sys.executable, "-B", str(folder / "run_stage.py"), "execute"], folder)
    assert peer["requests"] == []
    assert not (folder / "execute/submission.json").exists()
    assert load(folder / "execute/controller-stop.json")["reason"] == "budget_or_report_already_dispatched"


@pytest.mark.parametrize("stage", ["explore", "execute", "report"])
def test_real_stage_menu_startup_zero_requests(runtime, peer, stage):
    folder, _ = stage_fixture(runtime, stage, "spec")
    stop = runtime / "stop-after-start.mjs"
    stop.write_text("export default pi => pi.on('session_start', () => process.exit(0));\n")
    runner = folder / "run_stage.py"
    runner.write_text(runner.read_text().replace("'--mode', 'json', '-p'",
                                               f"'-e', {str(stop)!r}, '--mode', 'json', '-p'"))
    proc = run([sys.executable, "-B", str(runner), stage], folder)
    out = folder / stage
    assert (out / "tool-menu.json").is_file(), proc.stderr
    assert load(out / "tool-menu.json")["status"] == "PASS"
    assert "deliver_stage" in load(out / "tool-menu.json")["actual"]
    assert peer["requests"] == []
    assert load(out / "execution.json")["status"] == "BLOCKED_STAGE_OR_PROVIDER"


def test_missing_cli_delivery_tool_fails_before_provider(runtime, peer):
    folder, _ = stage_fixture(runtime, "explore", "spec")
    runner = folder / "run_stage.py"
    runner.write_text(runner.read_text().replace("','.join(CONFIG['stage_tools'][STAGE])", "'read,bash,write'"))
    proc = run([sys.executable, "-B", str(runner), "explore"], folder)
    out = folder / "explore"
    assert (out / "tool-menu.json").is_file(), proc.stderr
    assert load(out / "tool-menu.json")["status"] == "BLOCKED_TOOL_MENU"
    assert load(out / "execution.json")["status"] == "BLOCKED_STAGE_OR_PROVIDER"
    assert peer["requests"] == []
    assert not (out / "submission.json").exists()


def test_delivery_with_sibling_tool_is_blocked(runtime, peer):
    folder, data = stage_fixture(runtime, "execute", "spec")
    victim = folder / "work/must-not-exist.txt"
    peer["reply"] = lambda *_: [tool("deliver_stage", {"result": data}),
                                tool("write", {"path": str(victim), "content": "bad"}, 1)]
    proc = run([sys.executable, "-B", str(folder / "run_stage.py"), "execute"], folder)
    out = folder / "execute"
    assert (out / "delivery-blocked.json").is_file(), proc.stderr
    assert load(out / "execution.json")["status"] == "BLOCKED_STAGE_OR_PROVIDER"
    assert len(peer["requests"]) == 1
    assert not (out / "submission.json").exists()
    assert not victim.exists()


@pytest.mark.parametrize("mode", ["good", "parallel"])
def test_gateway_controller_requires_completed_state(runtime, peer, mode):
    folder = runtime / "spec"
    copied = []

    def reply(payload, number):
        if number == 1:
            assert not payload.get("stream")
            return "OK"
        if number == 2:
            calls = [tool("read", {"path": str(folder / "work/gateway-fixture.txt"), "offset": 1, "limit": 1})]
            if mode == "parallel":
                calls.append(tool("write", {"path": str(folder / "work/gateway-echo.txt"), "content": "guessed"}, 1))
            return calls
        if number == 3:
            copied.append([m for m in payload["messages"] if m["role"] == "tool"][-1]["content"])
            return [tool("write", {"path": str(folder / "work/gateway-echo.txt"), "content": copied[0]})]
        assert number == 4
        return copied[0].strip()

    peer["reply"] = reply
    proc = run([sys.executable, "-B", "-c", "import run_control; run_control.gateway()"], folder)
    assert proc.returncode == 0, proc.stderr
    receipt = load(folder / "gateway/receipt.json")
    assert receipt["status"] == ("PASS" if mode == "good" else "BLOCKED_PROVIDER_OR_ROUNDTRIP"), receipt
    assert receipt["protocol_state"]["phase"] == ("complete" if mode == "good" else "failed")
    assert len(peer["requests"]) == receipt["requests"] == (4 if mode == "good" else 2)
