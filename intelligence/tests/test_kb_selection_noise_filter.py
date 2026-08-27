"""V5：kb_search 选段结构噪声过滤（形状 IV）。

验收只看选段质量（噪声头是否去掉、正文是否前置）。不得从本文件推出
送达字符量或答案质量结论——那是 V3 / live 的验收面
（R-12 预测③：送达变大 ≠ 选段变好）。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from intelligence.services import agent_research
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_JCET = _FIXTURES / "v3-kbsearch-jcet-hits.json"
_PEROVSKITE = _FIXTURES / "v5-kbsearch-perovskite-hits.json"


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


def _run(hits: list[SimpleNamespace], query: str = "长电科技怎么看"):
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
    return tools["kb_search"](query, context)


def _load(path: Path) -> list[SimpleNamespace]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [_hit(**item) for item in payload["hits"]]


def _head_tag_soup(text: str) -> bool:
    """独立判据：头部是 frontmatter 标签汤（不复用实现分类器，避免同语反复）。"""

    head = (text or "").lstrip()[:120]
    return "tags:" in head and "section:" in head


def _head_locator(text: str) -> bool:
    head = (text or "").lstrip()
    return head.startswith("命中块") or head.startswith("相邻块")


def _head_path_line(text: str) -> bool:
    head = (text or "").lstrip()
    return head.startswith("- `raw/") or head.startswith("`raw/")


def test_synthetic_page_selects_body_not_source_list() -> None:
    """spec §V5：合成页（正文+来源清单）选段落正文。"""

    body = "长电科技作为国内封测龙头，2026年资本开支投向2.5D/3D封装。"
    noise = (
        "# 长电科技 tags: 封测 半导体 A股 section: 长电科技 > "
        "1. **来源清单**（2026-05-08）- 公司官方 - https://example.com/announ/831569 "
        "[[长电科技]] · [[通富微电]] · [[华天科技]] "
        "|---|---| "
        "- `raw/cninfo-baseline/长电科技.json`"
    )
    delivered = agent_research.kb_search_hit_text(_hit(llm_evidence=noise + " " + body))
    assert delivered.startswith(body)
    assert not _head_tag_soup(delivered)
    assert "https://example.com/announ/831569" not in delivered
    assert "[[通富微电]]" not in delivered
    assert "raw/cninfo-baseline" not in delivered


def test_perovskite_fixture_fronts_body_not_tag_soup() -> None:
    """今晚钙钛矿活体：6 条 V3 detail 头部的 tags/section 汤去掉，正文前置。"""

    hits = _load(_PEROVSKITE)
    assert hits, "夹具未冻结"
    raw_soup = sum(1 for hit in hits if _head_tag_soup(hit.llm_evidence))
    assert raw_soup == 6

    evidence, _observation, _trace = _run(hits, query="钙钛矿 产业链 公司 公告 订单 产能")
    details = [item.detail for item in evidence]
    assert len(details) == 6
    assert sum(1 for text in details if _head_tag_soup(text)) == 0
    first = details[0]
    assert first.lstrip()[:40].startswith("Baseline") or "涂布" in first[:60] or "GW级" in first[:80]
    assert "10.68亿" in first
    assert not first.lstrip().startswith("# 曼恩斯特")


def test_perovskite_observation_head_is_not_tag_soup() -> None:
    """observation 取 detail[:80]：过滤后摘要头应是正文，不是标签汤。"""

    hits = _load(_PEROVSKITE)
    _evidence, observation, _trace = _run(hits, query="钙钛矿 产业链 公司 公告 订单 产能")
    first = observation.split("；", 1)[0]
    assert "tags:" not in first
    assert "section:" not in first
    assert "涂布" in first or "GW" in first or "Baseline" in first


def test_jcet_replay_noise_heads_drop_and_body_fronted() -> None:
    """长电夹具：定位符/路径头去掉；实体页正文前置；全噪声条 fail-open 非空。"""

    hits = _load(_JCET)
    raw_locator = sum(1 for hit in hits if _head_locator(hit.llm_evidence))
    assert raw_locator == 6

    evidence, _observation, _trace = _run(hits)
    details = [item.detail for item in evidence]
    assert len(details) == 6
    assert all(text.strip() for text in details)
    assert sum(1 for text in details if _head_locator(text)) == 0
    assert sum(1 for text in details if _head_path_line(text)) == 0
    assert "一句话" in details[1][:40]
    assert "封测龙头" in details[1]
    assert details[2].strip() != "- `raw/cninfo-baseline/长电科技.json`"


def test_fail_open_keeps_unrecognized_body() -> None:
    body = "钙钛矿涂布设备在国内率先取得订单突破。"
    assert agent_research.kb_search_hit_text(_hit(llm_evidence=body)) == body


def test_fail_open_all_noise_not_empty() -> None:
    pile = "[[长电科技]] · [[通富微电]] · [[华天科技]]"
    out = agent_research.kb_search_hit_text(_hit(llm_evidence=pile))
    assert out.strip()
    assert "长电科技" in out


def test_filter_does_not_invent_char_cap() -> None:
    """过滤层不得偷偷加长度上限（V3 已定送达层不二次截断）。"""

    body = "正文级事实句。" * 80
    prefix = "# 页 tags: 钙钛矿 A股 section: 页 > "
    out = agent_research.kb_search_hit_text(_hit(llm_evidence=prefix + body))
    assert len(out) >= len(body)
    assert len(out) > 160
    assert len(out) > 240


def test_identity_passthrough_is_not_the_default() -> None:
    """变异闸：过滤器恒等放行 → 钙钛矿头仍是标签汤，本钉红。"""

    hits = _load(_PEROVSKITE)
    evidence, observation, _trace = _run(hits, query="钙钛矿 产业链 公司 公告 订单 产能")
    assert not _head_tag_soup(evidence[0].detail)
    assert "tags:" not in observation.split("；", 1)[0]
