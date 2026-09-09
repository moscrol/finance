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


def test_wait_out_cooldown_sleeps_reset_then_proceeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(
        [
            {"status": "cooldown", "reset_seconds": 120, "served_model": None},
            {"status": "ok", "reset_seconds": None, "served_model": "m"},
        ]
    )
    monkeypatch.setattr(cb, "gateway_probe_from_env", lambda model=None: next(answers))
    naps: list[float] = []
    history = cb.wait_out_cooldown(model="m", max_wait_s=7200, sleep=naps.append)
    assert naps == [150.0]
    assert [h["status"] for h in history] == ["cooldown", "ok"]
    assert history[0]["slept_s"] == 150.0


def test_wait_out_cooldown_gives_up_past_max_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cb,
        "gateway_probe_from_env",
        lambda model=None: {
            "status": "cooldown",
            "reset_seconds": 5000,
            "served_model": None,
        },
    )
    history = cb.wait_out_cooldown(model="m", max_wait_s=600, sleep=lambda _s: None)
    assert history[-1]["gave_up"] is True and len(history) == 1


def test_wait_out_cooldown_falls_through_to_backup_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """sol 独死 terra 活（2026-09-09 18:57 实测）：任一链上模型可用批就该放行。"""

    def _by_model(model: str | None = None) -> dict:
        if model == "gpt-5.6-sol":
            return {"status": "http_502", "reset_seconds": None, "served_model": None}
        return {"status": "ok", "reset_seconds": None, "served_model": model}

    monkeypatch.setattr(cb, "gateway_probe_from_env", _by_model)
    history = cb.wait_out_cooldown(
        model="gpt-5.6-sol,gpt-5.6-terra", max_wait_s=600, sleep=lambda _s: None
    )
    assert [h["status"] for h in history] == ["http_502", "ok"]
    assert history[-1]["probe_model"] == "gpt-5.6-terra"
    # 全失败且无 reset 信息：立即返回交上层，不盲睡
    monkeypatch.setattr(
        cb,
        "gateway_probe_from_env",
        lambda model=None: {
            "status": "http_502",
            "reset_seconds": None,
            "served_model": None,
        },
    )
    naps: list[float] = []
    history = cb.wait_out_cooldown(
        model="gpt-5.6-sol,gpt-5.6-terra", max_wait_s=600, sleep=naps.append
    )
    assert naps == [] and len(history) == 2


def test_gateway_probe_from_env_refuses_to_guess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "FORESIGHT_BUILTIN_LLM_BASE_URL",
        "LLM_BASE_URL",
        "FORESIGHT_BUILTIN_LLM_API_KEY",
        "LLM_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    assert cb.gateway_probe_from_env("m") is None


def _fake_preflight(base: str, *, users_dir: Path) -> dict:
    return {"ok": True, "problems": []}


def _mini_cases(n: int = 3) -> list[dict]:
    return [
        {
            "id": f"cb00-feel-{i:02d}",
            "category": "feel",
            "tier": "deep",
            "as_of": "2026-09-07",
            "question": f"q{i}",
        }
        for i in range(1, n + 1)
    ]


def test_run_benchmark_aborts_instead_of_running_through_cooldown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2026-09-09 实测教训：wait_out_cooldown gave_up 后照跑，25/30 题成了配额读数。"""

    monkeypatch.setattr(cb, "preflight", _fake_preflight)
    monkeypatch.setattr(
        cb,
        "gateway_probe_from_env",
        lambda model=None: {
            "status": "cooldown",
            "reset_seconds": 99999,
            "served_model": None,
        },
    )

    def _no_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("case must not run while the gateway is cooling")

    monkeypatch.setattr(cb, "run_case", _no_run)
    out = tmp_path / "a.json"
    artifact = cb.run_benchmark(
        base="http://127.0.0.1:8813",
        user="cb00-baseline",
        users_dir=tmp_path / "capability-benchmark-00" / "users",
        cases=_mini_cases(),
        output=out,
        arm_label="baseline-test",
        gateway_probe_model="m",
        max_cooldown_wait_s=60.0,
    )
    assert artifact["summary"]["execution_status"] == {"skipped_cooldown": 3}
    assert artifact["aborted_on_cooldown"]["status"] == "cooldown"
    assert cb._run_rc(artifact) == 4
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk["cases"][0]["execution_status"] == "skipped_cooldown"


def test_run_benchmark_tags_mid_episode_model_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cb, "preflight", _fake_preflight)
    monkeypatch.setattr(
        cb,
        "gateway_probe_from_env",
        lambda model=None: {"status": "ok", "reset_seconds": None, "served_model": "m"},
    )

    def _degraded(
        base: str, user: str, case: dict, *, users_dir: Path, poll_seconds: float
    ) -> cb.CaseResult:
        result = cb.CaseResult(
            case_id=str(case["id"]), category="feel", tier="deep", as_of="2026-09-07"
        )
        turn = cb.TurnRecord(0, str(case["question"]), status="completed", engine="A")
        turn.stop_reason = "repair_model_unavailable"
        result.turns.append(turn)
        result.execution_status = "completed"
        return result

    monkeypatch.setattr(cb, "run_case", _degraded)
    artifact = cb.run_benchmark(
        base="http://127.0.0.1:8813",
        user="cb00-baseline",
        users_dir=tmp_path / "capability-benchmark-00" / "users",
        cases=_mini_cases(1),
        output=tmp_path / "a.json",
        arm_label="baseline-test",
        gateway_probe_model="m",
    )
    case = artifact["cases"][0]
    assert case["quota_tainted"] is True
    assert case["taint_reason"] == "stop_reason=repair_model_unavailable"
    assert artifact["summary"]["quota_tainted"] == 1
    assert cb._run_rc(artifact) == 4
    # 污染读数不得进评审包
    with pytest.raises(cb.CapabilityBenchmarkError):
        cb.build_review_pack(
            [artifact, dict(artifact, arm_label="candidate")],
            visible_cases=cb.load_visible_set()["cases"],
            hidden_cases=None,
            output_dir=tmp_path / "review",
            seed="s",
        )


def test_run_benchmark_resume_carries_clean_and_reruns_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cb, "preflight", _fake_preflight)
    cases = _mini_cases(3)
    prior = {
        "benchmark": cb.BENCHMARK_ID,
        "arm_label": "baseline-test",
        "base": "http://127.0.0.1:8813",
        "user": "cb00-baseline",
        "cases": [
            {
                "case_id": cases[0]["id"],
                "category": "feel",
                "execution_status": "completed",
                "final_answer": "clean",
            },
            {
                "case_id": cases[1]["id"],
                "category": "feel",
                "execution_status": "completed",
                "quota_tainted": True,
            },
            {
                "case_id": cases[2]["id"],
                "category": "feel",
                "execution_status": "skipped_cooldown",
            },
        ],
    }
    resume = tmp_path / "prior.json"
    resume.write_text(json.dumps(prior), encoding="utf-8")
    ran: list[str] = []

    def _run(
        base: str, user: str, case: dict, *, users_dir: Path, poll_seconds: float
    ) -> cb.CaseResult:
        ran.append(str(case["id"]))
        result = cb.CaseResult(
            case_id=str(case["id"]), category="feel", tier="deep", as_of="2026-09-07"
        )
        result.turns.append(cb.TurnRecord(0, "q", status="completed", engine="A"))
        result.execution_status = "completed"
        return result

    monkeypatch.setattr(cb, "run_case", _run)
    artifact = cb.run_benchmark(
        base="http://127.0.0.1:8813",
        user="cb00-baseline",
        users_dir=tmp_path / "capability-benchmark-00" / "users",
        cases=cases,
        output=tmp_path / "b.json",
        arm_label="baseline-test",
        resume_from=resume,
    )
    assert ran == [cases[1]["id"], cases[2]["id"]]
    assert artifact["cases"][0]["resumed_from_artifact"] == str(resume)
    assert artifact["resumed_from"] == str(resume)
    assert cb._run_rc(artifact) == 0
    with pytest.raises(cb.CapabilityBenchmarkError, match="arm_label"):
        cb.run_benchmark(
            base="http://127.0.0.1:8813",
            user="cb00-baseline",
            users_dir=tmp_path / "capability-benchmark-00" / "users",
            cases=cases,
            output=tmp_path / "c.json",
            arm_label="other-arm",
            resume_from=resume,
        )
    with pytest.raises(cb.CapabilityBenchmarkError, match="seed"):
        cb.run_benchmark(
            base="http://127.0.0.1:8813",
            user="cb00-baseline",
            users_dir=tmp_path / "capability-benchmark-00" / "users",
            cases=cases,
            output=tmp_path / "d.json",
            arm_label="baseline-test",
            resume_from=resume,
            seed_tgz=tmp_path / "seed.tgz",
        )


def test_sealed_manifest_verifies_against_local_sealed_dir_when_present() -> None:
    sealed = Path.home() / "capability-benchmark-00-sealed-20260909"
    if not sealed.is_dir():
        pytest.skip("sealed dir lives outside the repo on the examiner's machine")
    report = cb.verify_sealed_dir(sealed, cb.load_sealed_manifest())
    assert report["ok"], report["mismatches"]
