"""market_watch 组件包：拒收之后、开口之前的四袋与精确站立日。"""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb

from intelligence.runtime.conversation_orchestrator import TurnOrchestrator
from intelligence.services.ask import (
    _answer_market_review,
    _resolve_market_data_context,
    bind_market_watch_pack,
)
from intelligence.services.ask_types import AskOptions, AskResult
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.honesty_gates import calendar_disclosure
from intelligence.services.market_watch_pack import (
    BAG_DUAL_RED,
    BAG_LIMIT_HEAT,
    BAG_MARKET,
    merge_into_public_answer,
    run_market_watch_pack,
)
from intelligence.services.query_understanding import (
    is_market_watch_query,
    understand_query,
)
from intelligence.services.run_store import RunStore
from intelligence.services.task_frame import build_task_frame
from intelligence.workbench_skills.contracts import (
    SkillDefinition,
    SkillExecutionContext,
    SkillOutput,
    build_module_answer_contract,
)
from intelligence.workbench_skills.registry import SkillRegistry
from intelligence.workbench_skills.router import SkillRouteResult, SkillSelection


def _db(tmp_path: Path) -> Path:
    path = tmp_path / "market.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        """
        create table fact_market_daily(
          trade_date date,
          market_stage varchar,
          stage_day integer,
          total_amount double,
          amount_vs_yesterday_pct double,
          volume_state varchar,
          limit_up integer,
          limit_down integer,
          sh_index_pct_chg double
        )
        """
    )
    con.execute(
        """
        insert into fact_market_daily values
          ('2026-07-23', '反弹阶段', 3, 21949.97, -17.27, '缩量观望', 116, 2, 0.2519),
          ('2026-07-24', '反弹阶段', 4, 18000, -10, '缩量', 80, 1, 0.1),
          ('2026-08-21', '反弹阶段', 10, 30000, 5, '放量', 90, 0, 1.2)
        """
    )
    con.execute(
        """
        create table fact_mainline_theme_daily(
          trade_date date,
          theme_name varchar,
          sector_count integer,
          min_sort integer
        )
        """
    )
    con.execute(
        "insert into fact_mainline_theme_daily values "
        "('2026-07-23', '半导体', 4, 1), ('2026-07-23', 'AI', 3, 2)"
    )
    con.execute(
        """
        create table fact_sector_daily(
          trade_date date,
          sector_name varchar,
          pct_chg double,
          diff_ratio double,
          amount double
        )
        """
    )
    con.execute(
        "insert into fact_sector_daily values "
        "('2026-07-23', '电力设备', 3.1, 12.0, 600),"
        "('2026-07-23', '锂矿', 2.0, 11.0, 550),"
        "('2026-07-24', '半导体', 4.0, 20.0, 800)"
    )
    con.execute(
        """
        create table fact_theme_limit_heat_daily(
          trade_date date,
          sector_name varchar,
          limit_up_count integer,
          market_share double
        )
        """
    )
    con.execute(
        "insert into fact_theme_limit_heat_daily values "
        "('2026-07-23', '储能', 40, 0.1), ('2026-07-24', '半导体', 20, 0.2)"
    )
    con.close()
    return path


def test_a1_query_is_market_watch_c1_original_is_not() -> None:
    assert is_market_watch_query("2026-07-23 今天市场怎么样")
    assert is_market_watch_query("2026-07-25 今天市场怎么样")
    assert not is_market_watch_query("2026-07-25 市场怎么样")


def test_explicit_standing_day_does_not_fall_back_to_neighbor(tmp_path: Path) -> None:
    db = _db(tmp_path)
    pack = run_market_watch_pack(
        "2026-07-25 今天市场怎么样",
        market_db_path=db,
    )
    market = pack.bag(BAG_MARKET)
    assert market is not None
    assert market.empty
    assert market.served_date is None
    assert pack.standing_date == "2026-07-25"
    assert pack.explicit is True
    assert "18000" not in pack.render()
    assert "07-24" not in pack.render() or pack.market_daily_empty


def test_a1_lock_fields_and_four_bags(tmp_path: Path) -> None:
    db = _db(tmp_path)
    pack = run_market_watch_pack(
        "2026-07-23 今天市场怎么样",
        market_db_path=db,
    )
    assert pack.complete
    assert pack.explicit is True
    market = pack.bag(BAG_MARKET)
    assert market is not None
    assert market.served_date == "2026-07-23"
    assert market.requested_date == "2026-07-23"
    row = market.rows[0]
    assert row["total_amount"] == 21949.97
    assert row["amount_vs_yesterday_pct"] == -17.27
    assert row["limit_up"] == 116
    assert row["limit_down"] == 2
    dual = pack.bag(BAG_DUAL_RED)
    assert dual is not None and not dual.empty
    assert {row["sector_name"] for row in dual.rows} == {"电力设备", "锂矿"}
    heat = pack.bag(BAG_LIMIT_HEAT)
    assert heat is not None and not heat.empty
    assert heat.rows[0]["sector_name"] == "储能"
    rendered = pack.render()
    assert "21949.97" in rendered
    assert "电力设备" in rendered
    assert "储能" in rendered
    assert "半导体" in rendered
    assert "30000" not in rendered


def test_neighbor_day_dual_red_is_not_served_for_explicit_date(tmp_path: Path) -> None:
    db = _db(tmp_path)
    pack = run_market_watch_pack(
        "2026-07-23 今天市场怎么样",
        market_db_path=db,
    )
    dual = pack.bag(BAG_DUAL_RED)
    assert dual is not None
    assert all(row["sector_name"] != "半导体" for row in dual.rows)


def test_resolve_context_does_not_echo_missing_requested_date(tmp_path: Path) -> None:
    db = _db(tmp_path)
    trade_date, source, notice, _warnings = _resolve_market_data_context(
        None,
        db,
        requested_date="2026-07-25",
    )
    assert trade_date is None
    assert source == "requested_date_missing"
    assert notice is not None and "2026-07-25" in notice

    hit, hit_source, _, _ = _resolve_market_data_context(
        None,
        db,
        requested_date="2026-07-23",
    )
    assert hit == "2026-07-23"
    assert hit_source == "requested_date"


def test_bind_stops_on_holiday_and_reuses_compose(tmp_path: Path) -> None:
    db = _db(tmp_path)
    query = "2026-07-25 今天市场怎么样"
    frame = build_task_frame(query, understand_query(query))
    disclosure = calendar_disclosure(frame)
    assert disclosure is not None and "休市" in disclosure
    options = AskOptions(
        query="2026-07-25 今天市场怎么样",
        market_db_path=db,
        compose=True,
        synthesize=True,
    )
    bound = bind_market_watch_pack(options, frame=frame)
    pack = bound.market_watch_pack
    assert pack is not None
    assert pack.complete
    assert pack.should_stop
    assert bound.compose is False
    assert bound.synthesize is False
    assert bound.date == "2026-07-25"
    assert "休市" in pack.stop_text()
    result = AskResult(
        query=options.query,
        trade_date=None,
        matched_theme=None,
        candidate_tier=None,
        priority_score=None,
    )
    answered = _answer_market_review(bound, result)
    assert answered.answer_spec is not None
    text = answered.answer_spec.to_prompt_block()
    assert "休市" in text
    assert "18000" not in text


def test_implicit_watch_without_db_does_not_stop() -> None:
    options = AskOptions(query="今日复盘", compose=True, synthesize=True)
    bound = bind_market_watch_pack(options, frame=None)
    pack = bound.market_watch_pack
    assert pack is not None
    assert pack.explicit is False
    assert pack.should_stop is False
    assert bound.compose is True
    assert bound.supplemental_evidence == ""


def test_bind_does_not_need_owner_to_run_pack(tmp_path: Path) -> None:
    db = _db(tmp_path)
    options = AskOptions(
        query="2026-07-23 今天市场怎么样",
        market_db_path=db,
        compose=True,
    )
    bound = bind_market_watch_pack(options, frame=None)
    pack = bound.market_watch_pack
    assert pack is not None and pack.complete
    assert pack.bag(BAG_MARKET) is not None
    assert bound.date == "2026-07-23"
    assert bound.compose is True
    assert "21949.97" in bound.supplemental_evidence


def test_merge_puts_lock_cells_in_front_of_owner_prose(tmp_path: Path) -> None:
    db = _db(tmp_path)
    pack = run_market_watch_pack(
        "2026-07-23 今天市场怎么样",
        market_db_path=db,
    )
    merged = merge_into_public_answer("日报正文：市场还行，没有锁格。", pack)
    assert merged.index("21949.97") < merged.index("日报正文")
    assert "电力设备" in merged


def _prepare_watch_turn(
    tmp_path: Path, query: str
) -> tuple[ConversationStore, RunStore, str, str, str]:
    db = _db(tmp_path)
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    shutil.copy(db, db_dir / "market_feature_store.duckdb")
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run = run_store.create_run(
        query,
        "ask",
        session_id=conversation.conversation_id,
        parent_run_id=conversation.last_run_id,
    )
    conversation_store.append_message(
        conversation.conversation_id,
        "user",
        query,
        run_id=run.run_id,
    )
    assistant = conversation_store.append_message(
        conversation.conversation_id,
        "assistant",
        "",
        status="pending",
        run_id=run.run_id,
    )
    conversation_store.update_summary(
        conversation.conversation_id,
        conversation.summary,
        last_run_id=run.run_id,
    )
    return (
        conversation_store,
        run_store,
        conversation.conversation_id,
        run.run_id,
        assistant.message_id,
    )


def test_owner_daily_review_cannot_replace_pack_lock_cells(tmp_path: Path) -> None:
    query = "2026-07-23 今天市场怎么样"
    conversation_store, run_store, conversation_id, run_id, assistant_id = (
        _prepare_watch_turn(tmp_path, query)
    )

    class DailyReviewOwner:
        skill_id = "daily-review"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            del context
            modules = [
                {
                    "type": "summary",
                    "summary": "日报正文：市场还行，没有锁格。",
                    "metrics": [{"label": "涨家数", "value": "3000"}],
                    "items": [
                        {
                            "title": "观察",
                            "summary": "日报只给结构，不给锁格。",
                        }
                    ],
                }
            ]
            citations = [
                {
                    "source": "2026-07-23-daily-review.md",
                    "title": "指定日日报",
                    "evidence_layer": "canonical",
                    "as_of": "2026-07-23",
                }
            ]
            return SkillOutput(
                skill_id=self.skill_id,
                modules=modules,
                citations=citations,
                warnings=[],
                as_of="2026-07-23",
                raw_result_ref=None,
                answer_contract=build_module_answer_contract(
                    skill_id=self.skill_id,
                    title="每日复盘",
                    modules=modules,
                    citations=citations,
                    warnings=[],
                    as_of="2026-07-23",
                    retrieval_plan=("读取指定日日报",),
                    output_contract=("输出复盘结构",),
                ),
            )

    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="daily-review",
            name="每日复盘",
            description="fixture owner",
            version="1.0.0",
            triggers=("复盘",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
            role="workflow",
            can_own_answer=True,
        ),
        DailyReviewOwner(),
    )

    def forbidden_answer(options: AskOptions) -> AskResult:
        raise AssertionError(f"owner path must not call ask: {options.query}")

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden_answer,
        route_skills_fn=lambda *_args, **_kwargs: SkillRouteResult(
            (SkillSelection("daily-review", "rule", "fixture"),),
            fallback_to_ask=False,
        ),
        skill_registry=registry,
    ).run_turn(
        conversation_id=conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert "21949.97" in result.content
    assert "电力设备" in result.content
    assert "储能" in result.content
    assert "日报正文" in result.content
    assert "18000" not in result.content


def test_no_owner_still_exposes_pack_lock_cells(tmp_path: Path) -> None:
    query = "2026-07-23 今天市场怎么样"
    conversation_store, run_store, conversation_id, run_id, assistant_id = (
        _prepare_watch_turn(tmp_path, query)
    )

    def ownerless_answer(options: AskOptions) -> AskResult:
        return AskResult(
            query=options.query,
            trade_date=None,
            matched_theme=None,
            candidate_tier=None,
            priority_score=None,
            synthesis="模型残差：只解释冲突，不含锁格。",
        )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=ownerless_answer,
        route_skills_fn=lambda *_args, **_kwargs: SkillRouteResult(
            (),
            fallback_to_ask=True,
        ),
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert "21949.97" in result.content
    assert "模型残差" in result.content
    assert "18000" not in result.content
