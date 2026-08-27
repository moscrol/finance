"""V3：kb_search 送达接 llm_evidence 粗管道。

验收只看送达量与结构（spec §V3）。不得从本文件推出选段/答案质量结论——
那是 V5 的验收面（R-12 预测③：送达变大 ≠ 选段变好）。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from intelligence.services import agent_research, kb_rag
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline

_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "v3-kbsearch-jcet-hits.json"
)
_LEGACY_MAX_HITS = 5
_LEGACY_DETAIL_CHARS = 160
_LEGACY_CHAR_CAP = _LEGACY_MAX_HITS * _LEGACY_DETAIL_CHARS  # 800


def _hit(**kwargs: object) -> SimpleNamespace:
    payload = {
        "title": "",
        "file_path": "wiki/x.md",
        "excerpt": "",
        "display_excerpt": "",
        "llm_evidence": "",
        "source_date": "",
    }
    payload.update(kwargs)
    return SimpleNamespace(**payload)


def _run(hits: list[SimpleNamespace]):
    class _Rag:
        def __init__(self) -> None:
            self.hits = list(hits)
            self.telemetry = SimpleNamespace(status="ok", warning="")

    tools = agent_research.build_default_tools(lambda *_a, **_k: _Rag())
    context = agent_research.AgentToolContext(
        ResearchDeadline.from_timeout(20.0),
        lambda: False,
        InformationCutoff(date(2026, 8, 21), "requested"),
    )
    return tools["kb_search"]("长电科技怎么看", context)


def _legacy_chars(hits: list[SimpleNamespace]) -> int:
    return sum(len((hit.excerpt or "")[:_LEGACY_DETAIL_CHARS]) for hit in hits[:_LEGACY_MAX_HITS])


def _load_jcet_hits() -> list[SimpleNamespace]:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return [_hit(**item) for item in payload["hits"]]


def test_same_query_delivery_chars_beat_legacy_800_cap() -> None:
    """夹具对比新旧规格：同 6 条命中，旧 5×160=800，新走 llm_evidence 全量。"""

    hits = [
        _hit(title=f"p{index}", excerpt="E" * 200, llm_evidence="L" * 800)
        for index in range(6)
    ]
    evidence, _observation, _trace = _run(hits)
    new_chars = sum(len(item.detail) for item in evidence)

    assert _legacy_chars(hits) == _LEGACY_CHAR_CAP
    assert new_chars > _LEGACY_CHAR_CAP
    assert new_chars == 6 * 800
    assert [item.detail for item in evidence] == ["L" * 800] * 6


def test_max_hits_and_detail_chars_are_configurable(monkeypatch) -> None:
    hits = [
        _hit(title=f"p{index}", excerpt="E" * 200, llm_evidence="L" * 800)
        for index in range(6)
    ]
    monkeypatch.setattr(agent_research, "KB_SEARCH_MAX_HITS", 5)
    monkeypatch.setattr(agent_research, "KB_SEARCH_DETAIL_CHARS", 160)
    evidence, _observation, _trace = _run(hits)

    assert len(evidence) == 5
    assert all(len(item.detail) == 160 for item in evidence)
    assert evidence[0].detail == "L" * 160


def test_jcet_replay_delivers_body_not_half_url_or_path_line() -> None:
    """长电案 6 命中重放：送达含正文级信息，不再是半个 URL / 纯路径行。

    不主张选段变好：第 1 条 llm_evidence 仍可能是来源清单（形状 IV，V5 验收面）。
    本钉只锁结构——截断点之后的正文/邻块进了 detail。
    """

    hits = _load_jcet_hits()
    evidence, _observation, _trace = _run(hits)
    details = [item.detail for item in evidence]
    new_chars = sum(len(text) for text in details)
    first_excerpt_160 = (hits[0].excerpt or "")[:_LEGACY_DETAIL_CHARS]
    path_only = "- `raw/cninfo-baseline/长电科技.json`"

    assert len(evidence) == 6
    assert new_chars > _legacy_chars(hits)
    assert new_chars > _LEGACY_CHAR_CAP
    assert details[0] != first_excerpt_160
    assert len(details[0]) > _LEGACY_DETAIL_CHARS
    assert "长电科技2026年一季报" in details[0]
    assert "一句话" in details[1]
    assert "先进封装" in details[1]
    assert details[2].strip() != path_only
    assert "annual_report_baseline" in details[2] or "L2" in details[2]


def test_legacy_160_truncation_is_not_the_default_pipe() -> None:
    """变异闸：管道退回 excerpt[:160] 或默认 160 截断 → 本钉红。"""

    hits = _load_jcet_hits()
    evidence, _observation, _trace = _run(hits)
    first = evidence[0].detail
    assert first != (hits[0].excerpt or "")[:_LEGACY_DETAIL_CHARS]
    assert len(first) > _LEGACY_DETAIL_CHARS
    assert sum(len(item.detail) for item in evidence) > _LEGACY_CHAR_CAP


def test_delivery_limits_do_not_invent_a_second_ladder() -> None:
    """retrieval-tier plan 只在 remaining <15s 把检索 mode 降到 BM25。

    送达字符不得另建第二套降档：4s 与 20s 的 (max_hits, detail_chars) 必须相同。
    """

    mode, reason = kb_rag.select_mode_for_remaining("hybrid", 4.0)
    assert mode == "bm25"
    assert reason == "remaining_budget"
    tight = agent_research.kb_search_delivery_limits(remaining_seconds=4.0)
    ample = agent_research.kb_search_delivery_limits(remaining_seconds=20.0)
    assert tight == ample
    assert tight == (
        agent_research.KB_SEARCH_MAX_HITS,
        agent_research.KB_SEARCH_DETAIL_CHARS,
    )
    assert tight[0] == 6
    assert tight[1] == 0
