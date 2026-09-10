"""graph_lookup 研究地图 mode 路由（cap-i2 03 适配）。

覆盖两层：
- 无 KB 时（_FakeKnowledge 桩），legacy 缺省路径逐字节不变、mode 注入不破坏既有工具；
- KB（kb-wt-cap03-runtime）存在时，package/view/trace/compare/scope 五种模式返回
  结构化证据，且全程只读：不追加 access_log、不建 research_map.db。

判官口径由 evidence.source 携带：研究地图命中的条目 source=
"本地知识图谱·研究地图"，区别于旧 graph_lookup 的 "本地知识图谱"。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services import agent_research as ar
from intelligence.services.agent_research import ProviderTrace

# 研究地图源码与运行数据目录。默认选 kb-wt-cap03-runtime（spec 指定只读运行目录），
# 可用 RESEARCH_MAP_KB 覆盖；缺失时跳过 KB 相关用例但保留桩隔离测试。
_KB_CANDIDATES = (
    Path(os.environ.get("RESEARCH_MAP_KB", str(Path.home() / "kb-wt-cap03-runtime"))),
    Path.home() / "knowledge-base-private",
)


def _kb_root() -> Path | None:
    for cand in _KB_CANDIDATES:
        if (cand / "skills" / "lib" / "research_map" / "__init__.py").is_file():
            return cand
    return None


_KbRoot = pytest.mark.skipif(
    _kb_root() is None,
    reason="KB 研究地图未在运行目录（缺 skills/lib/research_map），跳过 KB 用例",
)


class _FakeKnowledge:
    """无 KB 的 KnowledgeAdapter 桩：保持 legacy 缺省路径逐字节不变。"""

    def get_concept_matches(self, query: str, limit: int = 5) -> dict:
        return {"found": True, "items": [{"concept": "液冷服务器", "score": 20}]}

    def get_exposure_matches(self, query: str, limit: int = 8) -> dict:
        return {
            "found": True,
            "items": [
                {
                    "company": "川环科技",
                    "concept": "液冷服务器",
                    "strength": "related",
                    "evidence_layer": "L1_L3_candidate",
                }
            ],
        }

    def get_evidence(self, target: str, concept=None, limit: int = 6) -> dict:
        return {"found": True, "items": []}


def test_legacy_mode_preserves_default_when_no_kb() -> None:
    """无 KB 时缺省 mode（legacy）逐字节不变：概念+公司暴露，source=本地知识图谱。"""

    tools = ar.build_graph_tools(_FakeKnowledge())
    evidence, observation, trace = tools["graph_lookup"]("液冷")

    assert isinstance(trace, ProviderTrace)
    assert trace.provider == "agent:graph_lookup"
    assert trace.status == "success"
    assert any(item.source == "本地知识图谱" for item in evidence)
    assert not any(item.source == "本地知识图谱·研究地图" for item in evidence)
    assert "概念 液冷服务器" in observation
    assert "川环科技" in observation


def test_mode_kwarg_ignored_when_kb_absent() -> None:
    """mode 参数传给无 KB 的 runner 不应报错（回退 legacy）。"""

    tools = ar.build_graph_tools(_FakeKnowledge())
    evidence, observation, trace = tools["graph_lookup"]("液冷", mode="package")

    assert trace.status == "success"
    assert evidence


@_KbRoot
def test_legacy_mode_still_works_with_kb_present() -> None:
    """KB 在场时缺省 mode 仍走 legacy（概念匹配+公司暴露），不切换研究地图。"""

    kb = KnowledgeAdapter(wiki_root=str(_kb_root() / "wiki"))
    tools = ar.build_graph_tools(kb)
    evidence, observation, trace = tools["graph_lookup"]("液冷")

    assert any(item.source == "本地知识图谱" for item in evidence)
    assert not any(item.source == "本地知识图谱·研究地图" for item in evidence)
    assert "概念 液冷" in observation


@_KbRoot
def test_package_mode_returns_theme_package_evidence() -> None:
    kb = KnowledgeAdapter(wiki_root=str(_kb_root() / "wiki"))
    tools = ar.build_graph_tools(kb)
    evidence, observation, trace = tools["graph_lookup"]("液冷", mode="package")

    assert trace.status == "success"
    assert observation.startswith("题材「液冷」")
    assert "家公司" in observation
    assert "缺口" in observation
    assert evidence
    # 研究地图条目带自身来源标签与页级定位。
    assert all(item.source == "本地知识图谱·研究地图" for item in evidence)
    assert any(item.internal_locator.startswith("wiki/") for item in evidence)


@_KbRoot
def test_view_mode_does_not_write_research_map_db() -> None:
    kb = KnowledgeAdapter(wiki_root=str(_kb_root() / "wiki"))
    tools = ar.build_graph_tools(kb)
    db_path = _kb_root() / "wiki" / "relations" / "research_map.db"
    before = db_path.stat().st_mtime_ns if db_path.exists() else None

    evidence, observation, trace = tools["graph_lookup"]("液冷", mode="view")

    assert trace.status == "success"
    assert "研究地图·" in observation
    after = db_path.stat().st_mtime_ns if db_path.exists() else None
    # serve(auto_refresh=False) 不落库：不存在仍不存在，存在则时间戳不变。
    assert after == before


@_KbRoot
def test_trace_down_for_theme_and_up_for_company() -> None:
    kb = KnowledgeAdapter(wiki_root=str(_kb_root() / "wiki"))
    tools = ar.build_graph_tools(kb)

    down_ev, down_obs, down_tr = tools["graph_lookup"]("液冷", mode="trace")
    assert down_tr.status == "success"
    assert "向下追踪「液冷」" in down_obs
    assert down_ev

    up_ev, up_obs, up_tr = tools["graph_lookup"]("宁德时代", mode="trace")
    assert up_tr.status == "success"
    assert "向上追踪「宁德时代」" in up_obs
    assert "共同需求驱动" in up_obs
    assert up_ev


@_KbRoot
def test_compare_mode_known_unknown_and_unresolved() -> None:
    kb = KnowledgeAdapter(wiki_root=str(_kb_root() / "wiki"))
    tools = ar.build_graph_tools(kb)
    evidence, observation, trace = tools["graph_lookup"](
        "theme=液冷 companies=英维克,高澜股份", mode="compare"
    )

    assert trace.status == "success"
    assert "同口径对比 2 家公司" in observation
    # 维度分 known/computable/unknown；unknown 格 value=null 不输出 0。
    assert "unknown" in observation
    assert any(item.source == "本地知识图谱·研究地图" for item in evidence)


@_KbRoot
def test_compare_unresolved_company_reported() -> None:
    """compare 里解析不到的公司进 unresolved，不静默丢弃。"""

    kb = KnowledgeAdapter(wiki_root=str(_kb_root() / "wiki"))
    tools = ar.build_graph_tools(kb)
    _ev, observation, trace = tools["graph_lookup"](
        "theme=液冷 companies=英维克,不存在的公司", mode="compare"
    )

    assert "不存在的公司" in observation or trace.status in {"success", "empty"}


@_KbRoot
def test_scope_mode_returns_reading_plan() -> None:
    kb = KnowledgeAdapter(wiki_root=str(_kb_root() / "wiki"))
    tools = ar.build_graph_tools(kb)
    evidence, observation, trace = tools["graph_lookup"](
        "液冷产业链怎么分", mode="scope"
    )

    assert trace.status == "success"
    assert "读取范围" in observation
    assert evidence


@_KbRoot
def test_package_does_not_append_access_log() -> None:
    """只读红线：package 走 build_theme_package（不调 CLI），不追加 access_log.jsonl。"""

    kb = KnowledgeAdapter(wiki_root=str(_kb_root() / "wiki"))
    tools = ar.build_graph_tools(kb)
    log_path = _kb_root() / "wiki" / "relations" / "access_log.jsonl"
    before = log_path.stat().st_mtime_ns if log_path.exists() else None

    tools["graph_lookup"]("液冷", mode="package")
    tools["graph_lookup"]("宁德时代", mode="trace")
    tools["graph_lookup"]("theme=液冷 companies=英维克", mode="compare")

    after = log_path.stat().st_mtime_ns if log_path.exists() else None
    assert after == before  # 时间戳不变 = 未追加


def test_compare_args_parses_key_value_clauses() -> None:
    """compare 参数解析要兼容 `theme=X companies=A,B` 与裸题材/竖线两种形态。"""

    theme, companies = ar._research_map_compare_args(
        "theme=液冷 companies=英维克,高澜股份"
    )
    assert theme == "液冷"
    assert companies == ["英维克", "高澜股份"]

    theme2, companies2 = ar._research_map_compare_args("英维克|高澜股份")
    assert theme2 == "英维克"
    assert companies2 == ["高澜股份"]

    theme3, companies3 = ar._research_map_compare_args("液冷")
    assert theme3 == "液冷"
    assert companies3 == []


def test_trace_path_renders_hops_chain() -> None:
    """向下追踪的 chain 把 hops 边渲染成 起点→…→via_concept，而不是输出 dict 原文。"""

    path = {
        "via_concept": "液冷",
        "depth": 1,
        "hops": [
            {
                "from": "金刚石散热",
                "to": "液冷",
                "type": "AI 散热替代/互补方案",
            }
        ],
        "strength": "related",
    }
    assert ar._rm_render_trace_path(path) == "金刚石散热→液冷"
    assert ar._rm_render_trace_path({"via_concept": "液冷", "hops": []}) == "液冷"
    assert ar._rm_render_trace_path(None) == ""


def test_rm_field_reads_dict_or_dataclass() -> None:
    """scope 结果可能是 dict 或 dataclass，_rm_field 通吃。"""

    assert ar._rm_field({"plan": "p"}, "plan") == "p"
    assert ar._rm_field({"plan": "p"}, "scope") is None

    class _Obj:
        plan = "obj-plan"

    assert ar._rm_field(_Obj(), "plan") == "obj-plan"
