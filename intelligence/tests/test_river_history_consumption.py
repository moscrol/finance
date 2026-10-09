"""只验证镜头送达真实消费接缝；合成行情不证明金融效果。"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from intelligence.services import asof_prefetch, episode_tools, river_lens, river_window
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.task_frame import TaskFrame

QUESTION = "截至2025-04-10，当前行情与历史上哪些区间相似，像在哪、不像在哪？"
CUTOFF = date(2025, 4, 10)


def _make_db(path: Path) -> None:
    """所有数据均为合成；包含截止后的极值，专门检测日期透传失效。"""
    with duckdb.connect(str(path)) as con:
        con.execute("""
            CREATE TABLE fact_market_daily (
                trade_date DATE, total_amount DOUBLE, advancers DOUBLE,
                limit_up DOUBLE, limit_down DOUBLE, sh_deviation_pct DOUBLE,
                sh_index_pct_chg DOUBLE, stock_high_count_1y DOUBLE, updated_at TIMESTAMP
            );
            CREATE TABLE fact_sector_daily (
                trade_date DATE, sector_name VARCHAR, pct_chg DOUBLE,
                diff_ratio DOUBLE, amount DOUBLE, updated_at TIMESTAMP
            );
            CREATE TABLE fact_theme_limit_heat_daily (
                trade_date DATE, rank INTEGER, market_share DOUBLE, updated_at TIMESTAMP
            );
            CREATE TABLE fact_theme_flow_daily (
                trade_date DATE, source VARCHAR, total_fund DOUBLE, updated_at TIMESTAMP
            );
            CREATE TABLE fact_research_report_catalog (report_date DATE, created_at TIMESTAMP);
            CREATE TABLE fact_limit_advance_daily (trade_date DATE, boards INTEGER);
            CREATE TABLE fact_stock_high_daily (trade_date DATE, stock_ts_code VARCHAR);
        """)
        rows = []
        for i in range(150):
            day = date(2025, 1, 1) + timedelta(days=i)
            if day.weekday() >= 5:
                continue
            # 记录时间故意晚于截止，必须如实带 trade_date_only，而非宣称严格可重放。
            stamp = datetime(2025, 6, 1)
            shift = 100_000 if day > CUTOFF else 0
            rows.append((day, 9000 + (i % 17) * 100 + shift, 2000 + (i % 13) * 80,
                         30 + i % 29, i % 11, (i % 9) / 2, (i % 7 - 3) / 5,
                         20 + i % 19, stamp))
        con.executemany("INSERT INTO fact_market_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        con.executemany("INSERT INTO fact_sector_daily VALUES (?, '合成板块', ?, 15, 900, ?)",
                        [(r[0], 2 if i % 3 else -1, r[-1]) for i, r in enumerate(rows)])
        con.executemany("INSERT INTO fact_theme_limit_heat_daily VALUES (?, 1, ?, ?)",
                        [(r[0], (i % 13) / 20, r[-1]) for i, r in enumerate(rows)])
        con.executemany("INSERT INTO fact_limit_advance_daily VALUES (?, ?)",
                        [(r[0], 2 + i % 7) for i, r in enumerate(rows)])
        con.executemany("INSERT INTO fact_stock_high_daily VALUES (?, 'SYNTHETIC')",
                        [(r[0],) for r in rows])


def _apply_changed_gap(path: Path) -> None:
    """原第二组合成变体：固定生成规则，非挑选模型答卷后的改样本。"""
    with duckdb.connect(str(path)) as con:
        con.execute("DELETE FROM fact_theme_limit_heat_daily")
        con.execute("UPDATE fact_market_daily SET advancers=NULL WHERE trade_date >= DATE '2025-03-03'")
        con.execute("UPDATE fact_market_daily SET total_amount=total_amount*1.65 WHERE trade_date BETWEEN DATE '2025-03-06' AND DATE '2025-04-02'")
        con.execute("UPDATE fact_market_daily SET limit_down=CASE WHEN trade_date BETWEEN DATE '2025-02-05' AND DATE '2025-03-04' OR trade_date BETWEEN DATE '2025-03-06' AND DATE '2025-04-02' THEN 0 ELSE 100 END")
        con.execute("UPDATE fact_limit_advance_daily SET boards=CASE WHEN trade_date BETWEEN DATE '2025-02-05' AND DATE '2025-03-04' OR trade_date BETWEEN DATE '2025-03-06' AND DATE '2025-04-02' THEN 8 ELSE 1 END")


@pytest.fixture
def market_db(tmp_path: Path) -> Path:
    path = tmp_path / "db" / "market_feature_store.duckdb"
    path.parent.mkdir()
    _make_db(path)
    return path


def _items(db: Path, question: str = QUESTION):
    return asof_prefetch.collect_prefetch_items(
        question=question, question_type="comparison_analog", subject="A股市场",
        as_of=CUTOFF, market_db_path=db,
    )


def test_prefetch_supplies_lens_and_retains_forward_facts(market_db):
    items = _items(market_db)
    lens = next((x for x in items if "多维对照镜头" in x.title), None)
    assert lens is not None, "不能只新增独立 CLI，真实预取必须带镜头"
    assert "low_contribution_groups" in lens.detail
    assert "contribution_band" in lens.detail
    assert "trade_date_only" in lens.detail
    assert "fact_market_daily.total_amount" in lens.detail
    assert "theme_net_flow" in lens.detail and "suspended" in lens.detail
    assert "教学" in lens.detail and "未接入" in lens.detail
    assert "checkpoints_registered" in lens.detail  # 无用户态输入须显式缺失
    assert "不可嫁接" in lens.detail  # 两套候选并非一一对应
    assert lens.source_date == CUTOFF.isoformat()
    assert any("后续5交易日" in x.detail for x in items)
    assert "2025-05-" not in lens.detail


def test_lens_failure_is_local_gap_not_loss_of_d10(market_db, monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("private/path/should-not-leak")

    monkeypatch.setattr(river_lens, "lens_from_db", fail)
    items = _items(market_db)
    lens = next((x for x in items if "多维对照镜头" in x.title), None)
    assert lens is not None and "gap" in lens.detail
    assert "private/path" not in lens.detail
    assert any("后续5交易日" in x.detail for x in items)


def test_missing_db_yields_two_explicit_gaps_and_never_creates_db(tmp_path):
    db = tmp_path / "missing.duckdb"
    items = _items(db)
    assert not db.exists()
    assert any("historical_analogs" in x.detail for x in items)
    assert any("river_lens" in x.detail and "gap" in x.detail for x in items)


def test_unrelated_question_does_not_read_lens(tmp_path, monkeypatch):
    def fail(**kwargs):
        pytest.fail("普通快查不应启动历史镜头")

    monkeypatch.setattr(river_lens, "lens_from_db", fail)
    assert not any("镜头" in x.title for x in _items(tmp_path / "absent", "某公司收盘价多少"))


def test_lens_carries_fit_scope_and_upstream_pit_without_upgrading(market_db):
    result = river_lens.lens_from_db(
        db_path=str(market_db), knowledge_cutoff=CUTOFF.isoformat(), window=20,
    )
    payload = result.to_dict()
    assert payload["current_window"][1] == CUTOFF.isoformat()
    assert payload["standardization_window"][1] == CUTOFF.isoformat()
    assert payload["upstream_pit_counts"]["trade_date_only"] > 0
    assert payload["feature_sources"]["total_amount"] == "fact_market_daily.total_amount；当日原值"
    assert "theme_net_flow" in payload["excluded_features"]
    assert "完整历史版本" in river_lens.lens_block(result)
    assert "非逐日可知" in river_lens.lens_block(result)


def test_unknown_pit_does_not_become_strict(monkeypatch):
    daily = [
        {"trade_date": (date(2025, 1, 1) + timedelta(days=i)).isoformat(),
         **{f: (i % 7 + i / 10) for f in river_window.COMPARABLE_FEATURE_NAMES}}
        for i in range(60)
    ]
    monkeypatch.setattr(river_window, "build_daily_vectors", lambda **kw: daily)
    result = river_lens.lens_from_db(knowledge_cutoff=CUTOFF.isoformat())
    assert result.to_dict()["upstream_pit_counts"] == {"unknown": 60}
    assert "未核完整历史版本" in river_lens.lens_block(result)


def test_changing_future_rows_cannot_change_historical_lens(market_db):
    before = river_lens.lens_from_db(db_path=str(market_db), knowledge_cutoff=CUTOFF.isoformat()).to_dict()
    with duckdb.connect(str(market_db)) as con:
        con.execute("UPDATE fact_market_daily SET total_amount=1e12 WHERE trade_date > ?", [CUTOFF])
    after = river_lens.lens_from_db(db_path=str(market_db), knowledge_cutoff=CUTOFF.isoformat()).to_dict()
    assert before == after


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question=QUESTION, user_goal="比较多维历史结构", question_type="comparison_analog",
        subject="A股市场", subject_kind="market_pattern", market_scope="A股",
        timeframe=CUTOFF.isoformat(), required_outputs=("direct_assessment", "historical_analogs"),
        assumptions=(), ambiguities=(), clarification_question=None,
        evidence_policy="structured_market_data", confidence=1.0,
    )


def test_episode_registry_and_model_message_receive_same_hashed_lens(market_db, tmp_path):
    frame = _frame()
    context = build_episode_context(frame, task_id="synthetic-river", capabilities=("market_data",),
                                    timeout=30, today=CUTOFF.isoformat())
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=tmp_path, knowledge_wiki=tmp_path / "wiki",
    )
    lens = next((x for x in registry.opening_prefetch if "多维对照镜头" in x.title), None)
    assert lens is not None
    assert lens.content_hash and lens.source_date == CUTOFF.isoformat()
    from intelligence.runtime.agent_episode import _EpisodeLedger, _EpisodeToolAccumulator, _seed_opening_prefetch
    from intelligence.services.evidence_ledger import EvidenceLedger

    messages = []
    accumulator = _EpisodeToolAccumulator(
        messages=messages, ledger=_EpisodeLedger(frame),
        evidence_ledger=EvidenceLedger(information_cutoff=CUTOFF),
    )
    _seed_opening_prefetch(accumulator, messages, registry)
    assert lens.content_hash in accumulator.evidence_hashes
    message = "\n".join(x.content for x in messages)
    assert lens.detail in message
    assert "[E" in message and "low_contribution_groups" in message


def test_episode_without_market_permission_does_not_prefetch_lens(market_db, tmp_path, monkeypatch):
    def fail(**kwargs):
        pytest.fail("未获 market_data 许可不能先查再丢弃")

    frame = _frame()
    context = build_episode_context(frame, task_id="no-market", capabilities=("market_data",),
                                    timeout=30, today=CUTOFF.isoformat())
    context = replace(context, contract=replace(
        context.contract, allowed_capabilities=(),
        evidence_plan=replace(context.contract.evidence_plan, requirements=()),
    ))
    monkeypatch.setattr(river_lens, "lens_from_db", fail)
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=tmp_path, knowledge_wiki=tmp_path / "wiki",
    )
    assert not any("镜头" in x.title for x in registry.opening_prefetch)


@pytest.mark.parametrize("snapshot", [None, "2025-05-01", "2025-04-01"])
def test_episode_query_bound_uses_earlier_cutoff_and_snapshot(market_db, snapshot):
    from intelligence.services.research_contract import InformationCutoff

    frame = _frame()
    context = build_episode_context(
        frame, task_id="earlier-bound", capabilities=("market_data",), timeout=30,
        today="2025-05-01", information_cutoff=InformationCutoff(CUTOFF, "requested"),
    )
    context = replace(context, latest_data_date=snapshot)
    evidence = episode_tools._opening_prefetch_evidence(frame, context, market_db)
    lens = next(x for x in evidence if "多维对照镜头" in x.title)
    expected = min(snapshot, CUTOFF.isoformat()) if snapshot else CUTOFF.isoformat()
    assert lens.source_date == expected
    assert f"knowledge_cutoff={expected}" in lens.detail
    assert "2025-05-" not in lens.detail


def test_expired_episode_does_not_start_lens(market_db, monkeypatch):
    from intelligence.services.research_contract import ResearchDeadline

    def fail(**kwargs):
        pytest.fail("预算已耗尽不能启动历史镜头")

    frame = _frame()
    context = build_episode_context(frame, task_id="expired", capabilities=("market_data",), timeout=30)
    context = replace(context, deadline=ResearchDeadline.from_timeout(0))
    monkeypatch.setattr(river_lens, "lens_from_db", fail)
    evidence = episode_tools._opening_prefetch_evidence(frame, context, market_db)
    assert not any("镜头" in x.title for x in evidence)


def _offline_ask(market_db, tmp_path, monkeypatch, *, options_date=None, enabled=("D10",)):
    from intelligence.services import ask, llm_refine

    def no_network(*args, **kwargs):
        pytest.fail("离线接线验收不调用模型")

    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(market_db))
    monkeypatch.setattr(llm_refine, "detect_provider", lambda **kw: None)
    monkeypatch.setattr(llm_refine, "synthesize_messages", no_network)
    monkeypatch.setattr(ask, "synthesize_prepared_answer", no_network)
    return ask.answer_query(ask.AskOptions(
        query=QUESTION, date=options_date, market_db_path=market_db,
        exports_dir=tmp_path / "exports", kb_wiki=tmp_path / "wiki", user="synthetic-river",
        use_modules=False, use_wiki_rag=False, use_entity_anchor=False, use_llm=False,
        enabled_providers=enabled, compose=True, synthesize=False, compose_revise_on_warn=False,
    ))


@pytest.mark.parametrize("options_date", [None, "2025-04-01"])
def test_ask_answer_query_delivers_d10_lens_to_prepared_model_input(
    market_db, tmp_path, monkeypatch, options_date,
):
    result = _offline_ask(market_db, tmp_path, monkeypatch, options_date=options_date)
    expected = options_date or CUTOFF.isoformat()
    messages = result.prepared_synthesis_messages or []
    prompt = "\n".join(x["content"] for x in messages)
    assert "多维对照镜头" in prompt
    assert f"knowledge_cutoff={expected}" in prompt
    assert "trade_date_only" in prompt and "不可嫁接" in prompt
    assert "fact_market_daily.total_amount" in prompt
    assert "后续5交易日" in prompt
    assert result.trade_date == expected
    assert any(c.tag == "D10" for c in result.citations)
    from intelligence.services import answer_model

    claim = next(c for c in result.answer_spec.candidate_facts if c.claim_id == "data:D10:context")
    assert claim.status == answer_model.ClaimStatus.INFERRED
    assert "2025-05-" not in claim.text  # 只查事实块；未来复核日不是行情泄漏
    assert claim.text in prompt
    assert not any(c.claim_id == claim.claim_id for c in result.answer_spec.verified_facts)
    registry = answer_model.grounded_claim_registry_block(
        result.answer_spec, query=QUESTION, max_chars=12_000,
        required_claim_ids=("data:D10:context",),
    )
    assert '"claim_id": "data:D10:context"' in registry
    assert "逐维贡献" in registry and "fact_market_daily.total_amount" in registry
    assert "trade_date_only" in registry and "不可嫁接" in registry


def test_ask_disabled_d10_does_not_read_lens(market_db, tmp_path, monkeypatch):
    def fail(**kwargs):
        pytest.fail("D10 被禁用时不能读取镜头")

    monkeypatch.setattr(river_lens, "lens_from_db", fail)
    result = _offline_ask(market_db, tmp_path, monkeypatch, enabled=())
    assert not any(c.tag == "D10" for c in result.citations)


def test_lens_text_preserves_per_dimension_values_and_candidate_gaps():
    daily = [
        {"trade_date": f"2025-01-{i + 1:02d}", "a": i, "b": i if i >= 10 else None}
        for i in range(20)
    ]
    result = river_lens.build_lens(
        daily, ("a", "b"), current=("2025-01-11", "2025-01-20"),
        candidates=[("合成历史窗", "2025-01-01", "2025-01-10")],
    )
    block = river_lens.lens_block(result)
    import json

    payload = json.loads(block.split("```json\n")[1].split("\n```")[0])
    assert payload == result.model_payload()
    table = payload["candidates"]
    candidate = dict(zip(table["columns"], next(iter(table["windows"].values())), strict=True))
    assert candidate["only_current"] == ["b"]
    assert (candidate["shared_dims"], candidate["active_dims"]) == (1, 2)
    assert "逐维贡献" in block
    assert len(payload["signatures"]["windows"]["current"]) == 2
    assert "合成历史窗" in block


def test_history_pair_resolves_default_db_once(market_db, monkeypatch):
    from intelligence.services.market_history_context import market_history_blocks

    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(market_db))
    blocks = market_history_blocks(None, as_of=CUTOFF)
    assert "后续5交易日" in blocks[0].detail
    assert "逐维贡献" in blocks[1].detail


def test_deadline_expiring_during_d10_does_not_start_lens(market_db, monkeypatch):
    from intelligence.services import market_regime_analogs, research_contract
    from intelligence.services.market_history_context import market_history_blocks

    clock = [1.0]
    monkeypatch.setattr(research_contract.time, "monotonic", lambda: clock[0])
    deadline = research_contract.ResearchDeadline(expires_at=2.0)

    def facts(*args, **kwargs):
        clock[0] = 3.0
        return "合成 D10 后续事实"

    def forbidden(**kwargs):
        pytest.fail("D10 用尽父预算后不可再起镜头")

    monkeypatch.setattr(market_regime_analogs, "regime_block_for_llm", facts)
    monkeypatch.setattr(river_lens, "lens_from_db", forbidden)
    blocks = market_history_blocks(market_db, as_of=CUTOFF, deadline=deadline)
    assert "合成 D10 后续事实" in blocks[0].detail
    assert "river_lens gap" in blocks[1].detail and "预算" in blocks[1].detail


@pytest.mark.parametrize("scope", ["material_only", "local_only"])
def test_restricted_material_scope_skips_history_before_reading(market_db, monkeypatch, scope):
    from intelligence.services.material_contract import MaterialContract

    def forbidden(*args, **kwargs):
        pytest.fail("受限材料任务不得先自动预取再丢弃")

    frame = replace(_frame(), material_contract=MaterialContract(
        classification="constraint_confirmed", authenticity="real", data_scope=scope,
    ))
    context = build_episode_context(frame, task_id=f"restricted-{scope}", timeout=30)
    monkeypatch.setattr(asof_prefetch, "collect_prefetch_items", forbidden)
    assert episode_tools._opening_prefetch_evidence(frame, context, market_db) == ()
    assert episode_tools._asof_prefetch_text(frame, context, market_db) == ""


@pytest.mark.parametrize("grounded", [False, True])
@pytest.mark.parametrize("fact_repeat", [None, 12, 100])
def test_ask_mocked_provider_receives_lens_without_external_call(market_db, tmp_path, monkeypatch, grounded, fact_repeat):
    from intelligence.services import answer_model, ask_synthesis, llm_refine
    from intelligence.services.ask_types import AskOptions, PreparedAnswer

    result = _offline_ask(market_db, tmp_path, monkeypatch)
    if fact_repeat is not None:
        result.answer_spec = replace(result.answer_spec, verified_facts=tuple(
            answer_model.Claim(
                claim_id=f"synthetic:{i}", text="合成附加行情资料。" * fact_repeat,
                claim_type="market_data", theme="合成市场", status=answer_model.ClaimStatus.VERIFIED,
                evidence_tier="market_data", evidence_ids=("D1",),
            ) for i in range(40)
        ))
    captured = []

    def capture(messages, **kwargs):
        captured.append(messages)
        return None, "offline synthetic sink; no provider invoked"

    monkeypatch.setattr(llm_refine, "detect_provider", lambda *a, **kw: None)
    monkeypatch.setattr(llm_refine, "synthesize_messages", capture)
    monkeypatch.setattr(llm_refine, "synthesize_messages_stream", capture)
    ask_synthesis.synthesize_prepared_answer(PreparedAnswer(
        options=AskOptions(query=QUESTION, compose=True, grounded_presenter=grounded,
                           daily_agent_grounded_presenter=grounded, shadow_grounded_composer=False),
        result=result,
    ))
    if grounded and fact_repeat == 100:
        # Joint admission is stricter than D10-only delivery: even one complete
        # fact cannot fit. Keep the context intact and do not call a provider.
        assert captured == []
        assert result.grounded_composer_shadow.failure_reason == "required_context_exceeds_registry_budget"
        assert result.grounded_fallback_used
        return
    assert captured
    prompt = "\n".join(x["content"] for x in captured[0])
    assert "多维对照镜头" in prompt and "逐维贡献" in prompt
    assert "不可嫁接" in prompt and "trade_date_only" in prompt
    assert "fact_market_daily.total_amount" in prompt


def test_d10_only_can_enter_grounded_synthesis_without_promotion(market_db, tmp_path, monkeypatch):
    from intelligence.services import answer_model, ask_synthesis, llm_refine
    from intelligence.services.ask_types import AskOptions, PreparedAnswer

    result = _offline_ask(market_db, tmp_path, monkeypatch)
    context = next(c for c in result.answer_spec.candidate_facts if c.claim_id == "data:D10:context")
    result.answer_spec = ask_synthesis._build_answer_spec_for_result(
        result=result, research_spec=result.answer_spec.research_spec,
        structured_claims=[context], citations=[c for c in result.citations if c.tag == "D10"],
        conclusion_lines=[], company_candidates=[], counter_lines=[], gap_lines=[],
        trigger_lines=[], follow_ups=[],
    )
    captured = []

    def capture(messages, **kwargs):
        captured.append(messages)
        return None, "offline synthetic sink"

    monkeypatch.setattr(llm_refine, "synthesize_messages", capture)
    ask_synthesis.synthesize_prepared_answer(PreparedAnswer(
        options=AskOptions(query=QUESTION, compose=True, grounded_presenter=True,
                           daily_agent_grounded_presenter=True), result=result,
    ))
    assert captured, result.grounded_composer_shadow
    prompt = "\n".join(m["content"] for m in captured[0])
    assert "逐维贡献" in prompt and '"claim_type": "inference"' in prompt
    assert result.answer_spec.verified_facts == ()
    assert context.status == answer_model.ClaimStatus.INFERRED


@pytest.mark.parametrize("empty", ["signature", "candidates"])
def test_empty_lens_preserves_sources_and_pit_with_gap(market_db, monkeypatch, empty):
    from intelligence.services.market_history_context import market_history_blocks

    lens = river_lens.lens_from_db(db_path=market_db, knowledge_cutoff=CUTOFF.isoformat())
    if empty == "candidates":
        lens.candidates = []
    else:
        lens.current = replace(lens.current, stats={})
    monkeypatch.setattr(river_lens, "lens_from_db", lambda **kw: lens)
    block = market_history_blocks(market_db, as_of=CUTOFF)[1].detail
    assert "river_lens gap" in block
    assert "trade_date_only" in block and "fact_market_daily.total_amount" in block


def test_episode_first_model_request_receives_full_lens(market_db, tmp_path):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode

    class CapturedInput(BaseException):
        """Stop at the real model boundary; do not simulate a financial answer."""

    class OfflineSink:
        calls = []

        def complete(self, *, messages, tools, timeout):
            self.calls.append(messages)
            raise CapturedInput()

    frame = _frame()
    context = build_episode_context(frame, task_id="first-river-request", capabilities=("market_data",),
                                    timeout=30, today=CUTOFF.isoformat())
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=tmp_path, knowledge_wiki=tmp_path / "wiki",
    )
    lens = next(x for x in registry.opening_prefetch if "多维对照镜头" in x.title)
    sink = OfflineSink()
    with pytest.raises(CapturedInput):
        ContinuousAgentEpisode(sink).run(task_frame=frame, context=context, registry=registry)
    assert len(sink.calls) == 1
    assert lens.detail in "\n".join(m["content"] for m in sink.calls[0])


def test_required_registry_context_is_atomic_and_budgeted(market_db, tmp_path, monkeypatch):
    import json
    from intelligence.services import answer_model

    result = _offline_ask(market_db, tmp_path, monkeypatch)
    spec = result.answer_spec
    required = ("data:D10:context",)
    full = answer_model.grounded_claim_registry_block(spec)
    line = next(line for line in full.splitlines() if json.loads(line)["claim_id"] == required[0])
    budget = len(line)
    text = answer_model.grounded_claim_registry_block(spec, max_chars=budget, required_claim_ids=required)
    assert text == line and len(text) <= budget
    with pytest.raises(ValueError, match="exceed budget"):
        answer_model.grounded_claim_registry_block(spec, max_chars=budget - 1, required_claim_ids=required)
    with pytest.raises(ValueError, match="unavailable"):
        answer_model.grounded_claim_registry_block(spec, max_chars=budget, required_claim_ids=("absent",))


def test_oversized_context_fails_closed_before_model_call(market_db, tmp_path, monkeypatch):
    from intelligence.services import ask_synthesis, llm_refine
    from intelligence.services.ask_types import AskOptions, PreparedAnswer

    result = _offline_ask(market_db, tmp_path, monkeypatch)
    result.answer_spec = replace(result.answer_spec, candidate_facts=tuple(
        replace(c, text=c.text * 10) if c.claim_id == "data:D10:context" else c
        for c in result.answer_spec.candidate_facts
    ))

    def forbidden(*args, **kwargs):
        pytest.fail("共同限制装不下时不能送残表到模型")

    monkeypatch.setattr(llm_refine, "synthesize_messages", forbidden)
    monkeypatch.setattr(llm_refine, "synthesize_messages_stream", forbidden)
    ask_synthesis.synthesize_prepared_answer(PreparedAnswer(
        options=AskOptions(query=QUESTION, compose=True, grounded_presenter=True,
                           daily_agent_grounded_presenter=True), result=result,
    ))
    assert result.grounded_composer_shadow.failure_reason == "required_context_exceeds_registry_budget"
    assert result.grounded_fallback_used


@pytest.mark.parametrize("oversized", [False, True])
@pytest.mark.parametrize("fact_repeat", [12, 100])
def test_fulfillment_repair_keeps_full_lens_or_refuses_request(
    market_db, tmp_path, monkeypatch, oversized, fact_repeat,
):
    import json

    from intelligence.services import answer_model, ask_synthesis, llm_refine, task_fulfillment
    from intelligence.services.research_contract import RequiredOutput

    result = _offline_ask(market_db, tmp_path, monkeypatch)
    spec = result.answer_spec
    if oversized:
        spec = replace(spec, candidate_facts=tuple(
            replace(c, text=c.text * 10) if c.claim_id == "data:D10:context" else c
            for c in spec.candidate_facts
        ))
    # 长资料会挤满旧版 registry；补写须走真实的预算逻辑，而不是 registry 替身。
    spec = replace(spec, verified_facts=tuple(
        answer_model.Claim(
            claim_id=f"synthetic:{i}", text="合成附加行情资料。" * fact_repeat,
            claim_type="market_data", theme="合成市场", status=answer_model.ClaimStatus.VERIFIED,
            evidence_tier="market_data", evidence_ids=("D1",),
        ) for i in range(40)
    ))
    context = next(c for c in spec.candidate_facts if c.claim_id == "data:D10:context")
    captured = []
    rechecked = []

    def capture(messages, **kwargs):
        captured.append(messages)
        return llm_refine.SynthesisResult("合成补写文本", "offline", "synthetic", "stop"), ""

    def recheck(**kwargs):
        rechecked.append(kwargs)
        return task_fulfillment.FulfillmentVerdict(status="complete", items=())

    monkeypatch.setattr(llm_refine, "synthesize_messages", capture)
    monkeypatch.setattr(task_fulfillment, "evaluate_answer_spec_fulfillment", recheck)
    repaired = ask_synthesis.repair_unfulfilled_answer(
        question=QUESTION, answer_text="合成旧稿", answer_spec=spec,
        verdict=task_fulfillment.FulfillmentVerdict(
            status="missing",
            items=(task_fulfillment.FulfillmentItem(
                output_id="historical_analogs", status="missing", gap="正文尚未呈现历史比较",
            ),),
        ),
        required_outputs=(RequiredOutput("historical_analogs", "历史比较"),), timeout=30,
    )
    assert context.status == answer_model.ClaimStatus.INFERRED
    if oversized or fact_repeat == 100:
        assert repaired is None
        assert captured == [] and rechecked == []
        return
    assert repaired is not None and repaired[0] == "合成补写文本"
    assert len(captured) == len(rechecked) == 1
    admitted = answer_model.answer_spec_for_registry(spec, ask_synthesis._grounded_registry_for_synthesis(spec, QUESTION))
    assert rechecked[0]["answer_spec"] == admitted
    assert 0 < len(admitted.verified_facts) < len(spec.verified_facts)
    assert rechecked[0]["answer_text"] == "合成补写文本"
    prompt = "\n".join(m["content"] for m in captured[0])
    rows = [json.loads(line) for line in prompt.splitlines() if line.startswith('{"claim_id":')]
    row = next(row for row in rows if row["claim_id"] == context.claim_id)
    assert row["text"] == context.text
    assert row["claim_type"] == "inference"
    assert "逐维贡献" in row["text"] and "不可嫁接" in row["text"]
    assert "fact_market_daily.total_amount" in row["text"] and "trade_date_only" in row["text"]


def test_episode_passes_same_deadline_to_history_pair(market_db, monkeypatch):
    frame = _frame()
    context = build_episode_context(frame, task_id="river-deadline-propagation", timeout=30)
    deadlines = []

    def capture(*args, **kwargs):
        deadlines.append(kwargs.get("deadline"))
        return ()

    monkeypatch.setattr(asof_prefetch, "market_history_blocks", capture)
    episode_tools._opening_prefetch_evidence(frame, context, market_db)
    assert deadlines == [context.deadline]


def test_missing_schema_keeps_both_gaps_local(tmp_path):
    from intelligence.services.market_history_context import market_history_blocks

    path = tmp_path / "empty-schema.duckdb"
    duckdb.connect(str(path)).close()
    blocks = market_history_blocks(path, as_of=CUTOFF)
    assert "historical_analogs gap" in blocks[0].detail
    assert "river_lens gap" in blocks[1].detail
    assert str(path) not in "\n".join(b.detail for b in blocks)
