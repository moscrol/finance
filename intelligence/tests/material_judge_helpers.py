"""Explicit offline verdict fixtures, never evidence of live entailment quality."""


def material_judge_report(request, *, rejected=(), issues=()):
    payload = {
        "passed": not rejected,
        "rejected_sentence_indexes": list(rejected),
        "issues": list(issues),
    }
    if request.get("material_claims"):
        payload["material_claim_checks"] = [
            {"claim_id": row["claim_id"], "supported": row["sentence_index"] not in rejected,
             "reason": "离线夹具的逐句判断，不能代签真实语义支持。",
             "support_kind": ("unsupported" if row["sentence_index"] in rejected else
                              "bound_material" if row.get("material_anchors") else
                              "historical_quote" if row.get("old_answer_coordinate") else "nonfactual"),
             "anchor_indexes": ([] if row["sentence_index"] in rejected else list(range(1, len(row.get("material_anchors", ())) + 1)))}
            for row in request["material_claims"]
        ]
    if request.get("material_outputs"):
        payload["material_output_checks"] = [
            {"output_id": row["output_id"], "answered": row["state"] == "fulfilled",
             "answer_sentence_indexes": [s["index"] for s in row["candidate_sentences"]] if row["state"] == "fulfilled" else [],
             "reason": "离线夹具假定候选句已回答该题，不能代签真实完整性。"}
            for row in request["material_outputs"]
        ]
    return payload
