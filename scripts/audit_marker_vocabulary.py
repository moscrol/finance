#!/usr/bin/env python3
"""词表三方对账：required_outputs ↔ fulfillment `_MARKERS` ↔ 验收判据。

失败形状（cross-layer-vocabulary-reconciliation 第 3 例的延续）：生成侧按
`task_frame` 的 output_id 承诺答案槽位，覆盖判定按 `task_fulfillment._MARKERS`
的措辞词表检查，验收按 `acceptance_cases.json` 的 `must_mention` / `expect_facts`
判卷——三张表各自自洽、各自演进，没有一层负责对账。差集的两种后果：

- output_id 没有 marker 词表 → coverage 只能报 uncheckable（仪表盲区）；
- 验收短语没被任何生成侧词表命名 → 门禁要求但没人告诉模型（08-01 基线
  15 道 FAIL 的主形状：证据到了、措辞没到）。

三个数据源的取法刻意不同（「只钉配置保不住生效值」）：

- output_id 全集：live 调用 `derive_required_outputs`（题型默认表的生效值）
  + AST 收 wording 分支的 return 元组（那些分支要特定措辞才触发，live 调不到）；
- `_MARKERS`：直接 import 读模块级 dict（生效值）；
- 验收判据：读题集 JSON + overlay（`phrase_equivalents` / `phrase_discharged_by`）。

`--baseline` / `--write-baseline` 提供棘轮门禁：存量盲区免检，新增盲区拦截
（exit 1）。baseline 由本脚本从源码生成，不手抄。
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

from intelligence.services import task_frame, task_fulfillment

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = REPO_ROOT / "intelligence" / "eval" / "cases" / "acceptance_cases.json"
OVERLAY_PATH = (
    REPO_ROOT / "intelligence" / "eval" / "cases" / "acceptance_verdict_contracts.json"
)

_WORDING_FUNCTIONS = ("_explicit_required_outputs", "_default_required_outputs")


def slot_universe() -> dict[str, list[str]]:
    """全部 output_id → 来源清单（`type:<题型>` 或 `wording:<函数名>`）。"""

    slots: dict[str, set[str]] = {}
    for question_type in task_frame._POLICY_BY_QUESTION_TYPE:  # noqa: SLF001
        for slot in task_frame.derive_required_outputs(question_type, ""):
            slots.setdefault(slot, set()).add(f"type:{question_type}")
    for function_name, tuples in _wording_branch_tuples().items():
        for group in tuples:
            for slot in group:
                slots.setdefault(slot, set()).add(f"wording:{function_name}")
    return {slot: sorted(sources) for slot, sources in sorted(slots.items())}


def _wording_branch_tuples() -> dict[str, list[tuple[str, ...]]]:
    """AST 收 wording 分支里 `return ("a", "b", ...)` 的字符串元组。

    题型默认表已由 live 调用覆盖；这里只为收那些需要特定措辞才触发的
    return（比较/反事实/方法论/失效追问/反弹时长），live 调法要为每个
    分支构造触发问句，正则一改就漂，AST 收字面量反而稳。
    """

    source = Path(task_frame.__file__).read_text(encoding="utf-8")
    found: dict[str, list[tuple[str, ...]]] = {}
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.FunctionDef) and node.name in _WORDING_FUNCTIONS):
            continue
        tuples: list[tuple[str, ...]] = []
        for child in ast.walk(node):
            if not (isinstance(child, ast.Return) and isinstance(child.value, ast.Tuple)):
                continue
            items = [
                element.value
                for element in child.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            ]
            if items and len(items) == len(child.value.elts):
                tuples.append(tuple(items))
        found[node.name] = tuples
    return found


def marker_vocabulary() -> dict[str, tuple[str, ...]]:
    return dict(task_fulfillment._MARKERS)  # noqa: SLF001


def vocabulary_diff(
    slots: dict[str, list[str]],
    markers: dict[str, tuple[str, ...]],
) -> dict[str, Any]:
    slots_without_markers = {
        slot: sources for slot, sources in slots.items() if not markers.get(slot)
    }
    markers_without_slots = sorted(set(markers) - set(slots))
    return {
        "slot_count": len(slots),
        "marker_count": len(markers),
        "slots_without_markers": slots_without_markers,
        "markers_without_slots": markers_without_slots,
    }


def classify_must_mention(
    phrase: str,
    *,
    equivalents: dict[str, list[str]],
    discharged_by: dict[str, str],
    marker_phrases: set[str],
) -> str:
    """单条 must_mention 短语的归类：discharged / marker_named / grader_only。

    marker_named 的判据是宽的（双向子串）：只要生成侧词表**提过**这个概念就算
    命名过。grader_only 才是硬缺口——判卷要求它，生成侧任何词表都没这个词。
    """

    if phrase in discharged_by:
        return "discharged"
    candidates = {phrase, *equivalents.get(phrase, [])}
    for candidate in candidates:
        for marker in marker_phrases:
            if candidate in marker or marker in candidate:
                return "marker_named"
    return "grader_only"


def acceptance_report(markers: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))["cases"]
    marker_phrases = {
        phrase for phrases in markers.values() for phrase in phrases
    }
    rows: list[dict[str, Any]] = []
    totals = {"discharged": 0, "marker_named": 0, "grader_only": 0}
    for case in cases:
        case_id = str(case["id"])
        case_overlay = overlay.get(case_id, {})
        equivalents = {
            key: list(values)
            for key, values in (case_overlay.get("phrase_equivalents") or {}).items()
        }
        discharged_by = dict(case_overlay.get("phrase_discharged_by") or {})
        buckets: dict[str, list[str]] = {
            "discharged": [],
            "marker_named": [],
            "grader_only": [],
        }
        for phrase in case.get("must_mention", []) or []:
            bucket = classify_must_mention(
                str(phrase),
                equivalents=equivalents,
                discharged_by=discharged_by,
                marker_phrases=marker_phrases,
            )
            buckets[bucket].append(str(phrase))
            totals[bucket] += 1
        # 无 overlay 别名的字段判分时退回全文匹配（acceptance_verdict.py:644），
        # 能判但绑定弱——数字出现在别处也算命中。按「弱绑定」口径报告，不算缺口。
        aliases = case_overlay.get("fact_aliases") or {}
        weakly_bound_facts = sorted(
            {
                str(item.get("field"))
                for item in case.get("expect_facts", []) or []
                if item.get("field") and str(item.get("field")) not in aliases
            }
        )
        rows.append(
            {
                "case_id": case_id,
                "tier": case.get("tier"),
                **buckets,
                "weakly_bound_facts": weakly_bound_facts,
            }
        )
    return {"totals": totals, "cases": rows}


def build_report() -> dict[str, Any]:
    slots = slot_universe()
    markers = marker_vocabulary()
    return {
        "vocabulary": vocabulary_diff(slots, markers),
        "acceptance": acceptance_report(markers),
    }


def compare_with_baseline(
    report: dict[str, Any],
    baseline: dict[str, Any],
) -> list[str]:
    """棘轮：新增的仪表盲区 / grader_only 短语相对 baseline 只增不减则拦截。"""

    violations: list[str] = []
    known_blind = set(baseline.get("slots_without_markers", []))
    for slot in report["vocabulary"]["slots_without_markers"]:
        if slot not in known_blind:
            violations.append(f"新增无 marker 词表的 output_id: {slot}")
    known_grader_only = {
        (row["case_id"], phrase)
        for row in baseline.get("grader_only", [])
        for phrase in row.get("phrases", [])
    }
    for row in report["acceptance"]["cases"]:
        for phrase in row["grader_only"]:
            if (row["case_id"], phrase) not in known_grader_only:
                violations.append(
                    f"新增 grader_only 短语: {row['case_id']} · {phrase}"
                )
    return violations


def baseline_from_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "slots_without_markers": sorted(
            report["vocabulary"]["slots_without_markers"]
        ),
        "grader_only": [
            {"case_id": row["case_id"], "phrases": row["grader_only"]}
            for row in report["acceptance"]["cases"]
            if row["grader_only"]
        ],
    }


def render_text(report: dict[str, Any]) -> str:
    vocab = report["vocabulary"]
    acceptance = report["acceptance"]
    lines = [
        "# 词表三方对账",
        "",
        f"output_id 全集 {vocab['slot_count']} 个 · marker 词表 {vocab['marker_count']} 个",
        "",
        f"## 仪表盲区：有槽位、无 marker 词表（{len(vocab['slots_without_markers'])} 个）",
        "（coverage 对这些只能报 uncheckable，「答案漏写」与「无法检查」不可区分）",
    ]
    for slot, sources in vocab["slots_without_markers"].items():
        lines.append(f"- `{slot}` ← {', '.join(sources)}")
    lines += [
        "",
        "## marker 不在静态全集（动态追加或别名层，非残留；"
        f"{len(vocab['markers_without_slots'])} 个）",
        "（已核实：rebound/decline/invalidation 是 orchestrator 别名层"
        "（conversation_orchestrator.py:717-720），prior_recall 是记忆路径"
        "动态 extra。新出现的条目先查引用再判残留。）",
    ]
    for slot in vocab["markers_without_slots"]:
        lines.append(f"- `{slot}`")
    totals = acceptance["totals"]
    lines += [
        "",
        "## 验收 must_mention 短语归属",
        f"- 由数字规则蕴含（discharged）：{totals['discharged']}",
        f"- 生成侧词表已命名（marker_named）：{totals['marker_named']}",
        f"- 只有判卷方知道（grader_only，注入候选）：{totals['grader_only']}",
        "",
        "### grader_only 明细（门禁要求但没人告诉模型）",
    ]
    for row in acceptance["cases"]:
        if row["grader_only"]:
            lines.append(
                f"- {row['case_id']} ({row['tier']}): "
                + "、".join(row["grader_only"])
            )
    weak_rows = [row for row in acceptance["cases"] if row["weakly_bound_facts"]]
    lines += [
        "",
        f"### 弱绑定数字字段（无别名窗口，全文匹配，{len(weak_rows)} 题）",
    ]
    for row in weak_rows:
        lines.append(
            f"- {row['case_id']}: " + ", ".join(row["weakly_bound_facts"])
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="required_outputs ↔ _MARKERS ↔ 验收判据 三方词表对账",
    )
    parser.add_argument("--json", action="store_true", help="输出完整 JSON")
    parser.add_argument(
        "--baseline",
        default=None,
        help="棘轮 baseline 路径；给定时新增缺口 → exit 1",
    )
    parser.add_argument(
        "--write-baseline",
        default=None,
        help="把当前缺口写为 baseline（从源码生成，不手抄）",
    )
    args = parser.parse_args()

    report = build_report()
    if args.write_baseline:
        path = Path(args.write_baseline)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(baseline_from_report(report), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        print(f"baseline written: {path}")
        return 0

    print(
        json.dumps(report, ensure_ascii=False, indent=2)
        if args.json
        else render_text(report)
    )

    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        violations = compare_with_baseline(report, baseline)
        if violations:
            print("\n棘轮拦截（新增缺口，须补词表或显式更新 baseline）：")
            for violation in violations:
                print(f"  ✗ {violation}")
            return 1
        print("\n棘轮通过：无新增缺口。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
