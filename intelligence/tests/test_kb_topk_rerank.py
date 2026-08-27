"""V9b：kb_search 消费侧 top-k 槽位（形状 IV 邻页链接堆占槽）。

验收只看「哪些页进最终 k」。不得从本文件推出 #1 窗变成正文（那是 V9a /
R-20260822-01）。live 由验收方回填，不得 confirmed。

方案是启发式 B5（不调 cross-encoder）：via_neighbor 且代表段为
相关实体/相关概念 → 排后，sanitize_hits 截 k 时挤出。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from intelligence.services import agent_research, kb_rag  # noqa: E402
from intelligence.services.kb_index_hygiene import sanitize_hits  # noqa: E402
from intelligence.services.kb_slot_rerank import (  # noqa: E402
    NEIGHBOR_REP_SECTIONS,
    allocate_topk_slots,
    is_structural_neighbor_rep,
)
from intelligence.services.kb_window_reexcerpt import reexcerpt_hits  # noqa: E402
from scripts.audit_ceiling_sensors import inspect_shape_iii  # noqa: E402

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_CANDIDATES = _FIXTURES / "v9b-jcet-candidates.json"
_V9A_PAGES = _FIXTURES / "v9a-jcet-pages"
_V9B_PAGES = _FIXTURES / "v9b-jcet-pages"
_QUERY = "长电科技怎么看"
_K = 6
_NEIGHBOR_STEMS = ("颀中科技", "华天科技", "莱宝高科")


def _hit(**kwargs: object) -> SimpleNamespace:
    payload = {
        "title": "",
        "file_path": "wiki/x.md",
        "excerpt": "",
        "display_excerpt": "",
        "llm_evidence": "",
        "section": "",
        "via_neighbor": False,
        "source_date": "",
        "score": 0.5,
        "page_id": "",
        "reexcerpted": False,
    }
    payload.update(kwargs)
    if not payload["page_id"]:
        payload["page_id"] = str(payload["title"] or payload["file_path"])
    return SimpleNamespace(**payload)


def _load_candidates() -> list[SimpleNamespace]:
    payload = json.loads(_CANDIDATES.read_text(encoding="utf-8"))
    assert payload["query"] == _QUERY
    return [_hit(**item) for item in payload["hits"]]


def _stem(hit: object) -> str:
    return Path(str(getattr(hit, "file_path", "") or "")).stem


_LEDGER_REP_SECTIONS = frozenset({"相关实体", "相关概念"})


def _is_ledger_neighbor_rep(hit: object) -> bool:
    """台账行字面：via_neighbor 且代表段为相关实体/相关概念。不复用实现谓词。"""

    if _stem(hit) not in _NEIGHBOR_STEMS:
        return False
    if not bool(getattr(hit, "via_neighbor", False)):
        return False
    parts = [
        part.strip()
        for part in str(getattr(hit, "section", "") or "").split(">")
        if part.strip()
    ]
    return any(part in _LEDGER_REP_SECTIONS for part in parts)


def _neighbor_structural_in(hits: list[object]) -> list[object]:
    return [hit for hit in hits if _is_ledger_neighbor_rep(hit)]


def _apply_slots(hits: list[SimpleNamespace], *, k: int = _K) -> list[SimpleNamespace]:
    ordered, _stats = allocate_topk_slots(hits)
    return sanitize_hits(ordered, k=k)


def test_jcet_neighbors_no_longer_take_three_slots() -> None:
    """台账逐字：via_neighbor 且代表段为相关实体/相关概念的颀中/华天/莱宝 ≤1。"""

    top = _apply_slots(_load_candidates())
    assert len(top) == _K
    occupied = _neighbor_structural_in(top)
    assert len(occupied) <= 1, [(_stem(hit), hit.section) for hit in occupied]


def test_v9b_does_not_rewrite_windows() -> None:
    """本单只换槽，不改窗。#1 原文照留（窗内容是 R-20260822-01）。"""

    before = _load_candidates()
    first = next(hit for hit in before if "最新逻辑跟踪" in hit.file_path)
    original = str(first.llm_evidence)
    ordered, _stats = allocate_topk_slots(before)
    after = next(hit for hit in ordered if "最新逻辑跟踪" in hit.file_path)
    assert str(after.llm_evidence) == original
    assert str(after.excerpt) == str(first.excerpt)


def test_true_semantic_neighbor_stays() -> None:
    """via_neighbor 但代表段是正文（公司简介）→ 不当结构代表，不进 demoted 段。"""

    ordered, stats = allocate_topk_slots(_load_candidates())
    demoted_stems = {_stem(hit) for hit in ordered[len(ordered) - stats.demoted :]}
    assert "晶方科技" not in demoted_stems
    assert {"颀中科技", "华天科技", "莱宝高科"} <= demoted_stems


def test_structural_without_via_neighbor_stays() -> None:
    """无 via_neighbor 的相关实体页不挤（与 V9a retrieve 钉共存）。"""

    hit = _hit(
        title="颀中科技（688352）",
        file_path="wiki/entities/颀中科技.md",
        section="相关实体",
        via_neighbor=False,
        excerpt="[[长电科技]]",
        llm_evidence="[[长电科技]]",
        score=0.9,
    )
    filler = _hit(
        title="通富微电",
        file_path="wiki/entities/通富微电.md",
        section="公司简介",
        via_neighbor=False,
        excerpt="通富正文",
        llm_evidence="通富正文",
        score=0.1,
    )
    top = _apply_slots([hit, filler], k=1)
    assert _stem(top[0]) == "颀中科技"


def test_oversample_then_cut_fills_k() -> None:
    """B5③：过采样后丢结构代表块，sanitize_hits 仍能填满 k。"""

    top = _apply_slots(_load_candidates())
    stems = {_stem(hit) for hit in top}
    assert len(top) == _K
    assert "通富微电" in stems
    assert "先进封装" in stems or "封测" in stems


def test_identity_sorter_is_not_the_default() -> None:
    """变异闸①映射：排序器恒等 → 三邻页仍占 3 槽，本钉红。"""

    raw = _load_candidates()
    ordered, stats = allocate_topk_slots(raw)
    assert stats.demoted >= 3
    assert ordered is not raw or stats.demoted >= 3
    top = sanitize_hits(ordered, k=_K)
    assert len(_neighbor_structural_in(top)) <= 1
    raw_top = sanitize_hits(raw, k=_K)
    assert len(_neighbor_structural_in(raw_top)) == 3


def test_empty_neighbor_gate_is_not_the_default() -> None:
    """变异闸②映射：门控失效（空集合 / 谓词恒假）→ 本钉红。"""

    assert NEIGHBOR_REP_SECTIONS
    assert "相关实体" in NEIGHBOR_REP_SECTIONS
    assert "相关概念" in NEIGHBOR_REP_SECTIONS
    neighbors = [
        hit for hit in _load_candidates() if _stem(hit) in _NEIGHBOR_STEMS
    ]
    assert all(is_structural_neighbor_rep(hit) for hit in neighbors)
    top = _apply_slots(_load_candidates())
    assert len(_neighbor_structural_in(top)) <= 1


def test_no_second_budget_ladder() -> None:
    """禁止第二套降档：本模块不读 remaining、不改 15.0 真值表。"""

    source = Path(_REPO / "intelligence/services/kb_slot_rerank.py").read_text(
        encoding="utf-8"
    )
    assert "select_mode_for_remaining" not in source
    assert "HYBRID_MIN_REMAINING" not in source
    assert "15.0" not in source
    assert kb_rag.select_mode_for_remaining("hybrid", 4.0) == (
        "bm25",
        "remaining_budget",
    )
    assert kb_rag.select_mode_for_remaining("hybrid", 11.955) == (
        "bm25",
        "remaining_budget",
    )
    assert kb_rag.select_mode_for_remaining("hybrid", 20.0) == ("hybrid", None)
    assert kb_rag.select_mode_for_remaining("rerank", 4.0) == (
        "bm25",
        "remaining_budget",
    )
    assert "rerank" in kb_rag._DENSE_MODES


def test_remaining_tight_never_calls_cross_encoder() -> None:
    """remaining=4 / 11.955 零次模型调用；启发式在 BM25 档也跑。"""

    payload = json.loads(_CANDIDATES.read_text(encoding="utf-8"))
    items = []
    for index, raw in enumerate(payload["hits"]):
        items.append(
            {
                "page_id": raw["title"],
                "file_path": raw["file_path"],
                "title": raw["title"],
                "score": float(raw.get("score") or 0.5),
                "best_chunk_id": f"{raw['file_path']}::{index}",
                "content_hash": f"hash-v9b-{index}",
                "evidence_text": raw["excerpt"],
                "llm_evidence_text": raw["llm_evidence"],
                "section": raw["section"],
                "via_neighbor": raw["via_neighbor"],
                "index_source_revision": "abc123",
                "index_freshness": "fresh",
            }
        )
    score_calls: list[object] = []

    def _forbidden_score(*_args: object, **_kwargs: object) -> float:
        score_calls.append(1)
        return 0.0

    for remaining in (4, 11.955, 20):
        score_calls.clear()
        with _stub_retrieve_wiki() as wiki:
            proc = mock.Mock(
                returncode=0,
                stdout=json.dumps(items, ensure_ascii=False),
                stderr="",
            )
            with mock.patch.dict(
                "os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=False
            ):
                with mock.patch("subprocess.run", return_value=proc) as run:
                    with mock.patch(
                        "intelligence.services.kb_rag.allocate_topk_slots",
                        wraps=allocate_topk_slots,
                    ) as wrapped:
                        res = kb_rag.retrieve(
                            _QUERY,
                            wiki,
                            k=_K,
                            mode="hybrid",
                            timeout=remaining,
                        )
            cmd = run.call_args.args[0]
            mode = cmd[cmd.index("--mode") + 1]
            assert "rerank" not in cmd
            if remaining < 15:
                assert mode == "bm25"
                assert res.telemetry.effective_mode == "bm25"
            else:
                assert mode == "hybrid"
            assert wrapped.called
            assert score_calls == []
            occupied = _neighbor_structural_in(list(res.hits))
            assert len(occupied) <= 1


def test_retrieve_pipeline_squeezes_neighbors_after_reexcerpt() -> None:
    """retrieve：V9a 换窗之后、sanitize 截 k 之前排后。窗内容不是本单主张。"""

    payload = json.loads(_CANDIDATES.read_text(encoding="utf-8"))
    items = []
    for index, raw in enumerate(payload["hits"]):
        items.append(
            {
                "page_id": raw["title"],
                "file_path": raw["file_path"],
                "title": raw["title"],
                "score": float(raw.get("score") or 0.5),
                "best_chunk_id": f"{raw['file_path']}::{index}",
                "content_hash": f"hash-v9b-{index}",
                "evidence_text": raw["excerpt"],
                "llm_evidence_text": raw["llm_evidence"],
                "section": raw["section"],
                "via_neighbor": raw["via_neighbor"],
                "index_source_revision": "abc123",
                "index_freshness": "fresh",
            }
        )
    with _stub_retrieve_wiki() as wiki:
        proc = mock.Mock(
            returncode=0,
            stdout=json.dumps(items, ensure_ascii=False),
            stderr="",
        )
        with mock.patch.dict(
            "os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=False
        ):
            with mock.patch("subprocess.run", return_value=proc):
                res = kb_rag.retrieve(
                    _QUERY,
                    wiki,
                    k=_K,
                    mode="bm25",
                    timeout=20,
                )
    occupied = _neighbor_structural_in(list(res.hits))
    assert len(occupied) <= 1
    assert res.telemetry.structural_neighbor_demoted is not None
    assert res.telemetry.structural_neighbor_demoted >= 3
    assert len(res.hits) == _K
    stems = {_stem(hit) for hit in res.hits}
    assert "通富微电" in stems


def test_heuristic_incremental_budget() -> None:
    """启发式增量：夹具上应远低于 10ms（spec B5 <10ms），不进 _DENSE_MODES。"""

    hits = _load_candidates()
    started = time.perf_counter()
    for _ in range(50):
        allocate_topk_slots(hits)
    elapsed_ms = (time.perf_counter() - started) * 1000 / 50
    assert elapsed_ms < 10.0


def test_telemetry_new_field_and_historical_missing_is_unjudgeable() -> None:
    """新路径落盘 structural_neighbor_demoted；历史缺字段记 None，不报 0、不翻 unjudgeable。"""

    hits = _apply_slots(_load_candidates())
    evidence = [
        agent_research.AgentEvidence(
            tool="kb_search",
            title=hit.title,
            detail=str(hit.llm_evidence or hit.excerpt)[:80],
            source="本地知识库",
            internal_locator=hit.file_path,
            structural_neighbor_demoted=3,
        )
        for hit in hits
    ]
    observation = "；".join(f"{item.title}：{item.detail[:80]}" for item in evidence)
    tel = agent_research.kb_delivery_telemetry(evidence, observation)
    assert tel["structural_neighbor_demoted"] == 3

    old = agent_research.kb_delivery_telemetry(
        [
            agent_research.AgentEvidence(
                tool="kb_search",
                title="旧",
                detail="正文",
                source="本地知识库",
                internal_locator="wiki/x.md",
            )
        ],
        "旧：正文",
    )
    assert "structural_neighbor_demoted" not in old

    missing = inspect_shape_iii(
        {
            "events": [
                {
                    "kind": "tool_result",
                    "payload": {
                        "tool": "kb_search",
                        "telemetry": {
                            "delivered_chars": 12,
                            "hit_count": 1,
                            "source_pages": ["页A"],
                        },
                    },
                }
            ]
        }
    )
    assert missing["status"] == "judgeable"
    assert missing.get("structural_neighbor_demoted") == [None]
    assert missing.get("pointer_dropped") == [None]


def test_reexcerpt_hits_still_keeps_neighbor_windows() -> None:
    """V9a 钉不回退：reexcerpt_hits 本身仍保留颀中/华天/莱宝（槽位是下一刀）。"""

    from intelligence.tests.test_kb_window_reexcerpt import _load_jcet

    kept, _stats = reexcerpt_hits(_load_jcet(), wiki_root=_V9A_PAGES / "wiki")
    stems = {_stem(hit) for hit in kept}
    assert "颀中科技" in stems
    assert "华天科技" in stems
    assert "莱宝高科" in stems


class _stub_retrieve_wiki:
    """把 V9a + V9b 页侧车铺进临时 wiki，供 retrieve 重摘录。"""

    def __init__(self) -> None:
        self._tmp = None
        self._wiki: Path | None = None

    def __enter__(self) -> Path:
        from tempfile import TemporaryDirectory

        self._tmp = TemporaryDirectory()
        root = Path(self._tmp.name)
        wiki = root / "wiki"
        script = root / kb_rag.RAG_SCRIPT_REL
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
        (root / ".rag_index").mkdir()
        for src_root in (_V9A_PAGES / "wiki", _V9B_PAGES / "wiki"):
            for src in src_root.rglob("*.md"):
                dest = wiki / src.relative_to(src_root)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        self._wiki = wiki
        return wiki

    def __exit__(self, *exc: object) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()
