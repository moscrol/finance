"""工单 #53 收尾：证明坏行可逆与确认身份贯穿到记录，不只检查可读预览。"""

from __future__ import annotations

import json
from types import SimpleNamespace

import duckdb
import pytest

from intelligence import cli
from intelligence.services import observation_script as osc
from intelligence.services import personal_export


@pytest.mark.parametrize(
    "fragment",
    [
        b'{"n":"\xe7\xae',
        br'{"n":"\xe7\xae',
        '  {"n":"算'.encode() + b'\xff\\xff  \r',
        b'  {not-json}  \r',
        bytes(value for value in range(256) if value != 10),
    ],
    ids=["torn-utf8", "literal-escape", "mixed-text-and-byte", "json-whitespace", "all-non-lf-bytes"],
)
def test_bad_line_round_trips_exact_bytes_through_export(tmp_path, fragment):
    ledger = tmp_path / "observation_scripts.jsonl"
    user = SimpleNamespace(user_id="closeout", observation_scripts_path=ledger)
    original = b'{"id":"before"}\n' + fragment + b'\n{"id":"after"}\n'
    ledger.write_bytes(original)
    result = personal_export.export_ledger(user, now="2026-09-15T00:00:00Z")
    # 必须经过真实 JSON 序列化，而不是只检内存对象的预览文本。
    rows = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))["observation_scripts"]
    assert rows[0] == {"id": "before"}
    assert rows[-1] == {"id": "after"}
    assert bytes.fromhex(rows[1]["_unparsed_bytes_hex"]) == fragment
    assert result.counts["observation_scripts"] == 3
    assert ledger.read_bytes() == original


def test_literal_escape_and_torn_byte_do_not_collapse(tmp_path):
    ledger = tmp_path / "observation_scripts.jsonl"
    user = SimpleNamespace(user_id="closeout", observation_scripts_path=ledger)
    fragments = [b'{"n":"\xe7\xae', br'{"n":"\xe7\xae']
    exports = []
    for fragment in fragments:
        ledger.write_bytes(fragment)
        exports.append(personal_export.export_ledger(user, now="fixed").to_dict())
    assert fragments[0] != fragments[1]
    assert exports[0] != exports[1]


@pytest.mark.parametrize("late", [False, True], ids=["on-time", "late"])
@pytest.mark.parametrize("change", ["source_version", "conditions", "attempt"])
def test_distinct_confirmation_actions_have_distinct_record_ids(tmp_path, change, late):
    ledger = tmp_path / "observation_scripts.jsonl"
    common = dict(
        as_of="2026-09-02", scope="theme", user_id="u1", entity_ids=["990306.FP"],
        variables=["题材轨：题材所处阶段是否推进"],
        downgrade_or_abandon_conditions=["题材轨阶段标签回退或转为缺口"],
        recorded_at="2026-09-03T10:00:00+08:00" if late else "2026-09-02T18:00:00+08:00",
        status="confirmed",
    )
    options = dict(
        checkpoints_path=tmp_path / "checkpoints.jsonl",
        due="2026-09-03", user_authored=True, entrypoint="confirm_from_draft",
        source_draft_id="draft-v1", attempt_id="attempt-a",
    )
    _, first = osc.register(ledger, osc.make(**common), **options)
    if change == "source_version":
        options["source_draft_id"] = "draft-v3"
    elif change == "conditions":
        common["downgrade_or_abandon_conditions"] = ["题材轨连续无新增覆盖事件"]
    else:
        options["attempt_id"] = "attempt-b"
    _, second = osc.register(ledger, osc.make(**common), **options)
    _, retry = osc.register(ledger, osc.make(**common), **options)
    assert first["status"] == second["status"] == ("late" if late else "confirmed")
    assert second["action_event"]["action_key"] != first["action_event"]["action_key"]
    assert second["id"] != first["id"], "不同确认动作不能共享 script_id"
    assert retry == second
    events = osc.load_events(ledger)
    assert len(events) == 2
    assert len({event["script_id"] for event in events}) == 2


def test_retry_preserves_preexisting_confirmation_id(tmp_path):
    ledger = tmp_path / "observation_scripts.jsonl"
    script = osc.make(
        as_of="2026-09-02", scope="theme", entity_ids=["990306.FP"],
        variables=["题材轨：题材所处阶段是否推进"],
        downgrade_or_abandon_conditions=["题材轨阶段标签回退或转为缺口"],
        recorded_at="2026-09-03T10:00:00+08:00", status="confirmed",
    )
    options = dict(due="2026-09-03", entrypoint="manual_confirm", user_authored=True)
    _, saved = osc.register(ledger, script, **options)
    # 模拟升级前的成功行：相同动作键，但使用历史的短 id。
    saved["id"] = "os-2026-09-02-abcdef"
    ledger.write_text(json.dumps(saved) + "\n", encoding="utf-8")
    before = ledger.read_bytes()
    _, retry = osc.register(ledger, script, recorded_at="2026-09-03T10:01:00+08:00", **options)
    assert retry == saved
    assert ledger.read_bytes() == before


def test_real_cli_draft_read_and_receipt_with_local_database(tmp_path, monkeypatch, capsys):
    """真实 CLI、身份解析和 River 切片；仅在临时 DuckDB 写固定夹具。"""
    from market_feature_store import db as store_db

    database = tmp_path / "market.duckdb"
    with duckdb.connect(str(database)) as con:
        store_db.init_db(con)
        con.execute(
            "INSERT INTO fact_sector_daily_generation "
            "(trade_date, sector_ts_code, sector_name, sector_universe_snapshot_id, pct_chg, amount, "
            "updated_at) VALUES ('2026-09-02', '990306.FP', '算力租赁', 'legacy', 1.2, 100, "
            "'2026-09-02 16:00:00')"
        )
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FORESIGHT_GUIDED_READING", "on")
    common = ["--user", "closeout", "--as-of", "2026-09-02", "--db-path", str(database), "--json"]

    def invoke(action, *extra):
        assert cli.main(["observation", action, *common, *extra]) == 0
        return json.loads(capsys.readouterr().out)

    blocked = invoke("read", "--entity", "算力租赁")
    assert blocked["code"] == "E_DRAFT_REQUIRED"
    draft = invoke(
        "draft", "--entity", "990306.FP", "--variable", "题材所处阶段是否推进",
        "--abandon", "题材阶段标签回退或转为缺口", "--attempt-id", blocked["attempt_id"],
    )
    assert draft["canonical_entity_id"] == "990306.FP"
    delivered = invoke("read", "--entity", "算力租赁", "--attempt-id", draft["attempt_id"])
    assert delivered["extraction"]["code"] == "ALLOW_DRAFT"
    ledger = tmp_path / "users" / "closeout" / "observation_scripts.jsonl"
    events = osc.load_events(ledger)
    assert [e["event"] for e in events] == [osc.EVENT_DRAFT_SUBMITTED, osc.EVENT_READ_COMPLETED]
    assert events[-1]["source_draft_id"] == draft["draft_id"]
    retry = invoke("read", "--entity", "算力租赁", "--attempt-id", draft["attempt_id"])
    assert retry["event_id"] == events[-1]["event_id"]
    assert "draft" not in retry
    assert osc.load_events(ledger) == events
