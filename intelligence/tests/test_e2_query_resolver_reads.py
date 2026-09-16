"""P3e: material-only resolution skips KB/stock lexicons, including warm caches.

This is not whole-turn zero IO: static routing config/calendar rules, history,
unknown material boundaries, trusted continuation and injected resolvers remain
separate gates. All mutable data here is synthetic and lives under tmp_path.
"""
from collections import Counter
import json
from pathlib import Path
import socket

import duckdb
import pytest

from intelligence.adapters.knowledge import KnowledgeAdapter, clear_relation_cache
from intelligence.services import entity_anchor, query_resolution as qr
from intelligence.services.material_contract import compile_material_contract
from intelligence.services.query_understanding import understand_query
from intelligence.services.turn_controller import decide_turn
from intelligence.services.user_task import split_user_message


@pytest.fixture
def lexicons(tmp_path, monkeypatch):
    wiki = tmp_path / "wiki"
    relations = wiki / "relations"
    relations.mkdir(parents=True)
    (relations / "entity_exposures.json").write_text(json.dumps({"entities": {
        "甲设备": {"codes": ["300001.SZ"], "concepts": {"光模块": {}}},
        "乙设备": {"codes": ["300002.SZ"], "concepts": {"光模块": {}}},
    }}, ensure_ascii=False))
    (relations / "aliases.json").write_text(json.dumps({
        "aliases": {"光通信模块": "光模块"},
    }, ensure_ascii=False))
    db = tmp_path / "securities.duckdb"
    with duckdb.connect(str(db)) as con:
        con.execute("create table fact_stock_daily(stock_name varchar, stock_ts_code varchar)")
        con.execute("insert into fact_stock_daily values ('丙设备', '300003.SZ')")
    monkeypatch.setenv("ENTITY_ANCHOR_SECURITIES_DB", str(db))
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(db))
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance"))
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    adapter = KnowledgeAdapter(wiki_root=wiki)
    monkeypatch.setattr(qr, "KnowledgeAdapter", lambda: adapter)
    clear_relation_cache()
    entity_anchor._clear_entity_lexicon_cache()
    qr._THEME_CACHE.clear()
    attempts = Counter()
    guard = {"deny": False}

    def count(name):
        attempts[name] += 1
        if guard["deny"]:
            # OSError is intentionally swallowed by several production loaders.
            # The final counter assertions, not this exception, detect the read.
            raise PermissionError("synthetic lexicon denied: " + name)

    original_stat = Path.stat
    original_open = Path.open
    original_connect = duckdb.connect

    def stat(path, *args, **kwargs):
        if path == db or path.is_relative_to(wiki):
            count("metadata")
        return original_stat(path, *args, **kwargs)

    def open_file(path, *args, **kwargs):
        if path.is_relative_to(wiki):
            count("kb_open")
        return original_open(path, *args, **kwargs)

    def connect(database, *args, **kwargs):
        assert Path(database) == db, "only the synthetic securities DB is permitted"
        count("db_connect")
        return original_connect(database, *args, **kwargs)

    def network(*args, **kwargs):
        attempts["network"] += 1
        raise PermissionError("no network")

    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setattr(Path, "open", open_file)
    monkeypatch.setattr(duckdb, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect", network)
    monkeypatch.setattr(socket, "getaddrinfo", network)
    yield qr.QueryResolver(adapter), attempts, guard
    clear_relation_cache()
    entity_anchor._clear_entity_lexicon_cache()
    qr._THEME_CACHE.clear()


BODIES = (
    "「甲设备收入100，订单20。」\n\n1. 甲设备订单占收入多少？",
    "「300001只是材料编号，收入100。」\n\n1. 300001的订单比例是多少？",
    "「光通信模块收入100，订单20。」\n\n1. 光通信模块的订单比例是多少？",
    "「甲设备和乙设备均有订单。」\n\n1. 比较甲设备和乙设备2024年那一波的差异？",
    "「光模块收入100。」\n\n1. 复盘2024年光模块那一波的变化？",
)


@pytest.mark.parametrize("body", BODIES)
@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("deny", [False, True])
def test_material_only_never_touches_lexicons(lexicons, body, warm, deny):
    resolver, attempts, guard = lexicons
    if warm:
        resolver.resolve("光通信模块怎么看")
        resolver.resolve("丙设备怎么看")
        assert attempts["kb_open"] > 0 and attempts["db_connect"] > 0
    attempts.clear()
    guard["deny"] = deny
    query = "只依据以下材料回答。\n\n" + body
    expected = understand_query(query)
    result = resolver.resolve(query)
    assert not attempts, dict(attempts)
    assert result.anchor is None
    assert result.candidates == ()
    assert result.comparison_entities == ()  # no externally verified company list
    assert result.envelope == expected
    frame = result.envelope.task_frame
    assert frame.raw_question == query
    assert frame.material_contract.data_scope == "material_only"
    assert [q.question_id for q in frame.material_contract.questions] == ["q1"]
    assert frame.materials == expected.task_frame.materials


@pytest.mark.parametrize("prefix", ["", "不要联网。\n\n", "可以查真实数据。\n\n"])
@pytest.mark.parametrize("subject,expected", [
    ("甲设备", "甲设备"), ("丙设备", "丙设备"), ("光通信模块", "光模块"),
])
def test_allowed_queries_keep_real_synthetic_lexicon_reads(lexicons, prefix, subject, expected):
    resolver, attempts, _guard = lexicons
    result = resolver.resolve(prefix + subject + "怎么看")
    assert result.envelope.subject == expected
    assert attempts["kb_open"] > 0
    assert attempts["db_connect"] > 0
    assert attempts["network"] == 0


@pytest.mark.parametrize("query", [
    '「只依据以下材料回答。甲设备收入100。」\n\n1. 甲设备怎么看？',
    '```\n只依据以下材料回答。甲设备收入100。\n```\n\n1. 甲设备怎么看？',
    '只依据以下材料回答。\n\n可以查真实数据。\n\n甲设备怎么看？',
])
def test_only_top_level_effective_scope_blocks_reads(lexicons, query):
    resolver, attempts, _guard = lexicons
    parts = split_user_message(query)
    contract = compile_material_contract(parts.regions)
    assert contract is None or contract.data_scope == "full"
    result = resolver.resolve(query)
    assert result.anchor is not None
    assert attempts["kb_open"] > 0 and attempts["db_connect"] > 0


def test_restricted_then_full_then_restricted_does_not_poison_caches(lexicons):
    resolver, attempts, _guard = lexicons
    restricted = "只依据以下材料回答。\n\n" + BODIES[0]
    assert resolver.resolve(restricted).anchor is None
    assert not attempts
    assert resolver.resolve("甲设备怎么看").anchor.entity == "甲设备"
    assert attempts["kb_open"] > 0 and attempts["db_connect"] > 0
    attempts.clear()
    assert resolver.resolve(restricted).anchor is None
    assert not attempts


@pytest.mark.parametrize("injected", [False, True])
def test_real_controller_uses_guarded_default_or_injected_resolver(lexicons, injected):
    resolver, attempts, guard = lexicons
    guard["deny"] = True
    query = "只依据以下材料回答。\n\n" + BODIES[0]
    result = decide_turn(
        query, context="（无历史消息）", resolver=resolver if injected else None,
        llm_complete=lambda _messages: (None, None, "scripted unavailable"),
    )
    assert not attempts, dict(attempts)
    assert result.task_frame.raw_question == query
    assert result.task_frame.material_contract.data_scope == "material_only"


def test_plain_continuation_keeps_existing_reference_behavior(lexicons):
    resolver, attempts, _guard = lexicons
    result = resolver.resolve("继续看反证")
    assert result.reference_kind == "continuation"
    assert result.context_dependent
    assert result.suggested_action == "proceed"
    assert attempts["kb_open"] > 0 and attempts["db_connect"] > 0
