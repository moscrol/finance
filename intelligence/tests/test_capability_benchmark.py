"""00 · 真实能力基线题集：结构、零重叠、密封清单、盲配与汇总的确定性测试（不跑 live）。"""

from __future__ import annotations

import json
from pathlib import Path
import tarfile

import pytest

from intelligence.eval import capability_benchmark as cb


def test_visible_set_is_twenty_with_two_per_category() -> None:
    loaded = cb.load_visible_set()
    assert loaded["case_count"] == cb.VISIBLE_COUNT == 20
    counts: dict[str, int] = {}
    for case in loaded["cases"]:
        counts[case["category"]] = counts.get(case["category"], 0) + 1
        assert case["id"].startswith(f"cb00-{case['category']}-")
        assert case["as_of"] <= loaded["default_as_of"]
    assert counts == dict.fromkeys(cb.CATEGORIES, cb.VISIBLE_PER_CATEGORY)


def test_continue_cases_carry_a_real_prior_user_turn() -> None:
    loaded = cb.load_visible_set()
    for case in loaded["cases"]:
        if case["category"] == "continue":
            roles = [turn["role"] for turn in case["conversation_context"]]
            assert "user" in roles
            assert all(
                "不注入模型" in turn["content"]
                for turn in case["conversation_context"]
                if turn["role"] == "assistant"
            )


def test_sealed_manifest_hashes_thirty_rubrics_and_ten_hidden() -> None:
    manifest = cb.load_sealed_manifest()
    visible_ids = set(cb.load_visible_set()["case_ids"])
    hidden_ids = set(manifest["hidden_case_ids"])
    assert len(hidden_ids) == cb.HIDDEN_COUNT == 10
    assert not visible_ids & hidden_ids
    assert set(manifest["rubrics"]) == visible_ids | hidden_ids
    for hidden_id in hidden_ids:
        category = hidden_id.split("-")[1]
        assert category in cb.CATEGORIES
        assert hidden_id.rsplit("-", 1)[-1].startswith("h")


def test_visible_set_has_zero_overlap_with_existing_sets() -> None:
    report = cb.overlap_report(cb.load_visible_set()["cases"])
    assert report["compared_sets"], (
        "expected at least one existing set to compare against"
    )
    assert report["zero_overlap"], report["duplicates"]


def test_guards_reject_production_port_and_foreign_users_dir(tmp_path: Path) -> None:
    for port in sorted(cb.RESERVED_PORTS):
        with pytest.raises(cb.CapabilityBenchmarkError):
            cb.guard_base(f"http://127.0.0.1:{port}")
    cb.guard_base("http://127.0.0.1:8813")
    with pytest.raises(cb.CapabilityBenchmarkError):
        cb.guard_users_dir(tmp_path / "users")
    cb.guard_users_dir(tmp_path / "capability-benchmark-00" / "users")


def test_blind_shuffle_is_deterministic_and_not_constant() -> None:
    ids = [f"cb00-feel-{i:02d}" for i in range(30)]
    first = [
        cb._shuffle_labels("seed-1", cid, ["baseline", "candidate"]) for cid in ids
    ]
    second = [
        cb._shuffle_labels("seed-1", cid, ["baseline", "candidate"]) for cid in ids
    ]
    assert first == second
    assert len({tuple(order) for order in first}) == 2
    picked = cb.pick_second_review(ids, "seed-1")
    assert len(picked) == 6 and picked == cb.pick_second_review(ids, "seed-1")


def _artifact(label: str, cases: list[tuple[str, str]]) -> dict:
    return {
        "arm_label": label,
        "preflight": {"source_revision": f"{label}-rev"},
        "market_data_date": "2026-09-07",
        "summary": {
            "execution_status": {"completed": len(cases)},
            "invalid_actions": 0,
            "median_case_elapsed_s": 10.0,
            "total_elapsed_s": 10.0 * len(cases),
            "total_input_tokens": 100,
            "total_output_tokens": 10,
            "served_models": {"m": len(cases)},
        },
        "cases": [
            {"case_id": cid, "category": cid.split("-")[1], "final_answer": answer}
            for cid, answer in cases
        ],
    }


def _score(case_id: str, blind: dict[str, str], winner_label: str | None) -> dict:
    arms = {
        key: {
            "task_completed": "yes" if label != "decoy" else "no",
            "correct_useful_points": 3 if label != "decoy" else 0,
            "wrong_facts": 0 if label != "decoy" else 2,
            "calc_correct": "na",
            "ranking_with_conditions": "na",
            "followup_advances": "na",
            "over_refusal": False,
            "time_leakage": False,
            "notes": "",
        }
        for key, label in blind.items()
    }
    verdict = None
    for key, label in blind.items():
        if label == winner_label:
            verdict = key
    return {
        "case_id": case_id,
        "reviewer": "r1",
        "arms": arms,
        "pair_verdict": verdict or "tie",
        "verdict_reason": "test",
    }


def test_review_pack_and_aggregate_flag_a_winning_decoy(tmp_path: Path) -> None:
    visible = cb.load_visible_set()["cases"]
    ids = [case["id"] for case in visible[:3]]
    arts = [
        _artifact("baseline", [(cid, f"answer-a-{cid}") for cid in ids]),
        _artifact("candidate", [(cid, f"answer-b-{cid}") for cid in ids]),
    ]
    review = tmp_path / "review"
    pack = cb.build_review_pack(
        arts,
        visible_cases=visible,
        hidden_cases=None,
        output_dir=review,
        seed="s",
        decoy={"case_id": ids[0], "answer": "流畅但算错"},
    )
    assert pack["case_count"] == 3 and pack["decoy_case_id"] == ids[0]
    assert len(list((review / "sheets").glob("*.json"))) == 3
    mapping = json.loads((review / "mapping.sealed.json").read_text(encoding="utf-8"))
    assert "decoy" in mapping[ids[0]].values()
    (review / "scores").mkdir()
    for cid in ids:
        winner = "decoy" if cid == ids[0] else "candidate"
        (review / "scores" / f"{cid}.json").write_text(
            json.dumps(_score(cid, mapping[cid], winner), ensure_ascii=False),
            encoding="utf-8",
        )
    summary = cb.aggregate(review, artifacts=arts)
    assert summary["decoy_check"]["decoy_won"] is True
    assert summary["decoy_check"]["cases"] == [ids[0]]
    assert summary["main_table"]["candidate"]["pair_wins"] == 2
    # 去掉 decoy 的胜票后，反向验证应通过
    (review / "scores" / f"{ids[0]}.json").write_text(
        json.dumps(_score(ids[0], mapping[ids[0]], "baseline"), ensure_ascii=False),
        encoding="utf-8",
    )
    summary = cb.aggregate(review, artifacts=arts)
    assert summary["decoy_check"]["decoy_won"] is False
    assert summary["main_table"]["baseline"]["pair_wins"] == 1
    assert "单跑基线不做显著性宣称" in summary["significance_note"]
    assert cb.render_summary_markdown(summary).startswith("# capability-benchmark-00")


def test_aggregate_rejects_invalid_scores(tmp_path: Path) -> None:
    visible = cb.load_visible_set()["cases"]
    cid = visible[0]["id"]
    arts = [_artifact("baseline", [(cid, "a")]), _artifact("candidate", [(cid, "b")])]
    review = tmp_path / "review"
    cb.build_review_pack(
        arts, visible_cases=visible, hidden_cases=None, output_dir=review, seed="s"
    )
    mapping = json.loads((review / "mapping.sealed.json").read_text(encoding="utf-8"))
    bad = _score(cid, mapping[cid], "baseline")
    next(iter(bad["arms"].values()))["task_completed"] = "maybe"
    (review / "scores").mkdir()
    (review / "scores" / f"{cid}.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(cb.CapabilityBenchmarkError):
        cb.aggregate(review, artifacts=arts)


def test_reset_user_from_seed_only_inside_guarded_dir(tmp_path: Path) -> None:
    seed_root = tmp_path / "seed" / "cb00-baseline"
    seed_root.mkdir(parents=True)
    (seed_root / "corrections.jsonl").write_text("{}\n", encoding="utf-8")
    tgz = tmp_path / "seed.tgz"
    with tarfile.open(tgz, "w:gz") as tar:
        tar.add(seed_root, arcname="cb00-baseline")
    users_dir = tmp_path / "capability-benchmark-00" / "users"
    digest = cb.reset_user_from_seed(users_dir, "cb00-baseline", tgz)
    assert len(digest) == 64
    assert (users_dir / "cb00-baseline" / "corrections.jsonl").is_file()
    with pytest.raises(cb.CapabilityBenchmarkError):
        cb.reset_user_from_seed(tmp_path / "plain-users", "cb00-baseline", tgz)


def test_sealed_manifest_verifies_against_local_sealed_dir_when_present() -> None:
    sealed = Path.home() / "capability-benchmark-00-sealed-20260909"
    if not sealed.is_dir():
        pytest.skip("sealed dir lives outside the repo on the examiner's machine")
    report = cb.verify_sealed_dir(sealed, cb.load_sealed_manifest())
    assert report["ok"], report["mismatches"]
