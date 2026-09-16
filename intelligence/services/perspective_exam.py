"""视角考卷：用户写金标钉子，程序只做确定性核对。

设计：``docs/superpowers/specs/2026-08-17-perspective-known-answer-exam-design.md``。

测的是保真（蒸馏后能否重建博主已发表立场），不是留出泛化，也不是 LLM 当考官。
空卷 / 题量不够 / 坏 JSON 一律失败。边题命中诚实边界必须弃权。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.userspace import UserSpace
from intelligence.services import perspective_lab

EXAM_SCHEMA_VERSION = 1
MIN_KNOWN_ANSWER = 2
MIN_EDGE_CASE = 1
KNOWN_KINDS = ("known_answer", "edge_case")
DIRECTIONS = ("opportunity", "risk", "mixed", "none")
EXAM_FIELDS = (
    "opportunity_preferences",
    "risk_triggers",
    "anti_patterns",
    "falsification_style",
)
DIRECTIONAL = frozenset({"opportunity", "risk", "mixed"})


def exam_path(us: UserSpace, perspective_id: str) -> Path:
    pid = perspective_lab.resolve_perspective_id(perspective_id)
    return perspective_lab.perspectives_root(us) / "exam" / f"{pid}.json"


def empty_exam(perspective_id: str) -> dict[str, Any]:
    pid = perspective_lab.resolve_perspective_id(perspective_id)
    return {
        "schema_version": EXAM_SCHEMA_VERSION,
        "perspective_id": pid,
        "updated_at": _now_iso(),
        "cases": [],
    }


def load_exam(us: UserSpace, perspective_id: str) -> dict[str, Any]:
    """读考卷。缺文件由调用方处理；坏 JSON / 坏 schema 失败关闭，不返回空对象。"""
    pid = perspective_lab.resolve_perspective_id(perspective_id)
    path = exam_path(us, pid)
    if not path.exists():
        raise FileNotFoundError(f"考卷不存在：{path}（先 `perspective exam add`）")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"考卷 JSON 损坏：{path}（{exc}）") from exc
    if not isinstance(data, dict):
        raise ValueError(f"考卷必须是 JSON 对象：{path}")
    version = data.get("schema_version", EXAM_SCHEMA_VERSION)
    if version != EXAM_SCHEMA_VERSION:
        raise ValueError(f"不支持的考卷 schema_version={version}（只要 {EXAM_SCHEMA_VERSION}）")
    cases = data.get("cases")
    if cases is None:
        cases = []
    if not isinstance(cases, list):
        raise ValueError(f"考卷 cases 必须是数组：{path}")
    normalized = []
    for i, raw in enumerate(cases):
        normalized.append(_normalize_case(raw, index=i))
    data["perspective_id"] = pid
    data["cases"] = normalized
    return data


def load_exam_or_empty(us: UserSpace, perspective_id: str) -> dict[str, Any]:
    path = exam_path(us, perspective_id)
    if not path.exists():
        return empty_exam(perspective_id)
    return load_exam(us, perspective_id)


def save_exam(us: UserSpace, exam: dict[str, Any]) -> Path:
    pid = perspective_lab.resolve_perspective_id(exam["perspective_id"])
    path = exam_path(us, pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    exam = dict(exam)
    exam["schema_version"] = EXAM_SCHEMA_VERSION
    exam["perspective_id"] = pid
    exam["updated_at"] = _now_iso()
    path.write_text(json.dumps(exam, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def add_case(
    us: UserSpace,
    perspective_id: str,
    *,
    kind: str,
    question: str,
    facts: str = "",
    expected_direction: str | None = None,
    expected_field: str | None = None,
    expected_terms: list[str] | None = None,
    forbidden: list[str] | None = None,
) -> dict[str, Any]:
    """追加一道金标题。角色必须已 init；校验失败不写盘。"""
    pid = perspective_lab.resolve_perspective_id(perspective_id)
    perspective_lab.load_profile(us, pid)  # 角色不存在则 FileNotFoundError
    exam = load_exam_or_empty(us, pid)
    case = _normalize_case(
        {
            "kind": kind,
            "question": question,
            "facts": facts,
            "expected_direction": expected_direction,
            "expected_field": expected_field,
            "expected_terms": expected_terms or [],
            "forbidden": forbidden or [],
            "must_abstain": kind == "edge_case",
        },
        index=len(exam["cases"]),
    )
    case["id"] = _next_id(exam["cases"], case["kind"])
    exam["cases"].append(case)
    save_exam(us, exam)
    return case


def run_exam(us: UserSpace, perspective_id: str) -> dict[str, Any]:
    """跑整卷。缺卷/空卷/题量不够/任一题失败 → passed=False。"""
    pid = perspective_lab.resolve_perspective_id(perspective_id)
    profile = perspective_lab.load_profile(us, pid)
    try:
        exam = load_exam(us, pid)
    except FileNotFoundError:
        return _suite_result(pid, [], reason="无考卷（空≠过）")

    cases = exam["cases"]
    if not cases:
        return _suite_result(pid, [], reason="考卷为空（空≠过）")

    results = [score_case(profile, case) for case in cases]
    ka = sum(1 for c in cases if c["kind"] == "known_answer")
    ec = sum(1 for c in cases if c["kind"] == "edge_case")
    reasons: list[str] = []
    if ka < MIN_KNOWN_ANSWER:
        reasons.append(f"已知题不足 {ka}/{MIN_KNOWN_ANSWER}")
    if ec < MIN_EDGE_CASE:
        reasons.append(f"边题不足 {ec}/{MIN_EDGE_CASE}")
    failed = [r for r in results if not r["passed"]]
    if failed:
        reasons.append(f"{len(failed)} 题未通过")
    return _suite_result(
        pid,
        results,
        reason="；".join(reasons) if reasons else "通过",
        known_answer=ka,
        edge_case=ec,
        passed=not reasons,
    )


def score_case(profile: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    case = _normalize_case(case, index=0)
    ev = perspective_lab.evaluate_role(
        profile,
        question=case["question"],
        facts=case.get("facts") or "",
    )
    reasons: list[str] = []
    if case["kind"] == "known_answer":
        if ev["abstain"]:
            reasons.append("已知题不应弃权（题面落到了诚实边界）")
        if ev["direction"] != case["expected_direction"]:
            reasons.append(
                f"方向 {ev['direction']} ≠ 金标 {case['expected_direction']}"
            )
        field = case.get("expected_field")
        terms = case.get("expected_terms") or []
        if terms:
            bucket = _field_bucket(ev, field)
            missing = [t for t in terms if not _term_in_bucket(t, bucket)]
            if missing:
                reasons.append(f"{field} 未命中：{'、'.join(missing)}")
        for phrase in case.get("forbidden") or []:
            if _forbidden_in_artifact(ev, phrase):
                reasons.append(f"出现禁语：{phrase}")
    else:
        if not ev["abstain"]:
            reasons.append("边题必须弃权（诚实边界未拦住题面）")
        if ev["opportunity_hits"] or ev["risk_hits"]:
            reasons.append("弃权后仍给出方向性命中（实盘判断）")
        if not ev["matched_boundaries"]:
            reasons.append("未命中任何诚实边界")
    return {
        "id": case.get("id") or "",
        "kind": case["kind"],
        "passed": not reasons,
        "reasons": reasons,
        "evaluation": ev,
    }


def render_exam_report(result: dict[str, Any]) -> str:
    lines = [
        f"# 视角考卷 · {result['perspective_id']}",
        "",
        f"- 结果：{'通过' if result['passed'] else '失败'}",
        f"- 原因：{result['reason']}",
        f"- 已知题：{result['known_answer']}（至少 {MIN_KNOWN_ANSWER}）",
        f"- 边题：{result['edge_case']}（至少 {MIN_EDGE_CASE}）",
        "",
    ]
    if not result["results"]:
        lines.append("（没有可评分的题目）")
        return "\n".join(lines) + "\n"
    for row in result["results"]:
        mark = "PASS" if row["passed"] else "FAIL"
        lines.append(f"- [{mark}] {row['id'] or '（无 id）'}（{row['kind']}）")
        for why in row["reasons"]:
            lines.append(f"  - {why}")
    return "\n".join(lines) + "\n"


def _suite_result(
    pid: str,
    results: list[dict[str, Any]],
    *,
    reason: str,
    known_answer: int = 0,
    edge_case: int = 0,
    passed: bool = False,
) -> dict[str, Any]:
    return {
        "passed": passed,
        "reason": reason,
        "perspective_id": pid,
        "known_answer": known_answer,
        "edge_case": edge_case,
        "results": results,
    }


def _normalize_case(raw: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"cases[{index}] 必须是对象")
    kind = str(raw.get("kind") or "").strip()
    if kind not in KNOWN_KINDS:
        raise ValueError(
            f"cases[{index}] kind 非法：{kind!r}（只要 {' / '.join(KNOWN_KINDS)}）"
        )
    question = str(raw.get("question") or "").strip()
    if not question:
        raise ValueError(f"cases[{index}] 必须有 question")
    facts = str(raw.get("facts") or "")
    case: dict[str, Any] = {
        "id": str(raw.get("id") or "").strip(),
        "kind": kind,
        "question": question,
        "facts": facts,
    }
    if kind == "known_answer":
        if not facts.strip():
            raise ValueError(f"cases[{index}] 已知题必须有 facts")
        direction = str(raw.get("expected_direction") or "").strip()
        if direction not in DIRECTIONS:
            raise ValueError(
                f"cases[{index}] expected_direction 非法：{direction!r}"
                f"（只要 {' / '.join(DIRECTIONS)}）"
            )
        terms = _string_list(raw.get("expected_terms"), field="expected_terms", index=index)
        field = str(raw.get("expected_field") or "").strip() or None
        if direction in DIRECTIONAL:
            if field not in EXAM_FIELDS:
                raise ValueError(
                    f"cases[{index}] 方向 {direction} 必须带 expected_field"
                    f"（{' / '.join(EXAM_FIELDS)}）"
                )
            if not terms:
                raise ValueError(f"cases[{index}] 方向 {direction} 必须至少一条 expected_terms")
        else:
            if terms:
                raise ValueError(f"cases[{index}] direction=none 时 expected_terms 必须为空")
            if field is not None and field not in EXAM_FIELDS:
                raise ValueError(f"cases[{index}] expected_field 非法：{field!r}")
        case["expected_direction"] = direction
        case["expected_field"] = field
        case["expected_terms"] = terms
        case["forbidden"] = _string_list(raw.get("forbidden"), field="forbidden", index=index)
    else:
        case["must_abstain"] = True
        case["facts"] = facts
    return case


def _string_list(raw: Any, *, field: str, index: int) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or any(not isinstance(x, str) for x in raw):
        raise ValueError(f"cases[{index}] {field} 必须是字符串数组")
    return [x.strip() for x in raw if x.strip()]


def _next_id(cases: list[dict[str, Any]], kind: str) -> str:
    prefix = "ka" if kind == "known_answer" else "ec"
    nums: list[int] = []
    for case in cases:
        cid = str(case.get("id") or "")
        if not cid.startswith(prefix + "-"):
            continue
        tail = cid.split("-", 1)[1]
        if tail.isdigit():
            nums.append(int(tail))
    return f"{prefix}-{max(nums, default=0) + 1}"


def _field_bucket(ev: dict[str, Any], field: str | None) -> list[str]:
    if field == "opportunity_preferences":
        return list(ev.get("opportunity_hits") or [])
    if field == "risk_triggers":
        return list(ev.get("risk_hits") or [])
    if field == "anti_patterns":
        return list(ev.get("anti_patterns") or [])
    if field == "falsification_style":
        return list(ev.get("falsification_style") or [])
    return []


def _term_in_bucket(term: str, bucket: list[str]) -> bool:
    needle = re.sub(r"\s+", "", term)
    if not needle:
        return False
    return any(needle in re.sub(r"\s+", "", item) for item in bucket)


def _forbidden_in_artifact(ev: dict[str, Any], phrase: str) -> bool:
    needle = re.sub(r"\s+", "", phrase)
    if not needle:
        return False
    parts = (
        list(ev.get("opportunity_hits") or [])
        + list(ev.get("risk_hits") or [])
        + list(ev.get("anti_patterns") or [])
        + list(ev.get("falsification_style") or [])
    )
    blob = "".join(re.sub(r"\s+", "", p) for p in parts)
    return needle in blob


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
