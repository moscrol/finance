from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from intelligence.services.provider_observability import ProviderTrace

PROVIDER_BING_WEB = "bing_web"
DEFAULT_PROXY_URL = "http://localhost:3456"

_DEFINITION_PATTERN = re.compile(
    r"(?:什么是|是什么|技术原理|如何工作|产业链位置|背景介绍|define\b|what\s+is\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class WebSearchItem:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class WebSearchResult:
    items: tuple[WebSearchItem, ...]
    trace: ProviderTrace


def is_definition_query(query: str) -> bool:
    text = str(query or "").strip()
    if not text or re.search(r"(?:你|模型|model)", text, re.IGNORECASE):
        return False
    return bool(_DEFINITION_PATTERN.search(text))


def _direct_result_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc.endswith("bing.com") or parsed.path != "/ck/a":
        return url
    encoded = urllib.parse.parse_qs(parsed.query).get("u", [""])[0]
    if not encoded.startswith("a1"):
        return url
    payload = encoded[2:]
    payload += "=" * (-len(payload) % 4)
    try:
        direct = base64.urlsafe_b64decode(payload).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return url
    return direct if direct.startswith(("https://", "http://")) else url


def fetch_web_search(
    query: str,
    *,
    limit: int = 5,
    timeout: float = 20.0,
    proxy_url: str | None = None,
) -> WebSearchResult:
    keyword = re.sub(r"\s+", " ", str(query or "")).strip()
    if not keyword:
        return WebSearchResult(
            (),
            ProviderTrace(
                provider=PROVIDER_BING_WEB,
                capability="general_web_search",
                status="empty",
                detail="empty query",
            ),
        )
    if os.environ.get("FINANCE_WEB_SEARCH", "1") == "0":
        return WebSearchResult(
            (),
            ProviderTrace(
                provider=PROVIDER_BING_WEB,
                capability="general_web_search",
                status="disabled",
                detail="FINANCE_WEB_SEARCH=0",
            ),
        )
    base = (proxy_url or os.environ.get("WEB_ACCESS_PROXY_URL") or DEFAULT_PROXY_URL).rstrip("/")
    target_id = ""
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=min(timeout, 5.0)):
            pass
    except Exception:  # noqa: BLE001
        return WebSearchResult(
            (),
            ProviderTrace(
                provider=PROVIDER_BING_WEB,
                capability="general_web_search",
                status="proxy_unavailable",
                detail="CDP proxy health check failed",
            ),
        )
    try:
        search_url = "https://www.bing.com/search?q=" + urllib.parse.quote(keyword)
        with urllib.request.urlopen(
            f"{base}/new?url={urllib.parse.quote(search_url)}",
            timeout=timeout,
        ) as response:
            opened = json.loads(response.read())
        target_id = str(opened.get("targetId") or opened.get("id") or "")
        if not target_id:
            raise OSError("missing target id")
        script = (
            "JSON.stringify(Array.from(document.querySelectorAll('li.b_algo'))"
            f".slice(0,{max(1, int(limit))}).map(x=>({{"
            "title:x.querySelector('h2 a')?.textContent?.trim()||'',"
            "url:x.querySelector('h2 a')?.href||'',"
            "snippet:x.querySelector('p')?.textContent?.trim()||''"
            "})))"
        )
        evaluated: dict[str, object] = {"value": "[]"}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            request = urllib.request.Request(
                f"{base}/eval?target={urllib.parse.quote(target_id)}",
                data=script.encode(),
                method="POST",
            )
            remaining = deadline - time.monotonic()
            with urllib.request.urlopen(
                request,
                timeout=max(1.0, min(5.0, remaining)),
            ) as response:
                evaluated = json.loads(response.read())
            if str(evaluated.get("value") or "[]") != "[]":
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(1.0, remaining))
    except json.JSONDecodeError:
        return WebSearchResult(
            (),
            ProviderTrace(
                provider=PROVIDER_BING_WEB,
                capability="general_web_search",
                status="parse_error",
                detail="proxy response was not JSON",
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return WebSearchResult(
            (),
            ProviderTrace(
                provider=PROVIDER_BING_WEB,
                capability="general_web_search",
                status="request_error",
                detail=type(exc).__name__,
            ),
        )
    finally:
        if target_id:
            try:
                urllib.request.urlopen(
                    f"{base}/close?target={urllib.parse.quote(target_id)}",
                    timeout=5,
                ).close()
            except Exception:  # noqa: BLE001
                pass
    try:
        raw_items = json.loads(str(evaluated.get("value") or "[]"))
    except (json.JSONDecodeError, TypeError):
        return WebSearchResult(
            (),
            ProviderTrace(
                provider=PROVIDER_BING_WEB,
                capability="general_web_search",
                status="parse_error",
                detail="search result payload was not JSON",
            ),
        )
    items = tuple(
        WebSearchItem(
            title=str(item.get("title") or "").strip(),
            url=_direct_result_url(str(item.get("url") or "").strip()),
            snippet=str(item.get("snippet") or "").strip(),
        )
        for item in raw_items
        if isinstance(item, dict)
        and str(item.get("title") or "").strip()
        and str(item.get("url") or "").strip()
    )
    return WebSearchResult(
        items,
        ProviderTrace(
            provider=PROVIDER_BING_WEB,
            capability="general_web_search",
            status="success" if items else "empty",
            detail="Bing web results via CDP proxy",
            result_count=len(items),
        ),
    )
