"""spec 03 §4 / §8 repository：原子不可覆盖、并发收敛、软链 / 越权拒绝、崩溃残留无害。"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from intelligence.services.research_validation import ContractError, OwnerMismatch, Repository, freeze_study
from intelligence.services.research_validation.contracts import freeze_protocol_content
from intelligence.tests.test_research_validation_support import OWNER, forward_body, make_repo, sh, weekdays

CAL = weekdays("2026-09-01", 90)
NOW = sh("2026-09-11")


def test_publish_never_overwrites_and_returns_original(tmp_path):
    repo = make_repo(tmp_path)
    path = repo.root / "exposures" / "x.json"
    first, created = repo.publish(path, {"v": 1})
    assert created and first == {"v": 1}
    before = path.read_bytes()
    second, created2 = repo.publish(path, {"v": 2})
    assert not created2 and second == {"v": 1}
    assert path.read_bytes() == before, "已存在原件的字节不得变化"
    assert not [p for p in path.parent.iterdir() if p.name.startswith(".pending-")], "临时文件必须清理"


def test_concurrent_identical_publish_converges_to_exactly_one_creation(tmp_path):
    repo = make_repo(tmp_path)
    path = repo.root / "studies" / ("a" * 64) / "protocol.json"
    payload = {"same": "intent", "n": 1}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _i: repo.publish(path, payload), range(16)))
    assert sum(1 for _stored, created in results if created) == 1
    assert all(stored == payload for stored, _c in results)


def test_concurrent_conflicting_publish_has_one_winner_and_no_torn_file(tmp_path):
    repo = make_repo(tmp_path)
    path = repo.root / "exposures" / "race.json"
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda i: (i, repo.publish(path, {"writer": i})), range(16)))
    winners = [i for i, (_s, created) in results if created]
    assert len(winners) == 1
    winner = {"writer": winners[0]}
    assert all(stored == winner for _i, (stored, _c) in results)
    assert repo._read(path) == winner


def test_symlink_component_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    repo.root.mkdir(parents=True)
    os.symlink(elsewhere, repo.root / "studies")
    protocol = freeze_protocol_content(forward_body(CAL), owner=OWNER, now=NOW)
    with pytest.raises(ContractError, match="软链"):
        repo.publish_protocol(protocol)
    with pytest.raises(ContractError, match="软链"):
        Repository(repo.root / "studies", OWNER)


def test_owner_mismatch_is_rejected_on_read_and_at_service_boundary(tmp_path):
    repo_a = make_repo(tmp_path, "alice")
    protocol = freeze_study(owner="alice", repository=repo_a, now=NOW, protocol_input=forward_body(CAL))
    repo_b_same_root = Repository(repo_a.root, "bob")
    with pytest.raises(OwnerMismatch):
        repo_b_same_root.load_protocol(protocol["study_id"])
    with pytest.raises(OwnerMismatch):
        freeze_study(owner="bob", repository=repo_a, now=NOW, protocol_input=forward_body(CAL))
    # 篡改 owner 字段先撞身份哈希（owner 是语义字段）；哈希自洽但归属不同的协议才走 OwnerMismatch
    with pytest.raises(ContractError, match="哈希"):
        repo_a.publish_protocol({**protocol, "owner_user_id": "bob"})
    bobs = freeze_protocol_content(forward_body(CAL), owner="bob", now=NOW)
    with pytest.raises(OwnerMismatch):
        repo_a.publish_protocol(bobs)


def test_leftover_pending_temp_file_from_crash_is_ignored(tmp_path):
    repo = make_repo(tmp_path)
    protocol = freeze_study(owner=OWNER, repository=repo, now=NOW, protocol_input=forward_body(CAL))
    case_dir = repo.study_dir(protocol["study_id"]) / "forecasts" / ("c" * 64)
    case_dir.mkdir(parents=True)
    (case_dir / ".pending-crashed").write_text("{", encoding="utf-8")
    assert repo.list_forecasts(protocol["study_id"]) == []


def test_ids_and_operation_ids_are_validated(tmp_path):
    repo = make_repo(tmp_path)
    with pytest.raises(ContractError):
        repo.study_dir("not-a-sha")
    with pytest.raises(ContractError):
        repo.exposure_path("../escape")
    with pytest.raises(ContractError):
        repo.forecast_path("a" * 64, "b" * 64, "../x")
    with pytest.raises(ContractError, match="越界"):
        repo._guard(tmp_path / "outside.json")


def test_list_studies_only_reports_dirs_with_protocol(tmp_path):
    repo = make_repo(tmp_path)
    protocol = freeze_study(owner=OWNER, repository=repo, now=NOW, protocol_input=forward_body(CAL))
    (repo.studies_dir / ("f" * 64)).mkdir()
    assert repo.list_studies() == [protocol["study_id"]]
