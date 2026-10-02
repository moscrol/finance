"""Offline binding tests. No model gold or release exemptions are supplied."""

from copy import deepcopy
import json
import socket

import pytest

from scripts.review_probes.quantity_role_contract import (
    ContractError,
    check_review,
    main,
    prepare_review,
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("network forbidden")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    from intelligence.services import llm_http_transport

    monkeypatch.setattr(llm_http_transport, "urlopen", deny)


def request(text="若上述三日均满足条件，才作此定义。", days=3):
    return {
        "question": "比较历史记录",
        "runtime_context": {"today": "2026-10-01"},
        "sentences": [{"index": 1, "text": text}],
        "evidence_registry": [
            {
                "evidence_id": f"E{i}",
                "source_date": f"2026-09-{20 + i:02}",
                "detail": f"observation {i}",
            }
            for i in range(1, days + 1)
        ],
        "output_bindings": [
            {
                "output_id": "assessment",
                "evidence_ids": [f"E{i}" for i in range(1, days + 1)],
            }
        ],
    }


def prepared(req=None, token="三日", nonce="a" * 32):
    req = request() if req is None else req
    start = req["sentences"][0]["text"].index(token)
    return prepare_review(
        req,
        [{"sentence_index": 1, "start": start, "end": start + len(token)}],
        nonce=nonce,
    )


def response(bundle, role="historical_set_cardinality"):
    evidence = bundle["native_request"]["evidence_registry"]
    historical = role == "historical_set_cardinality"
    return {
        "schema": "quantity_role_response_v1",
        "review_id": bundle["review_id"],
        "grounding_report": {
            "passed": True,
            "rejected_sentence_indexes": [],
            "issues": [],
        },
        "quantity_roles": [
            {
                "target_id": t["target_id"],
                "role": role,
                "evidence_ids": [e["evidence_id"] for e in evidence]
                if historical
                else [],
                "historical_source_dates": [e["source_date"] for e in evidence]
                if historical
                else [],
                "historical_cardinality": len(evidence) if historical else None,
                "reason": "synthetic role assertion for binding tests only",
            }
            for t in bundle["targets"]
        ],
    }


def checked(bundle, raw):
    return check_review(bundle, raw, current_request=bundle["native_request"])


@pytest.mark.parametrize(
    "days,token", [(1, "一日"), (2, "两日"), (3, "三日"), (4, "4日")]
)
def test_general_cardinality_binding_is_diagnostic_only(days, token):
    b = prepared(request(f"若上述{token}都满足条件。", days), token)
    out = checked(b, response(b))
    assert out["diagnostic_only"] is True
    assert out["release_authorized"] is False
    assert out["model_identity_verified"] is False
    assert out["native_report"] == response(b)["grounding_report"]
    assert out["annotations"][0]["text"] == token


def test_future_role_is_recorded_without_historical_authority():
    b = prepared(request("若未来连续三日满足条件。"))
    out = checked(b, response(b, "future_duration_condition"))
    assert out["annotations"][0]["historical_cardinality"] is None
    assert not out["release_authorized"]


def test_even_forged_historical_role_on_future_text_is_not_release_proof():
    b = prepared(request("若未来连续三日满足条件。"))
    # Structure alone cannot prove that the model assigned the RIGHT role.
    out = checked(b, response(b))
    assert out["diagnostic_only"] and not out["release_authorized"]


@pytest.mark.parametrize("role", ["other", "unknown"])
def test_uncertainty_is_recorded_not_treated_as_permission(role):
    b = prepared()
    out = checked(b, response(b, role))
    assert not out["release_authorized"]


def test_existing_native_rejection_is_preserved():
    b = prepared()
    r = response(b)
    r["grounding_report"] = {
        "passed": False,
        "rejected_sentence_indexes": [1],
        "issues": ["other unsupported claim"],
    }
    assert checked(b, r)["native_report"] == r["grounding_report"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("passed", "true"),
        ("passed", False),
        ("rejected_sentence_indexes", [9]),
        ("unregistered_extra", []),
    ],
)
def test_native_core_stays_strict(field, value):
    b = prepared()
    r = response(b)
    r["grounding_report"][field] = value
    with pytest.raises(ContractError):
        checked(b, r)


def test_unbound_r21_style_shadow_cannot_be_promoted_to_native_report():
    b = prepared()
    with pytest.raises(ContractError):
        checked(
            b,
            {
                "schema": "quantity_role_shadow_v1",
                "sentence_index": 1,
                "role": "historical_set_cardinality",
            },
        )


def test_nonce_blocks_same_text_from_another_dispatch():
    a = prepared()
    b = prepared(nonce="b" * 32)
    assert a["review_id"] != b["review_id"]
    with pytest.raises(ContractError):
        checked(b, response(a))


@pytest.mark.parametrize(
    "part", ["sentence", "question", "date_context", "evidence", "binding"]
)
def test_current_context_drift_rejects_receipt(part):
    b = prepared()
    now = deepcopy(b["native_request"])
    if part == "sentence":
        now["sentences"][0]["text"] = "若未来连续三日满足条件。"
    elif part == "question":
        now["question"] = "另一个用户问题"
    elif part == "date_context":
        now["runtime_context"]["today"] = "2026-10-02"
    elif part == "evidence":
        now["evidence_registry"][0]["detail"] = "changed evidence"
    else:
        now["output_bindings"] = []
    with pytest.raises(ContractError):
        check_review(b, response(b), current_request=now)


@pytest.mark.parametrize(
    "field,value",
    [
        ("start", True),
        ("start", -1),
        ("end", 999),
        ("end", 0),
        ("sentence_index", True),
        ("sentence_index", 2),
    ],
)
def test_invalid_spans_are_rejected(field, value):
    span = {"sentence_index": 1, "start": 3, "end": 5}
    span[field] = value
    with pytest.raises(ContractError):
        prepare_review(request(), [span])


def test_each_repeated_occurrence_has_separate_binding():
    req = request("若三日满足条件，才叫三日达标。")
    text = req["sentences"][0]["text"]
    a = text.index("三日")
    z = text.rindex("三日")
    spans = [{"sentence_index": 1, "start": s, "end": s + 2} for s in (a, z)]
    b = prepare_review(req, spans)
    assert len(set(t["target_id"] for t in b["targets"])) == 2
    assert len(checked(b, response(b))["annotations"]) == 2
    with pytest.raises(ContractError):
        prepare_review(req, [spans[0], spans[0]])
    r = response(b)
    r["quantity_roles"].pop()
    with pytest.raises(ContractError):
        checked(b, r)


@pytest.mark.parametrize(
    "field,value",
    [
        ("evidence_ids", ["E999"]),
        ("evidence_ids", ["E1", "E1"]),
        ("historical_source_dates", ["2026-09-21", "2026-09-21", "2026-09-21"]),
        ("historical_source_dates", ["2026-09-21", "2026-09-22", "2026-09-31"]),
        ("historical_source_dates", ["2026-09-21", "2026-09-22", "2026-09-24"]),
        ("historical_cardinality", True),
        ("historical_cardinality", 2),
        ("role", "whitelisted"),
        ("reason", ""),
        ("target_id", "q999"),
        ("release_authorized", True),
    ],
)
def test_bad_role_records_fail_closed(field, value):
    b = prepared()
    r = response(b)
    r["quantity_roles"][0][field] = value
    with pytest.raises(ContractError):
        checked(b, r)


def test_future_cannot_claim_historical_cardinality_in_contract():
    b = prepared()
    r = response(b, "future_duration_condition")
    r["quantity_roles"][0]["historical_cardinality"] = 3
    with pytest.raises(ContractError):
        checked(b, r)


def test_duplicate_and_missing_role_rows_reject_whole_sidecar():
    b = prepared()
    r = response(b)
    r["quantity_roles"] *= 2
    with pytest.raises(ContractError):
        checked(b, r)
    r["quantity_roles"] = []
    with pytest.raises(ContractError):
        checked(b, r)


def test_bundle_mutation_is_detected():
    b = prepared()
    r = response(b)
    b["targets"][0]["text"] = "未来三日"
    with pytest.raises(ContractError):
        checked(b, r)


def test_prepare_does_not_hold_mutable_caller_objects():
    req = request()
    b = prepared(req)
    req["sentences"][0]["text"] = "changed"
    assert b["native_request"]["sentences"][0]["text"] != "changed"


@pytest.mark.parametrize("part", ["sentences", "evidence_registry"])
def test_duplicate_native_indexes_are_rejected(part):
    req = request()
    req[part].append(deepcopy(req[part][0]))
    with pytest.raises(ContractError):
        prepared(req)


def test_raw_native_parser_does_not_silently_accept_the_probe_envelope():
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier

    b = prepared()
    assert SemanticEpisodeVerifier._parse_report(response(b), 1) is None
    assert SemanticEpisodeVerifier._parse_report(
        response(b)["grounding_report"], 1
    ).passed


def test_production_numeric_mark_is_unchanged(monkeypatch):
    from intelligence.services import episode_semantic_verifier as sem, llm_refine
    from intelligence.services.research_contract import ResearchDeadline
    from intelligence.tests.test_episode_semantic_verifier import _structural, _judge

    monkeypatch.setenv(sem.NUMERIC_CONDITION_MARK_ENV, "1")
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "llm")
    monkeypatch.setattr(llm_refine, "judge_provider_chain", lambda: ())
    frame, verified = _structural(
        "若上述三日均满足条件，才作此定义。",
        detail="2026-09-21、2026-09-22、2026-09-23为历史记录。",
    )
    b = prepared()
    out = checked(b, response(b))
    actual = sem.SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert "待核" in actual.public_answer
    assert sem.numeric_condition_unsupported(verified)
    assert not out["release_authorized"]


def test_cli_refuses_overwrite_and_rejects_invalid_without_output(tmp_path):
    req = request()
    b = prepared(req)
    r = response(b)
    for name, obj in [("request", req), ("bundle", b), ("response", r)]:
        (tmp_path / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False))
    dest = tmp_path / "checked.json"
    args = [
        "check",
        "--bundle",
        str(tmp_path / "bundle.json"),
        "--response",
        str(tmp_path / "response.json"),
        "--current-request",
        str(tmp_path / "request.json"),
        "--out",
        str(dest),
    ]
    assert main(args) == 0
    old = dest.read_bytes()
    assert main(args) == 2 and dest.read_bytes() == old
    dest.unlink()
    r["review_id"] = "wrong"
    (tmp_path / "response.json").write_text(json.dumps(r))
    assert main(args) == 2 and not dest.exists()


def test_deletion_and_renumbering_require_a_fresh_review():
    req = request()
    req["sentences"].insert(0, {"index": 1, "text": "其他陈述。"})
    req["sentences"][1]["index"] = 2
    text = req["sentences"][1]["text"]
    start = text.index("三日")
    bundle = prepare_review(
        req, [{"sentence_index": 2, "start": start, "end": start + 2}]
    )
    current = deepcopy(req)
    current["sentences"] = [{"index": 1, "text": text}]
    with pytest.raises(ContractError):
        check_review(bundle, response(bundle), current_request=current)


def test_delivery_annotation_does_not_silently_reuse_prior_receipt():
    bundle = prepared()
    current = deepcopy(bundle["native_request"])
    current["sentences"][0]["text"] += "（待核）"
    with pytest.raises(ContractError):
        check_review(bundle, response(bundle), current_request=current)


def test_date_count_binding_does_not_prove_numeral_interpretation():
    bundle = prepared(request("若上述四日满足条件。", days=3), token="四日")
    result = checked(bundle, response(bundle))
    # No natural-language numeral parser or semantic truth claim is hidden here.
    assert result["annotations"][0]["historical_cardinality"] == 3
    assert result["annotations"][0]["text"] == "四日"
    assert result["diagnostic_only"] and not result["release_authorized"]


def test_cli_prepare_is_exclusive_and_offline(tmp_path):
    req = request()
    text = req["sentences"][0]["text"]
    start = text.index("三日")
    (tmp_path / "request.json").write_text(json.dumps(req, ensure_ascii=False))
    (tmp_path / "spans.json").write_text(
        json.dumps([{"sentence_index": 1, "start": start, "end": start + 2}])
    )
    dest = tmp_path / "bundle.json"
    args = [
        "prepare",
        "--native-request",
        str(tmp_path / "request.json"),
        "--spans",
        str(tmp_path / "spans.json"),
        "--out",
        str(dest),
    ]
    assert main(args) == 0
    original = dest.read_bytes()
    assert main(args) == 2 and dest.read_bytes() == original
    bundle = json.loads(original)
    assert checked(bundle, response(bundle))["release_authorized"] is False


def test_response_cannot_add_release_authority():
    bundle = prepared()
    raw = response(bundle)
    raw["release_authorized"] = True
    with pytest.raises(ContractError):
        checked(bundle, raw)
