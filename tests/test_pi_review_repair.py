"""Real pi CLI against a scripted loopback peer, never a live model or Keychain.

Requires the macOS review runtime. Skips elsewhere are NOT admission evidence.
All PASS/STAGE_COMPLETE artifacts here are synthetic fixtures, not QC verdicts.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts.review_probes.prepare_pi_review_repair import ARCHIVE, STAGE_TOOLS, prepare, sandbox_metadata

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


def test_probe_validation_checks_canonical_files_without_rewriting(tmp_path):
    work = tmp_path / "work"
    probes = work / "probes"
    probes.mkdir(parents=True)
    good = probes / "valid.py"
    good.write_text("# fixture\n")
    outside = work / "probes-other" / "outside.py"
    outside.parent.mkdir()
    outside.write_text("# outside\n")
    (probes / "escape.py").symlink_to(outside)
    (probes / "inside.py").symlink_to(good)
    script = """
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { validateExploreProbes } from './scripts/review_probes/pi_review_protocol.mjs';
const work = process.argv[1];
const probes = path.join(work, 'probes');
const good = path.join(probes, 'valid.py');
const raw = {probe_files: [good, path.join(probes, 'inside.py')]};
const before = JSON.stringify(raw);
validateExploreProbes(raw, work);
assert.equal(JSON.stringify(raw), before);
for (const files of [undefined, null, [], {}, 'encoded', [null], [42], ['valid.py'],
  [path.join(probes, 'missing.py')], [probes], [path.join(work, 'probes-other/outside.py')],
  [path.join(probes, 'escape.py')], [good, path.join(probes, 'missing.py')]]) {
  assert.throws(() => validateExploreProbes({probe_files: files}, work), /probe_files/);
}
fs.unlinkSync(path.join(probes, 'inside.py'));
fs.unlinkSync(path.join(probes, 'escape.py'));
const text = path.join(probes, 'notes.txt');
fs.renameSync(good, text);
assert.throws(() => validateExploreProbes({probe_files: [text]}, work), /Python probe/);
fs.renameSync(probes, path.join(work, 'saved-probes'));
fs.symlinkSync(path.join(work, 'saved-probes'), probes);
assert.throws(() => validateExploreProbes({probe_files: [text]}, work), /redirected/);
"""
    proc = subprocess.run(["node", "--input-type=module", "-e", script, str(work)],
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
        assert load(root / axis / "provider-template.json")["baseUrl"] == "http://127.0.0.1:19899/v1"
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
        assert "deliver_stage checks probe_files before accepting delivery" in explore
        assert "final reserved request has no retry allowance" in explore
        for stage in ("explore", "execute", "report"):
            prompt = (root / axis / f"prompt-{stage}.md").read_text()
            assert "complete=true" not in prompt
            assert "controller-owned" in prompt
        extension = (root / axis / "review.mjs").read_text()
        assert "result: Type.Object({}" in extension
        assert "FWP_WORKBENCH_PYTHON: PYTHON" in extension
        assert "FWP_ALLOW_ANY_PYTHON" not in extension
        preflight = (root / axis / "sandbox_preflight.mjs").read_text()
        assert "--collect-only" in preflight
        assert "tests/test_main_gate_receipt.py" in preflight
        assert "intelligence/tests/test_llm_timeout_diagnostic.py" in preflight
        assert "author-test collection (not execution)" in preflight
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


def configure_sandbox(folder, tree):
    config = load(folder / "config.json")
    old_tree = config["tree"]
    old_venv = Path(config["python"]).parent.parent
    config.update(tree=str(tree), python=sys.executable)
    dump(folder / "config.json", config)
    profile = folder / "tools.sb"
    # Regenerate prepare()'s tree-metadata rule rather than rewrite it: its ancestor literals are not
    # venv entries, yet repeat the venv anchor when the tree is nested under the venv's parent
    # (a .claude/worktrees/<name> checkout inside the main one).
    generated = sandbox_metadata(Path(old_tree), folder)
    policy = profile.read_text()
    assert policy.count(generated) == 1
    rest = [part.replace(old_tree, str(tree)) for part in policy.split(generated)]
    # The disposable policy must follow the interpreter selected by this test run.
    for selector, previous, current in (
        ("subpath", old_venv, Path(sys.prefix)),
        ("literal", old_venv.parent, Path(sys.prefix).parent),
    ):
        anchor = f"({selector} {json.dumps(str(previous))})"
        assert sum(part.count(anchor) for part in rest) == 1
        rest = [part.replace(anchor, f"({selector} {json.dumps(str(current))})") for part in rest]
    profile.write_text(sandbox_metadata(tree, folder).join(rest))


def sandbox_inputs(tmp_path, axis, tree):
    if sys.platform != "darwin" or not PI.is_file():
        pytest.skip("real macOS sandbox and pi tools required; not admission evidence")
    root = (tmp_path / "sandbox-inputs").resolve()
    prepare(root)
    folder = root / axis
    configure_sandbox(folder, tree)
    return folder


def test_sandbox_fixture_rewrites_only_venv_entries_for_nested_tree(tmp_path, monkeypatch):
    # Any checkout location: the tree path is derived from the archived venv, not from this run.
    root = (tmp_path / "sandbox-inputs").resolve()
    prepare(root)
    folder = root / "spec"
    venv = Path(load(folder / "config.json")["python"]).parent.parent
    tree = venv.parent / ".claude/worktrees/nested"
    selected = tmp_path / "selected/.venv"
    monkeypatch.setattr(sys, "prefix", str(selected))
    configure_sandbox(folder, tree)
    policy = (folder / "tools.sb").read_text()
    metadata = sandbox_metadata(tree, folder)
    assert policy.count(metadata) == 1
    rest = policy.replace(metadata, "")
    ancestor = f"(literal {json.dumps(str(venv.parent))})"
    assert ancestor in metadata and ancestor not in rest
    assert rest.count(f"(subpath {json.dumps(str(selected))})") == 1
    assert rest.count(f"(literal {json.dumps(str(selected.parent))})") == 1
    assert json.dumps(str(venv)) not in policy


def sandbox_tool_command(folder, command):
    out = folder / "offline-tool-run"
    (out / "commands").mkdir(parents=True)
    driver = folder / "offline-tool-run.mjs"
    driver.write_text("""
import {install} from './review.mjs';
import fs from 'node:fs';
import path from 'node:path';
const root = path.dirname(new URL(import.meta.url).pathname);
const tools = {};
process.env.REVIEW_PHASE = 'execute';
install({registerProvider() {}, on() {}, registerTool(t) {tools[t.name] = t;}}, {
  out: path.join(root, 'offline-tool-run'), token: 'offline-no-credential',
  terminate: () => {throw new Error('unexpected termination');},
});
try {
  const result = await tools.bash.execute('offline', {command: process.argv[2], timeout: 120});
  console.log(JSON.stringify(result));
} catch (error) {
  console.error(String(error));
  process.exitCode = 1;
}
if (fs.existsSync(path.join(root, 'offline-tool-run/request-admissions.jsonl'))) {
  throw new Error('offline tool validation must not admit model requests');
}
""")
    return subprocess.run(["node", str(driver), command], cwd=folder,
                          capture_output=True, text=True, timeout=140)


@pytest.mark.parametrize("axis", ["spec", "quality"])
@pytest.mark.parametrize("binding", ["configured", "removed", "relative"])
def test_sandbox_interpreter_binding_without_git_access(tmp_path, axis, binding):
    tree = (tmp_path / "candidate").resolve()
    (tree / "scripts").mkdir(parents=True)
    for name in ("conftest.py", "test-environment.json", "scripts/workspace_env.py"):
        shutil.copy2(ARCHIVE.parents[2] / name, tree / name)
    (tree / ".git").write_text("git metadata must remain unreadable\n")
    (tree / "test_binding.py").write_text(
        "import os, sys\nfrom pathlib import Path\nimport conftest\n"
        "def test_binding():\n"
        "    assert conftest.EXPECTED_PY == Path(sys.executable)\n"
        "    assert os.environ['FWP_WORKBENCH_PYTHON'] == sys.executable\n"
        "    assert 'FWP_ALLOW_ANY_PYTHON' not in os.environ\n"
        "    try: Path('.git').read_bytes()\n"
        "    except PermissionError: pass\n"
        "    else: raise AssertionError('git metadata became readable')\n",
    )
    folder = sandbox_inputs(tmp_path, axis, tree)
    if binding == "removed":
        extension = folder / "review.mjs"
        code = extension.read_text()
        assert code.count("FWP_WORKBENCH_PYTHON: PYTHON, ") == 1
        extension.write_text(code.replace("FWP_WORKBENCH_PYTHON: PYTHON, ", ""))
    if binding == "relative":
        config = load(folder / "config.json")
        config["python"] = ".venv-workbench/bin/python"
        dump(folder / "config.json", config)
    command = shlex.join([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_binding.py"])
    proc = sandbox_tool_command(folder, command)
    if binding == "configured":
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "1 passed" in proc.stdout
    elif binding == "removed":
        assert proc.returncode != 0
        raw = (folder / "offline-tool-run/commands/001-bash/output.log").read_text()
        assert "CalledProcessError" in raw and "rev-parse" in raw, raw
        assert "1 passed" not in raw
    else:
        assert proc.returncode != 0
        assert "review interpreter must be an absolute path" in proc.stderr
        assert not list((folder / "offline-tool-run/commands").iterdir())


RETIRED_OWNER_TREE = "/finance-worktrees/adaptive-research-loop/"


def repoint_retired_read_control(folder, tree):
    """Keep the archived out-of-candidate read control evaluable in disposable inputs.

    The sealed preflight names the #868 owner's live worktree, retired on 2026-09-26.
    A missing path raises ENOENT, not EPERM, so the control proves nothing and the
    preflight stops before its later checks. Point it at an existing file in a protected
    candidate subtree that the generated policy must still deny; outside-home reads stay
    covered by the archived credential-path control.
    """
    stand_in = tree / ".claude/settings.json"
    assert stand_in.is_file()
    preflight = folder / "sandbox_preflight.mjs"
    body = preflight.read_text()
    retired = re.findall(r"'([^']*" + re.escape(RETIRED_OWNER_TREE) + r"[^']*)'", body)
    assert len(retired) == 1, retired
    preflight.write_text(body.replace(f"'{retired[0]}'", json.dumps(str(stand_in))))


@pytest.mark.parametrize("axis", ["spec", "quality"])
@pytest.mark.parametrize("removed_guard", [None, "metadata", "keychain"])
def test_sandbox_preflight_collects_real_author_tests(tmp_path, axis, removed_guard):
    folder = sandbox_inputs(tmp_path, axis, ARCHIVE.parents[2])
    repoint_retired_read_control(folder, ARCHIVE.parents[2])
    if removed_guard:
        profile = folder / "tools.sb"
        guard = (sandbox_metadata(ARCHIVE.parents[2], folder) if removed_guard == "metadata"
                 else '(deny process-exec (literal "/usr/bin/security"))')
        body = profile.read_text()
        assert body.count(guard) == 1
        profile.write_text(body.replace(guard, ""))
    proc = subprocess.run(["node", str(folder / "sandbox_preflight.mjs")], cwd=folder,
                          capture_output=True, text=True, timeout=140)
    if removed_guard:
        assert proc.returncode != 0
        expected = "PermissionError" if removed_guard == "metadata" else "keychain CLI execution allowed"
        assert expected in proc.stderr, proc.stderr
        assert not (folder / "sandbox-preflight/receipt.json").exists()
        return
    assert proc.returncode == 0, proc.stdout + proc.stderr
    receipt = load(folder / "sandbox-preflight/receipt.json")
    assert receipt["status"] == "PASS" and receipt["real_model_requests"] == 0
    assert "author-test collection (not execution)" in receipt["checks"]
    logs = list((folder / "sandbox-preflight/commands").glob("*/output.log"))
    collection = [p.read_text() for p in logs if "tests collected" in p.read_text()]
    assert len(collection) == 1
    assert "test_real_late_judge_report_is_rejected" in collection[0]
    assert "test_gate_retains_complete_output_beside_its_own_receipt" in collection[0]
    assert not (folder / "work/author-tests.xml").exists()


@pytest.mark.parametrize("axis", ["spec", "quality"])
@pytest.mark.parametrize("claim", ["C3", "C7"])
def test_real_author_checks_execute_in_sandbox(tmp_path, axis, claim):
    folder = sandbox_inputs(tmp_path, axis, ARCHIVE.parents[2])
    work = folder / "work"
    xml = work / "author-checks.xml"
    args = ["-q", "-p", "no:cacheprovider", f"--basetemp={work / 'pytest-tmp'}", f"--junitxml={xml}"]
    if claim == "C7":
        args += ["tests/test_main_gate_receipt.py"]
        command = shlex.join([sys.executable, "-B", "-m", "pytest", *args])
    else:
        target = "intelligence/tests/test_llm_timeout_diagnostic.py::"
        args += [target + name for name in (
            "test_real_late_judge_report_is_rejected_at_the_transport_boundary",
            "test_shared_window_zero_rejection_is_not_a_third_request",
            "test_expired_root_is_distinct_from_exhausted_judge_window",
        )]
        driver = work / "author-ports.py"
        # Only relocate the author's ephemeral peers into the already allowed range.
        driver.write_text("""
import errno
import json
from pathlib import Path
import sys
from unittest.mock import patch
import pytest
from scripts.review_probes import diagnose_llm_timeout as probe

class ReviewHTTPServer(probe.ThreadingHTTPServer):
    def server_bind(self):
        assert self.server_address == ('127.0.0.1', 0)
        for port in range(26001, 26009):
            self.server_address = ('127.0.0.1', port)
            try:
                return super().server_bind()
            except OSError as error:
                if error.errno != errno.EADDRINUSE:
                    raise
        raise RuntimeError('review loopback ports unavailable')

observations = []
original = probe.run_judge_case

def observe(*args, **kwargs):
    result = original(*args, **kwargs)
    observations.append(result)
    return result

with patch.object(probe, 'ThreadingHTTPServer', ReviewHTTPServer), patch.object(probe, 'run_judge_case', observe):
    code = pytest.main(sys.argv[1:])
Path(__file__).with_suffix('.json').write_text(json.dumps(observations, indent=2))
raise SystemExit(code)
""")
        command = shlex.join([sys.executable, "-B", str(driver), *args])
    proc = sandbox_tool_command(folder, command)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    cases = ET.parse(xml).getroot().findall(".//testcase")
    assert cases and all(not list(case) for case in cases)
    if claim == "C7":
        names = {case.attrib["name"] for case in cases}
        assert "test_gate_retains_complete_output_beside_its_own_receipt[False]" in names
        assert "test_gate_refuses_receipts_inside_disposable_basetemp[True]" in names
        assert any(name.startswith("test_readback_refuses_invalid_or_untrustworthy_receipt[") for name in names)
    else:
        assert len(cases) == 3
        results = load(work / "author-ports.json")
        late = next(row for row in results if row["scenario"] == "judge_late_report")
        assert late["report_received"] is False and late["unavailable"] is True
        assert late["request_count"] == 1
        assert any(event["event"] == "headers" for event in late["attempts"][0]["events"])
        assert late["wall_elapsed_seconds"] <= 1.0
        assert 0 < late["remaining_root_seconds"] <= 9.6 - late["wall_elapsed_seconds"] + 0.01


@pytest.fixture
def runtime(tmp_path, peer):
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
        configure_sandbox(folder, tree)
        config = load(folder / "config.json")
        config.update(author=str(tree), revision=revision, baseline=revision)
        dump(folder / "config.json", config)
        # Only disposable test inputs use this fixture's already-bound loopback port.
        template = folder / "provider-template.json"
        provider = load(template)
        original_url = provider["baseUrl"]
        provider["baseUrl"] = peer["base_url"]
        dump(template, provider)
        extension = folder / "review.mjs"
        code = extension.read_text()
        assert code.count(original_url) == 1
        extension.write_text(code.replace(original_url, peer["base_url"]))
        control = folder / "run_control.py"
        code = control.read_text()
        original = "HTTPConnection('127.0.0.1', 19899, timeout=122)"
        assert code.count(original) == 1
        control.write_text(code.replace(original, f"HTTPConnection('127.0.0.1', {peer['port']}, timeout=122)"))
    return root


def test_runtime_sandbox_uses_selected_python_without_widening_access(runtime):
    folder = runtime / "spec"
    config = load(folder / "config.json")
    tree = Path(config["tree"])
    secret = tree / ".claude/private-fixture.txt"
    secret.parent.mkdir()
    secret.write_text("private fixture only")
    allowed = folder / "work/allowed.txt"
    forbidden = tree / "forbidden.txt"
    script = """
from pathlib import Path
import sys
assert sys.executable == sys.argv[1]
Path(sys.argv[2]).write_text('allowed')
for operation in (lambda: Path(sys.argv[3]).read_text(), lambda: Path(sys.argv[4]).write_text('forbidden')):
    try:
        operation()
    except PermissionError:
        pass
    else:
        raise AssertionError('sandbox boundary was widened')
"""
    proc = run(["/usr/bin/sandbox-exec", "-f", str(folder / "tools.sb"), config["python"], "-B", "-c",
                script, sys.executable, str(allowed), str(secret), str(forbidden)], tree)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert allowed.read_text() == "allowed"
    assert secret.read_text() == "private fixture only"
    assert not forbidden.exists()


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

    server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    state["port"] = server.server_address[1]
    state["base_url"] = f"http://127.0.0.1:{state['port']}/v1"
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
            "base_url": state["base_url"],
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


@pytest.mark.parametrize("axis", ["spec", "quality"])
@pytest.mark.parametrize("seed", [0, 15])
@pytest.mark.parametrize("in_tool_validation", [True, False])
def test_probe_path_repair_observes_tool_error_within_existing_budget(
    runtime, peer, axis, seed, in_tool_validation,
):
    folder, data = stage_fixture(runtime, "explore", axis)
    # Drop the workspace prefix, not /private (which aliases /var on macOS).
    bad_path = str(Path("/") / Path(data["probe_files"][0]).relative_to(runtime.parent))
    assert not Path(bad_path).exists()
    invalid = {**data, "probe_files": [bad_path]}
    extension = folder / "review.mjs"
    code = extension.read_text().replace("let admitted = 0;", f"let admitted = {seed};")
    if not in_tool_validation:
        assert code.count("validateExploreProbes(data, work);") == 1
        code = code.replace("validateExploreProbes(data, work);", "/* mutation: validate only after exit */")
    extension.write_text(code)
    out = folder / "explore"

    def reply(payload, number):
        if number == 1:
            return [tool("deliver_stage", {"result": invalid})]
        assert number == 2
        assert not (out / "submission.json").exists()
        assert not (out / "REPORT.md").exists()
        results = [m for m in payload["messages"] if m["role"] == "tool"]
        assert "delivery_probe_invalid" in results[-1]["content"]
        assert str(folder / "work/probes") in results[-1]["content"]
        rejected = load(out / "commands/001-deliver_stage/result.json")
        assert rejected["delivered"] is False and rejected["recoverable"] is True
        return [tool("deliver_stage", {"result": data})]

    peer["reply"] = reply
    proc = run([sys.executable, "-B", str(folder / "run_stage.py"), "explore"], folder)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    execution = load(out / "execution.json")
    assert execution["inputs_unchanged"] is True
    first = load(out / "commands/001-deliver_stage/request.json")
    assert first["params"]["result"] == invalid
    submission = load(out / "submission.json")
    if not in_tool_validation:
        assert execution["status"] == "BLOCKED_STAGE_OR_PROVIDER"
        assert submission["probe_files"] == [bad_path]
        assert len(peer["requests"]) == execution["requests"] == 1
        return
    assert execution["status"] == "STAGE_COMPLETE"
    assert submission["probe_files"] == data["probe_files"]
    assert len(peer["requests"]) == execution["requests"] == 2
    assert load(out / "commands/002-deliver_stage/result.json")["delivered"] is True
    admissions = [json.loads(line) for line in (out / "request-admissions.jsonl").read_text().splitlines()]
    assert [a["admission"] for a in admissions] == [seed + 1, seed + 2]
    if seed == 15:
        assert [t["function"]["name"] for t in peer["requests"][-1]["tools"]] == ["deliver_stage"]


@pytest.mark.parametrize("boundary", ["last_reserved", "repeated_invalid", "deadline_during_delivery", "hard_limit_during_delivery"])
def test_invalid_probe_delivery_cannot_reopen_budget(runtime, peer, boundary):
    folder, data = stage_fixture(runtime, "explore", "quality")
    data["probe_files"] = [str(folder / "work/probes/missing.py")]
    extension = folder / "review.mjs"
    code = extension.read_text()
    if boundary in {"last_reserved", "repeated_invalid"}:
        seed = 16 if boundary == "last_reserved" else 15
        code = code.replace("let admitted = 0;", f"let admitted = {seed};")
    else:
        expire = "clock = () => started + 600001;" if boundary == "deadline_during_delivery" else "admitted = 24;"
        code = code.replace("validateExploreProbes(data, work);", expire + " validateExploreProbes(data, work);")
    extension.write_text(code)
    peer["reply"] = lambda *_: [tool("deliver_stage", {"result": data})]
    proc = run([sys.executable, "-B", str(folder / "run_stage.py"), "explore"], folder)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    out = folder / "explore"
    assert load(out / "execution.json")["status"] == "BLOCKED_STAGE_OR_PROVIDER"
    assert not (out / "submission.json").exists()
    assert not (out / "REPORT.md").exists()
    attempts = 2 if boundary == "repeated_invalid" else 1
    assert len(peer["requests"]) == attempts
    rejection = load(out / f"commands/{attempts:03d}-deliver_stage/result.json")
    assert rejection["recoverable"] is False and rejection["delivered"] is False
    assert "delivery_probe_invalid" in load(out / "controller-stop.json")["reason"]


def test_post_exit_validation_still_rejects_disappeared_probe(runtime, peer):
    folder, data = stage_fixture(runtime, "explore", "spec")
    extension = folder / "review.mjs"
    code = extension.read_text()
    assert code.count("      delivered = true;") == 1
    extension.write_text(code.replace("      delivered = true;",
                                      "      delivered = true;\n      fs.unlinkSync(data.probe_files[0]);"))
    peer["reply"] = lambda *_: [tool("deliver_stage", {"result": data})]
    proc = run([sys.executable, "-B", str(folder / "run_stage.py"), "explore"], folder)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    out = folder / "explore"
    assert load(out / "commands/001-deliver_stage/result.json")["delivered"] is True
    assert load(out / "execution.json")["status"] == "BLOCKED_STAGE_OR_PROVIDER"
    assert len(peer["requests"]) == 1


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
