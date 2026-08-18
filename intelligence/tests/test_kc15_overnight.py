"""KC-15：隔夜美股→A 股映射块 [D17]。

规格写的是 [D11]，但 D11 已是个股走势类比；本单用 D17，不抢 D11/D12。
"""
from __future__ import annotations

from intelligence.services.overnight_map import (
    overnight_block_for_llm,
    parse_overnight_intent,
)


POSITIVE = (
    "隔夜美股走强对 A 股哪些板块有映射",
    "纳指隔夜涨了对应哪些 A 股板块",
    "美股 AI 主题对标 A 股板块",
    "隔夜外盘映射",
)

NEGATIVE = (
    "英维克历史上有没有类似这段的走势",
    "英维克客户证据硬不硬",
    "今天人工智能板块成交额多少",
    "后量子密码最近有什么新闻",
    "美股英伟达现在什么价",
    "固态电池对标历史上哪一段",
)


FIXTURE = {
    "as_of": "2026-08-14",
    "barometer_as_of": "2026-08-13",
    "is_trade_signal": False,
    "map_source": "manual",
    "map_note": "可编辑的美股主题 → A 股板块对照。不是公司映射。",
    "themes": [
        {
            "theme_code": "TH00001.FP",
            "theme_name": "AI算力",
            "heat": 92.1,
            "rank": 1,
            "avg_pct_chg": 1.8,
            "targets": [
                {
                    "sector_code": "990013.FP",
                    "sector_name": "CPO概念",
                    "relation": "primary",
                    "amount_chain_ratio": 1.24,
                    "limit_up_count": 3,
                    "is_double_red": True,
                    "pct_chg": 2.1,
                }
            ],
        },
        {
            "theme_code": "TH00099.FP",
            "theme_name": "无对照主题",
            "heat": 10.0,
            "rank": 9,
            "avg_pct_chg": -0.5,
            "targets": [],
        },
    ],
}


def test_intent_positive_samples_route() -> None:
    for query in POSITIVE:
        assert parse_overnight_intent(query), query


def test_intent_negative_samples_do_not_route() -> None:
    for query in NEGATIVE:
        assert not parse_overnight_intent(query), query
    assert not parse_overnight_intent("")
    assert not parse_overnight_intent("   ")


def test_block_renders_three_columns_with_dates_and_source() -> None:
    block = overnight_block_for_llm(fetcher=lambda: FIXTURE)
    assert "[D17]" in block
    assert "2026-08-14" in block
    assert "2026-08-13" in block
    assert "fph2026" in block
    assert "query overnight" in block
    assert "manual" in block
    assert "AI算力" in block
    assert "CPO概念" in block
    assert "primary" in block
    assert "92.1" in block
    assert "+1.80%" in block or "1.8" in block
    assert "2.1" in block
    assert "1.24" in block
    assert "涨停3" in block or "涨停 3" in block
    assert "无对照主题" in block
    assert "这张表没写" in block
    assert "不是买卖信号" in block
    assert "不表示必然跟涨" in block
    assert "必然跟涨。" not in block.replace("不表示必然跟涨", "")


def test_missing_payload_discloses_gap_and_does_not_invent() -> None:
    def boom() -> dict:
        raise FileNotFoundError("旁路库不存在")

    block = overnight_block_for_llm(fetcher=boom)
    assert "[D17]" in block
    assert "数据缺口" in block
    assert "CPO概念" not in block
    assert "禁止外推" in block


def test_empty_themes_discloses_gap() -> None:
    empty = {
        "as_of": "2026-08-14",
        "barometer_as_of": None,
        "is_trade_signal": False,
        "map_source": "manual",
        "map_note": "",
        "themes": [],
    }
    block = overnight_block_for_llm(fetcher=lambda: empty)
    assert "[D17]" in block
    assert "2026-08-14" in block
    assert "数据缺口" in block
    assert "CPO概念" not in block


def test_registry_gating_via_legacy_flag() -> None:
    from intelligence.services import evidence_registry
    from intelligence.services.ask import AskOptions

    on = AskOptions(query="q")
    off = AskOptions(query="q", include_overnight_block=False)
    assert evidence_registry.provider_enabled(on, "D17") is True
    assert evidence_registry.provider_enabled(off, "D17") is False


def test_d17_fact_lines_stay_verified() -> None:
    from intelligence.services.answer_model import ClaimStatus
    from intelligence.services.ask_synthesis import _claims_from_data_block

    claims = _claims_from_data_block(
        "- AI算力 热度 92.1 / 均涨 +1.80% → CPO概念（primary）额环比 1.24",
        "D17",
        "隔夜美股映射",
        "AI算力",
    )
    assert claims
    assert all(c.status == ClaimStatus.VERIFIED for c in claims)
