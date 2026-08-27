"""T-B：公开答案只经一条同步 view()，成因当输入参数。

同一份终局事实，三类成因必须走出不同首句。任意两类合并（同一首句）即红。
这是 dsh ``ctx.sessionProjections`` 的形状：冻结事实进、整段公开文本出，无 IO。
"""

from __future__ import annotations

import ast
import re
from itertools import combinations
from pathlib import Path

import pytest

from intelligence.services.session_projection import (
    CAUSE_EVIDENCE_GAP,
    CAUSE_JUDGE_UNAVAILABLE_HELD,
    CAUSE_MODEL_UNAVAILABLE,
    CAUSE_TRANSIENT_VERIFIER_OUTAGE,
    CAUSE_VERIFICATION_INCOMPLETE,
    CAUSE_VERIFIED,
    DEGRADED_CAUSES,
    TerminalFacts,
    opening_for,
    view,
)

_QUESTION = "当前市场怎么看？"
_PUBLIC = "成交收缩导致承接减弱，短线反弹持续性仍需观察。"
_SERVICES_ROOT = Path(__file__).resolve().parents[1] / "services"
_RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "runtime"
_VERIFIER = _SERVICES_ROOT / "episode_semantic_verifier.py"

_ALLOWED_PUBLIC_ANSWER_CALLEES = frozenset(
    {
        "view",
        "_gap_answer",
        "_generic_gap_answer",
    }
)


def _first_sentence(text: str) -> str:
    hits = [(text.find(sep), sep) for sep in ("。", "：") if sep in text]
    if not hits:
        return text.split("\n", 1)[0]
    index, sep = min(hits)
    return text[: index + len(sep)]


def _facts(cause: str) -> TerminalFacts:
    return TerminalFacts(cause=cause, question=_QUESTION, public=_PUBLIC)


def test_three_causes_emit_distinct_first_sentences() -> None:
    """同一份终局事实，各类成因各自产出不同的首句。"""

    rendered = {cause: view(_facts(cause)) for cause in DEGRADED_CAUSES}
    firsts = {cause: _first_sentence(text) for cause, text in rendered.items()}

    assert firsts[CAUSE_TRANSIENT_VERIFIER_OUTAGE] == (
        "本次未完成独立复核（复核服务超时）；内容与证据绑定已通过校验："
    )
    assert firsts[CAUSE_JUDGE_UNAVAILABLE_HELD] == (
        "本次未完成独立复核（复核服务不可用）。"
    )
    assert firsts[CAUSE_EVIDENCE_GAP] == (
        "关于“当前市场怎么看？”，现有证据不足，暂不能可靠回答。"
    )
    assert firsts[CAUSE_MODEL_UNAVAILABLE] == (
        "关于“当前市场怎么看？”，模型服务不可用，暂不能可靠回答。"
    )
    assert firsts[CAUSE_VERIFICATION_INCOMPLETE] == (
        "关于“当前市场怎么看？”，本轮核验未完成，已取得的观察不能当作完整结论。"
    )
    assert len(set(firsts.values())) == len(DEGRADED_CAUSES)


@pytest.mark.parametrize(
    "left,right",
    list(combinations(DEGRADED_CAUSES, 2)),
    ids=[f"{left}×{right}" for left, right in combinations(DEGRADED_CAUSES, 2)],
)
def test_merging_any_two_causes_must_go_red(left: str, right: str) -> None:
    """变异：任意两类共用首句即红——合并出口会先在这里爆。"""

    assert _first_sentence(view(_facts(left))) != _first_sentence(view(_facts(right)))


def test_transient_keeps_candidate_after_corrected_opening() -> None:
    text = view(_facts(CAUSE_TRANSIENT_VERIFIER_OUTAGE))
    assert text.startswith(opening_for(CAUSE_TRANSIENT_VERIFIER_OUTAGE, _QUESTION))
    assert "仅为候选草稿" not in text
    assert "不视为最终核验结论" not in text
    assert _PUBLIC in text


def test_verified_pass_through_is_byte_identical() -> None:
    assert view(TerminalFacts(cause=CAUSE_VERIFIED, public=_PUBLIC)) == _PUBLIC


def test_evidence_gap_with_remainder_does_not_replace_public() -> None:
    """view() 仍能「剩余 + 缺口行」；W1 的 marker_loss 不再走这条成因。"""

    gap = "证据缺口：直接判断中的未核验表述已删除，需补充直接证据后再判断。"
    text = view(
        TerminalFacts(
            cause=CAUSE_EVIDENCE_GAP,
            question=_QUESTION,
            public=_PUBLIC,
            gap_body=gap,
        )
    )
    assert text == f"{_PUBLIC}\n{gap}"
    assert "现有证据不足" not in text


def test_unknown_cause_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown projection cause"):
        view(TerminalFacts(cause="transient_verifier_outage,evidence_gap"))


def test_verification_incomplete_keeps_public_and_renders_unknown_slots() -> None:
    """R-12：核验未完成不是证据不足；已兑现句保留；缺口由 view() 渲成用户语言。"""

    text = view(
        TerminalFacts(
            cause=CAUSE_VERIFICATION_INCOMPLETE,
            question="2026-06-11 液冷",
            public="液冷服务器当日跌 1.11%。",
            unknown_slots=("直接回答用户问题并说明判断强度", "提供主要反证或竞争性解释"),
        )
    )
    assert text.startswith(
        "关于“2026-06-11 液冷”，本轮核验未完成，已取得的观察不能当作完整结论。"
    )
    assert "液冷服务器当日跌 1.11%。" in text
    assert "这次还核验不了：直接回答用户问题并说明判断强度。" in text
    assert "这次还核验不了：提供主要反证或竞争性解释。" in text
    assert "现有证据不足" not in text
    assert "【结构缺口】" not in text
    assert "【质检" not in text


def test_verification_incomplete_unknown_slots_never_use_qc_heading() -> None:
    text = view(
        TerminalFacts(
            cause=CAUSE_VERIFICATION_INCOMPLETE,
            question="2026-06-11 液冷",
            unknown_slots=("产业链层级、角色与关键环节",),
        )
    )
    assert "【结构缺口】" not in text
    assert "结构缺口" not in text
    assert "这次还核验不了：产业链层级、角色与关键环节。" in text


def test_public_answer_assignments_all_go_through_view() -> None:
    """grep 自证：生产赋值点不得再自己拼串。"""

    assigned: list[str] = []
    for root in (_SERVICES_ROOT, _RUNTIME_ROOT):
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                keywords = {
                    kw.arg: kw.value for kw in node.keywords if kw.arg
                }
                value = keywords.get("public_answer")
                if value is None:
                    continue
                if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
                    assigned.append(value.func.attr)
                elif isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                    assigned.append(value.func.id)
                else:
                    raise AssertionError(
                        f"{path}:{node.lineno} public_answer= bypasses view(): "
                        f"{ast.unparse(value)}"
                    )
    assert assigned
    unexpected = [name for name in assigned if name not in _ALLOWED_PUBLIC_ANSWER_CALLEES]
    assert unexpected == []


def test_gap_helpers_themselves_call_view() -> None:
    source = _VERIFIER.read_text(encoding="utf-8")
    assert re.search(r"def _gap_answer\([\s\S]*?\bview\(", source)
    assert re.search(r"def _generic_gap_answer\([\s\S]*?\bview\(", source)


# ── 出口登记表（棘轮）──────────────────────────────────────────────────
#
# 上面两条门禁只盖 ``public_answer=`` 关键字这一个形状。合并前对账时实测：
# 在 ``ask_synthesis._judge_outage_release`` 里重新塞一条 ``return f"..."``
# 拼串旁路，370 个测试**全绿**——那正是本轮亲手修掉的形状，却没人拦它回来。
#
# 故加两条：① 生产里调 view() 的函数必须在登记表内（新增出口要显式登记）；
# ② 登记为「产公开文本」的出口，其返回文本必须来自 view()，不许自己拼。
_VIEW_CALLERS = frozenset(
    {
        "services/ask_synthesis.py::_judge_outage_release",
        "services/episode_semantic_verifier.py::_transient_failure_candidate",
        "services/episode_semantic_verifier.py::_completed_public",
        "services/episode_semantic_verifier.py::_emit_withheld_repair",
        "services/episode_semantic_verifier.py::_marker_loss_partial_public",
        "services/episode_semantic_verifier.py::_project_semantic_quality_marks",
        "services/episode_semantic_verifier.py::_gap_answer",
        "services/episode_semantic_verifier.py::_generic_gap_answer",
    }
)

# 只列**返回公开文本**的出口；其余返回 outcome 对象，由 public_answer= 那条门禁盖。
_TEXT_OUTLETS = (
    ("services/ask_synthesis.py", "_judge_outage_release"),
    ("services/episode_semantic_verifier.py", "_gap_answer"),
    ("services/episode_semantic_verifier.py", "_generic_gap_answer"),
)

_INTELLIGENCE_ROOT = Path(__file__).resolve().parents[1]


def _production_view_callers() -> set[str]:
    found: set[str] = set()
    for path in _INTELLIGENCE_ROOT.rglob("*.py"):
        if "tests" in path.parts or path.name == "session_projection.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:  # pragma: no cover - 生产文件应当可解析
            continue
        rel = path.relative_to(_INTELLIGENCE_ROOT).as_posix()
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "view":
                    found.add(f"{rel}::{fn.name}")
                    break
    return found


def test_view_callers_are_registered() -> None:
    """新增一个公开文本出口，必须登记——不登记即红。"""

    assert _production_view_callers() == set(_VIEW_CALLERS)


@pytest.mark.parametrize(("rel", "func"), _TEXT_OUTLETS)
def test_text_outlets_never_hand_build_their_return(rel: str, func: str) -> None:
    """登记为产公开文本的出口，返回值只许是 view(...) 或 None。"""

    path = _INTELLIGENCE_ROOT / rel
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    target = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == func
    )
    nested = {
        inner.name
        for inner in ast.walk(target)
        if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef))
        and inner is not target
    }
    offenders: list[str] = []
    for node in ast.walk(target):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        if isinstance(node.value, ast.Constant) and node.value.value is None:
            continue
        if isinstance(node.value, ast.Call) and getattr(node.value.func, "id", "") == "view":
            continue
        offenders.append(f"{rel}:{node.lineno} {ast.unparse(node.value)[:70]}")
    assert offenders == [], (
        f"{func} 自己拼了公开文本，未经 view()（嵌套函数 {sorted(nested)}）：" + "; ".join(offenders)
    )
