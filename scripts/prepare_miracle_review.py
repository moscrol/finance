#!/usr/bin/env python3
"""Publish the bounded miracle remediation reviewed on 2026-09-22.

Two exact passages correct themes/hardness; two publisher signatures are
retracted. The remaining manifest batch is quarantined, not semantically guessed.
Every source event remains immutable. A changed batch requires a new review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.services.opinion_events import STORE_RELPATH, read_originals, record_hash  # noqa: E402
from scripts.review_opinion_events import publish  # noqa: E402

REVIEWED = {
    "oce-3c2b2394fb": {
        "quote": "）产能建设：①九州一轨：投资建设金刚石芯片基板建设项目（一期），产品覆盖单晶、多晶金刚石片，#项目部分分包合同已经落地。",
        "action": "replace", "layer": "L3",
        "reason": "原主题环保来自旧主营标签；本段是金刚石散热。分包建设合同不等于产品订单；未读一手披露，只保留卖方转述。",
    },
    "oce-2bcb7bd2a1": {
        "quote": "③国机精工：金刚石铜、单晶、多晶金刚石均已向重点客户送样验证，#年内有望获小批量订单。",
        "action": "replace", "layer": "L4",
        "reason": "原主题精密轴承错配；本段是金刚石散热。送样不等于订单，年内有望是预测；未独立核验，撤销硬证据标签。",
    },
    "oce-170324cda2": {
        "quote": "风电板块上涨点评：深远海政策有一定进展，落地确定性提升【中信建投电新】",
        "action": "retract", "reason": "中信建投电新是观点署名，不是这条风电观点的投资标的；撤回券商主体事件，不据此补造风电事件。",
    },
    "oce-6c7eaee3a8": {
        "quote": "【国泰海通建材】玻纤 Q3业绩弹性估算",
        "action": "retract", "reason": "国泰海通建材是卖方署名，不是该段玻纤业绩估算的主体；撤回券商主体事件。",
    },
}


def prepare(wiki: Path, manifest: Path) -> dict:
    pastes = json.loads(manifest.read_text(encoding="utf-8"))["pastes"]
    by_date = {p["report_date"]: p for p in pastes}
    originals = read_originals(wiki / STORE_RELPATH)
    batch = [r for r in originals if r.get("source") == "调研纪要miracle" and r.get("report_date") in by_date]
    if len(batch) != 475 or len({r["event_id"] for r in batch}) != 475:
        raise ValueError("review scope changed: expected 475 distinct events; re-review required")
    if not set(REVIEWED) <= {r["event_id"] for r in batch}:
        raise ValueError("reviewed events missing")
    corrections = []
    for original in batch:
        paste = by_date[original["report_date"]]
        rel = paste["verbatim_path"]
        data = (wiki / rel).read_bytes()
        text = data.decode("utf-8")
        review = REVIEWED.get(original["event_id"])
        if review:
            if original["report_date"] != "2026-09-11" or text.count(review["quote"]) != 1:
                raise ValueError("reviewed quote no longer uniquely identifies its source")
            start = text.index(review["quote"])
            end = start + len(review["quote"])
            action, reason = review["action"], review["reason"]
        else:
            start, end = 0, len(text)
            action = "quarantine"
            reason = "本批抽取存在空主张、旧主营主题和证据硬化风险；此记录尚未逐条复核。全文锚点仅绑定来源，不宣称已定位公司主张。"
        correction = {
            "event_id": original["event_id"], "base_sha256": record_hash(original), "supersedes": None,
            "action": action, "reason": reason,
            "raw_ref": {"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "start": start, "end": end},
        }
        if action == "replace":
            correction["replacement"] = {
                "concept": "金刚石散热", "term": "金刚石散热", "claim_summary": review["quote"],
                "hardness": "软推演", "hard_evidence": [], "soft_claims": [review["quote"]], "catalysts": [],
                "evidence_layer": review["layer"], "date_status": "inferred_unconfirmed",
                "verification_status": "unverified",
            }
        corrections.append(correction)
    return {"batch_id": "20260922-miracle-consumption-review-v1", "corrections": corrections}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    proposal = prepare(args.wiki, args.manifest)
    result = {"batch_id": proposal["batch_id"], "actions": dict(Counter(c["action"] for c in proposal["corrections"]))}
    if args.apply:
        path, created = publish(args.wiki, proposal)
        result.update(path=str(path), created=created)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
