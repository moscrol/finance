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
    CAUSE_MODEL_UNAVAILABLE,
    CAUSE_TRANSIENT_VERIFIER_OUTAGE,
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
    """同一份终局事实，三类成因各自产出不同的首句。"""

    rendered = {cause: view(_facts(cause)) for cause in DEGRADED_CAUSES}
    firsts = {cause: _first_sentence(text) for cause, text in rendered.items()}

    assert firsts[CAUSE_TRANSIENT_VERIFIER_OUTAGE] == (
        "本次未完成独立复核（复核服务超时）；内容与证据绑定已通过校验："
    )
    assert firsts[CAUSE_EVIDENCE_GAP] == (
        "关于“当前市场怎么看？”，现有证据不足，暂不能可靠回答。"
    )
    assert firsts[CAUSE_MODEL_UNAVAILABLE] == (
        "关于“当前市场怎么看？”，模型服务不可用，暂不能可靠回答。"
    )
    assert len(set(firsts.values())) == 3


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


def test_marker_loss_remainder_stays_remainder_plus_gap() -> None:
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
