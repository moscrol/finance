"""Financial local rejection -> real conversation persistence/publication.

Scripted evidence and adapter runtime, real verifiers/stores/API; no model or
network. Publication proves visibility, not financial completeness/quality.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from intelligence.api import app as app_module
from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.research_contract import (
    ResearchDeadline, ResearchPolicy, ResearchRunContext,
)
from intelligence.services.run_store import RunStore
from intelligence.tests.test_continuous_turn_adapter import _control
from intelligence.tests.test_episode_semantic_verifier import _judge
from intelligence.tests.test_financial_delivery_integration import BAD, GOOD, _metric_only
from intelligence.tests.test_financial_r6_regressions import SAFE
from intelligence.tests.test_workbench_conversation_integration import _LLM_KEY_NAMES

REVIEW = "请于2026-10-22复查现金回款。"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*_args, **_kwargs):
        raise AssertionError("financial publication integration attempted network IO")
    for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
        monkeypatch.setattr(name, denied)
    monkeypatch.setenv("FORESIGHT_LLM_KEYCHAIN", "0")
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    monkeypatch.setenv("FINANCE_NEWS_FETCH", "0")
    monkeypatch.setenv("FINANCE_WEB_SEARCH", "0")
    for key in _LLM_KEY_NAMES:
        monkeypatch.delenv(key, raising=False)


def _financial_result(*, recovery):
    frame, verified = _metric_only(SAFE + "[E1]。\n" + GOOD + "\n" + BAD + "\n" + REVIEW)
    context = ResearchRunContext(
        contract=verified.contract, deadline=ResearchDeadline.from_timeout(60),
        policy=ResearchPolicy("standard", 3, 60, 20), trace_parent_id=verified.contract.task_id,
    )
    class Runtime:
        def run(self, **_kwargs):
            return verified.outcome
    verifier = SemanticEpisodeVerifier(judge_fn=_judge(True))
    adapter = ContinuousTurnAdapter(
        runtime=Runtime(), mode="on", semantic_verifier=verifier,
        context_factory=lambda *_a, **_k: context,
        registry_factory=lambda *_a, **_k: "registry",
    )
    if recovery:
        semantic = verifier.verify(
            frame=frame, structurally_verified=verified, deadline=context.deadline,
        )
        result = adapter._recover_verified_delivery(frame, context, semantic, {})
        assert result is not None
    else:
        result = adapter.handle(frame=frame, control=_control(frame))
    assert result.status == "partial" and result.citations
    assert BAD not in result.answer and GOOD in result.answer
    assert SAFE in result.answer and REVIEW in result.answer
    assert result.private_artifact["semantic_verifier"]["gap_output_ids"] == ["metric_evidence"]
    return result


@pytest.mark.parametrize("recovery", [False, True], ids=["normal", "recovery"])
@pytest.mark.parametrize("blocked_at", ["report", "commit-event", "after-commit"])
def test_financial_partial_publication_preserves_debt_citations_and_safe_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recovery: bool, blocked_at: str,
) -> None:
    result = _financial_result(recovery=recovery)
    repo_root = Path(__file__).parent / "fixtures" / "chat_workbench_repo"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(repo_root))
    monkeypatch.setenv("KB_VAULT", str(repo_root / "wiki"))
    class Adapter:
        def handle(self, **_kwargs):
            return result
    monkeypatch.setattr(app_module, "_build_continuous_turn_adapter", lambda **_k: Adapter())
    reached, release = threading.Event(), threading.Event()
    original_artifact = RunStore.add_artifact
    original_event = RunStore.append_stream_event
    def block():
        reached.set()
        assert release.wait(10), "test must release publication barrier"
    def add_artifact(self, run_id, name, *args, **kwargs):
        if blocked_at == "report" and name == "report.json":
            block()
        return original_artifact(self, run_id, name, *args, **kwargs)
    def append_event(self, run_id, *args, **kwargs):
        if blocked_at == "commit-event" and kwargs.get("event_type") == "message.complete":
            block()
        event = original_event(self, run_id, *args, **kwargs)
        if blocked_at == "after-commit" and kwargs.get("event_type") == "message.complete":
            block()
        return event
    monkeypatch.setattr(RunStore, "add_artifact", add_artifact)
    monkeypatch.setattr(RunStore, "append_stream_event", append_event)

    with TestClient(app_module.create_app(repo_root=repo_root)) as client:
        conv = client.post("/api/conversations", json={"user": "alice"}).json()["conversation_id"]
        response = client.post(f"/api/conversations/{conv}/messages", json={
            "user": "alice", "content": "请比较中际旭创的利润与回款，不登记长期跟踪。",
            "skill_mode": "hybrid", "selected_skill_ids": [],
        })
        response.raise_for_status()
        created = response.json()
        run_id, message_id = created["run_id"], created["assistant_message_id"]
        route = f"/api/runs/{run_id}"
        try:
            assert reached.wait(10)
            early = client.get(route, params={"user": "alice"}).json()
            assert early["status"] == "completed"  # Transport ownership already settled.
            assert early["publication"] == (
                {"status": "published", "message_id": message_id} if blocked_at == "after-commit"
                else {"status": "pending", "message_id": None}
            )
            # Exact publication does not prove the writer has released ownership.
            assert early["delivery_pending"] is True
            assert ("report.json" in [a["path"] for a in early["artifacts"]]) == (blocked_at != "report")
            message = client.get(f"/api/conversations/{conv}/messages", params={"user": "alice"}).json()[-1]
            assert message["message_id"] == message_id and message["status"] == "completed"
            assert message["citations"] and BAD not in message["content"]
            assert SAFE in message["content"] and GOOD in message["content"] and REVIEW in message["content"]
            assert client.get(route, params={"user": "bob"}).status_code == 404
        finally:
            release.set()
        body = client.get(route + "/events", params={"user": "alice"}).text
        terminal = json.loads(body.split("event: run\ndata: ")[1].strip())
        assert terminal["publication"] == {"status": "published", "message_id": message_id}
        assert terminal["delivery_pending"] is False
        assert body.index("event: message.complete") < body.index("event: run")
        assert {"answer.md", "report.json"} <= {a["path"] for a in terminal["artifacts"]}
        assert "continuous-episode.json" not in {a["path"] for a in terminal["artifacts"]}
        report = client.get(route + "/report", params={"user": "alice"}).json()
        assert report["transport_status"] == "completed"
        assert report["status"] == report["business_status"] == report["answer_status"] == "partial"
        store = RunStore(user_id="alice")
        private = json.loads((store.run_dir(run_id) / "continuous-episode.json").read_text(encoding="utf-8"))
        semantic = private["semantic_verifier"]
        assert semantic["status"] == "partial" and semantic["gap_output_ids"] == ["metric_evidence"]
        assert any("financial_claim_mismatch" in row["reasons"] for row in semantic["sentence_verdicts"])
        assert semantic["delivery_retained_evidence_hashes"]
        assert bool(private.get("delivery_recovery")) == recovery
        answer = (store.run_dir(run_id) / "answer.md").read_text(encoding="utf-8")
        assert BAD not in answer and GOOD in answer and SAFE in answer and REVIEW in answer
