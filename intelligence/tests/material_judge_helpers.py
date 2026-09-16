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
             "reason": "离线夹具的逐句判断，不能代签真实语义支持。"}
            for row in request["material_claims"]
        ]
    return payload
