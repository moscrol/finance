"""T-C：FINAL_JSON 判据与生效解析器对齐。

夹具是 ``run_20260817_094617_943922`` 的原始 ``model_turn.content``。
seq14 过严 ``json.loads``；seq19 repair 不过，但生效解析器能捞出 draft。
"""

from __future__ import annotations

from pathlib import Path

from intelligence.eval.finish_json_criterion import (
    extracted_draft,
    legal_json,
    wrote_answer,
)
from intelligence.services.episode_protocol import parse_finish_json

_FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "eval" / "fixtures"
)
_SEQ14 = _FIXTURE_DIR / "finish-json-seq14-first-20260817.txt"
_SEQ19 = _FIXTURE_DIR / "finish-json-seq19-repair-20260817.txt"


def _load(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parser_wrote_answer(content: str) -> bool:
    parsed = parse_finish_json(content)
    return isinstance(parsed, dict) and isinstance(parsed.get("draft"), str) and bool(
        parsed["draft"]
    )


def test_seq19_wrote_answer_matches_effective_parser() -> None:
    content = _load(_SEQ19)
    assert wrote_answer(content) is _parser_wrote_answer(content)
    assert wrote_answer(content) is True
    parsed = parse_finish_json(content)
    assert parsed is not None
    assert '数据标签为"AI算力"' in str(parsed["draft"])


def test_seq19_legal_json_is_counted_separately() -> None:
    """格式坏了仍算写出答案；两计数不得并成一个。"""

    content = _load(_SEQ19)
    assert legal_json(content) is False
    assert wrote_answer(content) is True
    assert '数据标签为"AI算力"' in extracted_draft(content)


def test_seq14_both_counters_pass() -> None:
    content = _load(_SEQ14)
    assert legal_json(content) is True
    assert wrote_answer(content) is True
    assert wrote_answer(content) is _parser_wrote_answer(content)
    parsed = parse_finish_json(content)
    assert parsed is not None
    assert len(parsed["draft"]) == 732


def test_seq19_goes_red_if_wrote_answer_reverts_to_json_loads() -> None:
    """变异：把「写出答案」收成 ``json.loads``，本夹具必须转红。"""

    content = _load(_SEQ19)
    assert legal_json(content) is not wrote_answer(content)
