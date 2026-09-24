"""Offline D1 regression probe: prevent protected text and shared state operations drifting.

Read the committed original T2/T3 questions, plus minimal paired boundary cases.
No model, network, database or session writes. --repo selects the implementation;
JSON goes to stdout and exit 1 means at least one design assertion failed.
This is a P1 parser check, NOT the P7 fresh-session acceptance test.
P1v2 adds protection-composition, long-material and question-completeness probes.
The original T3 control now checks message kinds only: q7 premise annotation is
an intentional R6 repair, not a regression. All other original assertions remain.

Usage: python scripts/e2_boundary_review_probe.py --repo . > result.json
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo.resolve()
    sys.path.insert(0, str(root))
    module = importlib.import_module("intelligence.services.user_task")
    assert Path(module.__file__).resolve() == root / "intelligence/services/user_task.py"
    classify = module.classify_top_level_regions
    evidence = root / "docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok/e2-evidence"
    cases: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []

    def check(name: str, finding: str, text: str, expected: dict[str, Any]) -> None:
        actual = asdict(classify(text))
        comparable = {
            "classification": actual["classification"],
            "kinds": sorted({span["kind"] for span in actual["instructions"]}),
            "message_kinds": sorted({span["kind"] for span in actual["instructions"]
                                     if span["scope"] == "message"}),
            "question_count": len(actual["sub_questions"]),
            "questions": list(actual["sub_questions"]),
            "scopes": [span["scope"] for span in actual["instructions"]],
        }
        passed = all(comparable[key] == value for key, value in expected.items())
        cases.append({"name": name, "finding": finding, "input": text,
                      "expected": expected, "actual": actual, "passed": passed})

    for label in ("t2", "t3"):
        path, = evidence.glob(f"{label}-*/run.json")
        raw = path.read_bytes()
        question = json.loads(raw)["question"]
        sources.append({"path": str(path.relative_to(root)),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "question_sha256": hashlib.sha256(question.encode()).hexdigest()})
        check(f"{label}_original_eight_questions", "R2", question, {"question_count": 8})
        if label == "t2":
            check("t2_original_opening_constraint", "R1", question,
                  {"classification": "constraint_confirmed"})
        else:
            check("t3_original_continuation_control", "control", question,
                  {"message_kinds": ["continuation"]})

    check("inline_quoted_name_does_not_hide_constraint", "R2",
          "只依据“甲公司”的材料回答，不读取材料外数据。",
          {"classification": "constraint_confirmed", "kinds": ["constraint_b"]})
    check("quoted_question_preserves_outer_number", "R2",
          "1. 按“订单硬度”排序。\n\n2. 谁更受益？", {"question_count": 2})
    check("explicit_relaxation", "R1", "可以查真实数据。",
          {"classification": "constraint_confirmed", "kinds": ["constraint_b"]})
    check("if_premise", "R1", "如果甲公司明年订单翻倍会怎样？",
          {"classification": "constraint_confirmed", "kinds": ["premise_declaration"]})

    continuation = "本轮其余条件不变。"
    check("continuation_outside_block_control", "control", continuation,
          {"kinds": ["continuation"]})
    for name, text in (
        ("leadin", f"材料如下：\n丁公司收入10亿元。\n{continuation}\n\n1. 收入占比多少？"),
        ("indent", f"  {continuation}\n\n1. 收入占比多少？"),
    ):
        check(f"continuation_{name}_must_share_predicate", "R3", text,
              {"classification": "boundary_uncertain"})

    narrative = "甲公司是行业龙头，去年总收入20亿元，其中相关业务收入2亿元；乙公司总收入10亿元。"
    check("long_block_state_op_requires_review", "R4",
          narrative + "\n只依据本报告回答，不读取材料外数据。\n"
          "分析师认为当前景气持续，订单规模和收入确认节奏存在差异。\n请问这篇研报的要点是什么？",
          {"classification": "boundary_uncertain"})
    check("long_report_list_is_not_question_group", "R4",
          narrative + "\n1. 公司继续扩产，产业链需求旺盛。\n"
          "2. 收入确认仍需等待客户验收。\n请问这篇研报的核心观点靠谱吗？",
          {"question_count": 0})

    for name, wrapper in (("fence", "```text\n{}\n```"), ("quote", "「\n{}\n」")):
        for operation in ("只依据本报告回答，不要联网。", "继续上一轮，其余条件不变。"):
            protected = wrapper.format(operation)
            suffix = "\n\n1. 核心观点是什么？"
            check(f"{name}_{operation}_standalone_control", "control", protected + suffix,
                  {"classification": "no_constraint_confirmed", "kinds": []})
            check(f"{name}_{operation}_inside_leadin", "R5", "材料如下：\n" + protected + suffix,
                  {"classification": "no_constraint_confirmed", "kinds": []})
    check("unclosed_quote_inside_closed_fence_is_opaque", "R5",
          "```text\n他说「\n继续上一轮，其余条件不变。\n```\n\n1. 核心观点是什么？",
          {"classification": "no_constraint_confirmed", "kinds": []})
    check("multiline_question_keeps_qualification", "R6",
          "1. 请计算甲公司业务占比。\n结果保留两位小数，并列出公式。\n\n2. 哪些风险尚未确认？",
          {"questions": ["请计算甲公司业务占比。\n结果保留两位小数，并列出公式。", "哪些风险尚未确认？"]})
    check("question_local_premise_is_not_message_scope", "R6",
          "1. 请讨论甲公司利润。\n假设甲公司明年订单翻倍成立\n\n2. 再讨论乙公司。",
          {"scopes": ["q1"]})

    # P1v2: protected delimiters cannot participate in outer syntax.
    check("fenced_opener_cannot_mask_external_prohibition", "V2-R5",
          "```text\n他说「\n```\n\n不要联网。\n\n材料的另一行提到」字。",
          {"classification": "constraint_confirmed", "message_kinds": ["constraint_b"]})
    check("fence_without_opener_external_prohibition_control", "control",
          "```text\n他说某字\n```\n\n不要联网。\n\n材料的另一行提到」字。",
          {"classification": "constraint_confirmed", "message_kinds": ["constraint_b"]})
    check("closed_outer_quote_opaque_inner_opener", "V2-R5",
          "「研报原文：\n他说『\n继续上一轮，其余条件不变。\n」\n\n1. 核心观点是什么？",
          {"classification": "no_constraint_confirmed", "kinds": []})
    for operation in ("不要联网。", "继续上一轮，其余条件不变。", "如果订单翻倍会怎样？"):
        check(f"unclosed_quote_inline_{operation}", "V2-quote-failure",
              "他说「" + operation, {"classification": "boundary_uncertain"})
        check(f"closed_quote_inline_{operation}_control", "control",
              "他说「" + operation + "」", {"classification": "no_constraint_confirmed"})

    # P1v2: a material candidate must be reviewed before question claiming.
    for operation in ("只依据本报告回答，不读取材料外数据。", "本轮其余条件不变。"):
        check(f"numbered_report_with_state_op_{operation}", "V2-R4",
              narrative + "\n1. 行业空间说明\n" + operation
              + "\n2. 风险说明\n行业竞争加剧，客户验收周期仍存不确定性。",
              {"classification": "boundary_uncertain"})
    check("mixed_narrative_and_state_ops_on_each_line", "V2-R4",
          "甲公司是行业龙头，去年总收入20亿元，其中相关业务收入2亿元。"
          "只依据本报告回答，不读取材料外数据。\n"
          "乙公司总收入10亿元，相关业务增长稳健。其余条件不变。",
          {"classification": "boundary_uncertain"})

    # P1v2: accepted numbered paragraphs must retain all qualifications.
    long_tail = ("结果保留两位小数，同时列出完整计算公式、分子与分母的材料来源，"
                 "并说明上述比例本身不能用来证明未来的收入规模。")
    check("long_question_qualification_is_not_material_by_length", "V2-R6",
          "请回答以下两题。\n\n1. 请计算比例。\n" + long_tail + "\n\n2. 哪些风险未确认？",
          {"questions": ["请计算比例。\n" + long_tail, "哪些风险未确认？"]})
    quoted_tail = "「甲公司收入10亿元，相关业务收入2亿元。」"
    check("quoted_question_continuation_is_not_blank", "V2-R6",
          "1. 请计算比例。\n" + quoted_tail + "\n\n2. 哪些风险未确认？",
          {"questions": ["请计算比例。\n" + quoted_tail, "哪些风险未确认？"]})
    check("quoted_continuation_followed_by_qualification", "V2-R6",
          "1. 请计算比例。\n" + quoted_tail + "\n结果保留两位小数。\n\n2. 哪些风险未确认？",
          {"questions": ["请计算比例。\n" + quoted_tail + "\n结果保留两位小数。", "哪些风险未确认？"]})

    check("a8_hypothesis_and_current_market", "V2-R1",
          "假设甲公司明年订单翻倍，结合当前行情分析。",
          {"classification": "constraint_confirmed"})
    check("a8_hypothesis_and_latest_market", "V2-R1",
          "假设甲公司明年订单翻倍，结合最新行情分析。",
          {"classification": "constraint_confirmed"})
    check("fictional_declaration_plain", "V2-R1", "这些公司是虚构的。",
          {"classification": "constraint_confirmed", "kinds": ["premise_declaration"]})

    # The lead-in terminator must use the same instruction recognizer.
    for operation in ("不要联网。", "本轮其余条件不变。", "可以查真实数据。"):
        check(f"leadin_blank_top_level_{operation}", "V2-leadin",
              "材料如下：\n甲公司总收入20亿元。\n\n" + operation + "\n\n1. 占比多少？",
              {"classification": "constraint_confirmed"})
    check("leadin_blank_polite_instruction_control", "control",
          "材料如下：\n甲公司总收入20亿元。\n\n请不要联网。\n\n1. 占比多少？",
          {"classification": "constraint_confirmed"})

    def git(*arguments: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()

    passed = sum(case["passed"] for case in cases)
    result = {"schema": "e2-d1-review-v2", "revision": git("rev-parse", "HEAD"),
              "implementation_sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
              "interpreter": sys.version.split()[0],
              "tracked_status": git("status", "--short", "--untracked-files=no"),
              "scope": "pure classifier only; no P2-P7 runtime claim",
              "source_files": sources, "passed": passed, "failed": len(cases) - passed,
              "cases": cases}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(passed != len(cases))


if __name__ == "__main__":
    raise SystemExit(main())
