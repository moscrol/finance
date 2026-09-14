from __future__ import annotations

import json
import urllib.error
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from scripts import rejudge_quality_ablation as rejudge
from scripts.run_quality_ablation import aggregate_components, provider_label
from intelligence.services import llm_refine
from intelligence.tests.judge_validity_fixtures import valid_batch

_NOW = datetime(2026, 8, 27, 1, 30, tzinfo=timezone.utc)


def test_changed_judge_cannot_reuse_old_calibration():
    artifact = _two_case_artifact()
    artifact["noise_floor"] = {"measured": True, "sigma": 2, "sd_delta_single_question": 0.1}
    artifact["answers"][1]["judge"]["provider"] = "judge/grok-4"
    result = _run(artifact, lambda q, a: {**_judged(4), "provider": "judge/gpt-5"})
    assert result["aggregates"]["kb-rag"]["decision"] == "no_call"


def _versioned_artifact():
    answers, calibration, manifest, floor = valid_batch(zero_variance=True)
    return {
        "schema_version": 2, "kind": "quality_ablation", "manifest": manifest,
        "questions": deepcopy(manifest["run_manifest"]["questions"]),
        "answers": answers, "calibration": calibration, "noise_floor": floor,
        "aggregates": aggregate_components(answers, ["kb-rag"], calibration=calibration,
                                            manifest=manifest, noise_floor=floor),
    }


class _HTTPResponse:
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        content = json.dumps(_scores(3))
        return json.dumps({"model": "grok-4.1", "choices": [
            {"message": {"content": content}, "finish_reason": "stop"},
        ]}).encode()


def _configure_http(monkeypatch, transport):
    provider = llm_refine.LLMProvider("fixture", "secret", "https://example.invalid/v1", "grok-4.1")
    monkeypatch.setitem(rejudge._JUDGE_OVERRIDE, "provider", provider)
    monkeypatch.setattr(llm_refine.urllib.request, "urlopen", transport)
    return provider


def test_new_batch_uses_current_spec_rejudges_all_and_checkpoints_before_call(tmp_path, monkeypatch):
    artifact = _versioned_artifact()
    original = deepcopy(artifact)
    destination = tmp_path / "new.json"
    calls = []

    def transport(request, **_kwargs):
        checkpoint = json.loads(destination.read_text())
        assert checkpoint["manifest"]["answer_manifest"] is not None
        assert checkpoint["manifest"]["run_manifest"]["judge_spec"]["requested_model"] == "grok-4.1"
        if calls:
            assert checkpoint["call_ledger"]["call_count"] >= len(calls)
        calls.append(json.loads(request.data))
        return _HTTPResponse()

    _configure_http(monkeypatch, transport)
    result = rejudge.new_batch_artifact(
        artifact, source_path=tmp_path / "source.json", source_sha256="a" * 64,
        seed=1, calibration_repeats=2, output_path=destination,
    )

    assert len(calls) == 8
    assert artifact == original
    assert result["manifest"]["batch_id"] != artifact["manifest"]["batch_id"]
    assert result["manifest"]["run_manifest"]["judge_spec"] != artifact["manifest"]["run_manifest"]["judge_spec"]
    assert result["judging_validity"]["valid"] is True
    assert result["aggregates"]["kb-rag"]["decision"] == "callable"
    assert result["noise_floor"]["batch_id"] == result["manifest"]["batch_id"]
    assert result["parent_batch_id"] == artifact["manifest"]["batch_id"]
    assert json.loads(destination.read_text()) == result


@pytest.mark.parametrize("source_state", ["sealed", "open", "invalid"])
def test_pending_uses_new_diagnostic_batch_and_keeps_original_scores(
    tmp_path, monkeypatch, source_state,
):
    artifact = _versioned_artifact()
    artifact["manifest"]["state"] = source_state
    artifact["answers"][0]["judge"] = {"scored": False, "reason": "source outage",
                                        "attempt_records": [{"status": "failed", "attempt_id": "old-failed"}]}
    before = deepcopy(artifact)
    destination = tmp_path / "pending.json"
    calls = []
    _configure_http(monkeypatch, lambda *_a, **_k: calls.append(1) or _HTTPResponse())

    result = rejudge.rejudge_artifact(
        artifact, source_path=tmp_path / "source.json", source_sha256="b" * 64,
        seed=1, output_path=destination,
    )

    assert len(calls) == 1
    assert artifact == before
    assert result["manifest"]["batch_id"] != artifact["manifest"]["batch_id"]
    assert result["answers"][0]["judge"]["batch_id"] == result["manifest"]["batch_id"]
    assert result["answers"][0]["judge_history"] == [before["answers"][0]["judge"]]
    assert result["answers"][0]["rejudge_attempts"][0]["selected_attempt_id"]
    assert [r["judge"] for r in result["answers"][1:]] == [r["judge"] for r in before["answers"][1:]]
    assert result["noise_floor"] == artifact["noise_floor"]
    assert "calibration_stale" in result["judging_validity"]["reason_codes"]
    assert result["aggregates"]["kb-rag"]["decision"] == "no_call"
    assert json.loads(destination.read_text()) == result


def test_pending_failure_keeps_full_old_and_new_attempts(tmp_path, monkeypatch):
    artifact = _versioned_artifact()
    previous = {"scored": False, "reason": "source outage", "attempt_records": [
        {"status": "failed", "attempt_id": "source-failure", "reason": "http_502"},
    ]}
    artifact["answers"][0]["judge"] = deepcopy(previous)

    def transport(request, **_kwargs):
        raise urllib.error.HTTPError(request.full_url, 503, "outage", {}, None)

    _configure_http(monkeypatch, transport)
    result = rejudge.rejudge_artifact(
        artifact, source_path=tmp_path / "source.json", source_sha256="b" * 64, seed=1,
    )
    record = result["answers"][0]
    assert record["judge_history"] == [previous]
    assert record["judge"]["attempt_records"] == previous["attempt_records"]
    assert record["rejudge_attempts"][0]["attempt_records"][0]["reason"] == "http_503"
    assert record["rejudge_attempts"][0]["batch_id"] == result["manifest"]["batch_id"]
    assert result["call_ledger"]["failure_count"] == 1


@pytest.mark.parametrize("mutation", ["delete_failure", "change_arm", "duplicate_question", "change_text"])
def test_source_frozen_content_mismatch_refuses_calls(tmp_path, monkeypatch, mutation):
    artifact = _versioned_artifact()
    if mutation == "delete_failure":
        artifact["answers"][0]["ok"] = False
        artifact["answers"].pop(0)
    elif mutation == "change_arm":
        artifact["answers"][0]["arm"] = "kb-rag"
    elif mutation == "duplicate_question":
        artifact["questions"][1] = deepcopy(artifact["questions"][0])
    else:
        artifact["answers"][0]["answer"] += "different answer"
    calls = []
    _configure_http(monkeypatch, lambda *_a, **_k: calls.append(1) or _HTTPResponse())
    destination = tmp_path / "new.json"
    with pytest.raises(SystemExit, match="冻结内容校验失败"):
        rejudge.new_batch_artifact(
            artifact, source_path=tmp_path / "source.json", source_sha256="c" * 64,
            seed=1, output_path=destination,
        )
    assert calls == []
    assert not destination.exists()


def _write_source(tmp_path, artifact):
    path = tmp_path / "source.json"
    path.write_text(json.dumps(artifact))
    return path


@pytest.mark.parametrize("kind", ["unknown", "same_family"])
def test_cli_checks_source_writer_before_calls(tmp_path, monkeypatch, kind):
    artifact = _versioned_artifact()
    if kind == "unknown":
        for record in artifact["answers"]:
            record.pop("writer_provenance")
        source_manifest = deepcopy(artifact["manifest"])
        source_manifest.update(state="open", answer_manifest=None, answer_manifest_sha256=None)
        artifact["manifest"] = rejudge.validity.bind_answers(source_manifest, artifact["answers"])
    source = _write_source(tmp_path, artifact)
    calls = []
    provider = _configure_http(monkeypatch, lambda *_a, **_k: calls.append(1) or _HTTPResponse())
    if kind == "same_family":
        provider.model = "gpt-5.6-terra"
    monkeypatch.setattr(rejudge, "require_llm_ready", lambda: None)
    resolved = []

    def resolve(*, require_independent):
        resolved.append(require_independent)
        return {"override": provider, "judge": provider.model, "composer": "glm-5.3",
                "independence": "independent"}

    monkeypatch.setattr(rejudge, "resolve_judge", resolve)
    with pytest.raises(SystemExit, match="writer_identity_unknown|judge_not_independent"):
        rejudge.main(["--run", str(source), "--mode", "new-batch"])
    assert resolved == [False]
    assert calls == []
    assert not (tmp_path / "source-new-batch.json").exists()


def test_cli_existing_output_fails_before_provider_resolution(tmp_path, monkeypatch):
    source = _write_source(tmp_path, _versioned_artifact())
    destination = tmp_path / "exists.json"
    destination.write_text("original")
    monkeypatch.setattr(rejudge, "require_llm_ready", lambda: pytest.fail("provider resolution is too late"))
    with pytest.raises(SystemExit, match="输出已存在"):
        rejudge.main(["--run", str(source), "--output", str(destination), "--mode", "new-batch"])
    assert destination.read_text() == "original"


@pytest.mark.parametrize("mode", ["pending", "new-batch"])
def test_interrupt_keeps_settled_attempt_in_owned_receipt(tmp_path, monkeypatch, mode):
    artifact = _versioned_artifact()
    if mode == "pending":
        for record in artifact["answers"][:2]:
            record["judge"] = {"scored": False, "reason": "source failed"}
    destination = tmp_path / "interrupted.json"
    calls = []

    def transport(*_args, **_kwargs):
        calls.append(1)
        if len(calls) == 2:
            assert json.loads(destination.read_text())["call_ledger"]["call_count"] == 1
            raise KeyboardInterrupt()
        return _HTTPResponse()

    _configure_http(monkeypatch, transport)
    function = rejudge.new_batch_artifact if mode == "new-batch" else rejudge.rejudge_artifact
    with pytest.raises(KeyboardInterrupt):
        function(artifact, source_path=tmp_path / "source.json", source_sha256="d" * 64,
                 seed=1, output_path=destination)
    saved = json.loads(destination.read_text())
    assert saved["status"] == "incomplete"
    assert saved["manifest"]["state"] == "invalid"
    assert saved["call_ledger"]["call_count"] == 1
    assert saved["call_ledger"]["records"][0]["status"] == "success"
    assert saved["aggregates"]["kb-rag"]["decision"] == "no_call"


def test_response_identity_change_stops_new_calls_and_keeps_invalid_receipt(tmp_path, monkeypatch):
    artifact = _versioned_artifact()
    destination = tmp_path / "invalid.json"
    calls = []

    class WrongModel(_HTTPResponse):
        def read(self):
            return super().read().replace(b"grok-4.1", b"gpt-5.6")

    _configure_http(monkeypatch, lambda *_a, **_k: calls.append(1) or WrongModel())
    result = rejudge.new_batch_artifact(
        artifact, source_path=tmp_path / "source.json", source_sha256="f" * 64,
        seed=1, output_path=destination,
    )
    assert len(calls) == 1
    assert result["status"] == "invalid"
    assert "judge_identity_mismatch" in result["judging_validity"]["reason_codes"]
    assert result["call_ledger"]["records"][0]["reported_model"] == "gpt-5.6"
    assert json.loads(destination.read_text()) == result


def test_legacy_new_batch_exploration_never_recovers_qualification(tmp_path, monkeypatch):
    artifact = _two_case_artifact()
    calls = []
    _configure_http(monkeypatch, lambda *_a, **_k: calls.append(1) or _HTTPResponse())
    result = rejudge.new_batch_artifact(
        artifact, source_path=tmp_path / "source.json", source_sha256="e" * 64,
        seed=1, independence="allow-correlated",
    )
    assert calls
    assert "unsupported_schema" in result["judging_validity"]["reason_codes"]
    assert result["aggregates"]["kb-rag"]["decision"] == "no_call"


def test_cli_new_batch_completes_with_actual_judge_and_prints_qualification(tmp_path, monkeypatch, capsys):
    source = _write_source(tmp_path, _versioned_artifact())
    original = source.read_bytes()
    destination = tmp_path / "complete.json"
    calls = []
    provider = _configure_http(monkeypatch, lambda *_a, **_k: calls.append(1) or _HTTPResponse())
    monkeypatch.setattr(rejudge, "require_llm_ready", lambda: None)
    monkeypatch.setattr(rejudge, "resolve_judge", lambda **_kwargs: {
        "override": provider, "judge": provider.model, "composer": "gpt-5.6-sol",
        "independence": "independent",
    })
    assert rejudge.main(["--run", str(source), "--output", str(destination), "--mode", "new-batch"]) == 0
    result = json.loads(destination.read_text())
    assert len(calls) == 8
    assert source.read_bytes() == original
    assert result["judging_validity"]["valid"] is True
    assert result["source_sha256"] == rejudge.hashlib.sha256(original).hexdigest()
    output = capsys.readouterr().out
    assert "决定=callable" in output
    assert "总样本=4 已交付=4 已评分=4 本批失败尝试=0" in output


def test_budget_rejection_is_zero_attempts_and_never_qualifies(tmp_path, monkeypatch):
    calls = []
    _configure_http(monkeypatch, lambda *_a, **_k: calls.append(1) or _HTTPResponse())
    with llm_refine.call_ledger_scope(max_calls=0):
        result = rejudge.new_batch_artifact(
            _versioned_artifact(), source_path=tmp_path / "source.json", source_sha256="f" * 64,
            seed=1, output_path=tmp_path / "refused.json",
        )
    assert calls == []
    assert result["call_ledger"]["reserved_count"] == 0
    assert result["call_ledger"]["records"] == []
    assert result["aggregates"]["kb-rag"]["decision"] == "no_call"
    assert all((record.get("judge") or {}).get("identity_state") == "not_called"
               for record in result["answers"])


def test_new_batch_keeps_product_failures_in_registered_denominator(tmp_path, monkeypatch):
    artifact = _versioned_artifact()
    artifact["answers"][0].update(ok=False, delivery_state="no_answer")
    calls = []
    _configure_http(monkeypatch, lambda *_a, **_k: calls.append(1) or _HTTPResponse())
    result = rejudge.new_batch_artifact(
        artifact, source_path=tmp_path / "source.json", source_sha256="e" * 64, seed=1,
    )
    assert len(result["answers"]) == 4
    assert result["answers"][0]["ok"] is False
    assert result["answers"][0]["judge"]["reason"] == "product_not_delivered"
    assert result["aggregates"]["kb-rag"]["questions_total"] == 2
    assert result["aggregates"]["kb-rag"]["decision"] == "no_call"
    assert "product_undelivered" in result["judging_validity"]["reason_codes"]


def _scores(value: int) -> dict[str, int]:
    return {
        "directness": value,
        "coverage": value,
        "relevance": value,
        "truth_boundary": value,
        "usefulness": value,
    }


def _judged(value: int) -> dict[str, object]:
    return {
        "scored": True,
        "scores": _scores(value),
        "total": value * 5,
        "normalized": round(value * 5 / 20.0, 4),
        "justification": "桩",
        "attempts": 1,
    }


def _unscored(reason: str = "所有已配置 LLM provider 均失败（zhipu:URLError）") -> dict[str, object]:
    return {"scored": False, "reason": reason, "attempts": 1}


def _answer(
    arm: str,
    case_id: str,
    judge: dict[str, object],
    *,
    ok: bool = True,
    answer: str | None = None,
) -> dict:
    return {
        "arm": arm,
        "case_id": case_id,
        "ok": ok,
        "answer": f"{arm}/{case_id} 的答案正文" * 20 if answer is None else answer,
        "elapsed_sec": 12.0,
        "judge": judge,
    }


def _artifact(answers: list[dict], case_ids: list[str]) -> dict[str, object]:
    aggregates = aggregate_components(answers, ["kb-rag"])
    return {
        "kind": "quality_ablation",
        "generated_at": "2026-08-26T14:35:58+00:00",
        "seed": 20260830,
        "judge_note": "同一 judge 评所有臂，标签盲",
        "questions": [{"case_id": c, "text": f"问题 {c}", "as_of": "2026-07-22"} for c in case_ids],
        "answers": answers,
        "aggregates": aggregates,
    }


def _two_case_artifact() -> dict[str, object]:
    """q1 基线断链未打分（拖垮该题），q2 两臂都已打分。"""

    answers = [
        _answer("baseline", "q1", _unscored()),
        _answer("baseline", "q2", _judged(3)),
        _answer("kb-rag", "q1", _judged(2)),
        _answer("kb-rag", "q2", _judged(2)),
    ]
    return _artifact(answers, ["q1", "q2"])


def _run(artifact, judge_fn, *, seed: int = 1, tmp_path=None):
    return rejudge.rejudge_artifact(
        artifact,
        judge_fn=judge_fn,
        seed=seed,
        source_path=(tmp_path or "/tmp") and "/tmp/source.json",
        source_sha256="deadbeef",
        now=_NOW,
    )


def test_断链未打分的题补评后重新进入聚合():
    artifact = _two_case_artifact()
    # 补评前：q1 因基线未打分而 unusable，聚合只剩 q2。
    assert artifact["aggregates"]["kb-rag"]["questions_usable"] == 1
    assert artifact["aggregates"]["kb-rag"]["questions_total"] == 2

    result = _run(artifact, lambda q, a: {**_judged(3), "provider": "zhipu"})

    assert result["aggregates"]["kb-rag"]["questions_usable"] == 2
    # q1: 关断 10 − 基线 15 = −5；q2: 10 − 15 = −5 → 边际贡献 +5
    assert result["aggregates"]["kb-rag"]["marginal_contribution_total"] == 5.0
    assert [r["case_id"] for r in result["rejudged"]] == ["q1"]
    assert result["rejudged"][0]["provider"] == "zhipu"


def test_已打分的行不重评():
    artifact = _two_case_artifact()
    before = json.dumps(artifact["answers"][1]["judge"], sort_keys=True)

    calls: list[str] = []

    def _judge(question, answer):
        calls.append(question.case_id)
        return {**_judged(4), "provider": "zhipu"}

    result = _run(artifact, _judge)

    assert calls == ["q1"], "只应补评那份未打分的"
    assert json.dumps(result["answers"][1]["judge"], sort_keys=True) == before


def test_答案正文不被改写():
    artifact = _two_case_artifact()
    originals = [rec["answer"] for rec in artifact["answers"]]

    result = _run(artifact, lambda q, a: {**_judged(3), "provider": "zhipu"})

    assert [rec["answer"] for rec in result["answers"]] == originals


def test_正文被改写时不变量断言炸开():
    """直接压那层断言：调用路径现在碰不到答案，但断言得真的会拦。

    只测端到端「答案没变」是假门禁——代码里本来就没人改它，断言删掉照样绿。
    """

    answers = [_answer("baseline", "q1", _judged(3))]
    before = {0: rejudge._sha256_text(str(answers[0]["answer"]))}

    rejudge.assert_only_judge_changed(answers, before, {})  # 未动 → 不炸

    answers[0]["answer"] = "被换掉的答案"
    with pytest.raises(SystemExit, match="补评只补 judge"):
        rejudge.assert_only_judge_changed(answers, before, {})


def test_既有分数被改动时不变量断言炸开():
    answers = [_answer("baseline", "q1", _judged(3))]
    before = {0: rejudge._sha256_text(str(answers[0]["answer"]))}
    judged = {0: json.dumps(answers[0]["judge"], ensure_ascii=False, sort_keys=True)}

    answers[0]["judge"] = _judged(4)
    with pytest.raises(SystemExit, match="只碰未打分的行"):
        rejudge.assert_only_judge_changed(answers, before, judged)


def test_答案臂失败的行不送评():
    """ok=False 但**正文非空**——run_ask 对「答案过短」正是这个返回形状。

    这类行是 harness 判过的废答案，补评它等于把废答案洗成读数；缺口只能重跑 ask。
    夹具必须复刻真实失败形状：早先版本把正文写成空串，结果被「正文为空就跳过」
    那条先兜住，这条守门断言删掉测试照样绿（变异测试抓到的假门禁）。
    """

    answers = [
        _answer(
            "baseline",
            "q1",
            {"scored": False, "reason": "答案臂失败，未送评"},
            ok=False,
            answer="exit=1 只吐了半句就断了",
        ),
        _answer("baseline", "q2", _judged(3)),
        _answer("kb-rag", "q1", _judged(2)),
        _answer("kb-rag", "q2", _judged(2)),
    ]
    artifact = _artifact(answers, ["q1", "q2"])

    calls: list[str] = []
    result = _run(artifact, lambda q, a: calls.append(q.case_id) or _judged(3))

    assert calls == []
    assert result["rejudged"] == []
    assert result["aggregates"]["kb-rag"]["questions_usable"] == 1


def test_正文为空的行不送评():
    """另一条独立守门：ok=True 但正文空（判官拿不到东西评）。"""

    answers = [
        _answer("baseline", "q1", _unscored(), answer=""),
        _answer("baseline", "q2", _judged(3)),
        _answer("kb-rag", "q1", _judged(2)),
        _answer("kb-rag", "q2", _judged(2)),
    ]
    artifact = _artifact(answers, ["q1", "q2"])

    calls: list[str] = []
    _run(artifact, lambda q, a: calls.append(q.case_id) or _judged(3))

    assert calls == []


def test_补评再失败仍记未打分不编造分数():
    artifact = _two_case_artifact()

    result = _run(artifact, lambda q, a: {"scored": False, "reason": "judge 输出无法解析"})

    assert result["rejudged"] == []
    assert [r["case_id"] for r in result["still_unscored"]] == ["q1"]
    assert result["still_unscored"][0]["rejudge_reason"] == "judge 输出无法解析"
    judge = result["answers"][0]["judge"]
    assert judge["scored"] is False
    assert judge["rejudge_attempted"] is True
    # 聚合读数没有因为「试过了」就变好
    assert result["aggregates"]["kb-rag"]["questions_usable"] == 1


def test_基线绝对分只统计已打分的题并带样本量():
    artifact = _two_case_artifact()

    before = rejudge.baseline_absolute(artifact["answers"])
    assert before == {
        "mean_total": 15.0,
        "questions_scored": 1,
        "questions_total": 2,
        "by_dim": {d: 3.0 for d in before["by_dim"]},
        "max_total": 20,
    }

    result = _run(artifact, lambda q, a: {**_judged(4), "provider": "zhipu"})
    after = result["baseline_absolute"]
    assert after["questions_scored"] == 2
    assert after["mean_total"] == 17.5  # (15 + 20) / 2


def test_输出指向原文件时拒绝执行(tmp_path):
    source = tmp_path / "run.json"
    source.write_text(json.dumps(_two_case_artifact(), ensure_ascii=False), encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        rejudge.main(["--run", str(source), "--output", str(source)])

    assert "不可覆盖" in str(excinfo.value)


def test_dry_run_不写文件不调_llm(tmp_path, capsys):
    source = tmp_path / "run.json"
    source.write_text(json.dumps(_two_case_artifact(), ensure_ascii=False), encoding="utf-8")

    assert rejudge.main(["--run", str(source), "--dry-run"]) == 0

    assert not (tmp_path / "run-rejudge.json").exists()
    assert "待补评 1 份" in capsys.readouterr().out


def test_收据能被_json_序列化_provider_是数据类也不炸():
    """真实 provider 是 LLMProvider 数据类，不是字符串。

    首版桩回的是字符串 "zhipu"，测试全绿；真跑时 7 次判官调用都完成了，倒在最后
    json.dumps ——钱花了、收据没写出来。夹具比现实简单，测出来的绿就是假的。
    """

    artifact = _two_case_artifact()
    fake_provider = SimpleNamespace(name="zhipu", model="glm-5.3", base_url="https://x")

    result = _run(artifact, lambda q, a: {**_judged(3), "provider": fake_provider})

    json.dumps(result, ensure_ascii=False)  # 不炸即通过
    assert result["rejudged"][0]["provider"] == "zhipu/glm-5.3"
    assert result["answers"][0]["judge"]["provider"] == "zhipu/glm-5.3"


def test_provider_label_压成身份串():
    assert provider_label(SimpleNamespace(name="zhipu", model="glm-5.3")) == "zhipu/glm-5.3"
    assert provider_label(None) is None
    assert provider_label("zhipu") == "zhipu"


def test_收据登记补评来源与_judge_连续性():
    artifact = _two_case_artifact()

    result = _run(artifact, lambda q, a: {**_judged(3), "provider": "zhipu"})

    assert result["kind"] == "quality_ablation_rejudge"
    assert result["source_sha256"] == "deadbeef"
    assert result["source_generated_at"] == "2026-08-26T14:35:58+00:00"
    assert result["generated_at"] == _NOW.isoformat()
    assert "zhipu" in result["judge_continuity"]
    # 修正前的读数留在收据里，改了什么可自证
    assert result["aggregates_before"]["kb-rag"]["questions_usable"] == 1
