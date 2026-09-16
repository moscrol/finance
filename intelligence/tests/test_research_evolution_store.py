"""单 writer 的四条承诺：顺序、身份、不覆盖、完整（spec 06 §5）。

原子命名不等于原子发布，所以这里测的是**跨进程**行为：真的起子进程去抢同一把锁、
真的把台账写坏、真的重启后重建，而不是在一个线程里调两次函数。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from intelligence.services.research_evolution.contracts import ApiError, StoreCorrupt
from intelligence.services.research_evolution.store import EvolutionStore

OWNER = "default"
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def store(tmp_path: Path) -> EvolutionStore:
    return EvolutionStore(tmp_path / "research_evolution", OWNER)


def _binding(binding_id: str = "bind-1", *, hashes: dict[str, str | None] | None = None) -> dict:
    return {
        "schema_version": "judgment-maintenance-binding/v1",
        "binding_id": binding_id,
        "binding_version": 1,
        "owner_user_id": OWNER,
        "object_ref": {"kind": "judgment", "id": "j1", "namespace": "judgments", "version_or_hash": "content_sha256:" + "0" * 64, "ref": "judgments.jsonl:j1", "scope": {}},
        "baseline_evidence_refs": ["fact_market_daily:2026-09-01"],
        "baseline_source_hashes": hashes or {"fact_market_daily:2026-09-01": "h1"},
        "baseline_cutoff": "2026-09-14",
        "created_at": "2026-09-14T16:00:00+08:00",
        "binding_origin": "user_confirmed",
        "conditions": [],
    }


# --------------------------------------------------------------------------- #
# 身份与不覆盖
# --------------------------------------------------------------------------- #
def test_same_key_same_content_appends_once(store: EvolutionStore) -> None:
    source = {"entity": "制冷剂", "as_of": "2026-09-01", "evidence_versions": []}
    first, created_a = store.append_binding(_binding(), created_at="2026-09-14T16:00:00+08:00", source=source)
    second, created_b = store.append_binding(_binding(), created_at="2026-09-14T16:00:00+08:00", source=source)
    assert created_a is True and created_b is False
    assert first["content_digest"] == second["content_digest"]
    assert len(store.list_bindings()) == 1


def test_same_key_different_content_is_refused(store: EvolutionStore) -> None:
    source = {"entity": "制冷剂", "as_of": "2026-09-01", "evidence_versions": []}
    store.append_binding(_binding(), created_at="2026-09-14T16:00:00+08:00", source=source)
    with pytest.raises(ApiError) as exc:
        store.append_binding(
            _binding(hashes={"fact_market_daily:2026-09-01": "h2"}),
            created_at="2026-09-14T16:00:00+08:00",
            source=source,
        )
    assert exc.value.code == "idempotency_payload_mismatch"
    assert exc.value.http_status == 409
    assert len(store.list_bindings()) == 1


def test_immutable_publish_refuses_to_overwrite_but_replays_identical_content(store: EvolutionStore) -> None:
    value = {"policy": {"policy_id": "p1"}, "provenance": "synthetic"}
    stored, created = store.publish_immutable("registrations", "diagnostics_policy", value)
    again, created_again = store.publish_immutable("registrations", "diagnostics_policy", value)
    assert created is True and created_again is False
    assert stored == again
    with pytest.raises(ApiError) as exc:
        store.publish_immutable("registrations", "diagnostics_policy", {"policy": {"policy_id": "p2"}})
    assert exc.value.code == "idempotency_payload_mismatch"
    assert store.read_immutable("registrations", "diagnostics_policy")["policy"]["policy_id"] == "p1"


@pytest.mark.parametrize("content_id", ["../escape", "a/b", ".", "..", ".hidden", ""])
def test_immutable_ids_cannot_escape_the_owner_directory(store: EvolutionStore, content_id: str) -> None:
    with pytest.raises(ApiError) as exc:
        store.publish_immutable("registrations", content_id, {"x": 1})
    assert exc.value.code == "invalid_request"


def test_reads_are_scoped_to_the_owner(tmp_path: Path) -> None:
    mine = EvolutionStore(tmp_path / "re", OWNER)
    mine.append_binding(_binding(), created_at="2026-09-14T16:00:00+08:00", source={})
    # 同一个目录里混进另一个 owner 的行（模拟误写 / 迁移遗留）。
    with mine.bindings_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"binding_id": "bind-x", "owner_user_id": "alice", "binding": {}}) + "\n")
    assert [b["binding_id"] for b in mine.list_bindings()] == ["bind-1"]
    assert [b["binding_id"] for b in EvolutionStore(tmp_path / "re", "alice").list_bindings()] == ["bind-x"]


# --------------------------------------------------------------------------- #
# 完整性：坏行拒绝继续写，而不是静默跳过
# --------------------------------------------------------------------------- #
def test_a_corrupt_line_stops_business_writes_with_a_visible_error(store: EvolutionStore) -> None:
    store.append_binding(_binding(), created_at="2026-09-14T16:00:00+08:00", source={})
    with store.bindings_path.open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")
    with pytest.raises(StoreCorrupt) as exc:
        store.list_bindings()
    assert exc.value.code == "store_corrupt"
    assert exc.value.detail["line"] == 2
    with pytest.raises(StoreCorrupt):
        store.append_binding(_binding("bind-2"), created_at="2026-09-14T16:00:00+08:00", source={})


def test_a_corrupt_registration_is_visible_rather_than_treated_as_absent(store: EvolutionStore) -> None:
    store.publish_immutable("registrations", "exercise_pack", {"pack": {"cases": []}})
    path = store.root / "registrations" / "exercise_pack.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(StoreCorrupt):
        store.read_immutable("registrations", "exercise_pack")


# --------------------------------------------------------------------------- #
# 顺序与并发：真的开进程去抢
# --------------------------------------------------------------------------- #
_WORKER = textwrap.dedent(
    """
    import json, sys
    from intelligence.services.research_evolution.contracts import ApiError
    from intelligence.services.research_evolution.store import EvolutionStore

    root, owner, key, payload = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    store = EvolutionStore(root, owner)
    # 事件身份由**载荷**决定，不由进程决定：同一个幂等键 + 同一份载荷 = 同一条事件
    # （01 的 ``event_from_command`` 也是这么算 event_id 的）。用进程序号当 id 会把
    # 「重复提交」伪装成「载荷不同」，那样测出来的并发行为是假的。
    event = {"event_id": "e-" + payload, "item_id": "item-1", "owner_user_id": owner,
             "kind": "claimed", "at": "2026-09-14T16:00:00+08:00",
             "expected_management_revision": 0, "command_id": "same-key",
             "payload_digest": payload, "payload": {}}
    try:
        with store.transaction() as txn:
            _, created = txn.append_action(event, idempotency_key="same-key", action="claim",
                                           payload_digest=payload, recorded_at="2026-09-14T16:00:00+08:00",
                                           conversation_id="c1", result={"digest": payload})
        print(json.dumps({"ok": True, "created": created}))
    except ApiError as exc:
        print(json.dumps({"ok": False, "code": exc.code}))
    """
)


def _run_workers(root: Path, payloads: list[str]) -> list[dict]:
    script = root.parent / "worker.py"
    script.write_text(_WORKER, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    procs = [
        subprocess.Popen(
            [sys.executable, str(script), str(root), OWNER, f"w{i}", payload],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        for i, payload in enumerate(payloads)
    ]
    out = []
    for proc in procs:
        stdout, stderr = proc.communicate(timeout=120)
        assert proc.returncode == 0, stderr
        out.append(json.loads(stdout.strip().splitlines()[-1]))
    return out


def test_concurrent_processes_on_one_key_produce_exactly_one_record(tmp_path: Path) -> None:
    root = tmp_path / "research_evolution"
    results = _run_workers(root, ["same-digest"] * 4)
    created = [r for r in results if r.get("created")]
    assert len(created) == 1, results
    assert all(r["ok"] for r in results)
    assert len(EvolutionStore(root, OWNER).list_action_records()) == 1


def test_concurrent_processes_with_different_payloads_keep_the_first_and_refuse_the_rest(tmp_path: Path) -> None:
    root = tmp_path / "research_evolution"
    results = _run_workers(root, ["digest-a", "digest-b", "digest-c"])
    created = [r for r in results if r.get("created")]
    refused = [r for r in results if not r["ok"]]
    assert len(created) == 1, results
    assert len(refused) == 2, results
    assert {r["code"] for r in refused} == {"idempotency_payload_mismatch"}
    assert len(EvolutionStore(root, OWNER).list_action_records()) == 1


def test_records_survive_a_new_store_instance_in_a_new_process(tmp_path: Path) -> None:
    root = tmp_path / "research_evolution"
    _run_workers(root, ["digest-a"])
    reopened = EvolutionStore(root, OWNER)
    events = reopened.list_events()
    assert [e["item_id"] for e in events] == ["item-1"]
    assert reopened.find_action("same-key")["result"] == {"digest": "digest-a"}
