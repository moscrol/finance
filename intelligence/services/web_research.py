from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date

from intelligence.services import query_ledger
from intelligence.services.provider_observability import ProviderTrace

PROVIDER_BING_WEB = "bing_web"
PROVIDER_WEB_FETCH = "web_fetch"
DEFAULT_PROXY_URL = "http://localhost:3456"
WEB_FETCH_ENV_FLAG = "FINANCE_WEB_FETCH"
# 取页正文上限：够读一篇财经指标页 / 公告正文，又不至于把一个 5 MB 的 HTML 灌进证据。
_WEB_FETCH_MAX_BYTES = 2_000_000
_WEB_FETCH_MAX_TEXT_CHARS = 60_000

_DEFINITION_PATTERN = re.compile(
    r"(?:什么是|是什么|技术原理|如何工作|产业链位置|背景介绍|define\b|what\s+is\b)",
    re.IGNORECASE,
)

_FRESHNESS_PATTERN = re.compile(
    r"(?:今天|今日|昨天|昨日|隔夜|最近|近期|最新|刚刚|本周|本月|"
    r"消息|新闻|进展|动态|现状|公告|发布)"
)


def needs_fresh_web(query: str) -> bool:
    return bool(_FRESHNESS_PATTERN.search(str(query or "")))


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
    """全网搜索入口（经 turn 级 QueryLedger 去重）。

    同一 turn 内 E 兜底 / agent web_search / 其他层重复发起的同 query 搜索
    只真实执行一次，其余复用 memoized 结果；无活动账本（CLI 单调用）时
    行为不变。"""
    return query_ledger.executed(
        "web_search",
        query,
        lambda: _fetch_web_search_uncached(
            query,
            limit=limit,
            timeout=timeout,
            proxy_url=proxy_url,
        ),
        variant=(
            f"limit={limit};proxy="
            + (
                hashlib.sha256(proxy_url.encode("utf-8")).hexdigest()[:12]
                if proxy_url
                else "default"
            )
        ),
    )


# Bing 结果页分两步到达（2026-09-03 经 CDP 代理逐 0.15s 采样实测）：``/new`` 返回时页面已
# ``readyState=complete`` 且有 10 条 ``li.b_algo``，但那是 ``_G.JCache=1`` 的实体缓存壳——
# 新题时是官网/百科导航页（「拼多多 2024 营收」回「拼」字词典，「中国平安 年报」回
# 「中华人民共和国_百度百科」）；约 1–2.5s 后页面自行跳到 ``…&rdr=1&rdrig=…``，真正的
# 有机结果只在跳转后的页面上。原实现「首批非空即收」拿走的一直是壳，且 ``status=success``。
# 判据只认 href 里的 ``rdr=1``（``JCache`` 跳转前后都是 1，不能用）；没观察到跳转时，
# 结果连续稳定 ``_BING_SETTLE_SECONDS`` 才收，防 Bing 以后不再跳转导致永远超时。
_BING_RDR_MARKER = "rdr=1"
_BING_SETTLE_SECONDS = 3.0
_BING_POLL_SECONDS = 0.3
_BING_DETAIL_SETTLED_RDR = "settled after rdr redirect"
_BING_DETAIL_SETTLED_STABLE = "no rdr redirect; results stable"
_BING_DETAIL_UNSETTLED = "unsettled: rdr redirect not observed before deadline"


def _fetch_web_search_uncached(
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
    raw_items: list[object] = []
    settle_detail = _BING_DETAIL_UNSETTLED
    payload_malformed = False
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
        script = _bing_page_state_script(limit)
        stable_since: float | None = None
        stable_key: str | None = None
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
            page = _parse_bing_page_state(evaluated.get("value"))
            if page is None:
                payload_malformed = True
                break
            href, ready, items_now = page
            if items_now:
                raw_items = items_now
                if _BING_RDR_MARKER in href and ready == "complete":
                    settle_detail = _BING_DETAIL_SETTLED_RDR
                    break
                key = json.dumps(items_now, ensure_ascii=False, sort_keys=True)
                now = time.monotonic()
                if key != stable_key:
                    stable_key, stable_since = key, now
                elif stable_since is not None and now - stable_since >= _BING_SETTLE_SECONDS:
                    settle_detail = _BING_DETAIL_SETTLED_STABLE
                    break
            else:
                stable_key, stable_since = None, None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(_BING_POLL_SECONDS, remaining))
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
    if payload_malformed:
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
            detail=f"Bing web results via CDP proxy; {settle_detail}",
            result_count=len(items),
        ),
    )


def _bing_page_state_script(limit: int) -> str:
    """``/eval`` 用的页面状态脚本：href / readyState / 前 ``limit`` 条有机结果一次带回。

    字符串拼接的 JS 少一个括号就是代理 4xx → ``request_error``，单测桩掉代理看不见；
    ``test_web_research`` 对这段做括号配平检查。
    """

    return (
        "JSON.stringify({href:location.href,ready:document.readyState,"
        "items:Array.from(document.querySelectorAll('li.b_algo'))"
        f".slice(0,{max(1, int(limit))}).map(x=>({{"
        "title:x.querySelector('h2 a')?.textContent?.trim()||'',"
        "url:x.querySelector('h2 a')?.href||'',"
        "snippet:x.querySelector('p')?.textContent?.trim()||''"
        "}))})"
    )


def _parse_bing_page_state(value: object) -> tuple[str, str, list[object]] | None:
    """把 ``/eval`` 回来的页面状态解成 ``(href, readyState, items)``；不是预期形状返回 None。"""

    try:
        page = json.loads(str(value or "{}"))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(page, dict):
        return None
    items = page.get("items")
    return (
        str(page.get("href") or ""),
        str(page.get("ready") or ""),
        list(items) if isinstance(items, list) else [],
    )


# ---------------------------------------------------------------------------
# web_fetch：给 URL 取正文（spec 2026-09-02 capability-amplification §3.6）
# ---------------------------------------------------------------------------
#
# knevo 在茅台题上赢的机制是 ``web_fetch`` 拉新浪指标页全文；我们的 ``web_search`` 只回
# 5 条 × 160 字符 snippet，线索到不了「可读证据」。这里补取页，契约由注册表写：
# tier 永远 public_web、二手；as_of 取页面日期，取不到才记抓取日**并标明**；
# 取不到页要报 error 带原因，不静默回空。


@dataclass(frozen=True)
class WebPageResult:
    url: str
    final_url: str
    title: str
    text: str
    # 页面自述的发布/更新日（ISO）；None = 页面上找不到，调用方按抓取日处理并标明。
    page_date: str | None
    fetched_on: str
    # "cdp_proxy" | "direct_http" | ""（未取到）
    transport: str
    trace: ProviderTrace


_META_DATE_RE = re.compile(
    r"<meta[^>]+(?:property|name|itemprop)=[\"']"
    r"(?:article:published_time|article:modified_time|og:updated_time|pubdate|publishdate|"
    r"publish_date|datePublished|dateModified|weibo:article:create_at|"
    r"apub:time|original-publish-date|date)[\"'][^>]+content=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_TIME_TAG_RE = re.compile(r"<time[^>]+datetime=[\"']([^\"']+)[\"']", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})")
_CN_DATE_RE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_STRIP_BLOCK_RE = re.compile(
    r"<(script|style|noscript|svg|template)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_BLOCK_TAG_RE = re.compile(
    r"</?(?:p|div|br|li|ul|ol|tr|td|th|table|h[1-6]|section|article|header|footer|"
    r"blockquote|pre|dd|dt|dl)\b[^>]*>",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_CHARSET_RE = re.compile(rb"charset=[\"']?([A-Za-z0-9_\-]+)", re.IGNORECASE)


def _normalise_date(year: str, month: str, day: str, *, upper: date) -> str | None:
    try:
        value = date(int(year), int(month), int(day))
    except ValueError:
        return None
    # 未来日期不是发布日（模板占位、倒计时之类），丢弃。
    return value.isoformat() if value <= upper else None


def extract_page_date(html_text: str, body_text: str, *, fetched_on: date) -> str | None:
    """页面自述日期：meta / <time> 优先，其次正文开头的显式日期。找不到返回 None。"""

    candidates: list[str] = []
    for match in _META_DATE_RE.finditer(html_text or ""):
        candidates.append(match.group(1))
    for match in _TIME_TAG_RE.finditer(html_text or ""):
        candidates.append(match.group(1))
    for raw in candidates:
        iso = _ISO_DATE_RE.search(raw)
        if iso is not None:
            normalised = _normalise_date(*iso.groups(), upper=fetched_on)
            if normalised:
                return normalised
        cn = _CN_DATE_RE.search(raw)
        if cn is not None:
            normalised = _normalise_date(*cn.groups(), upper=fetched_on)
            if normalised:
                return normalised
    head = (body_text or "")[:3000]
    dated: list[str] = []
    for match in _CN_DATE_RE.finditer(head):
        normalised = _normalise_date(*match.groups(), upper=fetched_on)
        if normalised:
            dated.append(normalised)
    for match in _ISO_DATE_RE.finditer(head):
        normalised = _normalise_date(*match.groups(), upper=fetched_on)
        if normalised:
            dated.append(normalised)
    # 正文开头若有多枚日期，取最晚的一枚当「页面日期」——财经指标页表头列的是报告期，
    # 页面日期通常是最新那一列或「更新于」那一行。
    return max(dated) if dated else None


def html_to_text(raw_html: str) -> tuple[str, str]:
    """(title, text)。确定性剥标签，不做可读性打分——读者是模型，不是人眼。"""

    source = str(raw_html or "")
    title_match = _TITLE_RE.search(source)
    title = html.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip() if title_match else ""
    body = _COMMENT_RE.sub(" ", source)
    body = _STRIP_BLOCK_RE.sub(" ", body)
    body = _BLOCK_TAG_RE.sub("\n", body)
    body = _TAG_RE.sub(" ", body)
    body = html.unescape(body)
    lines = [re.sub(r"[ \t\u3000\xa0]+", " ", line).strip() for line in body.splitlines()]
    text = "\n".join(line for line in lines if line)
    return title, text[:_WEB_FETCH_MAX_TEXT_CHARS]


def _decode_html(payload: bytes, content_type: str) -> str:
    header_charset = _CHARSET_RE.search(content_type.encode("utf-8", "ignore"))
    meta_charset = _CHARSET_RE.search(payload[:4096])
    for candidate in (
        header_charset.group(1).decode("ascii", "ignore") if header_charset else None,
        meta_charset.group(1).decode("ascii", "ignore") if meta_charset else None,
        "utf-8",
        "gb18030",
    ):
        if not candidate:
            continue
        try:
            return payload.decode(candidate)
        except (UnicodeDecodeError, LookupError):
            continue
    return payload.decode("utf-8", "replace")


def _validate_fetch_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return "invalid_url: scheme must be http or https"
    if not parsed.netloc:
        return "invalid_url: missing host"
    return None


def _fetch_page_direct(url: str, *, timeout: float) -> tuple[str, str, str]:
    """(final_url, content_type, html)。异常原样抛给调用方归类。"""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(_WEB_FETCH_MAX_BYTES + 1)
        content_type = str(response.headers.get("Content-Type") or "")
        final_url = str(response.geturl() or url)
    if len(payload) > _WEB_FETCH_MAX_BYTES:
        payload = payload[:_WEB_FETCH_MAX_BYTES]
    return final_url, content_type, _decode_html(payload, content_type)


def _fetch_page_via_proxy(
    url: str, *, base: str, timeout: float
) -> tuple[str, str, str] | None:
    """经 CDP 代理渲染后取 (final_url, title, innerText)；代理不可用返回 None 让调用方走直连。"""

    try:
        with urllib.request.urlopen(f"{base}/health", timeout=min(timeout, 5.0)):
            pass
    except Exception:  # noqa: BLE001
        return None
    target_id = ""
    try:
        with urllib.request.urlopen(
            f"{base}/new?url={urllib.parse.quote(url, safe='')}",
            timeout=timeout,
        ) as response:
            opened = json.loads(response.read())
        target_id = str(opened.get("targetId") or opened.get("id") or "")
        if not target_id:
            raise OSError("missing target id")
        script = (
            "JSON.stringify({href:location.href,title:document.title,"
            "text:(document.body&&document.body.innerText)||''})"
        )
        evaluated: dict[str, object] = {"value": ""}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            request = urllib.request.Request(
                f"{base}/eval?target={urllib.parse.quote(target_id)}",
                data=script.encode(),
                method="POST",
            )
            remaining = deadline - time.monotonic()
            with urllib.request.urlopen(
                request, timeout=max(1.0, min(5.0, remaining))
            ) as response:
                evaluated = json.loads(response.read())
            payload = json.loads(str(evaluated.get("value") or "{}") or "{}")
            if isinstance(payload, dict) and str(payload.get("text") or "").strip():
                return (
                    str(payload.get("href") or url),
                    str(payload.get("title") or ""),
                    str(payload.get("text") or "")[:_WEB_FETCH_MAX_TEXT_CHARS],
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(1.0, remaining))
        return (url, "", "")
    finally:
        if target_id:
            try:
                urllib.request.urlopen(
                    f"{base}/close?target={urllib.parse.quote(target_id)}", timeout=5
                ).close()
            except Exception:  # noqa: BLE001
                pass


def _page_failure(
    url: str, *, status: str, detail: str, fetched_on: str
) -> WebPageResult:
    return WebPageResult(
        url=url,
        final_url=url,
        title="",
        text="",
        page_date=None,
        fetched_on=fetched_on,
        transport="",
        trace=ProviderTrace(
            provider=PROVIDER_WEB_FETCH,
            capability="web_fetch",
            status=status,
            detail=detail[:200],
        ),
    )


def fetch_web_page(
    url: str,
    *,
    timeout: float = 20.0,
    proxy_url: str | None = None,
    today: date | None = None,
) -> WebPageResult:
    """取一页正文。CDP 代理可用就走渲染（含 JS 页），否则直连 HTTP 剥标签。

    失败**分状态**：``invalid_url`` / ``disabled`` 之外一律 ``error`` 并把原因写进
    ``trace.detail``（HTTP 状态码、异常类名与消息）；正文为空是 ``empty``。
    调用方据此写观察值——「取不到页」和「页上没字」对模型是两件事。
    """

    fetched_on = (today or date.today()).isoformat()
    cleaned = str(url or "").strip()
    invalid = _validate_fetch_url(cleaned)
    if invalid:
        return _page_failure(cleaned, status="error", detail=invalid, fetched_on=fetched_on)
    if os.environ.get(WEB_FETCH_ENV_FLAG, "1").strip().lower() in {"0", "false", "off"}:
        return _page_failure(
            cleaned, status="disabled", detail=f"{WEB_FETCH_ENV_FLAG}=0", fetched_on=fetched_on
        )
    base = (proxy_url or os.environ.get("WEB_ACCESS_PROXY_URL") or DEFAULT_PROXY_URL).rstrip("/")
    final_url, title, text, html_text, transport = cleaned, "", "", "", ""
    try:
        rendered = _fetch_page_via_proxy(cleaned, base=base, timeout=timeout)
        if rendered is not None:
            final_url, title, text = rendered
            transport = "cdp_proxy"
        else:
            final_url, _content_type, html_text = _fetch_page_direct(cleaned, timeout=timeout)
            title, text = html_to_text(html_text)
            transport = "direct_http"
    except urllib.error.HTTPError as exc:
        return _page_failure(
            cleaned, status="error", detail=f"HTTP {exc.code} {exc.reason}", fetched_on=fetched_on
        )
    except Exception as exc:  # noqa: BLE001
        return _page_failure(
            cleaned,
            status="error",
            detail=f"{type(exc).__name__}: {exc}".strip(": "),
            fetched_on=fetched_on,
        )
    page_date = extract_page_date(
        html_text, text, fetched_on=date.fromisoformat(fetched_on)
    )
    return WebPageResult(
        url=cleaned,
        final_url=final_url or cleaned,
        title=title,
        text=text,
        page_date=page_date,
        fetched_on=fetched_on,
        transport=transport,
        trace=ProviderTrace(
            provider=PROVIDER_WEB_FETCH,
            capability="web_fetch",
            status="success" if text.strip() else "empty",
            detail=(
                f"{transport}; chars={len(text)}; "
                f"as_of={'page:' + page_date if page_date else 'fetched:' + fetched_on}"
            ),
            result_count=1 if text.strip() else 0,
        ),
    )
