"""图谱暴露的取舍与截断留证。

线上实测的形状（2026-07-31，「固态电池产业链现在走到哪一步了，谁最受益」）：
图谱匹配 86 家公司，同一题材下每一家拿到的都是同一个分（77 家并列 20 分），
于是排序键里最后那一项——公司名——成了实际决策者。正文拿到的 12 家是
``sorted(names)[:12]``：万润新能、万润股份、万顺新材、三祥新材……到「中」为止，
其中 3 家 peripheral/low、1 家标注全空；而 core 的先导智能/当升科技/赣锋锂业、
high 置信的宁德时代全被挤到 limit 之外。

更要命的是这一刀是**静默**的：正文写「另有 3 家仅有概念关联、9 家仅有间接证据」，
读者会把 12 当成全集。所以这里钉两件事：选得对（strength/confidence 参与排序）、
说得清（截断必须留证）。

排序测试都用「高价值的那家名字排最后」构造——名字顺序本身用 ``_assert_name_order``
钉死，免得以后有人改了 fixture 名字，测试还绿着却已经不构成陷阱了。
"""

from __future__ import annotations

import json

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services import ask
from intelligence.services.closed_loop_retrieval import ClosedLoopRetrievalResult

# 按 Unicode 码位：一(U+4E00) < 三(U+4E09) < 万(U+4E07) 之外的字都比「阿」小，
# 「阿」(U+963F) 排最后。旧排序键 (-score, company) 会先要「一」，最后才轮到「阿」。
_FIRST_BY_NAME = "一公司"
_MID_BY_NAME = "三公司"
_LAST_BY_NAME = "阿公司"


def _write_exposures(tmp_path, rows: list[dict]) -> KnowledgeAdapter:
    relations = tmp_path / "relations"
    relations.mkdir(exist_ok=True)
    (relations / "entity_exposures.json").write_text(
        json.dumps({"items": rows}, ensure_ascii=False),
        encoding="utf-8",
    )
    return KnowledgeAdapter(wiki_root=tmp_path)


def _row(company: str, strength: str, confidence: str) -> dict:
    return {
        "company": company,
        "concept": "固态电池",
        "strength": strength,
        "confidence": confidence,
        "evidence_layer": "L1_L3_candidate",
    }


def _assert_name_order(*companies: str) -> None:
    """确认这些名字确实是按字典序递增的，否则这条测试根本没构成陷阱。"""
    assert list(companies) == sorted(companies), (
        f"fixture 名字顺序变了：{companies}；"
        "本测试依赖「高价值的那家名字排最后」才能在修复前变红"
    )


def test_core_exposure_not_squeezed_out_by_company_name_order(tmp_path) -> None:
    """同分时按暴露强度取舍，不是按公司名。

    构造成线上那个形状：名字排最前的两家是 peripheral，core 的那家名字排最后。
    limit=2 时，旧的 (-score, company) 会留下两家 peripheral——修复前必红。
    """
    _assert_name_order(_FIRST_BY_NAME, _MID_BY_NAME, _LAST_BY_NAME)
    adapter = _write_exposures(
        tmp_path,
        [
            _row(_FIRST_BY_NAME, "peripheral", "low"),
            _row(_MID_BY_NAME, "peripheral", "medium"),
            _row(_LAST_BY_NAME, "core", "high"),
        ],
    )

    matches = adapter.get_exposure_matches("固态电池", limit=2)
    companies = [item["company"] for item in matches["items"]]

    assert companies[0] == _LAST_BY_NAME
    assert _FIRST_BY_NAME not in companies


def test_confidence_breaks_tie_within_same_strength(tmp_path) -> None:
    """强度相同就看置信度；名字仍然只做确定性兜底。"""
    _assert_name_order(_FIRST_BY_NAME, _LAST_BY_NAME)
    adapter = _write_exposures(
        tmp_path,
        [
            _row(_FIRST_BY_NAME, "core", "low"),
            _row(_LAST_BY_NAME, "core", "high"),
        ],
    )

    matches = adapter.get_exposure_matches("固态电池", limit=1)

    assert [item["company"] for item in matches["items"]] == [_LAST_BY_NAME]


def test_unlabeled_exposure_ranks_last_not_first(tmp_path) -> None:
    """标注缺失不该因为「字典里查不到」白捡一个高位。

    线上被留下的 12 家里就有一家 strength/confidence 全空——它凭字典序进的正文。
    这里让空标注那家名字排最前：修复前它会赢，修复后应该输给有标注的 peripheral。
    """
    _assert_name_order(_FIRST_BY_NAME, _LAST_BY_NAME)
    adapter = _write_exposures(
        tmp_path,
        [
            _row(_FIRST_BY_NAME, "", ""),
            _row(_LAST_BY_NAME, "peripheral", "low"),
        ],
    )

    matches = adapter.get_exposure_matches("固态电池", limit=1)

    assert [item["company"] for item in matches["items"]] == [_LAST_BY_NAME]


def test_truncation_is_disclosed_with_total(tmp_path) -> None:
    """截断必须留证：告知而非隐藏。

    修复前 warnings 只在「一条都没召回」时才填，召回 86 家送出 12 家是静默的。
    """
    adapter = _write_exposures(
        tmp_path,
        [_row(f"公司{index:02d}", "core", "high") for index in range(20)],
    )

    matches = adapter.get_exposure_matches("固态电池", limit=5)

    assert matches["total_matched"] == 20
    assert matches["truncated"] is True
    assert len(matches["items"]) == 5
    assert matches["warnings"], "截了 15 家却一句不说，就是隐藏"
    assert "20" in matches["warnings"][0]


def test_truncation_reaches_the_answer_not_just_the_adapter(monkeypatch) -> None:
    """留证要送到正文，不能只留在 adapter 里。

    这条是本轮要治的病本身：信息在系统里、但没送到消费者手上。上面那条
    ``test_truncation_is_disclosed_with_total`` 只证明 adapter 算出来了；只钉那一条
    就等于重犯一次同样的错。
    """
    def fake_exposures(self, term: str, limit: int = 12) -> dict:
        return {
            "found": True,
            "term": term,
            "items": [
                _row(f"公司{index:02d}", "core", "high") | {"score": 20}
                for index in range(limit)
            ],
            "total_matched": 86,
            "truncated": True,
            "warnings": ["图谱共 86 家匹配，本轮按暴露强度取前 12 家；未展示的不代表不存在"],
            "errors": [],
        }

    monkeypatch.setattr(KnowledgeAdapter, "get_exposure_matches", fake_exposures)
    # 本条只验「暴露截断有没有送到正文」，把 W 源检索短路掉：不短路要跑 80 秒，
    # 而且把测试绑死在本机 RAG 索引上。
    monkeypatch.setattr(
        ask.closed_loop_retrieval,
        "retrieve_closed_loop",
        lambda *args, **kwargs: ClosedLoopRetrievalResult(),
    )

    result = ask.answer_query(
        ask.AskOptions(
            query="固态电池产业链现在走到哪一步了，谁最受益",
            compose=False,
            synthesize=False,
        )
    )

    assert result.graph_exposure_telemetry.get("matched") == 86
    assert result.graph_exposure_telemetry.get("truncated") is True

    gap_lines = result.sections.get("分歧反证") or []
    assert any("86" in line for line in gap_lines), (
        "正文一个字都没提「86 家里只写了 12 家」——"
        f"读者会把展示的当全集。实际 gaps={gap_lines}"
    )


def test_no_truncation_means_no_warning(tmp_path) -> None:
    """没截断就别喊狼来了——留证要可信，就不能有假阳性。"""
    adapter = _write_exposures(
        tmp_path,
        [
            _row(_FIRST_BY_NAME, "core", "high"),
            _row(_LAST_BY_NAME, "core", "high"),
        ],
    )

    matches = adapter.get_exposure_matches("固态电池", limit=12)

    assert matches["total_matched"] == 2
    assert matches["truncated"] is False
    assert matches["warnings"] == []
