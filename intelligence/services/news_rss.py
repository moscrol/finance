"""W7 海外第二梯队：白名单 RSS。同一意图路由，失败降级为空，不编造。"""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from urllib.request import Request, urlopen

from intelligence.services.news_credibility import classify_news_credibility
from intelligence.services.provider_observability import ProviderTrace

PROVIDER_RSS = "rss"
RSS_FETCH_ENV_FLAG = "FINANCE_NEWS_RSS_FETCH"
_WHITELIST_PATH = Path(__file__).resolve().parents[1] / "data" / "news_rss_whitelist.json"
FeedFetchFn = Callable[[str], str]


def rss_fetch_enabled() -> bool:
    return os.environ.get(RSS_FETCH_ENV_FLAG, "1").strip().lower() not in {"0", "false", "off"}


def load_rss_whitelist(path: str | Path | None = None) -> tuple[dict[str, str], ...]:
    raw = json.loads(Path(path or _WHITELIST_PATH).read_text(encoding="utf-8"))
    feeds = raw.get("feeds") if isinstance(raw, dict) else raw
    out: list[dict[str, str]] = []
    for row in feeds or ():
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        name = str(row.get("name") or "").strip()
        if not url or not name:
            continue
        out.append(
            {
                "name": name,
                "url": url,
                "credibility": str(row.get("credibility") or "").strip(),
            }
        )
    return tuple(out)


def parse_rss_items(xml_text: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    rows: list[dict[str, str]] = []
    for node in root.iter():
        tag = node.tag.split("}")[-1]
        if tag not in {"item", "entry"}:
            continue
        fields = {_local(child.tag): (child.text or "").strip() for child in list(node)}
        link = fields.get("link") or ""
        if not link:
            for child in list(node):
                if _local(child.tag) == "link" and child.attrib.get("href"):
                    link = child.attrib["href"].strip()
                    break
        title = fields.get("title") or ""
        if not title or not link:
            continue
        rows.append(
            {
                "title": title,
                "url": link,
                "date": fields.get("pubDate") or fields.get("updated") or fields.get("published") or "",
                "summary": fields.get("description") or fields.get("summary") or "",
            }
        )
    return rows


def rss_keyword_match(text: str, keyword: str) -> bool:
    hay = str(text or "").casefold()
    kw = str(keyword or "").strip().casefold()
    if not hay or not kw:
        return False
    if kw in hay:
        return True
    tokens = [part for part in re.split(r"[\s,/]+", kw) if len(part) >= 4]
    return any(part in hay for part in tokens)


def fetch_rss_news_result(
    keyword: str,
    *,
    page_size: int = 8,
    within_days: int = 90,
    feeds: tuple[dict[str, str], ...] | None = None,
    fetch_fn: FeedFetchFn | None = None,
    timeout: float = 8.0,
):
    from intelligence.services.market_news import (
        NewsFetchResult,
        NewsItem,
        _normalize_time_text,
        _within_days,
    )

    kw = str(keyword or "").strip()
    if not kw:
        return NewsFetchResult(
            (),
            ProviderTrace(provider=PROVIDER_RSS, capability="directional_news", status="empty", detail="empty keyword"),
        )
    whitelist = feeds if feeds is not None else load_rss_whitelist()
    getter = fetch_fn or (lambda url: _http_get(url, timeout=timeout))
    items: list = []
    attempted = 0
    failed = 0
    for feed in whitelist:
        attempted += 1
        try:
            xml_text = getter(feed["url"])
            rows = parse_rss_items(xml_text)
        except Exception:  # noqa: BLE001
            failed += 1
            continue
        for row in rows:
            blob = f"{row['title']} {row['summary']}"
            if not rss_keyword_match(blob, kw):
                continue
            date_str = _normalize_time_text(row["date"])
            if date_str and not _within_days(date_str, within_days):
                continue
            items.append(
                NewsItem(
                    date=date_str or "未标注",
                    source=feed["name"],
                    title=row["title"],
                    url=row["url"],
                    provider=PROVIDER_RSS,
                    credibility=feed.get("credibility") or classify_news_credibility(feed["name"], row["url"]),
                )
            )
            if len(items) >= int(page_size):
                break
        if len(items) >= int(page_size):
            break
    if items:
        status = "success"
    elif failed == attempted and attempted:
        status = "request_error"
    else:
        status = "empty"
    return NewsFetchResult(
        tuple(items),
        ProviderTrace(
            provider=PROVIDER_RSS,
            capability="directional_news",
            status=status,
            detail=f"whitelist rss attempted={attempted} failed={failed}",
            result_count=len(items),
        ),
    )


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _http_get(url: str, timeout: float) -> str:
    req = Request(url, headers={"User-Agent": "finance-workspace-w7-rss/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")
