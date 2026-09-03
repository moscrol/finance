"""钉：held-out 题池不被测试 import、不进夹具。

本文件是唯一允许点名该路径的测试；扫描时排除自身。
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SELF = Path(__file__).resolve()
_POOL = (
    _REPO / "intelligence" / "eval" / "probe_pool" / "heldout-v1.json"
)
_TEST_ROOTS = (_REPO / "intelligence" / "tests", _REPO / "tests")
_NEEDLES = (
    "heldout-v1.json",
    "probe_pool/heldout",
    "eval.probe_pool",
    "eval/probe_pool",
)
_FORBIDDEN = ("长电科技怎么看", "液冷服务器产业链怎么看", "钙钛矿")


def test_heldout_file_is_not_referenced_by_other_tests() -> None:
    hits: list[str] = []
    for root in _TEST_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.resolve() == _SELF:
                continue
            if path.suffix not in {".py", ".json", ".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8")
            for needle in _NEEDLES:
                if needle in text:
                    hits.append(f"{path.relative_to(_REPO)}:{needle}")
    assert hits == []


def test_heldout_contract_shape() -> None:
    payload = json.loads(_POOL.read_text(encoding="utf-8"))
    questions = payload["questions"]
    assert len(questions) >= 8
    themes = {item["theme"] for item in questions}
    kinds = {item["kind"] for item in questions}
    assert len(themes) >= 6
    assert kinds == {"concept", "stock", "chain"}
    joined = " ".join(item["question"] for item in questions)
    for marker in _FORBIDDEN:
        assert marker not in joined
