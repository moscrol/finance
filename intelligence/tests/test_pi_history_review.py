"""Real Pi lifecycle with scripted author/reviewer, no network or model-quality claim."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from intelligence.history_context_cli import encode_payload, history_payload
from intelligence.tests.test_river_history_consumption import _make_db

ROOT = Path(__file__).resolve().parents[2]
PI = shutil.which("pi")
pytestmark = pytest.mark.skipif(PI is None, reason="optional Pi CLI not installed")


@pytest.mark.parametrize("scenario", ["repair", "always_reject", "unavailable", "malformed", "truncated", "missing_receipt", "tampered_ack", "nonfactual_laundering", "cancelled", "fresh_turn", "judge_flip", "fenced"])
def test_native_pi_history_review_is_bound_and_finite(tmp_path, scenario):
    db = tmp_path / "market.duckdb"
    _make_db(db)
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "settings.json").write_text(json.dumps({"retry": {"enabled": False}, "cacheWarming": "off", "compaction": {"enabled": False}}))
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "TMPDIR", "SYSTEMROOT") if key in os.environ}
    env.update(PI_OFFLINE="1", PI_TELEMETRY="0", PI_CODING_AGENT_DIR=str(agent),
               FINANCE_HISTORY_CODE_ROOT=str(ROOT), FINANCE_HISTORY_PYTHON=sys.executable,
               FINANCE_HISTORY_DB=str(db), FINANCE_REVIEW_SCENARIO=scenario)
    result = subprocess.run([
        PI, "--offline", "--mode", "json", "--no-session", "--no-extensions", "--no-skills", "--no-context-files",
        "--no-prompt-templates", "--no-themes", "--no-approve",
        "-e", str(ROOT / "integrations/pi/reviewed-history.ts"),
        "-e", str(ROOT / "integrations/pi/tests/review-provider.ts"),
        "--tools", "finance_market_history", "--provider", "history-review-offline", "--model", "scripted",
        "--system-prompt", "Offline state-machine test only.", "截至2025-04-10，比较历史窗口。",
    ], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=90)
    (tmp_path / "events.jsonl").write_text(result.stdout)
    (tmp_path / "stderr.txt").write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    events = [json.loads(line) for line in result.stdout.split("\n") if line.strip()]
    assert events[-1]["type"] == "agent_settled"
    assistant = [event["message"] for event in events if event["type"] == "message_end" and event["message"]["role"] == "assistant"]
    assert all(message["stopReason"] in {"stop", "toolUse"} for message in assistant), result.stdout
    receipts = [event["entry"]["data"] for event in events if event["type"] == "entry_appended"
                and event["entry"].get("customType") == "finance_history_review"]
    assert receipts, result.stdout + result.stderr
    assert len(receipts) <= (3 if scenario == "fresh_turn" else 2)
    tools = [event for event in events if event["type"] == "tool_execution_end"]
    assert len(tools) == 1
    assert tools[0]["result"]["content"][0]["text"] == encode_payload(history_payload(db, as_of="2025-04-10"))
    final = "\n".join(block["text"] for block in assistant[-1]["content"] if block["type"] == "text")
    if scenario == "fresh_turn":
        assert len(receipts) == 3 and len(assistant) == 4
        assert [receipt["status"] for receipt in receipts] == ["revision_required", "reviewed", "unavailable"]
        assert receipts[-1]["source_hashes"] == []
        assert receipts[-1]["reviewer_attempts"] == []
        assert receipts[-1]["repairs"] == 0
    elif scenario in {"repair", "nonfactual_laundering", "fenced"}:
        assert receipts[0]["status"] == "revision_required"
        assert receipts[-1]["status"] == "reviewed"
        assert len(assistant) == 3
        assert "原稿" not in final
        assert "动能相反" not in final and "研报有0条" not in final
        feedback = next(event["entry"] for event in events if event["type"] == "entry_appended"
                        and event["entry"].get("customType") == "finance_history_revision")
        assert "rejected_statements" in feedback["content"]
        assert "text" in feedback["content"]
        if scenario == "nonfactual_laundering":
            assert receipts[0]["nonfactual_audit"]["status"] == "revision_required"
    elif scenario in {"always_reject", "judge_flip"}:
        assert len(receipts) == 2 and len(assistant) == 3
        assert receipts[-1]["status"] == "revision_required"
        assert receipts[-1]["reused_review"]
        assert receipts[-1]["reviewer_attempts"] == []
        assert "未确认的原稿" in final and "涨家数动能相反" in final
    else:
        assert len(receipts) == 1 and len(assistant) == 2
        assert receipts[-1]["status"] == "unavailable"
        assert "未确认的原稿" in final and "涨家数动能相反" in final
    if scenario == "tampered_ack":
        assert receipts[0]["reviewer_usage"] == []
    if scenario == "cancelled":
        assert receipts[0]["reviewer_attempts"][0]["cancelled"]
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


OTHER_CONTINUATION_OWNER = """export default function () {
  (globalThis as Record<symbol, unknown>)[Symbol.for("finance.pi.continuation-owner")] = "finance-mode";
}
"""


def _pi_with(tmp_path, *extensions):
    db = tmp_path / "market.duckdb"
    _make_db(db)
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "settings.json").write_text(json.dumps({"retry": {"enabled": False}, "cacheWarming": "off", "compaction": {"enabled": False}}))
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "TMPDIR", "SYSTEMROOT") if key in os.environ}
    env.update(PI_OFFLINE="1", PI_TELEMETRY="0", PI_CODING_AGENT_DIR=str(agent),
               FINANCE_HISTORY_CODE_ROOT=str(ROOT), FINANCE_HISTORY_PYTHON=sys.executable,
               FINANCE_HISTORY_DB=str(db), FINANCE_REVIEW_SCENARIO="repair")
    loads = [arg for path in (*extensions, ROOT / "integrations/pi/tests/review-provider.ts") for arg in ("-e", str(path))]
    return subprocess.run([
        PI, "--offline", "--mode", "json", "--no-session", "--no-extensions", "--no-skills", "--no-context-files",
        "--no-prompt-templates", "--no-themes", "--no-approve", *loads,
        "--tools", "finance_market_history", "--provider", "history-review-offline", "--model", "scripted",
        "--system-prompt", "Offline state-machine test only.", "截至2025-04-10，比较历史窗口。",
    ], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=90)


def test_revision_loop_refuses_to_stack_on_another_continuation_owner(tmp_path):
    other = tmp_path / "other-owner.ts"
    other.write_text(OTHER_CONTINUATION_OWNER)
    result = _pi_with(tmp_path, other, ROOT / "integrations/pi/reviewed-history.ts")
    assert result.returncode != 0
    assert "continuation already owned by finance-mode" in result.stderr
    assert "message_end" not in result.stdout


def test_review_without_revisions_leaves_the_continuation_unclaimed(tmp_path):
    other = tmp_path / "other-owner.ts"
    other.write_text(OTHER_CONTINUATION_OWNER)
    review_only = tmp_path / "review-only.ts"
    review_only.write_text(
        f'import {{ createHistoryTool }} from "{ROOT / "integrations/pi/market-history.ts"}";\n'
        f'import {{ installHistoryReview }} from "{ROOT / "integrations/pi/reviewed-history.ts"}";\n'
        "export default function (pi) { pi.registerTool(createHistoryTool(true)); installHistoryReview(pi, { maxRepairs: 0 }); }\n")
    result = _pi_with(tmp_path, other, review_only)
    assert result.returncode == 0, result.stderr
    events = [json.loads(line) for line in result.stdout.split("\n") if line.strip()]
    assistant = [event for event in events if event["type"] == "message_end" and event["message"]["role"] == "assistant"]
    assert len(assistant) == 2
    assert not any(event["type"] == "entry_appended" and event["entry"].get("customType") == "finance_history_revision"
                   for event in events)
