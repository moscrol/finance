#!/usr/bin/env python3
"""内容正确性题集：导出题面 / 给答卷判分 / 夹具自检。确定性，不调模型。

    # 1) 导出题面，交给任意被测方（2×2 实验四个臂拿到逐字相同的文本）
    python3 scripts/content_correctness_eval.py export --out /tmp/cc_prompts.jsonl
    # 2) 被测方产出 {"case_id": ..., "answer": ...} 每行一条，判分
    python3 scripts/content_correctness_eval.py score --answers answers.jsonl [--json]
    # 3) 夹具自检：金标答案必须过、坏答案必须因为标注的原因被抓
    python3 scripts/content_correctness_eval.py selftest

判分口径见 intelligence/eval/content_correctness.py 模块文档。没有答卷的题记为
未作答（失败），不会从分母里消失——「漏答」本身就是 0/12 里的一类失败。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.eval import content_correctness as cc  # noqa: E402


def _export(out: Path | None) -> int:
    rows = [{"case_id": c.id, "error_class": c.error_class, "prompt": c.prompt()} for c in cc.load_cases()]
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    if out:
        out.write_text(text, encoding="utf-8")
        print(f"导出 {len(rows)} 题 → {out}")
    else:
        sys.stdout.write(text)
    return 0


def _score(answers_path: Path, as_json: bool) -> int:
    answers = {}
    for line in answers_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            answers[row["case_id"]] = row.get("answer", "")
    results = []
    for case in cc.load_cases():
        if case.id not in answers:
            results.append(cc.CaseResult(case.id, case.error_class, False, ["未作答"]))
        else:
            results.append(cc.score(case, answers[case.id]))
    report = cc.summarize(results)
    unknown = sorted(set(answers) - {r.case_id for r in results})
    if unknown:
        report["unknown_case_ids"] = unknown
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"内容正确性 {report['passed']}/{report['total']}（{report['pass_rate']}）")
        for cls, row in report["by_class"].items():
            print(f"  {cls:<11} {row['passed']}/{row['n']}")
        for case_id, failures in report["failures"].items():
            print(f"  ✗ {case_id}: {'；'.join(failures)}")
    return 0


def _selftest() -> int:
    cases = {c.id: c for c in cc.load_cases()}
    problems = []
    for case_id, fixtures in cc.load_fixtures().items():
        case = cases[case_id]
        for answer in fixtures.get("gold", []):
            result = cc.score(case, answer)
            if not result.passed:
                problems.append(f"{case_id} 金标未通过: {result.failures}")
        for answer, kind in fixtures.get("bad", []):
            result = cc.score(case, answer)
            if result.passed or not any(kind in f for f in result.failures):
                problems.append(f"{case_id} 坏答案没有因「{kind}」被抓: {result.failures}")
    for p in problems:
        print("✗", p)
    print("selftest", "通过" if not problems else f"失败 {len(problems)} 处")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_export = sub.add_parser("export")
    p_export.add_argument("--out", type=Path)
    p_score = sub.add_parser("score")
    p_score.add_argument("--answers", type=Path, required=True)
    p_score.add_argument("--json", action="store_true")
    sub.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.cmd == "export":
        return _export(args.out)
    if args.cmd == "score":
        return _score(args.answers, args.json)
    return _selftest()


if __name__ == "__main__":
    raise SystemExit(main())
