"""Joint snapshot witnesses: real local producers/consumers, never a model-quality test."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from intelligence.services import answer_model, ask_blocks, ask_synthesis, episode_tools, llm_refine
from intelligence.services.market_history_context import market_history_blocks
from intelligence.tests.test_river_history_consumption import CUTOFF, QUESTION, _frame, _make_db, _offline_ask


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    attempts = []

    def forbidden(*_args, **_kwargs):
        attempts.append(True)
        raise AssertionError("joint consumer witnesses must not contact a network or model")

    for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
        monkeypatch.setattr(name, forbidden)
    for name in ("synthesize", "synthesize_messages", "synthesize_messages_stream", "complete"):
        monkeypatch.setattr(llm_refine, name, forbidden)
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_a, **_kw: None)
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_READING_BASELINE", "1")
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    yield
    assert attempts == [], "a swallowed IO exception is still a failed offline witness"


@pytest.fixture
def joint_db(tmp_path):
    """Extend a temporary synthetic fixture, not either frozen evaluation database."""
    path = tmp_path / "joint.duckdb"
    _make_db(path)
    schema = (Path(__file__).parents[2] / "market_feature_store/schema.sql").read_text()
    start = schema.index("CREATE TABLE IF NOT EXISTS fact_mainline_sector_daily (")
    statement = schema[start:schema.index(";", start) + 1]
    with duckdb.connect(str(path)) as con:
        con.execute(statement)
        con.execute("ALTER TABLE fact_sector_daily ADD COLUMN sector_ts_code VARCHAR")
        con.execute("ALTER TABLE fact_sector_daily ADD COLUMN sw_l1 VARCHAR")
        for code, sector, amount in (("S0", "合成未过板块", 500), ("S1", "合成通过板块", 501),
                                     ("S2", "合成缺数板块", None)):
            con.execute(
                "INSERT INTO fact_mainline_sector_daily "
                "(trade_date,theme_code,theme_name,sector_ts_code,sector_name,sort_no,today_pct) "
                "VALUES (?, 'SYNTHETIC', '合成主题', ?, ?, 1, 2)", [CUTOFF, code, sector],
            )
            con.execute(
                "INSERT INTO fact_sector_daily "
                "(trade_date,sector_ts_code,sector_name,pct_chg,diff_ratio,amount,sw_l1) "
                "VALUES (?, ?, ?, 2, 42, ?, '合成行业')", [CUTOFF, code, sector, amount],
            )
        con.execute(
            "INSERT INTO fact_mainline_sector_daily "
            "(trade_date,theme_code,theme_name,sector_ts_code,sector_name) "
            "VALUES ('2025-04-11','FUTURE','FUTURE_D4_SENTINEL','FUTURE','FUTURE_D4_SENTINEL')"
        )
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    yield path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_untyped_d4_cannot_mint_facts_or_method_claims():
    block = "## 主线题材结构数据块 [D4]\n- 判读：强势意味着后续延续。\n- 合成板块量价确认。"
    assert ask_synthesis._claims_from_data_block(block, "D4", "主线", "合成") == []


def test_d10_is_one_lossless_inferred_object_not_fact_lines():
    block = "## 历史比较 [D10]\n```json\n{\"source\":\"fact_market_daily.total_amount\"}\n```\n边界：不可嫁接。"
    claims = ask_synthesis._claims_from_data_block(block, "D10", "历史", "合成")
    assert len(claims) == 1
    assert claims[0].claim_id == "data:D10:context"
    assert claims[0].text == "历史：\n" + block
    assert claims[0].status is answer_model.ClaimStatus.INFERRED


@pytest.mark.parametrize("grounded", [False, True])
def test_one_ask_request_keeps_d10_and_d4_fact_roles(joint_db, tmp_path, monkeypatch, grounded):
    from intelligence.services.ask_types import AskOptions, PreparedAnswer

    result = _offline_ask(joint_db, tmp_path, monkeypatch, enabled=("D4", "D10"))
    spec = result.answer_spec
    history = next(c for c in spec.candidate_facts if c.claim_id == "data:D10:context")
    assert history.status is answer_model.ClaimStatus.INFERRED
    blocks = market_history_blocks(joint_db, as_of=CUTOFF)
    assert all(block.detail in history.text for block in blocks)
    assert not any(c.claim_id == history.claim_id for c in spec.verified_facts)
    rows = [c for c in spec.verified_facts if c.claim_id.startswith("data:D4:row:")]
    assert len(rows) == 3
    snapshot = ask_blocks.mainline_context_snapshot(QUESTION, None, joint_db, as_of=CUTOFF.isoformat())
    expected = ask_synthesis._claims_from_mainline_snapshot(snapshot, rows[0].theme)
    assert [c.text for c in rows] == [c.text for c in expected]
    assert all("判读[" not in c.text and "满足严格双红" not in c.text for c in rows)
    prepared = "\n".join(m["content"] for m in result.prepared_synthesis_messages)
    basis = json.loads('{"query_basis": ' + prepared.rsplit('\n{"query_basis": ', 1)[1])
    expected_basis = episode_tools.mainline_snapshot_tool_result(snapshot).query_basis
    assert basis["query_basis"]["D4"] == expected_basis
    assert {r["sector_ts_code"]: r["strict_double_red"] for r in expected_basis["price_volume_signals"]} == {
        "S0": False, "S1": True, "S2": None,
    }
    calls = []

    def capture(messages, **_kwargs):
        calls.append(deepcopy(messages))
        return None, "offline joint boundary stop; no financial answer"

    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_a, **_kw: None)
    monkeypatch.setattr(llm_refine, "synthesize_messages", capture)
    monkeypatch.setattr(llm_refine, "synthesize_messages_stream", capture)
    ask_synthesis.synthesize_prepared_answer(PreparedAnswer(
        options=AskOptions(query=QUESTION, compose=True, grounded_presenter=grounded,
                           daily_agent_grounded_presenter=grounded, shadow_grounded_composer=False),
        result=result,
    ))
    assert calls
    prompt = "\n".join(m["content"] for m in calls[0])
    assert "FUTURE_D4_SENTINEL" not in prompt
    if grounded:
        registry = ask_synthesis._grounded_registry_for_synthesis(spec, QUESTION)
        assert registry in prompt and len(registry) <= 12_000
        records = [json.loads(line) for line in registry.splitlines()]
        item = next(r for r in records if r.get("claim_id") == history.claim_id)
        assert item["text"] == history.text and item["claim_type"] == "inference"
        fact_ids = {c.claim_id for c in rows}
        delivered = [r for r in records if r.get("claim_id") in fact_ids]
        assert delivered, {"registry_chars": len(registry), "rows": records,
                           "d4_claims": [c.text for c in rows]}
        assert all(r["text"] in {c.text for c in rows} for r in delivered)
        admitted_ids = {r["claim_id"] for r in records if "claim_id" in r}
        brief = result.grounded_composer_shadow.decision_brief
        assert brief is not None
        for ids in brief.to_dict().values():
            if isinstance(ids, list):
                assert set(ids) <= admitted_ids
        assert "未纳入" in records[-1]["note"]
        assert any(r.get("claim_id", "").startswith(("counter:", "gap:")) for r in records)
    else:
        assert history.text in prompt
        assert all(c.text in prompt for c in rows)
        assert '"d4_mainline_snapshot_v1"' in prompt


def test_native_episode_keeps_history_and_owned_d4_in_one_tool_loop(joint_db, tmp_path):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier, recheck_owned_public_delivery
    from intelligence.services.episode_verifier import verify_episode_outcome
    from intelligence.services.evidence_capabilities import EvidencePlan
    from intelligence.services.research_contract import RequiredOutput

    frame = replace(_frame(), required_outputs=("direct_assessment",))
    context = build_episode_context(frame, task_id="synthetic-joint-episode",
        capabilities=("market_data", "mainline_context"), timeout=60,
        latest_data_date=CUTOFF.isoformat(), today=CUTOFF.isoformat())
    context = replace(context, contract=replace(context.contract, required_outputs=(
        RequiredOutput("direct_assessment", "核对合成量价资格", ("mainline_context",), True),
    ), evidence_plan=EvidencePlan()))
    registry = episode_tools.build_episode_registry(frame, context, finance_root=tmp_path,
        knowledge_wiki=tmp_path / "wiki", fixture_policy=episode_tools.SealedFixturePolicy(market_db_path=joint_db))
    blocks = market_history_blocks(joint_db, as_of=CUTOFF)
    source = episode_tools.mainline_snapshot_tool_result(
        ask_blocks.market_review_mainline_context_snapshot(QUESTION, None, joint_db, as_of=CUTOFF.isoformat()))
    calls, views = [], []

    class ScriptedModel:
        def complete(self, *, messages, **_kwargs):
            calls.append(deepcopy(messages))
            received = "\n".join(m["content"] for m in messages)
            missing = [b.title for b in blocks if b.detail not in received]
            if missing:
                pytest.fail(f"history missing from native request {len(calls)}: {missing}; {received}")
            if len(calls) == 1:
                return ModelTurn("", (ModelToolCall("d4-joint", "mainline_context", {}),))
            tool_views = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
            view = next((v for v in tool_views if "owned_results" in v), None)
            if view is None:
                pytest.fail(f"D4 ownership catalogue absent: {tool_views}")
            views.append(view)
            part = next(p for p in view["owned_results"]["parts"]
                        if "合成未过板块" in p["text"] and "不满足严格双红" in p["text"])
            return ModelTurn(json.dumps({
                "status": "completed", "draft": "", "gaps": [],
                "bindings": [{"output_id": "direct_assessment", "evidence_hashes": [source.evidence[0].content_hash],
                              "basis": "evidence", "gap": ""}],
                "answer_parts": [{"result_ref": part["result_ref"]}, "历史比较仍是推断，不能升级为路径或预测。"],
            }, ensure_ascii=False), ())

    outcome = ContinuousAgentEpisode(ScriptedModel()).run(task_frame=frame, context=context, registry=registry)
    assert len(calls) == 2 and outcome.stop_reason == "model_finish", outcome
    view = views[0]
    assert view["query_basis"] == source.query_basis
    assert all("判读[" not in e["detail"] for e in view["evidence"])
    assert "FUTURE_D4_SENTINEL" not in json.dumps(calls, ensure_ascii=False)
    assert all("历史比较" not in p["text"] for p in view["owned_results"]["parts"])
    semantic = SemanticEpisodeVerifier().verify(frame=frame,
        structurally_verified=verify_episode_outcome(context.contract, outcome), context=context, deadline=context.deadline)
    public = recheck_owned_public_delivery(semantic, context=context, projected=semantic.public_answer)
    assert "合成未过板块不满足严格双红" in public.public_answer
    assert public.owned_coverage["owned_faithful"] == 1
    assert public.owned_coverage["free_unassessed"] == 1
    assert public.owned_coverage["whole_answer"] == "unassessed"
