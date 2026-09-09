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


# ------------------------------------------------------------- 可用性四类判据（spec I1）


def _write_episode(
    run_dir: Path,
    *,
    draft: str,
    failures: int = 0,
    stop_reason: str = "model_finish",
    status: str = "completed",
    judge_status: str | None = "ok",
    exc_class: str | None = None,
) -> None:
    """按真实 continuous-episode.json 的决定性字段构造最小原件。

    形状对照 2026-09-09 实测：漏判反例 run_20260909_205227_971715（修复收尾连续
    502、draft=0、终态改名 invalid_repair_finish）与判官不可用的 feel 样本
    （draft 900+、judge_status=unavailable）。
    """

    events: list[dict] = [
        {"kind": "model_turn", "payload": {"served_model": "m", "content": "…"}}
    ]
    for _ in range(failures):
        events.append(
            {"kind": "repair_model_retry", "payload": {"reason": "LLM 调用 HTTP 502"}}
        )
        events.append({"kind": "model_turn", "payload": {"error": "LLM 调用 HTTP 502"}})
    episode = {
        "execution_kind": "continuous_episode",
        "events": events,
        "outcome": {
            "status": status,
            "stop_reason": stop_reason,
            "draft": draft,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "gaps": [],
        },
        "structural_verifier": {"verified_status": "ok"},
        "semantic_verifier": {
            "status": "ok",
            "judge_status": judge_status,
            "exc_class": exc_class,
        },
        "contract": {},
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "continuous-episode.json").write_text(
        json.dumps(episode, ensure_ascii=False), encoding="utf-8"
    )


def _old_style_case(case_id: str, run_dir: Path, *, answer: str = "降级模板稿") -> dict:
    """旧 artifact 里的题记录：没有可用性字段，只有 run_dir 可回读。"""

    return {
        "case_id": case_id,
        "category": case_id.split("-")[1],
        "tier": "deep",
        "as_of": "2026-09-07",
        "execution_status": "completed",
        "final_answer": answer,
        "total_elapsed_s": 60.0,
        "total_input_tokens": 100,
        "total_output_tokens": 20,
        "turns": [
            {
                "turn_index": 0,
                "question": "q",
                "status": "completed",
                "engine": "A",
                "stop_reason": None,
                "degrades": [],
                "run_dir": str(run_dir),
            }
        ],
    }


def test_renamed_terminal_failure_is_isolated_even_without_stored_flag(
    tmp_path: Path,
) -> None:
    """红→绿主反例：终态改名 invalid_repair_finish、无有效终稿的题，
    旧代码按名字白名单放行（quota_tainted 缺失），新判据必须隔离。"""

    run_dir = tmp_path / "runs" / "run_miss"
    _write_episode(
        run_dir,
        draft="",
        failures=2,
        stop_reason="invalid_repair_finish",
        status="partial",
        judge_status="unavailable",
        exc_class=None,
    )
    case = _old_style_case("cb00-calc-01", run_dir)
    isolated, reason = cb.case_service_isolated(case)
    assert isolated is True
    assert reason is not None and "repair_model_retry=LLM 调用 HTTP 502" in reason
    verdict = cb.classify_case_availability(cb._augment_case_from_run_dirs(case))
    assert verdict["availability_class"] == "unavailable_final"


def test_recovered_case_is_reviewable_and_keeps_failure_records(
    tmp_path: Path,
) -> None:
    """上游失败后恢复、产出可评回答：接受，失败证据保留，不被一次 502 污损整题。"""

    run_dir = tmp_path / "runs" / "run_recovered"
    _write_episode(run_dir, draft="有效终稿" * 100, failures=1)
    case = _old_style_case("cb00-feel-01", run_dir, answer="有效终稿")
    isolated, reason = cb.case_service_isolated(case)
    assert isolated is False and reason is None
    augmented = cb._augment_case_from_run_dirs(case)
    verdict = cb.classify_case_availability(augmented)
    assert verdict["availability_class"] == "recovered"
    assert any("502" in item for item in verdict["evidence"])


def test_product_failure_without_service_excuse_is_accepted_as_failure(
    tmp_path: Path,
) -> None:
    """模型可用但空稿/拒答：不是服务隔离，照常进评审判败，不许重跑洗分。"""

    run_dir = tmp_path / "runs" / "run_refusal"
    _write_episode(run_dir, draft="", failures=0)
    case = _old_style_case("cb00-counter-01", run_dir, answer="")
    isolated, _reason = cb.case_service_isolated(case)
    assert isolated is False
    verdict = cb.classify_case_availability(cb._augment_case_from_run_dirs(case))
    assert verdict["availability_class"] == "product_failure"


def test_resume_shares_the_isolation_criterion_and_reruns_renamed_miss(
    tmp_path: Path,
) -> None:
    """resume 与评审包共用判据：旧件里被改名漏标的服务失败题续跑时重跑，
    恢复题与产品失败题原样搬走（不给重跑洗分的机会）。"""

    miss_dir = tmp_path / "runs" / "run_miss"
    _write_episode(
        miss_dir,
        draft="",
        failures=2,
        stop_reason="invalid_repair_finish",
        status="partial",
    )
    recovered_dir = tmp_path / "runs" / "run_recovered"
    _write_episode(recovered_dir, draft="有效终稿" * 50, failures=1)
    refusal_dir = tmp_path / "runs" / "run_refusal"
    _write_episode(refusal_dir, draft="")
    prior = {
        "benchmark": cb.BENCHMARK_ID,
        "arm_label": "baseline-test",
        "base": "http://127.0.0.1:8813",
        "user": "cb00-baseline",
        "cases": [
            _old_style_case("cb00-calc-01", miss_dir),
            _old_style_case("cb00-feel-01", recovered_dir, answer="有效终稿"),
            _old_style_case("cb00-counter-01", refusal_dir, answer=""),
        ],
    }
    resume = tmp_path / "prior.json"
    resume.write_text(json.dumps(prior, ensure_ascii=False), encoding="utf-8")
    carried = cb._load_resume_cases(
        resume,
        arm_label="baseline-test",
        base="http://127.0.0.1:8813",
        user="cb00-baseline",
    )
    assert set(carried) == {"cb00-feel-01", "cb00-counter-01"}

    with pytest.raises(cb.CapabilityBenchmarkError, match="不是能力读数"):
        cb.build_review_pack(
            [prior, dict(prior, arm_label="candidate")],
            visible_cases=cb.load_visible_set()["cases"],
            hidden_cases=None,
            output_dir=tmp_path / "review",
            seed="s",
        )


def test_run_benchmark_isolates_renamed_failure_at_run_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """live 路径：episode 信号在场时按四类判，改名的终态失败当场隔离，
    恢复题不再被打成污染。"""

    monkeypatch.setattr(cb, "preflight", _fake_preflight)

    def _run(
        base: str, user: str, case: dict, *, users_dir: Path, poll_seconds: float
    ) -> cb.CaseResult:
        result = cb.CaseResult(
            case_id=str(case["id"]), category="feel", tier="deep", as_of="2026-09-07"
        )
        turn = cb.TurnRecord(0, str(case["question"]), status="completed", engine="A")
        if case["id"].endswith("01"):
            turn.stop_reason = "invalid_repair_finish"
            turn.upstream_failures = ["model_turn_error=LLM 调用 HTTP 502"]
            turn.final_draft_chars = 0
        else:
            turn.stop_reason = "model_finish"
            turn.upstream_failures = ["repair_model_retry=LLM 调用 HTTP 502"]
            turn.final_draft_chars = 812
        result.turns.append(turn)
        result.execution_status = "completed"
        return result

    monkeypatch.setattr(cb, "run_case", _run)
    artifact = cb.run_benchmark(
        base="http://127.0.0.1:8813",
        user="cb00-baseline",
        users_dir=tmp_path / "capability-benchmark-00" / "users",
        cases=_mini_cases(2),
        output=tmp_path / "a.json",
        arm_label="baseline-test",
    )
    first, second = artifact["cases"]
    assert first["availability_class"] == "unavailable_final"
    assert first["quota_tainted"] is True
    assert first["taint_reason"] == "model_turn_error=LLM 调用 HTTP 502"
    assert second["availability_class"] == "recovered"
    assert "quota_tainted" not in second
    assert artifact["summary"]["availability_class"] == {
        "unavailable_final": 1,
        "recovered": 1,
    }
    assert artifact["summary"]["attempts"] == 2
    assert cb._run_rc(artifact) == 4


def test_reclassify_rederives_report_and_keeps_original(tmp_path: Path) -> None:
    """重审旧基线原件：派生新分类报告，旧件逐字节保留；所有尝试计入分母；
    判官不可用逐轮明示（exc_class=None 也要列出）。"""

    miss_dir = tmp_path / "runs" / "run_miss"
    _write_episode(
        miss_dir,
        draft="",
        failures=2,
        stop_reason="invalid_repair_finish",
        status="partial",
        judge_status="unavailable",
        exc_class=None,
    )
    clean_dir = tmp_path / "runs" / "run_clean"
    _write_episode(clean_dir, draft="干净答案" * 80)
    artifact = {
        "benchmark": cb.BENCHMARK_ID,
        "arm_label": "baseline-test",
        "base": "http://127.0.0.1:8813",
        "user": "cb00-baseline",
        "cases": [
            _old_style_case("cb00-calc-01", miss_dir),
            _old_style_case("cb00-feel-02", clean_dir, answer="干净答案"),
            {
                "case_id": "cb00-chain-01",
                "category": "chain",
                "execution_status": "skipped_cooldown",
            },
        ],
    }
    source = tmp_path / "artifact.json"
    source.write_text(json.dumps(artifact, ensure_ascii=False), encoding="utf-8")
    before = source.read_bytes()
    output = tmp_path / "reclassified.json"
    rc = cb.main(
        ["reclassify", "--artifact", str(source), "--output", str(output)]
    )
    assert rc == 0
    assert source.read_bytes() == before
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["attempts"] == 3
    assert report["availability_class"] == {
        "unavailable_final": 1,
        "clean": 1,
        "skipped_cooldown": 1,
    }
    assert report["classification_changed_case_ids"] == ["cb00-calc-01"]
    flags = report["judge_flags"]
    assert any(
        flag["case_id"] == "cb00-calc-01" and flag["exc_class"] is None
        for flag in flags
    )
    with pytest.raises(cb.CapabilityBenchmarkError, match="refusing to overwrite"):
        cb.main(["reclassify", "--artifact", str(source), "--output", str(output)])
