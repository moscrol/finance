from __future__ import annotations

import json
from pathlib import Path

from intelligence.services.checkpoint_recall import recall_block_for_query
from intelligence.services.followups import FollowupState, compose_followups
from intelligence.services.stance_pack import (
    lint_public_answer,
    run_stance_pack,
    should_run_stance_pack,
)


HOLDING_QUERY = "扬杰科技我持仓，101.6 止损现在该不该减"
MAOTAI_QUERY = "茅台现在该不该买"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in records),
        encoding="utf-8",
    )


def _stock_db(tmp_path: Path, rows: list[tuple]) -> Path:
    import duckdb

    db = tmp_path / "market_feature_store.duckdb"
    con = duckdb.connect(str(db))
    try:
        con.execute(
            """
            create table fact_stock_daily (
                trade_date date,
                stock_ts_code varchar,
                stock_name varchar,
                close double,
                pct_chg double
            )
            """
        )
        con.executemany(
            "insert into fact_stock_daily values (?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        con.close()
    return db


def test_holding_target_trade_intent_runs_on_research_lane() -> None:
    assert should_run_stance_pack(
        lane="research",
        question_type="stock_deep_dive",
        query=HOLDING_QUERY,
    )
    pack = run_stance_pack(HOLDING_QUERY, standing_date="2026-08-24")
    assert set(pack.stance_kinds) >= {"holding", "target", "trade_intent"}


def test_trade_advice_runs_even_when_lane_is_wrong() -> None:
    assert should_run_stance_pack(
        lane="chat",
        question_type="trade_advice",
        query=MAOTAI_QUERY,
    )


def test_plain_market_watch_does_not_run() -> None:
    assert not should_run_stance_pack(
        lane="research",
        question_type="market_watch",
        query="今天市场怎么样",
    )


def test_same_holding_query_on_chat_without_trade_advice_does_not_run() -> None:
    assert not should_run_stance_pack(
        lane="chat",
        question_type="general_finance_qa",
        query=HOLDING_QUERY,
    )


def test_empty_checkpoints_make_prior_bag_empty(tmp_path: Path) -> None:
    pack = run_stance_pack(
        HOLDING_QUERY,
        standing_date="2026-08-24",
        users_root=tmp_path,
    )
    assert pack.prior_bag.status == "empty"
    assert pack.prior_bag.rows == ()
    assert pack.prior_bag.gap
    assert not any("用户判断" in str(row) for row in pack.prior_bag.rows)


def test_quote_bag_does_not_fall_back_to_neighbor_day(tmp_path: Path) -> None:
    db = _stock_db(
        tmp_path,
        [("2026-08-21", "300373.SZ", "扬杰科技", 99.5, 2.1)],
    )
    pack = run_stance_pack(
        HOLDING_QUERY,
        standing_date="2026-08-24",
        market_db_path=db,
        capabilities=("market_data",),
        subject="扬杰科技",
    )
    assert pack.quote_bag.status == "empty"
    assert pack.quote_bag.served_date is None
    assert pack.quote_bag.rows == ()
    assert "邻日" in pack.quote_bag.gap


def test_lint_drops_bag_external_price() -> None:
    pack = run_stance_pack(HOLDING_QUERY, standing_date="2026-08-24")
    cleaned, flags = lint_public_answer(
        "现价 88.8 元已经跌破止损，可以按条件减仓。",
        pack,
        query=HOLDING_QUERY,
    )
    assert "bag_external_price" in flags
    assert "88.8" not in cleaned


def test_lint_flags_prior_promoted_to_fact() -> None:
    pack = run_stance_pack(HOLDING_QUERY, standing_date="2026-08-24")
    _cleaned, flags = lint_public_answer(
        "市场已经确认你上次的判断，短线逻辑成立。",
        pack,
        query=HOLDING_QUERY,
    )
    assert "prior_promoted_to_fact" in flags


def test_same_bind_chip_keeps_subject_and_standing_date() -> None:
    state = FollowupState(
        subject="扬杰科技",
        question=HOLDING_QUERY,
        question_kind="stock",
        same_bind=True,
        standing_date="2026-08-24",
        question_type="trade_advice",
    )
    result = compose_followups(state)
    chip = result.followups[0]
    assert chip.type == "continue"
    assert len(chip.label) <= 20
    assert "扬杰科技" in chip.full_prompt
    assert "2026-08-24" in chip.full_prompt
    assert 2 <= len(result.followups) <= 4


def test_dropping_quote_capability_does_not_shrink_research_caps(tmp_path: Path) -> None:
    db = _stock_db(
        tmp_path,
        [("2026-08-24", "300373.SZ", "扬杰科技", 12.5, -1.2)],
    )
    capabilities = ("kb_search", "graph_lookup", "evidence_lookup", "news_search")
    pack = run_stance_pack(
        HOLDING_QUERY,
        standing_date="2026-08-24",
        market_db_path=db,
        capabilities=capabilities,
        subject="扬杰科技",
    )
    assert pack.quote_bag.status == "empty"
    assert "stance_quote_capability_absent" in pack.quote_bag.gap
    assert capabilities == (
        "kb_search",
        "graph_lookup",
        "evidence_lookup",
        "news_search",
    )


def test_dropping_memory_lookup_still_fills_prior_from_v_loader(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "checkpoints.jsonl",
        [
            {
                "id": "c-yangjie",
                "claim": "扬杰科技止损后观察回流",
                "due": "2026-09-01",
                "category": "交易纪律",
                "stocks": ["扬杰科技"],
                "ts": "2026-08-01T00:00:00Z",
            }
        ],
    )
    _write_jsonl(
        tmp_path / "verdicts.jsonl",
        [
            {
                "id": "c-yangjie",
                "verdict": "partial",
                "reason": "尚未触发",
                "checked_at": "2026-08-10T00:00:00Z",
            }
        ],
    )
    capabilities = ("market_data", "kb_search")
    pack = run_stance_pack(
        HOLDING_QUERY,
        standing_date="2026-08-24",
        users_root=tmp_path,
        capabilities=capabilities,
        subject="扬杰科技",
    )
    assert "memory_lookup" not in capabilities
    assert pack.prior_bag.status == "hit"
    assert pack.prior_bag.rows
    assert pack.prior_bag.rows[0]["claim"] == "扬杰科技止损后观察回流"


def test_ask_v_projection_does_not_reload_when_pack_exists(tmp_path: Path, monkeypatch) -> None:
    from intelligence.services.ask import v_block_for_ask
    from intelligence.services.ask_types import AskOptions

    _write_jsonl(
        tmp_path / "checkpoints.jsonl",
        [
            {
                "id": "c1",
                "claim": "扬杰科技止损后观察回流",
                "due": "2026-09-01",
                "category": "交易纪律",
                "stocks": ["扬杰科技"],
                "ts": "2026-08-01T00:00:00Z",
            }
        ],
    )
    pack = run_stance_pack(
        HOLDING_QUERY,
        standing_date="2026-08-24",
        users_root=tmp_path,
        subject="扬杰科技",
    )
    calls = {"n": 0}

    def _forbidden(*_args, **_kwargs):
        calls["n"] += 1
        raise AssertionError("pack 已存在时禁止 recall_block_for_query 自查")

    monkeypatch.setattr(
        "intelligence.services.checkpoint_recall.recall_block_for_query",
        _forbidden,
    )
    options = AskOptions(query=HOLDING_QUERY, user="alice", stance_pack=pack)
    block = v_block_for_ask(options)
    assert calls["n"] == 0
    assert "扬杰科技止损后观察回流" in block
    assert recall_block_for_query(
        HOLDING_QUERY,
        entity="扬杰科技",
        users_root=tmp_path,
    )
