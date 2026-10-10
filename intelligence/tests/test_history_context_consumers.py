"""External CLI and full Workbench entry: synthetic data, zero network/model IO."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import subprocess
import sys
import time

import pytest

from intelligence.history_context_cli import encode_payload, history_payload
from intelligence.services.market_history_context import market_history_blocks
from intelligence.tests.test_river_history_consumption import CUTOFF, QUESTION, _make_db, _apply_changed_gap


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "db" / "market_feature_store.duckdb"
    path.parent.mkdir()
    _make_db(path)
    return path


def test_external_payload_matches_workbench_blocks_and_never_writes(db):
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    payload = history_payload(db, as_of=CUTOFF.isoformat())
    blocks = market_history_blocks(db, as_of=CUTOFF)
    assert payload["evidence_grade"] == "INFERRED"
    assert [b["detail"] for b in payload["blocks"]] == [b.detail for b in blocks]
    for block in payload["blocks"]:
        assert block["sha256"] == hashlib.sha256(block["detail"].encode()).hexdigest()
    assert json.loads(encode_payload(payload)) == payload
    assert str(db) not in encode_payload(payload)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("as_of", ["2025-02-30", "20250410", "2025-04-10T00:00:00"])
def test_invalid_cutoff_refused(db, as_of):
    with pytest.raises(ValueError):
        history_payload(db, as_of=as_of)


@pytest.mark.parametrize("timeout", [0, -1, 121, float("inf"), float("nan")])
def test_invalid_timeout_refused(db, timeout):
    with pytest.raises(ValueError):
        history_payload(db, as_of=CUTOFF.isoformat(), timeout=timeout)


def test_missing_database_never_created(tmp_path):
    path = tmp_path / "missing.duckdb"
    with pytest.raises(FileNotFoundError):
        history_payload(path, as_of=CUTOFF.isoformat())
    assert not path.exists()


def test_existing_database_without_tables_keeps_explicit_gaps(tmp_path):
    import duckdb

    path = tmp_path / "no-tables.duckdb"
    duckdb.connect(str(path)).close()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = history_payload(path, as_of=CUTOFF.isoformat())
    assert len(payload["blocks"]) == 2
    assert all("gap" in block["detail"] for block in payload["blocks"])
    assert "不可嫁接" in payload["blocks"][1]["detail"]
    assert payload["evidence_grade"] == "INFERRED"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_output_budget_refuses_whole_context():
    with pytest.raises(ValueError, match="atomic output budget"):
        encode_payload({"detail": "镜头" * 10_000})


def test_real_cli_process_delivers_complete_json(db):
    result = subprocess.run(
        [sys.executable, "-m", "intelligence.history_context_cli", "--db", str(db),
         "--as-of", CUTOFF.isoformat()],
        capture_output=True, text=True, timeout=30, check=True,
    )
    payload = json.loads(result.stdout)
    assert payload == history_payload(db, as_of=CUTOFF.isoformat())
    assert "trade_date_only" in result.stdout and "不可嫁接" in result.stdout
    rejected = subprocess.run(
        [sys.executable, "-m", "intelligence.history_context_cli", "--db", str(db),
         "--as-of", "2025-99-99"], capture_output=True, text=True, timeout=30,
    )
    assert rejected.returncode == 2
    assert str(db) not in rejected.stdout + rejected.stderr


@pytest.mark.parametrize("sample,day", [("normal", "2025-04-10"), ("changed-gap", "2025-04-02")])
def test_workbench_http_real_assembly_reaches_model_with_full_lens(db, tmp_path, monkeypatch, sample, day):
    from fastapi.testclient import TestClient
    from intelligence.api import app as app_module
    from intelligence.runtime.glm_agent_runtime import GLMModelClient
    from intelligence.services.agent_runtime import ModelTurn
    from intelligence.tests.test_workbench_conversation_integration import _LLM_KEY_NAMES

    if sample == "changed-gap":
        _apply_changed_gap(db)
    network_attempts = []

    def forbidden(*_a, **_kw):
        network_attempts.append(True)
        raise AssertionError("offline consumer test attempted network IO")

    for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
        monkeypatch.setattr(name, forbidden)
    for key in _LLM_KEY_NAMES:
        monkeypatch.delenv(key, raising=False)
    for name, value in {
        "FORESIGHT_LLM_KEYCHAIN": "0", "ASK_SEMANTIC_JUDGE": "off",
        "FINANCE_NEWS_FETCH": "0", "FINANCE_WEB_SEARCH": "0",
        "ASK_CONTINUOUS_RUNTIME": "on", "AGENT_RUNTIME_BACKEND": "continuous_glm",
        "FINANCE_WS": str(tmp_path), "KB_VAULT": str(tmp_path / "wiki"),
        "MARKET_FEATURE_STORE_DB": str(db), "FORESIGHT_USERS_DIR": str(tmp_path / "users"),
        "FORESIGHT_EPISODE_STORE": str(tmp_path / "episodes"),
    }.items():
        monkeypatch.setenv(name, value)
    calls = []

    def capture(self, *, messages, tools, timeout):
        calls.append(deepcopy(messages))
        # A known failure, not a scripted answer masquerading as model quality.
        return ModelTurn("", (), "offline", error="synthetic_consumer_stop", provider_attempts=0)

    monkeypatch.setattr(GLMModelClient, "complete", capture)
    with TestClient(app_module.create_app(repo_root=tmp_path)) as client:
        conv = client.post("/api/conversations", json={"user": "alice"})
        conv.raise_for_status()
        conv_id = conv.json()["conversation_id"]
        response = client.post(f"/api/conversations/{conv_id}/messages", json={
            "user": "alice", "content": QUESTION.replace(CUTOFF.isoformat(), day), "skill_mode": "auto", "selected_skill_ids": [],
        })
        response.raise_for_status()
        run_id = response.json()["run_id"]
        until = time.monotonic() + 20
        while time.monotonic() < until:
            run = client.get(f"/api/runs/{run_id}", params={"user": "alice"}).json()
            if run["status"] in {"completed", "failed", "cancelled"} and not run.get("delivery_pending"):
                break
            time.sleep(0.02)
        else:
            pytest.fail(f"Workbench delivery did not settle: {run}")
        assert calls, run
        received = "\n".join(str(message["content"]) for message in calls[0])
        blocks = market_history_blocks(db, as_of=day)
        for block in blocks:
            assert block.detail in received
        lens = blocks[1]
        assert "trade_date_only" in received and "fact_market_daily.total_amount" in received
        assert "2025-05-" not in lens.detail
        # Transport completion can legitimately publish a deterministic gap answer.
        # Business status, not the HTTP/run terminal alone, must remain partial.
        assert run["status"] == "completed" and run["degrades"]
        report = client.get(f"/api/runs/{run_id}/report", params={"user": "alice"}).json()
        assert report["status"] == report["business_status"] == "partial"
        assert report["llm"]["used"] is False
        private = json.loads((tmp_path / "users" / "alice" / "runs" / run_id / "continuous-episode.json").read_text())
        assert "synthetic_consumer_stop" in json.dumps(private)
        messages = client.get(f"/api/conversations/{conv_id}/messages", params={"user": "alice"}).json()
        assert messages[-1]["status"] == "completed" and messages[-1]["degrades"]
    assert not network_attempts, "network attempts must fail even if a service swallowed the error"
