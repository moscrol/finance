#!/usr/bin/env python3
"""05 输入理解 · 判卷（unit 与 real 共用一套判据）。

unit  : 在指定代码树上离线构造 TaskFrame（TurnControlCore.control，控制器 LLM 关闭 → 纯规则帧），
        逐题 / 逐链判卷；链内用上一轮的 turn_intent / task_frame 与模拟的对话块续跑。
score : 读 run_05_acceptance.py 产出的 <out_dir>/*.json（真实入口的控制器 task_frame + 助手正文）判卷。

判据只看「进入正确任务」的最小条件（题型 / 主体 / 时间 / 澄清 / 材料身份 / 假设 / 方法候选），
不判答案对错——那是 00 与 01 的事。每题输出 pass/fail 与原因，末尾给 N-of-12 与链 / 反向校验读数。

用法：
  judge_05.py unit  --frozen frozen_questions.json --out unit-baseline.json
  judge_05.py score --frozen frozen_questions.json --runs <out_dir> --out real-baseline-score.json
返回码恒 0（读数写文件，不用返回码代替读数）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MISSING_MATERIAL_MARKERS = ("材料", "原文", "贴进来", "来源链接")
SUBJECT_CLARIFY_MARKERS = ("主体", "哪个", "哪条", "哪家", "围绕")


def _norm_date(text: str) -> str:
    m = re.fullmatch(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?", str(text or "").strip())
    if not m:
        return str(text or "")
    return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def judge_turn(expected: dict, frame: dict | None, *, decision: dict | None = None,
               turn_intent: dict | None = None, answer: str = "", first_frame: dict | None = None,
               episode_context: str = "") -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not frame:
        return False, ["no task_frame captured"]
    ok = True
    qt = frame.get("question_type")
    subject = frame.get("subject") or ""
    clar = frame.get("clarification_question")
    lane = (decision or {}).get("lane")
    assumptions = " ".join(frame.get("assumptions") or [])
    materials = frame.get("materials") or []
    premises = frame.get("user_premises") or []
    hyps = frame.get("competing_explanations") or []
    methods = frame.get("method_candidates") or []
    comparison_entities = " ".join((turn_intent or {}).get("comparison_entities") or [])

    if "question_type" in expected and qt not in expected["question_type"]:
        ok = False
        reasons.append(f"question_type={qt} not in {expected['question_type']}")
    if "not_question_type" in expected and qt in expected["not_question_type"]:
        ok = False
        reasons.append(f"question_type={qt} is forbidden")
    if "subject" in expected and subject != expected["subject"]:
        ok = False
        reasons.append(f"subject={subject!r} != {expected['subject']!r}")
    if "subject_contains" in expected and expected["subject_contains"] not in subject:
        ok = False
        reasons.append(f"subject={subject!r} lacks {expected['subject_contains']!r}")
    if "subjects_all" in expected:
        haystack = subject + " " + assumptions + " " + comparison_entities
        missing = [s for s in expected["subjects_all"] if s not in haystack]
        if missing:
            ok = False
            reasons.append(f"subjects missing {missing} (subject={subject!r})")
    if "timeframe" in expected and _norm_date(frame.get("timeframe")) != expected["timeframe"]:
        ok = False
        reasons.append(f"timeframe={frame.get('timeframe')!r} != {expected['timeframe']!r}")
    if "clarification" in expected:
        is_clar = bool(clar) or lane == "clarify"
        if is_clar != expected["clarification"]:
            ok = False
            reasons.append(f"clarification={is_clar} (q={clar!r}, lane={lane}) expected {expected['clarification']}")
        elif is_clar and "clarification_about" in expected:
            text = str(clar or "")
            markers = MISSING_MATERIAL_MARKERS if expected["clarification_about"] == "material" else SUBJECT_CLARIFY_MARKERS
            if not any(m in text for m in markers):
                ok = False
                reasons.append(f"clarification text {text!r} not about {expected['clarification_about']}")
    if expected.get("competing_explanations") and not hyps:
        ok = False
        reasons.append("no competing_explanations in frame")
    if "materials" in expected and len(materials) != expected["materials"]:
        ok = False
        reasons.append(f"materials={len(materials)} != {expected['materials']}")
    if "material_kind" in expected and not any(m.get("kind") == expected["material_kind"] for m in materials):
        ok = False
        reasons.append(f"material kind {expected['material_kind']} not found in {[m.get('kind') for m in materials]}")
    if "material_dates" in expected:
        got = {d for m in materials for d in (m.get("dates") or [])}
        if not set(expected["material_dates"]).issubset(got):
            ok = False
            reasons.append(f"material dates {got} lack {expected['material_dates']}")
    if "material_headers" in expected:
        got = {h for m in materials for h in (m.get("headers") or [])}
        if not set(expected["material_headers"]).issubset(got):
            ok = False
            reasons.append(f"material headers {sorted(got)} lack {expected['material_headers']}")
    if "user_premises" in expected and len(premises) < expected["user_premises"]:
        ok = False
        reasons.append(f"user_premises={len(premises)} < {expected['user_premises']}")
    if expected.get("user_premises_reference"):
        ref = bool(premises) or "prior_recall" in (frame.get("required_outputs") or []) or "此前" in assumptions or "之前" in assumptions
        if not ref:
            ok = False
            reasons.append("no reference to user's prior judgement in frame")
    if "method_candidates" in expected and len(methods) < expected["method_candidates"]:
        ok = False
        reasons.append(f"method_candidates={len(methods)} < {expected['method_candidates']}")
    if "method_status" in expected and not any(expected["method_status"] in str(m.get("status", "")) for m in methods):
        ok = False
        reasons.append(f"method status {[m.get('status') for m in methods]} lacks {expected['method_status']}")
    if expected.get("no_fabrication"):
        if re.search(r"\d+(\.\d+)?\s*(亿|万|%|吨|元)", answer or ""):
            ok = False
            reasons.append("answer contains figures although no material was given")
        if any(seg in assumptions for seg in ("硫化物", "12 亿", "毛利率")):
            ok = False
            reasons.append("assumptions contain material-like content")
    if "same_material_as_turn" in expected:
        # 身份可以落在两处：frame.referenced_material_ids（需要控制器把对话块传给
        # build_task_frame，B05-1）或 episode 输入里的材料身份表（episode_factory 装配，
        # 默认入口已生效）。任一处带着首轮材料 id 就算同一材料身份。
        first_ids = {m.get("material_id") for m in ((first_frame or {}).get("materials") or [])}
        this_ids = {m.get("material_id") for m in materials} | set(frame.get("referenced_material_ids") or [])
        in_context = any(mid and mid in (episode_context or "") for mid in first_ids)
        # 真实入口的 run 产物不归档 episode 输入；答案正文点到材料 id 也算身份带到了模型。
        in_answer = any(mid and mid in (answer or "") for mid in first_ids)
        if not first_ids or not ((first_ids & this_ids) or in_context or in_answer):
            ok = False
            reasons.append(f"material identity not carried: first={sorted(map(str, first_ids))} now={sorted(map(str, this_ids))} in_episode_context={in_context} in_answer={in_answer}")
    if expected.get("keeps_original_task") and first_frame is not None:
        if frame.get("question_type") != first_frame.get("question_type"):
            ok = False
            reasons.append(f"question_type changed {first_frame.get('question_type')} -> {frame.get('question_type')}")
        if clar:
            ok = False
            reasons.append("still asking a clarification after material was pasted")
    return ok, reasons


def material_usage(answer: str, material_text: str) -> dict:
    """信息读数：答案里出现了材料的多少个表头 / 日期 / 数字（不进 pass/fail）。"""
    dates = set(re.findall(r"20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?", material_text))
    numbers = set(re.findall(r"\d+(?:\.\d+)?\s*(?:亿|%|吨|元)", material_text))
    first_line = material_text.strip().splitlines()[0] if material_text.strip() else ""
    headers = [h for h in re.split(r"[\t|]+", first_line) if h.strip()] if ("\t" in first_line or "|" in first_line) else []
    return {
        "dates_hit": sorted(d for d in dates if d in (answer or "")),
        "numbers_hit": sorted(n for n in numbers if n.replace(" ", "") in (answer or "").replace(" ", "")),
        "headers_hit": [h for h in headers if h in (answer or "")],
        "answer_chars": len(answer or ""),
    }


def _expand(frozen: dict) -> tuple[dict[str, list[dict]], dict[str, str]]:
    materials = frozen.get("materials", {})
    by_id = {q["id"]: q for q in frozen["questions"]}

    def render(text: str) -> tuple[str, str | None]:
        used = None
        for key, value in materials.items():
            if "{" + key + "}" in text:
                text = text.replace("{" + key + "}", value)
                used = key
        return text, used

    cases: dict[str, list[dict]] = {}
    for q in frozen["questions"]:
        text, used = render(q["text"])
        cases[q["id"]] = [{"text": text, "expected": q.get("expected", {}), "material": used}]
    for chain in frozen.get("chains", []):
        turns = []
        for turn in chain["turns"]:
            src = by_id[turn["ref"]] if "ref" in turn else turn
            text, used = render(src["text"])
            turns.append({"text": text, "expected": src.get("expected", {}), "material": used})
        cases[chain["id"]] = turns
    return cases, materials


def _reverse_variants(frozen: dict) -> list[dict]:
    materials = frozen.get("materials", {})
    by_id = {q["id"]: q for q in frozen["questions"]}
    out = []
    for r in frozen.get("reverse_checks", []):
        base_text = by_id[r["base"]]["text"]
        for key, value in materials.items():
            base_text = base_text.replace("{" + key + "}", value)
        if "variant" in r:
            variant = r["variant"]
        elif "variant_material" in r:
            variant = by_id[r["base"]]["text"].replace("{" + by_id[r["base"]].get("material", "") + "}", materials[r["variant_material"]])
        else:
            variant = None
        out.append({**r, "base_text": base_text, "variant_text": variant})
    return out


# ------------------------------------------------------------------ unit mode
def _frame_dict(frame) -> dict:
    return frame.to_dict() if frame is not None else {}


def unit_mode(args) -> int:
    from intelligence.runtime.turn_control_core import TurnControlCore
    from intelligence.services.research_contract import TurnIntent

    frozen = json.loads(Path(args.frozen).read_text(encoding="utf-8"))
    cases, materials = _expand(frozen)
    core = TurnControlCore()
    disabled = lambda *_a, **_k: (None, None, "disabled")  # noqa: E731
    report: dict = {"mode": "unit", "cases": {}, "reverse": {}}
    passed_q = 0
    total_q = 0
    for case_id, turns in cases.items():
        prev_intent = None
        prev_frame = None
        prev_turn_id = None
        history: list[str] = []
        first_frame = None
        case_out = []
        for index, turn in enumerate(turns, start=1):
            context = (
                "## 较早消息（原文，超预算时从最早处截断）\n（无较早消息）\n\n## 最近消息原文\n"
                + ("\n".join(history) if history else "（无历史消息）")
            )
            episode_context = ""
            try:
                result = core.control(
                    turn["text"], context=context, previous_frame=prev_frame,
                    previous_intent=prev_intent, previous_turn_id=prev_turn_id, llm_complete=disabled,
                )
                frame = result.task_frame
                frame_d = _frame_dict(frame)
                decision_d = {"lane": result.execution_route if result.terminal_kind == "clarification" else result.execution_route,
                              "terminal_kind": result.terminal_kind}
                intent_d = result.turn_intent.to_dict() if result.turn_intent is not None else None
                error = None
                if result.terminal_kind == "research":
                    # 装配层（episode_factory）是材料身份表进入模型输入的地方；单元判卷也看它。
                    from intelligence.services.episode_factory import build_episode_context

                    run_context = build_episode_context(
                        frame, task_id=f"unit-{case_id}-{index}", capabilities=result.capabilities,
                        conversation_context=context,
                    )
                    episode_context = run_context.conversation_context
            except Exception as exc:  # noqa: BLE001 - 判卷必须记下异常而不是死掉
                frame, frame_d, decision_d, intent_d, error = None, {}, {}, None, f"{type(exc).__name__}: {exc}"
            if index == 1:
                first_frame = frame_d
            ok, reasons = judge_turn(turn["expected"], frame_d, decision={"lane": "clarify" if decision_d.get("terminal_kind") == "clarification" else decision_d.get("lane")},
                                     turn_intent=intent_d, first_frame=first_frame, episode_context=episode_context)
            case_out.append({"turn": index, "text": turn["text"][:80], "pass": ok, "reasons": reasons, "error": error,
                             "frame": frame_d, "terminal_kind": decision_d.get("terminal_kind"),
                             "episode_context_head": episode_context[:600]})
            history.append(f"user: {turn['text']}")
            history.append("assistant: " + (str(frame_d.get("clarification_question")) if frame_d.get("clarification_question") else "（上一轮回答略）"))
            if frame is not None:
                prev_frame = frame
                prev_intent = TurnIntent.from_dict(intent_d) if intent_d and hasattr(TurnIntent, "from_dict") else (result.turn_intent if error is None else prev_intent)
                prev_turn_id = f"turn-{index}"
        report["cases"][case_id] = case_out
        if case_id.startswith("Q"):
            total_q += 1
            passed_q += int(all(t["pass"] for t in case_out))
    # reverse checks
    for r in _reverse_variants(frozen):
        base = core.control(r["base_text"], llm_complete=disabled).task_frame.to_dict()
        entry = {"kind": r["kind"], "base": {k: base.get(k) for k in ("question_type", "subject", "timeframe", "user_goal", "clarification_question")},
                 "base_materials": [m.get("material_id") for m in base.get("materials") or []]}
        if r.get("variant_text"):
            var = core.control(r["variant_text"], llm_complete=disabled).task_frame.to_dict()
            entry["variant"] = {k: var.get(k) for k in ("question_type", "subject", "timeframe", "user_goal", "clarification_question")}
            entry["variant_materials"] = [m.get("material_id") for m in var.get("materials") or []]
            diffs = [k for k in ("question_type", "subject", "timeframe", "user_goal", "clarification_question") if base.get(k) != var.get(k)]
            if entry["base_materials"] != entry["variant_materials"]:
                diffs.append("materials")
            hyp_b = [h.get("label") for h in base.get("competing_explanations") or []]
            hyp_v = [h.get("label") for h in var.get("competing_explanations") or []]
            entry["competing_same_shape"] = (len(hyp_b) == len(hyp_v) and bool(hyp_b))
            entry["diffs"] = diffs
            want_diff = set(r.get("expect_diff", []))
            want_same = set(r.get("expect_same", []))
            ok = True
            why = []
            for k in want_diff:
                key = "materials" if k.startswith("materials") else k
                if key not in diffs:
                    ok = False
                    why.append(f"expected {k} to differ")
            for k in want_same:
                if k == "competing_explanations_shape":
                    if not entry["competing_same_shape"]:
                        ok = False
                        why.append("competing explanations shape differs / empty")
                elif k == "competing_explanations":
                    if hyp_b != hyp_v or not hyp_b:
                        ok = False
                        why.append("competing explanations differ / empty")
                elif k == "clarification":
                    if bool(base.get("clarification_question")) != bool(var.get("clarification_question")):
                        ok = False
                        why.append("clarification behaviour differs")
                elif k in diffs:
                    ok = False
                    why.append(f"expected {k} same, got {base.get(k)!r} vs {var.get(k)!r}")
            entry["pass"] = ok
            entry["reasons"] = why
        else:
            joined = " ".join(base.get("assumptions") or []) + json.dumps(base.get("materials") or [], ensure_ascii=False)
            entry["pass"] = not any(seg in joined for seg in ("硫化物", "12 亿", "毛利率")) and bool(base.get("clarification_question")) and any(m in str(base.get("clarification_question")) for m in MISSING_MATERIAL_MARKERS)
            entry["reasons"] = [] if entry["pass"] else ["no material clarification or material-like content fabricated"]
        report["reverse"][r["id"]] = entry
    report["questions_passed"] = passed_q
    report["questions_total"] = total_q
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_report(report)
    return 0


# ----------------------------------------------------------------- score mode
def score_mode(args) -> int:
    frozen = json.loads(Path(args.frozen).read_text(encoding="utf-8"))
    cases, materials = _expand(frozen)
    runs_dir = Path(args.runs)
    report: dict = {"mode": "score", "runs": str(runs_dir), "cases": {}}
    passed_q = 0
    total_q = 0
    for case_id, turns in cases.items():
        path = runs_dir / f"{case_id}.json"
        if not path.is_file():
            report["cases"][case_id] = [{"turn": 1, "pass": False, "reasons": ["no run captured"]}]
            if case_id.startswith("Q"):
                total_q += 1
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        case_out = []
        first_frame = None
        for index, (turn, run) in enumerate(zip(turns, data.get("turns", [])), start=1):
            frame = run.get("task_frame") or {}
            if index == 1:
                first_frame = frame
            episode_context = ""
            run_dir = run.get("run_dir")
            if run_dir:
                for name in ("continuous-episode.json", "stream.jsonl"):
                    artifact = Path(run_dir) / name
                    if artifact.is_file():
                        try:
                            episode_context += artifact.read_text(encoding="utf-8", errors="replace")
                        except OSError:
                            pass
            ok, reasons = judge_turn(turn["expected"], frame, decision=run.get("decision"), turn_intent=run.get("turn_intent"),
                                     answer=run.get("answer", ""), first_frame=first_frame, episode_context=episode_context)
            entry = {"turn": index, "pass": ok, "reasons": reasons, "run_status": run.get("run_status"), "elapsed_seconds": run.get("elapsed_seconds"),
                     "lane": (run.get("decision") or {}).get("lane"), "question_type": frame.get("question_type"), "subject": frame.get("subject"),
                     "timeframe": frame.get("timeframe"), "clarification_question": frame.get("clarification_question"),
                     "materials": [m.get("material_id") for m in frame.get("materials") or []]}
            if turn.get("material"):
                entry["material_usage"] = material_usage(run.get("answer", ""), materials[turn["material"]])
            if run.get("run_status") not in {"completed"}:
                entry["reasons"] = entry["reasons"] + [f"run_status={run.get('run_status')}"]
            case_out.append(entry)
        if len(case_out) < len(turns):
            case_out.append({"turn": len(case_out) + 1, "pass": False, "reasons": ["turn not captured (timeout / protocol)"]})
        report["cases"][case_id] = case_out
        if case_id.startswith("Q"):
            total_q += 1
            passed_q += int(all(t["pass"] for t in case_out))
    report["questions_passed"] = passed_q
    report["questions_total"] = total_q
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_report(report)
    return 0


def _print_report(report: dict) -> None:
    print(f"== {report['mode']} : questions {report.get('questions_passed')}/{report.get('questions_total')}")
    for case_id, turns in report["cases"].items():
        for t in turns:
            flag = "PASS" if t.get("pass") else "FAIL"
            extra = f" [{t.get('terminal_kind') or t.get('lane') or ''}]"
            print(f"{flag} {case_id}#{t.get('turn')}{extra} {'; '.join(t.get('reasons') or [])}")
    for rid, entry in (report.get("reverse") or {}).items():
        print(f"{'PASS' if entry.get('pass') else 'FAIL'} {rid} {entry.get('kind')} diffs={entry.get('diffs')} {'; '.join(entry.get('reasons') or [])}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    u = sub.add_parser("unit")
    u.add_argument("--frozen", required=True)
    u.add_argument("--out", required=True)
    s = sub.add_parser("score")
    s.add_argument("--frozen", required=True)
    s.add_argument("--runs", required=True)
    s.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    return unit_mode(args) if args.mode == "unit" else score_mode(args)


if __name__ == "__main__":
    sys.exit(main())
