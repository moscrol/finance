"""能力升级任务包 02 · 深读检索：找到页以后继续读到能解题。

覆盖合同任务 5 的反向用例，各留独立测试：
- 答案藏在章节末端（超过模型可见 240 字）
- 表头在相邻块（表格切片每片带表头）
- 别名与股票代码混用（面包屑末级同名定位）
- 无关页变更（fresh 命中不被重读）
- 目标页改变（stale 命中当轮重读原页：原节在则恢复、原节没了则丢并写具体缺口）
- 历史资料与最新资料冲突（同节两个日期都送达，节内最晚日期随行）
- 官方原文与转载同文不同发布者（web_fetch 来源分类）

全部离线：知识库页写进临时目录，检索器子进程用 ``subprocess.run`` 打桩，取页用
``fetch_web_page`` 打桩。不调模型。
"""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from intelligence.services import agent_research, closed_loop_retrieval, kb_rag, web_research
from intelligence.services.agent_research import AgentToolContext
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.tool_result_budget import MAX_EVIDENCE_DETAIL_CHARS

# ---------------------------------------------------------------------------
# 夹具：一页「长电科技」，答案（HBM 封装产能数字）藏在「产能」节末端，
# 表格在「财务映射」节，另有结构小节。
# ---------------------------------------------------------------------------
_FILLER = "先进封装是把多颗芯片在封装层面集成的技术路线，包括 2.5D、3D 与扇出型封装。" * 4  # ≈ 160 字
_PAGE = f"""---
title: 长电科技
tags: [封测, 先进封装]
---

# 长电科技

## 一句话

长电科技是国内封测龙头，先进封装占比持续提升。

## 产能

{_FILLER}
{_FILLER}
公司 2026 年资本开支重点投向 2.5D/3D 封装。
公告披露：HBM 封装产能规划为每月 1.2 万片，2026-06-30 前投产。

## 财务映射

| 逻辑 | 影响科目 | 金额（亿元） |
| --- | --- | --- |
| 百亿资本开支扩产 | 固定资产、在建工程 | 100 |
| HBM 封装放量 | 营业收入 | 35 |
| 折旧上升 | 营业成本 | 8 |
| 客户导入 | 应收账款 | 5 |

## 反证与风险

2025-03-01 的判断：HBM 需求存在不确定性，产能利用率或低于 70%。
2026-05-12 的更新：一季度产能利用率回升到 85%，此前的担忧部分证伪。

## 相关实体

- [[通富微电]]
- [[华天科技]]

## 原始资料链接

1. **长电科技年报** https://example.com/jcet
"""


def _write_kb(root: Path) -> Path:
    wiki = root / "wiki"
    page = wiki / "entities" / "长电科技.md"
    page.parent.mkdir(parents=True)
    page.write_text(_PAGE, encoding="utf-8")
    script = root / kb_rag.RAG_SCRIPT_REL
    script.parent.mkdir(parents=True)
    script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    (root / ".rag_index").mkdir()
    return wiki


def _hit(**overrides: object) -> kb_rag.WikiHit:
    payload: dict[str, object] = dict(
        page_id="entities/长电科技",
        file_path="wiki/entities/长电科技.md",
        title="长电科技",
        score=0.9,
        excerpt="产能 展示短摘录。",
        llm_evidence="命中块 wiki/entities/长电科技.md::2: " + _FILLER[:120],
        display_excerpt="产能 展示短摘录。",
        best_chunk_id="wiki/entities/长电科技.md::2",
        evidence_chunk_ids=("wiki/entities/长电科技.md::2",),
        evidence_query_terms=("长电科技", "HBM"),
        evidence_char_budget=1200,
        section="长电科技 > 产能",
        content_hash="a" * 40,
        index_built_at="2026-08-31T11:01:16Z",
        index_source_revision="manifest:v1:abc",
        index_freshness="fresh",
    )
    payload.update(overrides)
    return kb_rag.WikiHit(**payload)  # type: ignore[arg-type]


def _raw_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "page_id": "entities/长电科技",
        "file_path": "wiki/entities/长电科技.md",
        "title": "长电科技",
        "score": 0.9,
        "best_chunk_id": "wiki/entities/长电科技.md::2",
        "section": "长电科技 > 产能",
        "content_hash": "a" * 40,
        "display_excerpt": "产能 展示短摘录。",
        "llm_evidence_text": "命中块 wiki/entities/长电科技.md::2: " + _FILLER[:120],
        "evidence_chunk_ids": ["wiki/entities/长电科技.md::2"],
        "evidence_query_terms": ["长电科技", "HBM"],
        "evidence_char_budget": 1200,
        "index_built_at": "2026-08-31T11:01:16Z",
        "index_source_revision": "manifest:v1:abc",
        "index_freshness": "fresh",
    }
    row.update(overrides)
    return row


def _retrieve(wiki: Path, rows: list[dict[str, object]], **kwargs: object) -> kb_rag.WikiRagResult:
    proc = mock.Mock(returncode=0, stdout=json.dumps(rows, ensure_ascii=False), stderr="")
    kb_rag.clear_result_cache()
    with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=False):
        with mock.patch("subprocess.run", return_value=proc):
            return kb_rag.retrieve("长电科技 HBM 封装产能", wiki, k=3, worker_enabled=False, **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 常数钉死：深读每段宽度 = 模型可见 detail 上限。改任何一边都要一起改。
# ---------------------------------------------------------------------------
def test_deep_read_item_chars_pinned_to_model_visible_detail_cap() -> None:
    assert kb_rag.DEEP_READ_ITEM_CHARS == MAX_EVIDENCE_DETAIL_CHARS
    assert agent_research.WEB_FETCH_FOCUS_ITEM_CHARS == MAX_EVIDENCE_DETAIL_CHARS


# ---------------------------------------------------------------------------
# 切段
# ---------------------------------------------------------------------------
def test_section_slices_keep_paragraphs_within_item_chars_and_split_on_sentences() -> None:
    text = "第一句很短。" + ("第二句很长" * 30 + "。") + "\n第三句另起一行。"
    slices = kb_rag.section_slices(text, 60)
    assert slices
    assert all(len(item) <= 60 for item in slices)
    joined = "".join(slices)
    assert "第一句很短" in joined and "第三句另起一行" in joined


def test_table_slices_carry_header_and_separator_into_every_slice() -> None:
    header = "| 逻辑 | 影响科目 | 金额（亿元） |"
    sep = "| --- | --- | --- |"
    rows = [f"| 项目{i} | 科目{i} | {i} |" for i in range(12)]
    slices = kb_rag.section_slices("\n".join([header, sep, *rows]), 120)
    assert len(slices) > 1, "12 行表格 120 字预算必须切成多片"
    for item in slices:
        assert item.startswith("|逻辑|影响科目|金额（亿元）|\n|---|---|---|"), item
        assert len(item) <= 120
    assert "项目11" in slices[-1]


# ---------------------------------------------------------------------------
# 节定位
# ---------------------------------------------------------------------------
def test_locate_section_exact_then_alias_code_tail_then_window_then_terms() -> None:
    sections = [
        ("国光电气", "公司简介。"),
        ("国光电气 > 反证与风险", "反证/风险 2026-06-16 微波器件订单不确定。"),
        ("国光电气 > 财务映射", "营业收入 12 亿。"),
    ]
    assert kb_rag.locate_section(sections, crumb="国光电气 > 财务映射", window_text="", terms=()) == 2
    # 别名与股票代码混用：索引面包屑带代码前缀，当前页没有——末级同名仍能对上。
    assert kb_rag.locate_section(sections, crumb="688776_国光电气 > 反证与风险", window_text="", terms=()) == 1
    # 面包屑对不上时用窗口前缀落点。
    assert kb_rag.locate_section(sections, crumb="不存在的节", window_text="命中块 x::1: 营业收入 12 亿。", terms=()) == 2
    # 都没有时按问句词最多的节。
    assert kb_rag.locate_section(sections, crumb="", window_text="", terms=("微波器件", "订单")) == 1
    assert kb_rag.locate_section([], crumb="x", window_text="y", terms=("z",)) is None


# ---------------------------------------------------------------------------
# 深读：节末答案 / 表头 / 目录 / 预算
# ---------------------------------------------------------------------------
def test_deep_read_reaches_answer_at_section_end_and_lists_outline() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        hit = _hit()
        stats = kb_rag.deep_read_hits([hit], wiki_root=wiki, query="长电科技 HBM 封装产能多少")
        assert stats.pages == 1 and stats.paragraphs >= 2
        assert hit.deep_read_section == "长电科技 > 产能"
        assert all(len(p) <= MAX_EVIDENCE_DETAIL_CHARS for p in hit.deep_read_paragraphs)
        tail = "".join(hit.deep_read_paragraphs)
        assert "每月 1.2 万片" in tail, "节末答案必须进深读段"
        assert hit.section_latest_date == "2026-06-30"
        assert not hit.deep_read_truncated
        # 目录：其余章节，去掉结构小节；不含被读的那节。
        tails = [kb_rag._crumb_tail(c) for c in hit.page_outline]
        assert "财务映射" in tails and "反证与风险" in tails and "一句话" in tails
        assert "产能" not in tails
        assert "相关实体" not in tails and "原始资料链接" not in tails


def test_deep_read_table_section_delivers_header_with_each_slice() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        hit = _hit(section="长电科技 > 财务映射", llm_evidence="命中块 x::5: | HBM 封装放量 | 营业收入 | 35 |")
        kb_rag.deep_read_hits([hit], wiki_root=wiki, query="长电科技 HBM 营业收入", item_chars=90)
        assert hit.deep_read_paragraphs
        for item in hit.deep_read_paragraphs:
            assert item.startswith("|逻辑|影响科目|金额（亿元）|"), "表头（含单位）必须随每片"
        assert any("|35|" in item.replace(" ", "") for item in hit.deep_read_paragraphs)


def test_deep_read_conflicting_dated_statements_both_delivered() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        hit = _hit(section="长电科技 > 反证与风险", llm_evidence="命中块 x::7: 产能利用率")
        kb_rag.deep_read_hits([hit], wiki_root=wiki, query="长电科技 产能利用率 风险")
        joined = "\n".join(hit.deep_read_paragraphs)
        assert "2025-03-01" in joined and "2026-05-12" in joined, "新旧判断都要在，由模型按日期取舍"
        assert hit.section_latest_date == "2026-05-12"


def test_deep_read_budget_prefers_term_paragraphs_and_reports_omission() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        hit = _hit()
        # 预算只够一两段：含问句词（HBM/产能）的节末段要优先于纯填充段。
        kb_rag.deep_read_hits([hit], wiki_root=wiki, query="长电科技 HBM 封装产能", per_hit_chars=300, total_chars=300)
        assert hit.deep_read_paragraphs
        assert sum(len(p) for p in hit.deep_read_paragraphs) <= 300
        assert any("HBM" in p for p in hit.deep_read_paragraphs)
        assert hit.deep_read_truncated and hit.deep_read_omitted_chars > 0


def test_deep_read_total_budget_leaves_room_for_every_page() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        wiki = _write_kb(root)
        second = wiki / "entities" / "通富微电.md"
        second.write_text(
            "# 通富微电\n\n## 产能\n\n通富微电 HBM 封装产能规划为每月 0.8 万片。\n" + "填充。" * 200 + "\n",
            encoding="utf-8",
        )
        first = _hit()
        other = _hit(
            page_id="entities/通富微电",
            file_path="wiki/entities/通富微电.md",
            title="通富微电",
            section="通富微电 > 产能",
            llm_evidence="命中块 y::1: 通富微电 HBM",
            evidence_query_terms=("通富微电", "HBM"),
        )
        stats = kb_rag.deep_read_hits([first, other], wiki_root=wiki, query="长电科技 通富微电 HBM 产能对比", total_chars=700)
        assert stats.pages == 2, "跨实体比较：第一页不能把预算吃光"
        assert first.deep_read_paragraphs and other.deep_read_paragraphs
        assert any("0.8 万片" in p for p in other.deep_read_paragraphs)
        assert stats.chars <= 700


def test_deep_read_fail_open_when_page_missing_or_disabled() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        missing = _hit(file_path="wiki/entities/不存在.md")
        stats = kb_rag.deep_read_hits([missing], wiki_root=wiki, query="x")
        assert stats.pages == 0 and stats.skipped_pages == 1
        assert missing.deep_read_paragraphs == ()
        hit = _hit()
        assert kb_rag.deep_read_hits([hit], wiki_root=wiki, query="x", total_chars=0).pages == 0
        with mock.patch.dict("os.environ", {kb_rag.DEEP_READ_TOTAL_ENV: "0"}):
            assert kb_rag.deep_read_total_chars() == 0
        with mock.patch.dict("os.environ", {kb_rag.DEEP_READ_TOTAL_ENV: "junk"}):
            assert kb_rag.deep_read_total_chars() == kb_rag.DEEP_READ_TOTAL_CHARS


# ---------------------------------------------------------------------------
# 过期命中当轮重读原页
# ---------------------------------------------------------------------------
def test_stale_hit_recovered_from_live_page_when_section_still_matches() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        stale = _hit(index_freshness="stale", llm_evidence="命中块 x::2: 旧版正文，索引建后页面已改。")
        stats = kb_rag.recover_stale_hits([stale], wiki_root=wiki, query="长电科技 HBM 封装产能")
        assert stats.recovered == 1 and stats.unrecoverable == 0
        assert stale.index_freshness == kb_rag.FRESHNESS_RECOVERED
        assert stale.recovered_from_source
        assert "HBM" in stale.llm_evidence and "旧版正文" not in stale.llm_evidence
        assert len(stale.content_hash) == 40 and stale.content_hash != "a" * 40
        assert stale.excerpt and stale.display_excerpt == stale.excerpt


def test_stale_hit_dropped_with_specific_gap_when_section_gone() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        wiki = _write_kb(root)
        # 目标页改了：整个「产能」节被删掉，问句词也不再出现。
        page = wiki / "entities" / "长电科技.md"
        page.write_text("# 长电科技\n\n## 一句话\n\n只剩一句话。\n", encoding="utf-8")
        stale = _hit(index_freshness="stale", llm_evidence="命中块 x::2: HBM 封装产能")
        stats = kb_rag.recover_stale_hits([stale], wiki_root=wiki, query="长电科技 HBM 封装产能")
        assert stats.recovered == 0 and stats.unrecoverable == 1
        assert stale.index_freshness == "stale"
        rows = [_raw_row(index_freshness="stale")]
        res = _retrieve(wiki, rows)
        assert res.hits == []
        assert "已尝试当轮重读原页" in res.warning
        assert res.telemetry.stale_unrecoverable == 1 and res.telemetry.stale_recovered == 0


def test_fresh_hits_are_not_reread_when_another_hit_is_stale() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        fresh = _hit()
        original = fresh.llm_evidence
        stale = _hit(index_freshness="stale", section="长电科技 > 反证与风险", llm_evidence="命中块 x::7: 产能利用率")
        stats = kb_rag.recover_stale_hits([fresh, stale], wiki_root=wiki, query="长电科技 产能利用率")
        assert stats.recovered == 1
        assert fresh.llm_evidence == original and not fresh.recovered_from_source
        assert fresh.index_freshness == "fresh"


def test_retrieve_keeps_recovered_hit_and_reports_it() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        res = _retrieve(wiki, [_raw_row(index_freshness="stale")])
        assert res.ok and len(res.hits) == 1
        assert res.hits[0].index_freshness == kb_rag.FRESHNESS_RECOVERED
        assert "重读原页恢复" in res.warning
        assert res.telemetry.stale_recovered == 1
        assert res.telemetry.index_freshness == kb_rag.FRESHNESS_RECOVERED
        assert "过期命中重读恢复=1" in res.telemetry.summary_line()


def test_retrieve_populates_deep_read_and_scope_telemetry() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        res = _retrieve(wiki, [_raw_row()])
        hit = res.hits[0]
        assert hit.deep_read_paragraphs and any("1.2 万片" in p for p in hit.deep_read_paragraphs)
        assert res.telemetry.deep_read_pages == 1
        assert res.telemetry.deep_read_paragraphs == len(hit.deep_read_paragraphs)
        assert res.telemetry.deep_read_chars == sum(len(p) for p in hit.deep_read_paragraphs)
        assert res.telemetry.material_scope == "general"
        assert "深读=1页" in res.telemetry.summary_line()


def test_retrieve_stale_recovery_disabled_by_env_restores_drop_contract() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        with mock.patch.dict("os.environ", {kb_rag.STALE_RECOVERY_ENV: "0"}):
            res = _retrieve(wiki, [_raw_row(index_freshness="stale")])
        assert res.hits == [] and "丢弃 1 条非 fresh 命中" in res.warning
        assert res.telemetry.stale_recovered is None


def test_retrieve_deep_read_disabled_by_env() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        with mock.patch.dict("os.environ", {kb_rag.DEEP_READ_TOTAL_ENV: "0"}):
            res = _retrieve(wiki, [_raw_row()])
        assert res.hits[0].deep_read_paragraphs == ()
        assert res.telemetry.deep_read_pages == 0


def test_result_cache_accepts_recovered_hits_under_require_fresh() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        first = _retrieve(wiki, [_raw_row(index_freshness="stale")], cache_scope="task-1")
        assert first.hits and first.hits[0].index_freshness == kb_rag.FRESHNESS_RECOVERED
        proc = mock.Mock(returncode=0, stdout="[]", stderr="")
        with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=False):
            with mock.patch("subprocess.run", return_value=proc) as run:
                again = kb_rag.retrieve("长电科技 HBM 封装产能", wiki, k=3, worker_enabled=False, cache_scope="task-1")
        assert again.telemetry.cache_hit and again.hits
        run.assert_not_called()


# ---------------------------------------------------------------------------
# 材料口径 / 日期 / 问句词
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("query", "scope"),
    [
        ("长电科技最新产能进展", "current"),
        ("2024年光模块行情回顾", "history"),
        ("液冷是什么原理", "concept"),
        ("怎么看估值口径", "method"),
        ("长电科技 HBM 封装产能", "general"),
        ("2024年报里的资本开支", "general"),
    ],
)
def test_material_scope_for_query(query: str, scope: str) -> None:
    assert kb_rag.material_scope_for_query(query) == scope


def test_section_latest_date_and_query_terms() -> None:
    assert kb_rag.section_latest_date("2025年3月1日 与 2026-05-12 以及 2026/13/40") == "2026-05-12"
    assert kb_rag.section_latest_date("没有日期") == ""
    terms = kb_rag.deep_read_query_terms("长电科技 HBM 封装产能有哪些公司受益 688776")
    assert "长电科技" in terms and "hbm" in terms and "688776" in terms and "封装" in terms
    assert "哪些" not in terms and "公司" not in terms and "受益" not in terms
    assert terms[0] == max(terms, key=len)


def test_query_terms_split_on_function_words_and_keep_alnum_tokens() -> None:
    terms = kb_rag.deep_read_query_terms("800G和1.6T光模块的单价大概是多少？")
    assert "800g" in terms and "1.6t" in terms and "光模块" in terms and "单价" in terms
    for junk in ("块的", "是多", "概是", "价大", "大概", "多少"):
        assert junk not in terms, junk
    terms = kb_rag.deep_read_query_terms("沃格光电2024年盈利情况怎么样，为什么？")
    assert "沃格光电" in terms and "2024" in terms and "盈利" in terms
    assert "年盈" not in terms and "么样" not in terms and "况怎" not in terms
    terms = kb_rag.deep_read_query_terms("洛阳钼业的铜产能多大，靠哪两个矿？")
    assert "洛阳钼业" in terms and "产能" in terms
    assert "靠哪两个矿" not in terms and "业的" not in terms


def test_deep_read_also_reads_section_with_more_query_terms_than_hit_section() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        # 命中落在「一句话」（不含问句词），答案在「反证与风险」（含 产能利用率）。
        hit = _hit(section="长电科技 > 一句话", llm_evidence="命中块 x::1: 长电科技是国内封测龙头", evidence_query_terms=())
        kb_rag.deep_read_hits([hit], wiki_root=wiki, query="长电科技 产能利用率 回升到多少")
        sections = [kb_rag._crumb_tail(c) for c in hit.deep_read_sections]
        assert sections[0] == "一句话" and "反证与风险" in sections, sections
        assert any("85%" in p for p in hit.deep_read_paragraphs), "所缺章节里的答案要进深读段"
        items, note = agent_research.deep_read_evidence([hit])
        assert any("深读《反证与风险》" in item.title for item in items)
        assert "《一句话》《反证与风险》" in note


def test_deep_read_only_reads_top_pages() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        hits = [_hit() for _ in range(5)]
        stats = kb_rag.deep_read_hits(hits, wiki_root=wiki, query="长电科技 HBM 封装产能", max_pages=3)
        assert stats.pages == 3
        assert all(h.deep_read_paragraphs for h in hits[:3]) and all(not h.deep_read_paragraphs for h in hits[3:])


# ---------------------------------------------------------------------------
# kb_search 送达：段落级证据 + 限定语在前 + 送达遥测分开计数
# ---------------------------------------------------------------------------
def _context() -> AgentToolContext:
    return AgentToolContext(
        ResearchDeadline.from_timeout(30.0),
        lambda: False,
        InformationCutoff(date(2026, 9, 9), "runtime_default"),
    )


def test_kb_search_delivers_deep_read_paragraphs_after_primary_hits() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        hit = _hit()
        kb_rag.deep_read_hits([hit], wiki_root=wiki, query="长电科技 HBM 封装产能")
        rag = SimpleNamespace(hits=[hit], telemetry=kb_rag.RetrievalTelemetry(status="ok", hit_count=1))
        tool = agent_research.build_default_tools(lambda *_a, **_k: rag)["kb_search"]
        evidence, observation, trace = tool("长电科技 HBM 封装产能", _context())
        primary = [item for item in evidence if not item.deep_read]
        deep = [item for item in evidence if item.deep_read]
        assert len(primary) == 1 and deep, "命中之后跟着段落级证据"
        assert evidence[0] is primary[0], "命中排在深读段之前"
        assert all(len(item.detail) <= MAX_EVIDENCE_DETAIL_CHARS for item in deep)
        assert all(item.title.startswith("长电科技｜深读《产能》") for item in deep)
        assert any("1.2 万片" in item.detail for item in deep)
        assert observation.startswith("已深读 1 页"), observation
        assert "同页其余章节" in observation and "财务映射" in observation
        assert trace.status == "success" and trace.result_count == len(evidence)
        telemetry = agent_research.kb_delivery_telemetry(evidence, observation)
        assert telemetry["hit_count"] == 1
        assert telemetry["deep_read_items"] == len(deep)
        assert telemetry["deep_read_chars"] == sum(len(item.detail) for item in deep)


def test_kb_search_marks_recovered_hits_in_freshness_and_observation() -> None:
    with tempfile.TemporaryDirectory() as td:
        wiki = _write_kb(Path(td))
        stale = _hit(index_freshness="stale", llm_evidence="命中块 x::2: 旧版正文")
        kb_rag.recover_stale_hits([stale], wiki_root=wiki, query="长电科技 HBM 封装产能")
        rag = SimpleNamespace(hits=[stale], telemetry=kb_rag.RetrievalTelemetry(status="ok", hit_count=1))
        tool = agent_research.build_default_tools(lambda *_a, **_k: rag)["kb_search"]
        with mock.patch.dict("os.environ", {kb_rag.DEEP_READ_TOTAL_ENV: "0"}):
            evidence, observation, _trace = tool("长电科技 HBM 封装产能", _context())
        assert evidence[0].freshness == kb_rag.FRESHNESS_RECOVERED
        assert observation.startswith("1 条命中的索引已过期，正文取自当前页面")


def test_deep_read_evidence_skips_paragraphs_already_visible_in_hit_window() -> None:
    hit = _hit(
        llm_evidence="命中块 x::2: 这一段已经在命中窗口里。",
        deep_read_section="长电科技 > 产能",
        deep_read_paragraphs=("这一段已经在命中窗口里。", "这一段是新的节末内容。"),
    )
    items, note = agent_research.deep_read_evidence([hit])
    assert [item.detail for item in items] == ["这一段是新的节末内容。"]
    assert items[0].title == "长电科技｜深读《产能》1/1"
    assert note.startswith("已深读 1 页共 1 段")


def test_deep_read_evidence_empty_when_nothing_to_add() -> None:
    assert agent_research.deep_read_evidence([_hit()]) == ([], "")


# ---------------------------------------------------------------------------
# web_fetch：定向选段 + 发布主体 / 文档类型
# ---------------------------------------------------------------------------
def test_page_focus_chunks_reach_answer_deep_in_page_and_keep_head() -> None:
    head = "贵州茅台2024年年度报告全文。\n\n"
    filler = "\n\n".join(f"第{i}节 无关叙述 " + "内容" * 60 for i in range(30))
    tail = "\n\n经营活动产生的现金流量净额为 924.6 亿元，同比增长 38.85%。"
    text = head + filler + tail
    terms = kb_rag.deep_read_query_terms("贵州茅台 经营活动现金流量净额 同比")
    chunks, total, matched = agent_research.page_focus_chunks(text, terms)
    assert total > agent_research.WEB_FETCH_FOCUS_MAX_ITEMS
    assert len(chunks) == agent_research.WEB_FETCH_FOCUS_MAX_ITEMS
    assert chunks[0].startswith("贵州茅台2024年年度报告全文"), "页首永远保留"
    assert any("924.6" in chunk for chunk in chunks), "页尾答案要被定向选中"
    assert matched >= 1
    assert all(len(chunk) <= MAX_EVIDENCE_DETAIL_CHARS for chunk in chunks)
    # 无问句词：退化为页首顺序。
    plain, _total, plain_matched = agent_research.page_focus_chunks(text, ())
    assert plain_matched == 0 and plain[0] == chunks[0] and not any("924.6" in c for c in plain)


@pytest.mark.parametrize(
    ("url", "title", "publisher", "document", "official"),
    [
        ("http://www.cninfo.com.cn/new/disclosure/detail?stockCode=600519", "贵州茅台：关于回购股份的公告", "official_disclosure", "announcement", True),
        ("https://finance.sina.com.cn/stock/relnews/cn/2026-09-01/doc-1.shtml", "贵州茅台：关于回购股份的公告", "media", "announcement", False),
        ("https://www.csrc.gov.cn/csrc/c100028/c1234.shtml", "关于加强上市公司监管的意见", "regulator", "policy", True),
        ("https://zh.wikipedia.org/wiki/贵州茅台", "贵州茅台", "encyclopedia", "reference", False),
        ("https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2024-04-03/600519_20240403_1.pdf", "贵州茅台2024年年度报告", "official_disclosure", "periodic_report", True),
        ("https://www.unknown-site.example/page", "随便一页", "other", "webpage", False),
    ],
)
def test_classify_web_source(url: str, title: str, publisher: str, document: str, official: bool) -> None:
    result = agent_research.classify_web_source(url, title, "")
    assert (result.publisher_kind, result.document_type, result.official) == (publisher, document, official)
    assert result.label == f"{result.publisher_label}·{result.document_label}"


def test_same_announcement_official_vs_repost_get_different_usage_notes() -> None:
    title = "贵州茅台：关于回购股份的公告"
    official = agent_research.classify_web_source("http://www.cninfo.com.cn/x", title, "")
    repost = agent_research.classify_web_source("https://finance.sina.com.cn/x", title, "")
    assert official.usage_note.startswith("官方原文")
    assert repost.usage_note.startswith("媒体转载的官方文件")
    assert official.label != repost.label


def _page_result(url: str, title: str, text: str) -> web_research.WebPageResult:
    return web_research.WebPageResult(
        url=url,
        final_url=url,
        title=title,
        text=text,
        page_date="2026-09-01",
        fetched_on="2026-09-09",
        transport="direct_http",
        trace=ProviderTrace(provider="web_fetch", capability="agent_loop", status="success", detail=url, result_count=1),
    )


def test_web_fetch_with_focus_query_targets_answer_and_labels_source() -> None:
    filler = "\n\n".join(f"第{i}段 无关叙述 " + "内容" * 60 for i in range(30))
    text = "贵州茅台 2024 年年度报告。\n\n" + filler + "\n\n经营活动产生的现金流量净额为 924.6 亿元。"
    page = _page_result("http://www.cninfo.com.cn/new/disclosure/detail?id=1", "贵州茅台2024年年度报告", text)
    tools = agent_research.build_default_tools(
        lambda *_a, **_k: object(),
        focus_query=lambda: "贵州茅台 2024 经营活动现金流量净额",
    )
    with mock.patch.object(web_research, "fetch_web_page", return_value=page):
        evidence, observation, trace = tools["web_fetch"](page.url, _context())
    assert trace.status == "success"
    assert any("924.6" in item.detail for item in evidence), "页尾数字要进证据"
    assert all(len(item.detail) <= MAX_EVIDENCE_DETAIL_CHARS for item in evidence)
    assert evidence[0].title.startswith("〔官方披露平台·定期报告〕")
    assert evidence[0].publisher_kind == "official_disclosure" and evidence[0].document_type == "periodic_report"
    assert evidence[0].evidence_tier == "public_web", "分档归判官，这里只如实分类"
    assert observation.startswith("来源分类：发布主体=官方披露平台，文档类型=定期报告，官方原文")
    assert "已按问题定向选段" in observation


def test_web_fetch_without_focus_keeps_legacy_head_chunks() -> None:
    text = "\n".join(f"第{i}行 " + "内容" * 40 for i in range(40))
    page = _page_result("https://finance.sina.com.cn/x.shtml", "某新闻", text)
    tools = agent_research.build_default_tools(lambda *_a, **_k: object())
    with mock.patch.object(web_research, "fetch_web_page", return_value=page):
        evidence, observation, _trace = tools["web_fetch"](page.url, _context())
    assert [item.detail for item in evidence] == agent_research.page_text_chunks(text)
    assert evidence[0].title.startswith("〔财经媒体/门户·新闻/资讯〕")
    assert "（页首起）" in observation


# ---------------------------------------------------------------------------
# 闭环检索：跨口径同查询不重跑
# ---------------------------------------------------------------------------
def test_run_aperture_skips_queries_already_executed_in_earlier_aperture() -> None:
    calls: list[str] = []

    def retrieve(query: str) -> kb_rag.WikiRagResult:
        calls.append(query)
        res = kb_rag.WikiRagResult()
        res.telemetry.status = "empty"
        return res

    result = closed_loop_retrieval.ClosedLoopRetrievalResult()
    budget = closed_loop_retrieval._AttemptBudget(deadline=float("inf"))
    executed: set[str] = set()
    closed_loop_retrieval._run_aperture("narrow", ("长电科技 HBM", "长电科技 688576"), retrieve, result, budget, None, executed=executed)
    closed_loop_retrieval._run_aperture("broad", ("长电科技 HBM", "长电科技 产业链"), retrieve, result, budget, None, executed=executed)
    assert calls == ["长电科技 HBM", "长电科技 688576", "长电科技 产业链"]
    assert any("skipped duplicate query" in line for line in result.diagnostics)
    assert executed == set(calls)
