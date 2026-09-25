#!/usr/bin/env python3
"""Paired Workbench probes with only adaptive research toggled.

Runs isolated sidecars, never 8792; keeps raw answers and private run artifacts.
The caller supplies a compatible gateway and a key environment variable. No
credential is serialized. This is an n=1 diagnostic, not a quality verdict.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.eval.live_probe import (  # noqa: E402
    DEFAULT_LAUNCHER, DEFAULT_PYTHON, LIVE_LOCK_PATH,
    SidecarSpec, assert_safe_to_start, choose_port, port_is_listening, sidecar_zsh,
)


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def request(base: str, path: str, payload=None, *, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        base + path, data=data, headers={"Content-Type": "application/json"},
        method=method or ("POST" if data else "GET"),
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def run_arm(args, arm: str, key: str) -> dict[str, object]:
    dest = args.output / arm
    dest.mkdir()
    port = choose_port(preferred=8796, is_busy=port_is_listening)
    assert_safe_to_start(lock_path=LIVE_LOCK_PATH, port=port, is_busy=port_is_listening)
    user = "adaptive-" + arm
    spec = SidecarSpec(port, REPO, args.python, args.launcher, dest / "users", user)
    command = sidecar_zsh(spec).replace(
        "export WORKBENCH_GROUNDED_PRESENTER=0",
        f"export WORKBENCH_GROUNDED_PRESENTER=0\nexport WORKBENCH_ADAPTIVE_RESEARCH={arm}",
    )
    base = f"http://127.0.0.1:{port}"
    with (dest / "server.log").open("w") as log:
        process = subprocess.Popen(["/bin/zsh", "-c", command], stdout=log, stderr=subprocess.STDOUT)
        configured = False
        try:
            startup = time.monotonic() + 90
            while True:
                if process.poll() is not None:
                    raise RuntimeError("sidecar exited during startup; see server.log")
                try:
                    health = request(base, "/api/health")
                    break
                except OSError:
                    if time.monotonic() >= startup:
                        raise RuntimeError("sidecar startup timed out") from None
                    time.sleep(1)
            runtime = health["runtime"]
            if Path(runtime["loaded_code_root"]).resolve() != REPO / "intelligence":
                raise RuntimeError("sidecar imported the wrong code root")
            dump(dest / "health.json", health)
            request(base, "/api/llm/config", {
                "user": user, "provider": "openai", "api_key": key,
                "base_url": args.gateway, "model": args.model, "remember": False,
            }, method="PUT")
            configured = True
            conversation = request(base, "/api/conversations", {"user": user, "title": "Adaptive research paired probe"})
            conversation_id = conversation["conversation_id"]
            started = time.monotonic()
            submitted = request(base, f"/api/conversations/{conversation_id}/messages", {
                "user": user, "content": args.question, "skill_mode": "hybrid", "perspective_mode": "neutral",
            })
            dump(dest / "submission.json", submitted)
            run_id = submitted["run_id"]
            message_id = submitted["assistant_message_id"]
            while time.monotonic() - started < args.timeout:
                run = request(base, f"/api/runs/{run_id}?user={user}")
                dump(dest / "run.json", run)
                if run["status"] in {"failed", "cancelled"}:
                    raise RuntimeError(f"run ended {run['status']}")
                if run["status"] == "completed" and not run.get("delivery_pending"):
                    messages = request(base, f"/api/conversations/{conversation_id}/messages?user={user}")
                    items = messages.get("messages", []) if isinstance(messages, dict) else messages
                    answer = next((m for m in items if m.get("message_id") == message_id), None)
                    if answer and answer.get("content"):
                        dump(dest / "message.json", answer)
                        (dest / "answer.md").write_text(answer["content"], encoding="utf-8")
                        source = spec.users_dir / user / "runs" / run_id
                        if source.is_dir():
                            shutil.copytree(source, dest / "raw-run")
                        result = {"arm": arm, "run_id": run_id, "elapsed_seconds": round(time.monotonic() - started, 2), "status": run["status"]}
                        dump(dest / "result.json", result)
                        return result
                time.sleep(2)
            raise RuntimeError("probe deadline exceeded")
        finally:
            if configured:
                try:
                    request(base, f"/api/llm/config?user={user}", method="DELETE")
                except OSError:
                    pass
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--key-env", default="MIRASIM_CODEX_API_KEY")
    parser.add_argument("--question", required=True)
    parser.add_argument("--arms", choices=("off", "on"), nargs="+", default=["off", "on"])
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--launcher", type=Path, default=DEFAULT_LAUNCHER)
    parser.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if len(args.arms) != len(set(args.arms)):
        parser.error("arms must not contain duplicates")
    key = os.environ.get(args.key_env, "")
    if not key:
        parser.error(f"missing credential environment variable {args.key_env}")
    if args.output.exists():
        parser.error("output already exists; refuse to overwrite previous evidence")
    args.output.mkdir(parents=True)
    dump(args.output / "protocol.json", {
        "question": args.question, "model_requested": args.model, "arms": args.arms,
        "code_root": str(REPO), "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip()),
        "production_changed": False, "presenter": "marker lane in both arms",
        "scope": "diagnostic; live data not frozen; a single arm is not a comparison; no broad quality claim",
    })
    results = []
    for arm in args.arms:
        try:
            result = run_arm(args, arm, key)
        except Exception as exc:
            # Do not serialize provider exceptions, which may contain request credentials.
            result = {"arm": arm, "status": "probe_failed", "error_type": type(exc).__name__}
            dump(args.output / arm / "failure.json", result)
        results.append(result)
        print(json.dumps(result), flush=True)
    dump(args.output / "results.json", results)
    return int(any(item["status"] != "completed" for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
