"""KC-14：海外 RSS 第二梯队、来源可信度、别名表生成器。"""
from __future__ import annotations

import json
from pathlib import Path

from intelligence.services.market_news import (
    PROVIDER_WEB,
    NewsItem,
    english_alias,
    news_block_result_for_keyword,
)
from intelligence.services.news_alias_propose import accept_alias, propose_alias_candidates
from intelligence.services.news_credibility import (
    CRED_AUTHORITY,
    CRED_MEDIA,
    CRED_SELF,
    classify_news_credibility,
)
from intelligence.services.news_rss import (
    PROVIDER_RSS,
    fetch_rss_news_result,
    parse_rss_items,
    rss_keyword_match,
)


def test_pqc_alias_baseline_still_maps_to_english() -> None:
    assert english_alias("后量子密码") == "post-quantum cryptography"
    assert english_alias("抗量子密码") == "post-quantum cryptography"
    assert english_alias("AI智能体") == "AI agent"


def test_credibility_grades_authority_media_and_self() -> None:
    assert classify_news_credibility("NIST", "https://www.nist.gov/news/pqc") == CRED_AUTHORITY
    assert classify_news_credibility("Reuters", "https://www.reuters.com/technology/pqc") == CRED_MEDIA
    assert classify_news_credibility("未知博客", "https://example.com/p/1") == CRED_SELF


def test_rss_filters_by_keyword_and_keeps_credibility() -> None:
    xml = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>NIST releases post-quantum cryptography guidance</title>
        <link>https://www.nist.gov/news/pqc</link>
        <pubDate>Mon, 10 Aug 2026 12:00:00 GMT</pubDate>
      </item>
      <item>
        <title>Unrelated chip earnings</title>
        <link>https://www.eetimes.com/other</link>
        <pubDate>Mon, 10 Aug 2026 12:00:00 GMT</pubDate>
      </item>
    </channel></rss>
    """
    assert len(parse_rss_items(xml)) == 2
    assert rss_keyword_match("NIST releases post-quantum cryptography guidance", "post-quantum cryptography")
    result = fetch_rss_news_result(
        "post-quantum cryptography",
        feeds=(
            {
                "name": "NIST News",
                "url": "https://example.test/nist.xml",
                "credibility": CRED_AUTHORITY,
            },
        ),
        fetch_fn=lambda url: xml,
    )
    assert len(result.items) == 1
    assert result.items[0].provider == PROVIDER_RSS
    assert result.items[0].credibility == CRED_AUTHORITY
    assert "post-quantum" in result.items[0].title.lower()


def test_rss_failure_degrades_to_empty_not_invented() -> None:
    result = fetch_rss_news_result(
        "post-quantum cryptography",
        feeds=({"name": "dead", "url": "https://example.test/x", "credibility": CRED_MEDIA},),
        fetch_fn=lambda url: (_ for _ in ()).throw(TimeoutError()),
    )
    assert result.items == ()
    assert result.trace.status == "request_error"


def test_w7_block_marks_credibility_on_new_source_items() -> None:
    result = news_block_result_for_keyword(
        "后量子密码",
        fetcher=lambda *args: [
            NewsItem("2026-07-08", "证券时报", "PQC标准进展", "http://x/a"),
        ],
        web_fetcher=lambda *args: [
            NewsItem(
                "2026-07-07",
                "Reuters",
                "PQC executive order",
                "https://www.reuters.com/world/pqc",
                provider=PROVIDER_WEB,
            ),
        ],
        rss_fetcher=lambda *args: [
            NewsItem(
                "2026-08-10",
                "NIST News",
                "NIST post-quantum cryptography update",
                "https://www.nist.gov/news/pqc",
                provider=PROVIDER_RSS,
                credibility=CRED_AUTHORITY,
            ),
        ],
    )
    assert "PQC标准进展" in result.block
    assert "PQC executive order" in result.block
    assert "[rss|权威机构]" in result.block
    assert "[web|媒体]" in result.block
    assert [trace.status for trace in result.traces] == ["success", "success", "success"]


def test_alias_generator_extracts_cn_en_and_skips_existing(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "AI智能体.md").write_text(
        "---\ntitle: AI智能体\naliases: [AI Agent, 智能体]\n---\n\n# AI智能体\n",
        encoding="utf-8",
    )
    (wiki / "concepts" / "CPO.md").write_text(
        "---\ntitle: CPO（共封装光学）\n---\n\nCPO（Co-Packaged Optics，共封装光学）是光电集成。\n",
        encoding="utf-8",
    )
    (wiki / "concepts" / "固态电池.md").write_text(
        "---\ntitle: 固态电池\n---\n\n固态电池（solid-state battery）\n",
        encoding="utf-8",
    )
    found = propose_alias_candidates(wiki, existing={"固态电池": "solid-state battery"})
    pairs = {item.zh: item.en for item in found}
    assert pairs["AI智能体"] == "AI Agent"
    assert pairs["共封装光学"] == "CPO"
    assert "固态电池" not in pairs
    assert all(item.status == "pending" for item in found)


def test_alias_accept_writes_confirmed_row(tmp_path: Path) -> None:
    table = tmp_path / "aliases.json"
    table.write_text('{"_comment": "x"}\n', encoding="utf-8")
    written = accept_alias("AI智能体", "AI agent", path=table)
    assert written == {"AI智能体": "AI agent"}
    payload = json.loads(table.read_text(encoding="utf-8"))
    assert payload["AI智能体"] == "AI agent"
    assert payload["_comment"] == "x"
