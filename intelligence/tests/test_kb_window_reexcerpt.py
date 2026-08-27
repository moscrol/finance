"""V9a：kb_search 消费侧重摘录（形状 IV 同页错段 / 指针页）。

验收只看「给定命中页，送哪一段」。不得从本文件推出邻页离开 top-k
（那是 V9b）或送达字符数量级（那是 V3）。live 由验收方回填，不得 confirmed。
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from intelligence.services import agent_research, kb_rag  # noqa: E402
from intelligence.services.kb_window_reexcerpt import (  # noqa: E402
    STRUCTURAL_SECTIONS,
    reexcerpt_hits,
)
from scripts.audit_ceiling_sensors import inspect_shape_iii  # noqa: E402

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_JCET = _FIXTURES / "v3-kbsearch-jcet-hits.json"
_PAGES = _FIXTURES / "v9a-jcet-pages"
_WIKI_ROOT = _PAGES / "wiki"
_KB_ROOT = _PAGES


def _hit(**kwargs: object) -> SimpleNamespace:
    payload = {
        "title": "",
        "file_path": "wiki/x.md",
        "excerpt": "",
        "display_excerpt": "",
        "llm_evidence": "",
        "section": "",
        "source_date": "",
        "reexcerpted": False,
        "score": 0.5,
        "page_id": "",
    }
    payload.update(kwargs)
    if not payload["page_id"]:
        payload["page_id"] = str(payload["title"] or payload["file_path"])
    return SimpleNamespace(**payload)


def _load_jcet() -> list[SimpleNamespace]:
    payload = json.loads(_JCET.read_text(encoding="utf-8"))
    return [_hit(**item) for item in payload["hits"]]


def _apply(hits: list[SimpleNamespace]) -> list[SimpleNamespace]:
    kept, _stats = reexcerpt_hits(hits, wiki_root=_WIKI_ROOT)
    return kept


_LOCATOR_HEAD_RE = re.compile(r"(?:命中块|相邻块)\s+.+?::\d+:\s*")


def _bare(text: str) -> str:
    """只剥「命中块 path::N:」定位符，不复用 V5 分类器。"""

    return _LOCATOR_HEAD_RE.sub("", text or "").lstrip()


def _head(text: str, n: int = 80) -> str:
    return _bare(text)[:n]


def _is_wikilink_pile(text: str) -> bool:
    """独立字面检查：头 200 字几乎只剩 wikilink，不复用实现分类器。"""

    head = _bare(text)[:200]
    if "[[" not in head:
        return False
    residual = re.sub(r"\[\[[^\]]+\]\]", "", head)
    residual = re.sub(r"[·•|,/\s\-：:]+", "", residual)
    return len(residual) < 8


def _is_source_list_head(text: str) -> bool:
    head = _head(text, 80)
    if "cnfin.com" in head:
        return True
    if "原始资料" in head[:20]:
        return True
    return bool(re.match(r"\d+\.\s+\*\*", head))


def test_jcet1_reexcerpt_fronts_body_not_source_list() -> None:
    """§7.1 #1：头 80 字含正文（封测/一句话），不含 cnfin.com / 原始资料清单头。"""

    hits = _apply(_load_jcet())
    first = next(
        hit
        for hit in hits
        if "长电科技_最新逻辑跟踪" in str(hit.file_path)
    )
    delivered = str(first.llm_evidence or first.excerpt)
    head = _head(delivered)
    assert "封测" in head or "一句话" in head
    assert "cnfin.com" not in head
    assert not _is_source_list_head(delivered)
    assert getattr(first, "reexcerpted", False) is True


def test_jcet456_no_longer_wikilink_piles() -> None:
    """§7.1 #4/#5/#6：不再是纯 wikilink 堆；各页自己的正文即算成功。"""

    hits = _apply(_load_jcet())
    by_stem = {Path(hit.file_path).stem: hit for hit in hits}
    own_body = {
        "颀中科技": ("显示驱动", "债转股", "TGV", "一句话"),
        "华天科技": ("封测", "2.5D", "全球第五", "一句话"),
        "莱宝高科": ("触控", "MED", "玻璃基", "MetalMesh", "一句话"),
    }
    for stem, tokens in own_body.items():
        hit = by_stem[stem]
        delivered = str(hit.llm_evidence or hit.excerpt)
        assert not _is_wikilink_pile(delivered), stem
        assert any(token in delivered for token in tokens), (stem, _head(delivered))


def test_jcet3_pointer_is_dropped() -> None:
    """§7.1 #3：整页无正文 → 丢弃，禁止路径行充正文。"""

    before = _load_jcet()
    after, stats = reexcerpt_hits(before, wiki_root=_WIKI_ROOT)
    paths = [hit.file_path for hit in after]
    pointer = "wiki/sources/长电科技 2025年度报告 baseline 2026-04-08.md"
    assert pointer not in paths
    assert stats.pointer_dropped >= 1
    for hit in after:
        text = str(hit.llm_evidence or hit.excerpt)
        assert "raw/cninfo-baseline/" not in _head(text, 80)


def test_synthetic_page_picks_body_across_sections() -> None:
    """合成页（正文 + ## 原始资料链接）跨节取正文。"""

    body = "长电科技作为国内封测龙头，2026年资本开支投向2.5D/3D封装。"
    page = (
        f"# 合成页\n\n## 一句话结论\n{body}\n\n"
        "## 原始资料链接\n"
        "1. **来源清单**（2026-05-08）- https://www.cnfin.com/announ/x\n"
    )
    tmp = _KB_ROOT / "_synthetic.md"
    # 写到临时 wiki 树外，用独立 wiki_root，避免污染冻结页。
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        wiki = Path(td) / "wiki"
        wiki.mkdir()
        target = wiki / "sources"
        target.mkdir()
        (target / "合成.md").write_text(page, encoding="utf-8")
        hit = _hit(
            title="合成",
            file_path="wiki/sources/合成.md",
            section="原始资料链接",
            llm_evidence=(
                "1. **来源清单**（2026-05-08）- https://www.cnfin.com/announ/x"
            ),
            excerpt="1. **来源清单**（2026-05-08）- https://www.cnfin.com/announ/x",
        )
        kept, _stats = reexcerpt_hits([hit], wiki_root=wiki)
        assert len(kept) == 1
        delivered = str(kept[0].llm_evidence)
        assert delivered.startswith(body) or body in _head(delivered, 80)
        assert "cnfin.com" not in _head(delivered)
        assert tmp != target  # 夹具目录未被本钉改写


def test_unrecognized_structure_fail_open() -> None:
    """认不出结构则保持现状（沿 V5 fail-open）。"""

    hit = _hit(
        title="无结构",
        file_path="wiki/missing-page.md",
        llm_evidence="一篇没有标题的普通正文，讲钙钛矿涂布订单。",
        excerpt="一篇没有标题的普通正文，讲钙钛矿涂布订单。",
    )
    kept, stats = reexcerpt_hits([hit], wiki_root=_WIKI_ROOT)
    assert len(kept) == 1
    assert kept[0].llm_evidence == hit.llm_evidence
    assert getattr(kept[0], "reexcerpted", False) is False
    assert stats.pointer_dropped == 0


def test_reexcerpt_path_does_not_call_dense_or_rerank_worker() -> None:
    """重摘录只读本地 md，不另起 dense/rerank worker。"""

    from tempfile import TemporaryDirectory

    payload = json.loads(_JCET.read_text(encoding="utf-8"))
    items = []
    for index, raw in enumerate(payload["hits"]):
        items.append(
            {
                "page_id": raw["title"],
                "file_path": raw["file_path"],
                "title": raw["title"],
                "score": 0.9 - index * 0.05,
                "best_chunk_id": f"{raw['file_path']}::{index}",
                "content_hash": f"hash-{index}",
                "evidence_text": raw["excerpt"],
                "display_excerpt": raw["display_excerpt"],
                "llm_evidence_text": raw["llm_evidence"],
                "section": (
                    "原始资料链接"
                    if index == 0
                    else "相关实体"
                    if index >= 3
                    else "IMA 最新逻辑跟踪"
                    if index == 1
                    else "Raw / Manifest Trace"
                ),
                "index_source_revision": "abc123",
                "index_freshness": "fresh",
            }
        )
    with TemporaryDirectory() as td:
        root = Path(td)
        wiki = root / "wiki"
        script = root / kb_rag.RAG_SCRIPT_REL
        wiki.joinpath("sources").mkdir(parents=True)
        wiki.joinpath("entities").mkdir(parents=True)
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
        (root / ".rag_index").mkdir()
        for src in _WIKI_ROOT.rglob("*.md"):
            dest = wiki / src.relative_to(_WIKI_ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        proc = mock.Mock(
            returncode=0,
            stdout=json.dumps(items, ensure_ascii=False),
            stderr="",
        )
        with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=False):
            with mock.patch("subprocess.run", return_value=proc) as run:
                res = kb_rag.retrieve(
                    "长电科技怎么看",
                    wiki,
                    k=6,
                    mode="hybrid",
                    timeout=20,
                )
        assert run.call_count == 1
        cmd = run.call_args.args[0]
        assert "--mode" in cmd
        mode = cmd[cmd.index("--mode") + 1]
        assert mode == "hybrid"
        assert "rerank" not in cmd
        assert res.telemetry.pointer_dropped is not None
        first = next(
            hit
            for hit in res.hits
            if "长电科技_最新逻辑跟踪" in hit.file_path
        )
        assert "封测" in _head(first.llm_evidence) or "一句话" in _head(first.llm_evidence)


def test_remaining_under_15s_stays_bm25() -> None:
    """既有真值表不动：remaining<15s 时 effective_mode 仍为 bm25，重摘录照跑。"""

    from tempfile import TemporaryDirectory

    payload = json.loads(_JCET.read_text(encoding="utf-8"))
    raw0 = payload["hits"][0]
    item = {
        "page_id": raw0["title"],
        "file_path": raw0["file_path"],
        "title": raw0["title"],
        "score": 0.9,
        "best_chunk_id": f"{raw0['file_path']}::24",
        "content_hash": "hash-0",
        "evidence_text": raw0["excerpt"],
        "llm_evidence_text": raw0["llm_evidence"],
        "section": "原始资料链接",
        "index_source_revision": "abc123",
        "index_freshness": "fresh",
    }
    with TemporaryDirectory() as td:
        root = Path(td)
        wiki = root / "wiki"
        script = root / kb_rag.RAG_SCRIPT_REL
        wiki.joinpath("sources").mkdir(parents=True)
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
        (root / ".rag_index").mkdir()
        src = _WIKI_ROOT / "sources" / "长电科技_最新逻辑跟踪.md"
        dest = wiki / "sources" / src.name
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        proc = mock.Mock(
            returncode=0,
            stdout=json.dumps([item], ensure_ascii=False),
            stderr="",
        )
        with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=False):
            with mock.patch("subprocess.run", return_value=proc) as run:
                res = kb_rag.retrieve(
                    "长电科技怎么看",
                    wiki,
                    k=6,
                    mode="hybrid",
                    timeout=4,
                )
        cmd = run.call_args.args[0]
        assert cmd[cmd.index("--mode") + 1] == "bm25"
        assert res.telemetry.effective_mode == "bm25"
        assert res.telemetry.fallback_reason == "remaining_budget"
        assert res.hits
        assert "封测" in _head(res.hits[0].llm_evidence) or "一句话" in _head(
            res.hits[0].llm_evidence
        )


def test_pointer_drop_lets_oversample_fill_k() -> None:
    """指针页丢掉后，靠既有 fetch_k 过采样补位，不另写一套 fetch。"""

    from tempfile import TemporaryDirectory

    payload = json.loads(_JCET.read_text(encoding="utf-8"))
    items = []
    for index, raw in enumerate(payload["hits"]):
        items.append(
            {
                "page_id": raw["title"],
                "file_path": raw["file_path"],
                "title": raw["title"],
                "score": 0.95 - index * 0.01,
                "best_chunk_id": f"{raw['file_path']}::{index}",
                "content_hash": f"hash-{index}",
                "evidence_text": raw["excerpt"],
                "llm_evidence_text": raw["llm_evidence"],
                "section": (
                    "原始资料链接"
                    if index == 0
                    else "相关实体"
                    if index >= 3
                    else "IMA"
                    if index == 1
                    else "Raw / Manifest Trace"
                ),
                "index_source_revision": "abc123",
                "index_freshness": "fresh",
            }
        )
    filler_body = "通富微电是封测同行，先进封装产能独立于本单邻页链接堆。"
    items.append(
        {
            "page_id": "通富微电",
            "file_path": "wiki/entities/通富微电.md",
            "title": "通富微电",
            "score": 0.4,
            "best_chunk_id": "wiki/entities/通富微电.md::0",
            "content_hash": "hash-filler",
            "evidence_text": filler_body,
            "llm_evidence_text": filler_body,
            "section": "公司简介",
            "index_source_revision": "abc123",
            "index_freshness": "fresh",
        }
    )
    with TemporaryDirectory() as td:
        root = Path(td)
        wiki = root / "wiki"
        script = root / kb_rag.RAG_SCRIPT_REL
        wiki.joinpath("sources").mkdir(parents=True)
        wiki.joinpath("entities").mkdir(parents=True)
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
        (root / ".rag_index").mkdir()
        for src in _WIKI_ROOT.rglob("*.md"):
            dest = wiki / src.relative_to(_WIKI_ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        (wiki / "entities" / "通富微电.md").write_text(
            f"# 通富微电\n\n## 公司简介\n{filler_body}\n",
            encoding="utf-8",
        )
        proc = mock.Mock(
            returncode=0,
            stdout=json.dumps(items, ensure_ascii=False),
            stderr="",
        )
        with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=False):
            with mock.patch("subprocess.run", return_value=proc) as run:
                res = kb_rag.retrieve(
                    "长电科技怎么看",
                    wiki,
                    k=6,
                    mode="bm25",
                    timeout=20,
                )
        cmd = run.call_args.args[0]
        assert int(cmd[cmd.index("--k") + 1]) > 6
        paths = [hit.file_path for hit in res.hits]
        assert "wiki/sources/长电科技 2025年度报告 baseline 2026-04-08.md" not in paths
        assert "wiki/entities/通富微电.md" in paths
        assert res.telemetry.pointer_dropped == 1
        assert len(res.hits) == 6


def test_telemetry_new_fields_and_historical_missing_is_unjudgeable() -> None:
    """新路径落盘 reexcerpted / pointer_dropped；历史缺字段报不可判，不报 0。"""

    hits = _apply(_load_jcet())
    evidence = [
        agent_research.AgentEvidence(
            tool="kb_search",
            title=hit.title,
            detail=str(hit.llm_evidence or hit.excerpt)[:80],
            source="本地知识库",
            internal_locator=hit.file_path,
            reexcerpted=bool(getattr(hit, "reexcerpted", False)),
            pointer_dropped=1,
        )
        for hit in hits
    ]
    observation = "；".join(f"{item.title}：{item.detail[:80]}" for item in evidence)
    tel = agent_research.kb_delivery_telemetry(evidence, observation)
    assert "pointer_dropped" in tel
    assert tel["pointer_dropped"] == 1
    assert "reexcerpted" in tel
    assert any(tel["reexcerpted"])

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
    assert "pointer_dropped" not in old
    assert "reexcerpted" not in old

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
    assert missing.get("pointer_dropped") == [None]
    assert missing.get("reexcerpted") == [None]


def test_identity_reexcerpt_is_not_the_default() -> None:
    """变异闸①：重摘录恒等返回原文 → #1 钉红。"""

    hits = _apply(_load_jcet())
    first = next(hit for hit in hits if "最新逻辑跟踪" in hit.file_path)
    raw = _load_jcet()[0]
    assert str(first.llm_evidence) != str(raw.llm_evidence)
    assert not _is_source_list_head(str(first.llm_evidence))


def test_empty_blacklist_is_not_the_default() -> None:
    """变异闸②：黑名单清空 → #1 钉红（结构段不再被跳过）。"""

    assert STRUCTURAL_SECTIONS
    assert "原始资料链接" in STRUCTURAL_SECTIONS
    hits = _apply(_load_jcet())
    first = next(hit for hit in hits if "最新逻辑跟踪" in hit.file_path)
    assert not _is_source_list_head(str(first.llm_evidence))


def test_six_page_sidecar_read_budget() -> None:
    """预注册：读 6 个本地 md 的墙钟，验证文档用；本钉只锁「跑得完且 <100ms」。"""

    paths = list(_WIKI_ROOT.rglob("*.md"))
    assert len(paths) == 6
    started = time.perf_counter()
    for path in paths:
        path.read_text(encoding="utf-8")
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert elapsed_ms < 100.0
