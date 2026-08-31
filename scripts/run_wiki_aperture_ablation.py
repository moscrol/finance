#!/usr/bin/env python3
"""Wiki 闭环三铲对照：L0 激活 → L1 检索页 → L2 盲评。

工单 ``docs/superpowers/specs/2026-08-30-wiki-aperture-ablation-workorder.md`` /
台账 ``R-20260830-06``。

顺序写死，不许倒：先预热，确认 A2 三铲都 ``executed=True`` 且无
``budget_exhausted``，再比页集合，最后才盲评答案。后两铲没跑的题整题作废，
不准写成「三铲没帮助」。可用题 <4 → 整单停在 L0，结论只能是「无资格」。

用法：
    python3 scripts/run_wiki_aperture_ablation.py --dry-run
    python3 scripts/run_wiki_aperture_ablation.py --phase l0l1
    python3 scripts/run_wiki_aperture_ablation.py
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import run_quality_ablation as qa  # noqa: E402

from intelligence.adapters.knowledge import KnowledgeAdapter  # noqa: E402
from intelligence.paths import default_paths  # noqa: E402
from intelligence.services import closed_loop_retrieval, kb_rag  # noqa: E402
from intelligence.services.entity_anchor import resolve_entity_anchor  # noqa: E402

LEDGER_ID = "R-20260831-01"
ARMS = (
    ("A0", "narrow"),
    ("A1", "narrow_broad"),
    ("A2", "all"),
)
INELIGIBLE = "现网预算撑不满三铲，质量对照无资格"
KEEP_NARROW = "默认勿吹三铲，考虑默认 narrow 或加预算"
KEEP_ALL = "预算够时三铲值得保留"
NO_SIGNIFICANT = "检索有/无增量，答案无显著差，保持现状"
FORBIDDEN_PHRASE = "三铲无用"


def latest_as_of(exports_dir: Path) -> str:
    dates: list[str] = []
    for path in exports_dir.glob("????-??-??-daily-agent.md"):
        stamp = path.name[:10]
        if stamp != "2026-07-22":
            dates.append(stamp)
    if not dates:
        raise SystemExit("❌ 找不到当日最新导出，禁止回退 2026-07-22")
    return max(dates)


def default_questions(as_of: str) -> tuple[qa.Question, ...]:
    return (
        qa.Question("theme-liquid-cooling", "液冷服务器现在处于什么阶段", as_of),
        qa.Question("shenling-order", "申菱环境液冷订单落地了没有", as_of),
        qa.Question("invic-piping", "英维克和液冷管路的关系", as_of),
        qa.Question("glass-vs-ceramic", "玻璃基板和陶瓷基板的区别", as_of),
        qa.Question("star50-support", "科创50支撑位在哪", as_of),
        qa.Question("zhongji-16t", "中际旭创和1.6T光模块的关系", as_of),
    )


EXPECTED_PAGES: dict[str, tuple[str, ...]] = {
    "theme-liquid-cooling": ("concepts/液冷服务器", "concepts/液冷"),
    "shenling-order": ("entities/申菱环境",),
    "invic-piping": ("entities/英维克", "concepts/液冷"),
    "glass-vs-ceramic": ("concepts/玻璃基板", "concepts/陶瓷基板"),
    "zhongji-16t": ("entities/中际旭创", "concepts/800G_1.6T光模块"),
}


def page_id_of(hit: object) -> str:
    raw = str(getattr(hit, "page_id", "") or "").strip()
    if raw and "/" in raw and not raw.endswith(".md"):
        return raw
    path = str(getattr(hit, "file_path", "") or "").replace("\\", "/")
    if path.startswith("wiki/"):
        path = path[5:]
    if path.endswith(".md"):
        path = path[:-3]
    return raw or path


def bucket_page_ids(items: list[object]) -> set[str]:
    return {page_id_of(getattr(item, "hit", item)) for item in items if page_id_of(getattr(item, "hit", item))}


def l0_activated(attempts: list[dict[str, Any]]) -> tuple[bool, str]:
    by_aperture: dict[str, list[dict[str, Any]]] = {"narrow": [], "broad": [], "counter": []}
    for item in attempts:
        aperture = str(item.get("aperture") or "")
        if aperture in by_aperture:
            by_aperture[aperture].append(item)
    missing = [
        name
        for name, rows in by_aperture.items()
        if not any(bool(row.get("executed")) for row in rows)
    ]
    exhausted = [
        str(row.get("aperture"))
        for row in attempts
        if row.get("status") == "budget_exhausted"
    ]
    if missing:
        return False, f"missing_executed:{','.join(missing)}"
    if exhausted:
        return False, f"budget_exhausted:{','.join(exhausted)}"
    return True, "ok"


def l1_delta(a0: set[str], a2: set[str]) -> dict[str, Any]:
    added = sorted(a2 - a0)
    dropped = sorted(a0 - a2)
    return {
        "added": added,
        "dropped": dropped,
        "added_n": len(added),
        "dropped_n": len(dropped),
    }


def hit_at_k(pages: list[str], expected: tuple[str, ...], k: int = 6) -> float | None:
    if not expected:
        return None
    window = set(pages[:k])
    return round(sum(1 for item in expected if item in window) / len(expected), 3)


def decide_conclusion(
    *,
    usable_n: int,
    crowding: bool,
    mean_delta_a2_minus_a0: float | None,
    a2_worse_than_a0_by_over_2: int,
    l2_ran: bool,
) -> dict[str, str]:
    if usable_n < 4:
        return {"code": "INELIGIBLE", "text": INELIGIBLE}
    if not l2_ran or mean_delta_a2_minus_a0 is None:
        return {
            "code": "NO_SIGNIFICANT",
            "text": NO_SIGNIFICANT,
            "note": "L2 未出分，不上线门缺答案分，不得写成三铲无用",
        }
    if (
        usable_n >= 4
        and mean_delta_a2_minus_a0 <= -1.0
        and crowding
    ):
        return {"code": "KEEP_NARROW", "text": KEEP_NARROW}
    if mean_delta_a2_minus_a0 >= 1.0 and not crowding:
        if usable_n == 6 and a2_worse_than_a0_by_over_2 > 2:
            return {
                "code": "NO_SIGNIFICANT",
                "text": NO_SIGNIFICANT,
                "note": "否决全面更好：可用仅6题且逐题A2低于A0超过2题",
            }
        return {"code": "KEEP_ALL", "text": KEEP_ALL}
    return {"code": "NO_SIGNIFICANT", "text": NO_SIGNIFICANT}


def _eval_env(extra: dict[str, str], *, wiki_seconds: float) -> dict[str, str]:
    env = {
        "PYTHONPATH": str(REPO),
        "ASK_EVIDENCE_JUDGE": "off",
        "ASK_WIKI_TOTAL_SECONDS": str(wiki_seconds),
    }
    env.update(extra)
    return env


def run_prewarm(kb_wiki: Path, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    status = kb_rag.prewarm(str(kb_wiki), timeout=timeout)
    elapsed = time.monotonic() - started
    payload = dict(status) if isinstance(status, dict) else {"status": status}
    payload["elapsed_sec"] = round(elapsed, 3)
    payload["ok"] = payload.get("state") == "ready"
    return payload


def _serialize_attempt(item: object) -> dict[str, Any]:
    return {
        "aperture": item.aperture,
        "query": item.query,
        "status": item.status,
        "hit_count": item.hit_count,
        "executed": item.executed,
    }


def run_l1_arm(
    question: qa.Question,
    *,
    arm: str,
    apertures: str,
    kb_wiki: Path,
    knowledge: KnowledgeAdapter,
    total_seconds: float,
) -> dict[str, Any]:
    os.environ["ASK_WIKI_APERTURES"] = apertures
    os.environ["ASK_EVIDENCE_JUDGE"] = "off"
    os.environ["ASK_WIKI_TOTAL_SECONDS"] = str(total_seconds)
    kb_rag.clear_result_cache()
    anchor = resolve_entity_anchor(question.text, knowledge)
    graph_query = anchor.graph_query if anchor is not None else question.text
    cache_scope = f"wiki-aperture-{arm}-{question.case_id}"
    deadline = time.monotonic() + total_seconds

    def retrieve(retrieval_query: str):
        remaining = max(0.001, deadline - time.monotonic())
        return kb_rag.retrieve(
            retrieval_query,
            kb_wiki,
            k=6,
            mode="hybrid",
            timeout=max(1, int(remaining)),
            excerpt_chars=200,
            budget_query=graph_query,
            require_fresh=True,
            cache_scope=cache_scope,
        )

    started = time.monotonic()
    loop = closed_loop_retrieval.retrieve_closed_loop(
        graph_query,
        anchor=anchor,
        retrieve=retrieve,
        total_seconds=max(0.0, deadline - time.monotonic()),
    )
    elapsed = time.monotonic() - started
    attempts = [_serialize_attempt(item) for item in loop.attempts]
    conclusion = [page_id_of(item.hit) for item in loop.conclusion if page_id_of(item.hit)]
    counter = [page_id_of(item.hit) for item in loop.counter_clues if page_id_of(item.hit)]
    return {
        "arm": arm,
        "apertures": apertures,
        "case_id": question.case_id,
        "graph_query": graph_query,
        "anchor": None
        if anchor is None
        else {"entity": anchor.entity, "ticker": anchor.ticker, "concepts": list(anchor.concepts)},
        "elapsed_sec": round(elapsed, 3),
        "attempts": attempts,
        "warnings": list(loop.warnings),
        "conclusion": list(dict.fromkeys(conclusion)),
        "counter": list(dict.fromkeys(counter)),
        "discarded_n": len(loop.discarded),
    }


def _answers_without_body(answers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slim: list[dict[str, Any]] = []
    for row in answers:
        item = dict(row)
        answer = str(item.pop("answer", "") or "")
        item["answer_chars"] = len(answer)
        slim.append(item)
    return slim


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("l0", "l0l1", "all"), default="all")
    parser.add_argument("--as-of", default=None, help="交易日；默认最新导出，禁止 2026-07-22")
    parser.add_argument("--max-questions", type=int, default=0)
    parser.add_argument("--wiki-seconds", type=float, default=90.0)
    parser.add_argument("--prewarm-timeout", type=float, default=360.0)
    parser.add_argument("--ask-timeout", type=float, default=540.0)
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--skip-l2", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--exports-dir",
        default=str(Path(os.environ.get("FINANCE_WS", REPO)) / "market_feature_store" / "exports"),
    )
    args = parser.parse_args()

    if args.as_of == "2026-07-22":
        raise SystemExit("❌ 禁止再用 2026-07-22 当本单 as_of")
    as_of = args.as_of or latest_as_of(Path(args.exports_dir))
    if as_of == "2026-07-22":
        raise SystemExit("❌ 最新导出不应回退到 2026-07-22")
    questions = default_questions(as_of)
    if args.max_questions > 0:
        questions = questions[: args.max_questions]

    print(
        f"[plan] {LEDGER_ID} as_of={as_of} n={len(questions)} "
        f"phase={args.phase} wiki_seconds={args.wiki_seconds}",
        flush=True,
    )
    print(
        "[plan] 臂 A0=narrow / A1=narrow_broad / A2=all；闸 ASK_EVIDENCE_JUDGE=off；"
        f"ASK_WIKI_TOTAL_SECONDS={args.wiki_seconds}",
        flush=True,
    )
    for q in questions:
        print(f"  {q.case_id:<22} {q.text}", flush=True)
    if args.dry_run:
        return 0

    os.environ["PYTHONPATH"] = str(REPO)
    os.environ["ASK_EVIDENCE_JUDGE"] = "off"
    paths = default_paths()
    kb_wiki = Path(os.environ.get("KNOWLEDGE_WIKI") or paths.knowledge_wiki)
    print(f"[prewarm] {kb_wiki} …", flush=True)
    prewarm = run_prewarm(kb_wiki, args.prewarm_timeout)
    print(f"       {prewarm}", flush=True)
    if not prewarm.get("ok"):
        raise SystemExit(f"❌ 预热未 ready，不准继续谈三铲：{prewarm}")

    knowledge = KnowledgeAdapter(wiki_root=kb_wiki)
    retrieval: list[dict[str, Any]] = []
    for q in questions:
        for arm, apertures in ARMS:
            print(f"[l1] {arm} × {q.case_id} …", flush=True)
            row = run_l1_arm(
                q,
                arm=arm,
                apertures=apertures,
                kb_wiki=kb_wiki,
                knowledge=knowledge,
                total_seconds=args.wiki_seconds,
            )
            retrieval.append(row)
            print(
                f"       executed={[a['aperture'] for a in row['attempts'] if a['executed']]} "
                f"C={len(row['conclusion'])} K={len(row['counter'])} {row['elapsed_sec']:.1f}s",
                flush=True,
            )

    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    for row in retrieval:
        by_case.setdefault(str(row["case_id"]), {})[str(row["arm"])] = row

    l0_rows: list[dict[str, Any]] = []
    for q in questions:
        a2 = by_case[q.case_id]["A2"]
        ok, reason = l0_activated(list(a2["attempts"]))
        l0_rows.append(
            {
                "case_id": q.case_id,
                "usable": ok,
                "reason": reason,
                "attempts": a2["attempts"],
            }
        )
    usable_ids = {row["case_id"] for row in l0_rows if row["usable"]}
    usable_n = len(usable_ids)
    print(f"[l0] 可用 {usable_n}/{len(questions)}：{sorted(usable_ids) or '无'}", flush=True)

    l1_rows: list[dict[str, Any]] = []
    for case_id in usable_ids:
        a0 = by_case[case_id]["A0"]
        a2 = by_case[case_id]["A2"]
        c0, c2 = set(a0["conclusion"]), set(a2["conclusion"])
        k0, k2 = set(a0["counter"]), set(a2["counter"])
        c_delta = l1_delta(c0, c2)
        k_delta = l1_delta(k0, k2)
        expected = EXPECTED_PAGES.get(case_id, ())
        l1_rows.append(
            {
                "case_id": case_id,
                "C_A0": sorted(c0),
                "C_A2": sorted(c2),
                "K_A0": sorted(k0),
                "K_A2": sorted(k2),
                "C_added_n": c_delta["added_n"],
                "C_dropped_n": c_delta["dropped_n"],
                "K_added_n": k_delta["added_n"],
                "K_dropped_n": k_delta["dropped_n"],
                "C_added": c_delta["added"],
                "C_dropped": c_delta["dropped"],
                "K_added": k_delta["added"],
                "counter_nonempty": int(len(k2) >= 1),
                "hit_at_6": hit_at_k(list(a2["conclusion"]), expected) if expected else None,
            }
        )

    l1_summary: dict[str, Any] | None = None
    crowding = False
    if l1_rows:
        mean_c_add = statistics.mean(row["C_added_n"] for row in l1_rows)
        mean_c_drop = statistics.mean(row["C_dropped_n"] for row in l1_rows)
        mean_k_add = statistics.mean(row["K_added_n"] for row in l1_rows)
        crowding = mean_c_drop > mean_c_add
        l1_summary = {
            "usable": usable_n,
            "mean_C_added": round(mean_c_add, 3),
            "mean_C_dropped": round(mean_c_drop, 3),
            "mean_K_added": round(mean_k_add, 3),
            "counter_rate": round(sum(row["counter_nonempty"] for row in l1_rows) / len(l1_rows), 3),
            "crowding": crowding,
        }

    latency = {
        arm: (
            round(statistics.median([row["elapsed_sec"] for row in retrieval if row["arm"] == arm]), 3)
            if any(row["arm"] == arm for row in retrieval)
            else None
        )
        for arm, _ in ARMS
    }

    l2: dict[str, Any] | None = None
    conclusion = decide_conclusion(
        usable_n=usable_n,
        crowding=crowding,
        mean_delta_a2_minus_a0=None,
        a2_worse_than_a0_by_over_2=0,
        l2_ran=False,
    )
    if usable_n < 4:
        conclusion = {"code": "INELIGIBLE", "text": INELIGIBLE}
        print(f"[stop] {INELIGIBLE}", flush=True)
    elif args.phase in {"l0", "l0l1"} or args.skip_l2:
        print("[l2] 跳过（--phase/--skip-l2）", flush=True)
    elif args.phase == "all":
        try:
            qa.require_llm_ready()
        except SystemExit as exc:
            print(f"[l2] 无 key，只交 L0+L1：{exc}", flush=True)
        else:
            usable_questions = [q for q in questions if q.case_id in usable_ids]
            answers: list[dict[str, Any]] = []
            plan = [("A2", "all"), ("A0", "narrow")]
            for arm, apertures in plan:
                for q in usable_questions:
                    print(f"[ask] {arm} × {q.case_id} …", flush=True)
                    result = qa.run_ask(
                        q,
                        extra_env=_eval_env(
                            {"ASK_WIKI_APERTURES": apertures},
                            wiki_seconds=args.wiki_seconds,
                        ),
                        extra_flags=("--wiki-rag-timeout", str(int(args.wiki_seconds))),
                        exports_dir=args.exports_dir,
                        timeout=args.ask_timeout,
                    )
                    answers.append({"arm": arm, "case_id": q.case_id, **result})
                    print(
                        f"       {'ok' if result.get('ok') else result.get('error')} "
                        f"({result.get('elapsed_sec', 0):.0f}s)",
                        flush=True,
                    )
            order = list(range(len(answers)))
            random.Random(args.seed).shuffle(order)
            by_q = {q.case_id: q for q in usable_questions}
            for idx in order:
                rec = answers[idx]
                if not rec.get("ok"):
                    rec["judge"] = {"scored": False, "reason": "答案臂失败，未送评"}
                    continue
                print(f"[judge] #{idx} 盲评 {rec['case_id']} …", flush=True)
                rec["judge"] = qa.judge_answer(by_q[str(rec["case_id"])], str(rec["answer"]))

            paired: list[dict[str, Any]] = []
            a2_by = {r["case_id"]: r for r in answers if r["arm"] == "A2"}
            a0_by = {r["case_id"]: r for r in answers if r["arm"] == "A0"}
            for case_id in usable_ids:
                left, right = a2_by.get(case_id), a0_by.get(case_id)
                j2 = (left or {}).get("judge") or {}
                j0 = (right or {}).get("judge") or {}
                if j2.get("scored") and j0.get("scored"):
                    paired.append(
                        {
                            "case_id": case_id,
                            "A2_total": j2["total"],
                            "A0_total": j0["total"],
                            "delta": j2["total"] - j0["total"],
                        }
                    )
            mean_delta = (
                round(sum(row["delta"] for row in paired) / len(paired), 3) if paired else None
            )
            worse = sum(1 for row in paired if row["A2_total"] < row["A0_total"])
            # 与 run_quality_ablation 同号：A2=baseline，A0=减铲臂，
            # marginal = -mean(A0-A2) = mean(A2-A0)
            l2 = {
                "questions_usable": len(paired),
                "marginal_contribution_total": mean_delta,
                "a2_worse_count": worse,
                "rows": paired,
                "answers": answers,
            }
            conclusion = decide_conclusion(
                usable_n=usable_n,
                crowding=crowding,
                mean_delta_a2_minus_a0=mean_delta,
                a2_worse_than_a0_by_over_2=worse,
                l2_ran=True,
            )

    if FORBIDDEN_PHRASE in json.dumps(conclusion, ensure_ascii=False):
        raise SystemExit("❌ 结论含禁语「三铲无用」")

    artifact = {
        "kind": "wiki_aperture_ablation",
        "ledger_id": LEDGER_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of,
        "ask_evidence_judge": "off",
        "ask_wiki_total_seconds": args.wiki_seconds,
        "prewarm": prewarm,
        "questions": [q.__dict__ for q in questions],
        "l0": {
            "usable": usable_n,
            "total": len(questions),
            "activation_rate": round(usable_n / len(questions), 3) if questions else 0,
            "rows": l0_rows,
        },
        "l1": {"summary": l1_summary, "rows": l1_rows},
        "latency_p50_sec": latency,
        "l2": (
            None
            if l2 is None
            else {**l2, "answers": _answers_without_body(list(l2["answers"]))}
        ),
        "l2_answers_full": None if l2 is None else l2["answers"],
        "retrieval": retrieval,
        "conclusion": conclusion,
        "as_of_date": date.fromisoformat(as_of).isoformat(),
    }
    output = args.output or (
        REPO
        / "intelligence"
        / "eval"
        / "runs"
        / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-wiki-aperture-ablation.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结论 {conclusion['code']}: {conclusion['text']}")
    print(f"收据 → {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
