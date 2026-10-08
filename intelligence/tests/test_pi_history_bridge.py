"""Optional real Pi CLI loop with a scripted provider; never calls a live model.

Pi is an external optional host, not a Python runtime dependency. CI without Pi
skips explicitly; a skip is not a Pi-consumer verification receipt.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from intelligence.history_context_cli import history_payload
from intelligence.tests.test_river_history_consumption import _make_db

PI = shutil.which("pi")
ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(PI is None, reason="optional Pi CLI not installed")


@pytest.mark.parametrize("scenario", ["success", "invalid_date", "missing_db", "unconfigured", "oversized", "bad_json"])
def test_pi_native_tool_loop(tmp_path, scenario):
    db = tmp_path / "synthetic market.duckdb"
    _make_db(db)
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    agent_dir = tmp_path / "pi-agent"
    agent_dir.mkdir()
    (agent_dir / "settings.json").write_text(json.dumps({
        "retry": {"enabled": False}, "cacheWarming": "off", "compaction": {"enabled": False},
    }))
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "TMPDIR", "SYSTEMROOT") if key in os.environ}
    env.update({
        "PI_OFFLINE": "1", "PI_TELEMETRY": "0", "PI_CODING_AGENT_DIR": str(agent_dir),
        "FINANCE_HISTORY_CODE_ROOT": str(ROOT), "FINANCE_HISTORY_PYTHON": sys.executable,
        "FINANCE_HISTORY_DB": str(db), "FINANCE_TEST_EXPECT_ERROR": "0" if scenario == "success" else "1",
    })
    if scenario == "invalid_date":
        env["FINANCE_TEST_AS_OF"] = "2025-02-30"
    elif scenario == "missing_db":
        env["FINANCE_HISTORY_DB"] = str(tmp_path / "absent.duckdb")
    elif scenario == "unconfigured":
        env.pop("FINANCE_HISTORY_CODE_ROOT")
    elif scenario in {"oversized", "bad_json"}:
        fake_root = tmp_path / "fake-code"
        module = fake_root / "intelligence"
        module.mkdir(parents=True)
        (module / "__init__.py").write_text("")
        # Marker stands in for a credential; the child must not inherit it.
        env["FINANCE_TEST_SECRET"] = "must-not-reach-child"
        output = "'中' * 20000" if scenario == "oversized" else "'private /secret/path: not JSON'"
        (module / "history_context_cli.py").write_text(
            "import os\nfrom pathlib import Path\n"
            "assert 'FINANCE_TEST_SECRET' not in os.environ\n"
            "Path('child-env-checked').touch()\nprint(" + output + ")\n"
        )
        env["FINANCE_HISTORY_CODE_ROOT"] = str(fake_root)
    result = subprocess.run([
        PI, "--offline", "--mode", "json", "--no-session", "--no-extensions", "--no-skills",
        "--no-context-files", "--no-prompt-templates", "--no-themes", "--no-approve",
        "-e", str(ROOT / "integrations/pi/market-history.ts"),
        "-e", str(ROOT / "integrations/pi/tests/offline-provider.ts"),
        "--tools", "finance_market_history", "--provider", "finance-offline-test", "--model", "scripted",
        "--system-prompt", "Offline protocol test only.", "Read market history as of 2025-04-10.",
    ], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    (tmp_path / "events.jsonl").write_text(result.stdout)
    (tmp_path / "pi-stderr.txt").write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    # Pi JSON mode can exit zero on provider failure: inspect finalized events.
    events = [json.loads(line) for line in result.stdout.split("\n") if line.strip()]
    assert any(event["type"] == "agent_settled" for event in events)
    calls = [event for event in events if event["type"] == "tool_execution_start"]
    assert len(calls) == 1 and calls[0]["toolName"] == "finance_market_history"
    ends = [event for event in events if event["type"] == "tool_execution_end"]
    assert len(ends) == 1 and ends[0]["toolCallId"] == calls[0]["toolCallId"]
    final = [event["message"] for event in events if event["type"] == "message_end" and event["message"]["role"] == "assistant"][-1]
    assert final["stopReason"] == "stop", (final, result.stderr)
    receipt = json.loads(final["content"][0]["text"])
    assert receipt["offline"] and receipt["provider_received_tool_result"]
    text = ends[0]["result"]["content"][0]["text"]
    assert receipt["result_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert receipt["is_error"] == ends[0]["isError"] == (scenario != "success")
    if scenario == "success":
        assert json.loads(text) == history_payload(db, as_of="2025-04-10")
    else:
        assert str(tmp_path) not in text and "/secret/path" not in text
    if scenario in {"oversized", "bad_json"}:
        assert (fake_root / "child-env-checked").is_file(), "child environment guard actually reached"
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert not (tmp_path / "absent.duckdb").exists()
