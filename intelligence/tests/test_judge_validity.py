"""判官身份与校准有效性的纯合同测试（plans/2026-09-14-judge-calibration-validity.md §5 V1-V8）。

**不调模型、不读文件、不看环境**：每条用例只改正常夹具的一处，断言资格结果。
「只改一处」是这组测试的全部价值——同时改两处就分不清是哪一条门在拦。
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

import pytest

from intelligence.eval.judge_validity import (
    FAMILY_TABLE_VERSION,
    KNOWN_FAMILIES,
    REASON_ANSWER_BINDING_MISMATCH,
    REASON_BATCH_EXPIRED,
    REASON_CALIBRATION_BINDING_MISMATCH,
    REASON_CALIBRATION_INCOMPLETE,
    REASON_CALIBRATION_STALE,
    REASON_COVERAGE_INCOMPLETE,
    REASON_JUDGE_IDENTITY_MISMATCH,
    REASON_JUDGE_IDENTITY_UNKNOWN,
    REASON_JUDGE_NOT_INDEPENDENT,
    REASON_JUDGE_SPEC_MISMATCH,
    REASON_MANIFEST_MISMATCH,
    REASON_NOISE_FLOOR_INVALID,
    REASON_SCHEMA_UNSUPPORTED,
    REASON_WRITER_IDENTITY_UNKNOWN,
    canonical_json,
    canonical_sha256,
    judge_spec_sha256,
    resolve_family,
    validate_judging_batch,
)

_OPENED = datetime(2026, 9, 14, 0, 0, tzinfo=timezone.utc)
_EXPIRES = _OPENED + timedelta(seconds=3600)
_NOW = _OPENED + timedelta(seconds=60)

_JUDGE_SPEC = {
    "requested_model": "grok-4",
    "allowed_reported_models": ["grok-4"],
    "family_table_version": FAMILY_TABLE_VERSION,
    "endpoint_id": "xai-prod",
    "transport": "http",
    "rubric_label": "v3-veto-split",
    "rubric_text_sha256": "rubric-body-sha",
    "temperature": 0.0,
    "max_output_tokens": 1024,
    "truncation": {"algo": "head-tail-v1", "limit": 8000},
    "retry_policy": {"json_retry_prompt_sha256": "retry-sha", "max_attempts": 2},
}
_SPEC_SHA = judge_spec_sha256(_JUDGE_SPEC)

# 校准：两份不同文本、每份两次。c1 有散布、c2 零散布 → sd_judging=1.0
_CAL_TEXTS = {"c1": "sha-c1", "c2": "sha-c2"}
_CAL_TOTALS = {"c1": [13.0, 15.0], "c2": [12.0, 12.0]}
_EXPECTED_SD_DELTA = round(math.sqrt(1.0) * math.sqrt(2), 4)  # 1.4142


def _attempt(attempt_id: str, *, reported: str | None = "grok-4", state: str = "reported",
             status: str = "success") -> dict:
    return {
        "attempt_id": attempt_id,
        "status": status,
        "identity_state": state,
        "requested_model": "grok-4",
        "reported_model": reported,
        "endpoint_id": "xai-prod",
        "transport": "http",
        "finished_at": _NOW.isoformat(),
    }


def _answer(case_id: str, arm: str, *, total: int = 15, writer=("anthropic",),
            attempts=None, judge_spec_sha: str | None = None) -> dict:
    aid = f"{case_id}/{arm}"
    attempts = attempts if attempts is not None else [_attempt(f"a-{aid}")]
    return {
        "answer_id": aid,
        "case_id": case_id,
        "arm": arm,
        "ok": True,
        "answer_sha256": f"ans-{aid}",
        "judge_input_sha256": f"in-{aid}",
        "writer_provenance": {"families": list(writer), "unknown": False,
                              "receipt_sha256": f"wp-{aid}"},
        "attempts": attempts,
        "judge": {
            "scored": True,
            "total": total,
            "judge_spec_sha256": judge_spec_sha or _SPEC_SHA,
            "attempt_ref": {"call_id": f"c-{aid}", "attempt_id": attempts[0]["attempt_id"]},
        },
    }


def _fixture(*, state: str = "sealed") -> tuple[list[dict], dict, dict]:
    """完整 v2 正常夹具：两题两臂、冻结 writer 家族、同一 judge、每题两次校准。"""

    answers = [
        _answer("q1", "baseline", total=15),
        _answer("q1", "kb-rag", total=12),
        _answer("q2", "baseline", total=14),
        _answer("q2", "kb-rag", total=11),
    ]
    run_manifest = {
        "schema_version": 2,
        "batch_id": "batch-1",
        "source_sha256": "src-sha",
        "cases": [
            {"case_id": "q1", "arms": ["baseline", "kb-rag"]},
            {"case_id": "q2", "arms": ["baseline", "kb-rag"]},
        ],
        "judge_spec": _JUDGE_SPEC,
        "judge_spec_sha256": _SPEC_SHA,
        "calibration_plan": {"texts": ["c1", "c2"], "repeats_per_text": 2,
                             "include_first_pass": True},
        "retry_budget": 4,
        "opened_at": _OPENED.isoformat(),
        "expires_at": _EXPIRES.isoformat(),
        "denominators": {"n_total": 4},
        "exclusion_rules": [],
    }
    answer_manifest = {
        "schema_version": 2,
        "batch_id": "batch-1",
        "run_manifest_sha256": canonical_sha256(run_manifest),
        "answer_sha256_by_id": {a["answer_id"]: a["answer_sha256"] for a in answers},
        "calibration_texts": dict(_CAL_TEXTS),
        "sealed_at": _NOW.isoformat(),
        "state": state,
    }
    calibration = {
        "batch_id": "batch-1",
        "judge_spec_sha256": _SPEC_SHA,
        "calibration_sha256": "cal-sha",
        "repeats": [
            {"text_id": tid, "text_sha256": _CAL_TEXTS[tid], "total": total,
             "attempt_ref": {"attempt_id": f"cal-{tid}-{i}"}, "finished_at": _NOW.isoformat()}
            for tid, totals in _CAL_TOTALS.items()
            for i, total in enumerate(totals)
        ],
        "noise_floor": {"measured": True, "sigma": 2.0,
                        "sd_delta_single_question": _EXPECTED_SD_DELTA},
    }
    return answers, calibration, {"run_manifest": run_manifest,
                                  "answer_manifest": answer_manifest}


def _validate(answers, calibration, manifest, *, now=_NOW):
    return validate_judging_batch(answers, calibration, manifest, now=now)


# --------------------------------------------------------------------------- #
# 正例与基础设施
# --------------------------------------------------------------------------- #


def test_正常夹具取得有效资格():
    result = _validate(*_fixture())

    assert result.valid, result.reason_codes
    assert result.reason_codes == ()
    assert result.counts["registered_arms"] == 4
    assert result.counts["scored"] == 4


def test_规范哈希拒绝非有限数():
    """NaN 不许一路哈希一致地穿过绑定校验——在序列化这步就炸。"""

    with pytest.raises(ValueError):
        canonical_json({"sigma": float("nan")})
    # 键排序与固定分隔符：同一对象的两种写法必须同哈希
    assert canonical_sha256({"b": 1, "a": 2}) == canonical_sha256({"a": 2, "b": 1})
    assert canonical_json({"a": 1}) == '{"a":1}'


def test_家族解析认不出就是unknown不是异构():
    assert resolve_family("grok-4") == "xai"
    assert resolve_family("gpt-4.1-mini") == "openai"
    assert resolve_family("judge/grok-test") == "xai"
    # 陌生别名 → None。两个陌生字符串不相等不能推出异构。
    assert resolve_family("mystery-judge-a") is None
    assert resolve_family("mystery-judge-b") is None
    assert "xai" in KNOWN_FAMILIES


# --------------------------------------------------------------------------- #
# V1-V8
# --------------------------------------------------------------------------- #


def test_V1_配置没变但响应换模型():
    answers, calibration, manifest = _fixture()
    bad = _attempt("a-q1/kb-rag", reported="gpt-4.1-mini")
    answers[1]["attempts"] = [bad]

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_JUDGE_IDENTITY_MISMATCH in result.reason_codes
    assert "q1/kb-rag" in result.invalid_answer_ids
    # attempt 保留：门是拦结论，不是删证据
    assert answers[1]["attempts"] == [bad]


def test_V2_成功但没报结构化模型():
    answers, calibration, manifest = _fixture()
    answers[1]["attempts"] = [
        _attempt("a-q1/kb-rag", reported=None, state="unreported")
    ]

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_JUDGE_IDENTITY_UNKNOWN in result.reason_codes
    # 不能拿 requested_model 冒充：它还在记录里，但没被当成身份
    assert answers[1]["attempts"][0]["requested_model"] == "grok-4"
    assert REASON_JUDGE_IDENTITY_MISMATCH not in result.reason_codes


def test_V3_补评换判官源旧底仍在():
    answers, calibration, manifest = _fixture()
    # 规格换了（新判官），旧底原样留着
    calibration["judge_spec_sha256"] = "another-spec-sha"

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_CALIBRATION_STALE in result.reason_codes
    # 旧底留作证据，没有被抹掉
    assert calibration["noise_floor"]["measured"] is True


def test_V4_源writer与判官同族按源拦截():
    answers, calibration, manifest = _fixture()
    # 当前环境 writer 是 anthropic，但**源** writer 是 xai —— 与判官同族
    answers[1]["writer_provenance"]["families"] = ["xai"]

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_JUDGE_NOT_INDEPENDENT in result.reason_codes
    assert "q1/kb-rag" in result.invalid_answer_ids


def test_V4b_源writer不可考是unknown不是独立():
    answers, calibration, manifest = _fixture()
    answers[1]["writer_provenance"] = {"unknown": True}

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_WRITER_IDENTITY_UNKNOWN in result.reason_codes


def test_V5_rubric标签不变但截断规则改了():
    answers, calibration, manifest = _fixture()
    spec = dict(_JUDGE_SPEC, truncation={"algo": "head-tail-v1", "limit": 4000})
    manifest["run_manifest"]["judge_spec"] = spec
    # 标签没动，哈希却必须变
    assert spec["rubric_label"] == _JUDGE_SPEC["rubric_label"]
    assert judge_spec_sha256(spec) != _SPEC_SHA

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_JUDGE_SPEC_MISMATCH in result.reason_codes


def test_V6_校准totals合法但文本哈希对不上():
    answers, calibration, manifest = _fixture()
    calibration["repeats"][0]["text_sha256"] = "sha-of-some-other-text"

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_CALIBRATION_BINDING_MISMATCH in result.reason_codes


def test_V6b_校准引用别的批次():
    answers, calibration, manifest = _fixture()
    calibration["batch_id"] = "batch-2"

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_CALIBRATION_BINDING_MISMATCH in result.reason_codes


def test_V7_旧v1收据可读但不能出结论():
    answers, calibration, manifest = _fixture()
    manifest["run_manifest"]["schema_version"] = 1

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_SCHEMA_UNSUPPORTED in result.reason_codes


def test_V7b_陌生模型家族仍是unknown():
    answers, calibration, manifest = _fixture()
    spec = dict(_JUDGE_SPEC, allowed_reported_models=["mystery-judge-a"],
                requested_model="mystery-judge-a")
    manifest["run_manifest"]["judge_spec"] = spec
    manifest["run_manifest"]["judge_spec_sha256"] = judge_spec_sha256(spec)
    for a in answers:
        a["judge"]["judge_spec_sha256"] = judge_spec_sha256(spec)
        a["attempts"] = [_attempt(a["attempts"][0]["attempt_id"], reported="mystery-judge-a")]
        a["judge"]["attempt_ref"]["attempt_id"] = a["attempts"][0]["attempt_id"]
    calibration["judge_spec_sha256"] = judge_spec_sha256(spec)

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_JUDGE_IDENTITY_UNKNOWN in result.reason_codes


@pytest.mark.parametrize(
    "bad",
    [
        {"measured": True, "sigma": 2.0},  # 缺 sd_delta
        {"measured": True, "sigma": 2.0, "sd_delta_single_question": float("nan")},
        {"measured": True, "sigma": 2.0, "sd_delta_single_question": float("inf")},
        {"measured": True, "sigma": 2.0, "sd_delta_single_question": -1.0},
        {"measured": True, "sigma": 0, "sd_delta_single_question": 1.4142},
        {"measured": False, "reason": "本轮未实测"},
    ],
)
def test_V8_底值缺失或非有限或非正sigma一律无效(bad):
    answers, calibration, manifest = _fixture()
    calibration["noise_floor"] = bad

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_NOISE_FLOOR_INVALID in result.reason_codes


def test_V8b_真实零方差不被过度拦截():
    """同文本重复恰好同分是**重算出来的零**，与「字段缺失当成零」不是一回事。"""

    answers, calibration, manifest = _fixture()
    for rep in calibration["repeats"]:
        rep["total"] = 13.0
    calibration["noise_floor"] = {"measured": True, "sigma": 2.0,
                                  "sd_delta_single_question": 0.0}

    result = _validate(answers, calibration, manifest)

    assert result.valid, result.reason_codes


def test_V8c_存量底与重算不一致时无效():
    answers, calibration, manifest = _fixture()
    calibration["noise_floor"]["sd_delta_single_question"] = 0.0001  # 编的

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_NOISE_FLOOR_INVALID in result.reason_codes


# --------------------------------------------------------------------------- #
# §3.3-1 / §3.3-4 / §3.3-6 的结构与覆盖
# --------------------------------------------------------------------------- #


def test_删行不能换来更好的资格():
    answers, calibration, manifest = _fixture()
    answers.pop()  # 删掉 q2/kb-rag

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_MANIFEST_MISMATCH in result.reason_codes
    # 分母仍可核：预登记 4 臂，只到 3 份
    assert result.counts["registered_arms"] == 4
    assert result.counts["answers_present"] == 3


def test_改arm或重复case不能换来更好的资格():
    answers, calibration, manifest = _fixture()
    answers[3]["arm"] = "kb-rag"
    answers[3]["case_id"] = "q1"  # 与 answers[1] 重复

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_MANIFEST_MISMATCH in result.reason_codes


def test_替换答案正文会被哈希绑定发现():
    answers, calibration, manifest = _fixture()
    answers[0]["answer_sha256"] = "tampered"

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_ANSWER_BINDING_MISMATCH in result.reason_codes


def test_校准只有一份文本时不完整():
    answers, calibration, manifest = _fixture()
    manifest["run_manifest"]["calibration_plan"]["texts"] = ["c1"]
    manifest["answer_manifest"]["run_manifest_sha256"] = canonical_sha256(
        manifest["run_manifest"]
    )

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_CALIBRATION_INCOMPLETE in result.reason_codes


def test_计划内的重复缺失不得挑成功样本凑底():
    answers, calibration, manifest = _fixture()
    calibration["repeats"] = [r for r in calibration["repeats"] if r["text_id"] != "c2"][:1]

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_CALIBRATION_INCOMPLETE in result.reason_codes


def test_有题未评分时阻断该批次质量结论但保留交付数():
    answers, calibration, manifest = _fixture()
    answers[3]["judge"] = {"scored": False, "reason": "外部判官最终失败"}

    result = _validate(answers, calibration, manifest)

    assert not result.valid
    assert REASON_COVERAGE_INCOMPLETE in result.reason_codes
    # 产品仍然交付了 4 份：失败不因身份门重归因为实验条件失效
    assert result.counts["delivered"] == 4
    assert result.counts["scored"] == 3


def test_open批次过期后不得再取得资格():
    answers, calibration, manifest = _fixture(state="open")

    late = _EXPIRES + timedelta(seconds=1)
    result = _validate(answers, calibration, manifest, now=late)

    assert not result.valid
    assert REASON_BATCH_EXPIRED in result.reason_codes


def test_已封存收据不因读取日期变晚而失效():
    """期限约束的是采集和追加；sealed 收据日后再读按当时证据判断（§3.2）。"""

    answers, calibration, manifest = _fixture(state="sealed")

    much_later = _EXPIRES + timedelta(days=30)
    result = _validate(answers, calibration, manifest, now=much_later)

    assert result.valid, result.reason_codes


def test_结果可序列化进收据():
    result = _validate(*_fixture())

    payload = json.loads(json.dumps(result.as_dict(), ensure_ascii=False))
    assert payload["valid"] is True
    assert payload["reason_codes"] == []
