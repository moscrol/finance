"""W7 web 事件检索数据块：东财免费全文资讯搜索（标题/来源/时间/链接，可溯源）。

- 取数走东财免费全文搜索 `search-api-web.eastmoney.com`，无需 key，与 D5/D7 同一条东财免费路线。
- **只列不编**：仅输出「日期 | 来源媒体 | 标题 | 链接」原文事实，不做 LLM 摘要、不下结论、
  不推断事件影响；取不到写显式缺口。规避 Knevo 无溯源印象流（如拍脑袋切换概率）的软肋。
- 补的缺口：横向联想/事件题里 PQC、涨价、海外对标等消息面全靠 web，工作台此前完全缺失。
- 关键词优先用实体锚定名 > 匹配题材名；命中「事件/消息/催化/进展/涨价/制裁/中标/量产…」
  意图词且能拿到关键词才追加本块，否则行为不变。
- 双 provider：东财（中文财媒聚合）+ web-access CDP proxy（Bing News 全网/海外源，#2b）；
  proxy 不可达或 FINANCE_NEWS_WEB_FETCH=0 时静默降级为单源东财，行为不变。
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from intelligence.services.provider_observability import ProviderTrace

FETCH_ENV_FLAG = "FINANCE_NEWS_FETCH"
WEB_FETCH_ENV_FLAG = "FINANCE_NEWS_WEB_FETCH"
PROXY_URL_ENV = "WEB_ACCESS_PROXY_URL"
_SEARCH_URL = "https://search-api-web.eastmoney.com/search/jsonp"
_DEFAULT_PROXY_URL = "http://localhost:3456"
_BING_NEWS_URL = "https://www.bing.com/news/search"

PROVIDER_EASTMONEY = "东财"
PROVIDER_WEB = "web"

# 中→英关键词别名表：Bing News 对中文题材词命中极差，web 通道检索前先查表换英文词。
_ALIAS_PATH = Path(__file__).resolve().parents[1] / "data" / "news_keyword_aliases.json"

DEFAULT_PAGE_SIZE = 8
DEFAULT_WITHIN_DAYS = 90

# 命中即触发（确定性词面）：事件/消息面/催化/横向联想类问题。
_NEWS_TERMS = (
    "事件",
    "消息",
    "新闻",
    "资讯",
    "催化",
    "进展",
    "最新",
    "近期",
    "涨价",
    "提价",
    "制裁",
    "中标",
    "订单",
    "量产",
    "投产",
    "对标",
    "联想",
    "发生了什么",
    "有什么变化",
    "海外",
)

_EM_TAG_RE = re.compile(r"</?em>")


@dataclass
class NewsItem:
    date: str  # "2026-07-08 15:07:00"
    source: str  # 媒体名
    title: str
    url: str
    provider: str = PROVIDER_EASTMONEY  # 取数通道：东财 / web（web-access 全网检索）


@dataclass(frozen=True)
class NewsFetchResult:
    items: tuple[NewsItem, ...]
    trace: ProviderTrace


@dataclass(frozen=True)
class NewsBlockResult:
    block: str
    traces: tuple[ProviderTrace, ...]


def fetch_enabled() -> bool:
    return os.environ.get(FETCH_ENV_FLAG, "1").strip().lower() not in {"0", "false", "off"}


def web_fetch_enabled() -> bool:
    return os.environ.get(WEB_FETCH_ENV_FLAG, "1").strip().lower() not in {"0", "false", "off"}


def parse_news_intent(query: str) -> bool:
    """确定性意图路由：命中事件/消息/催化/涨价/对标类词面即触发。"""
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return False
    return any(term in text for term in _NEWS_TERMS)


# 从问句兼射关键词时要剥离的脚手架：时间窗口词 + 提问/意图词（确定性词面，非 NLP）。
_QUERY_SCAFFOLD_RE = re.compile(
    r"(最近|近|过去)?\s*\d+\s*(天|个月|月|周|年)内?"
    r"|最近|近期|目前|现在|今年|今天"
    r"|有什么|什么|哪些|有没有|是否|怎么样|如何|为什么"
    r"|实质|重大|重要|相关"
    r"|催化|进展|消息|事件|新闻|资讯|发生了|变化|动态"
    r"|[？?吗呢吧。，,、\s]"
)


def _extract_query_keyword(query: str) -> str | None:
    """无实体/题材可锚时的兜底：从问句里剥离时间窗口词与提问/意图词，取剩余主题词。
    纯确定性正则剥离（非 NLP）；剩余过长/过短视为提不出主题，返回 None 不检索。"""
    text = str(query or "").strip()
    if not text:
        return None
    kw = _QUERY_SCAFFOLD_RE.sub("", text).strip()
    if 2 <= len(kw) <= 16:
        return kw
    return None


@lru_cache(maxsize=1)
def _load_keyword_aliases() -> dict[str, str]:
    try:
        raw = json.loads(_ALIAS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        str(k).strip(): str(v).strip()
        for k, v in raw.items()
        if not str(k).startswith("_") and str(v).strip()
    }


def english_alias(keyword: str) -> str | None:
    """查中→英别名（精确匹配）；无别名返回 None，web 通道用原词检索。"""
    return _load_keyword_aliases().get(str(keyword or "").strip()) or None


def resolve_news_keyword(
    query: str, theme: str | None = None, entity: str | None = None
) -> str | None:
    """检索关键词：实体锚定名 > 匹配题材名 > 问句剥离兜底（都无则不检索）。

    注意：theme 入参应传真实匹配到的题材（matched_theme），不要传「题材兼射不到就用
    整句 query」的兜底值：整句问题当检索词会导致标题搜索零命中（PQC 回归的根因）。"""
    query_text = str(query or "").strip()
    for cand in (entity, theme):
        cand = (cand or "").strip()
        if cand and cand != query_text:
            return cand
    return _extract_query_keyword(query_text)


def _within_days(date_str: str, within_days: int) -> bool:
    if within_days <= 0:
        return True
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
    except ValueError:
        return True  # 日期不可解析时保留，交由上层展示原始日期
    return dt >= datetime.now() - timedelta(days=within_days)


def fetch_eastmoney_news_result(
    keyword: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    within_days: int = DEFAULT_WITHIN_DAYS,
    timeout: float = 8.0,
) -> NewsFetchResult:
    """东财全文资讯搜索，并保留 provider 失败原因。"""
    kw = str(keyword or "").strip()
    if not kw:
        return NewsFetchResult(
            (),
            ProviderTrace(
                provider=PROVIDER_EASTMONEY,
                capability="directional_news",
                status="empty",
                detail="empty keyword",
            ),
        )
    param = {
        "uid": "",
        "keyword": kw,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                # 只搜标题：全文模糊匹配会捞进大量标题无关资讯（正文命中），标题命中才是事件存在性证据
                "searchScope": "title",
                "sort": "time",
                "pageIndex": 1,
                "pageSize": max(1, int(page_size) * 2),
                "preTag": "<em>",
                "postTag": "</em>",
            }
        },
    }
    url = f"{_SEARCH_URL}?cb=x&param={urllib.parse.quote(json.dumps(param, ensure_ascii=False))}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://so.eastmoney.com/"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        return NewsFetchResult(
            (),
            ProviderTrace(
                provider=PROVIDER_EASTMONEY,
                capability="directional_news",
                status="request_error",
                detail=type(exc).__name__,
            ),
        )
    try:
        body = raw[raw.find("(") + 1 : raw.rfind(")")]
        articles = ((json.loads(body).get("result")) or {}).get("cmsArticleWebOld") or []
    except Exception:  # noqa: BLE001
        return NewsFetchResult(
            (),
            ProviderTrace(
                provider=PROVIDER_EASTMONEY,
                capability="directional_news",
                status="parse_error",
                detail="Eastmoney response parse failed",
            ),
        )
    out: list[NewsItem] = []
    for a in articles:
        date_str = str(a.get("date") or "").strip()
        if not _within_days(date_str, within_days):
            continue
        title = _EM_TAG_RE.sub("", str(a.get("title") or "")).strip()
        if not title:
            continue
        # 相关性硬过滤：东财搜索是全文模糊匹配，正文命中会捞进大量标题无关的资讯；
        # 只保留标题含完整检索词的条目，宁缺勿滥（缺数走显式缺口，不给噪声）。
        if kw not in title:
            continue
        out.append(
            NewsItem(
                date=date_str,
                source=str(a.get("mediaName") or "").strip() or "未标注",
                title=title,
                url=str(a.get("url") or "").strip(),
            )
        )
        if len(out) >= int(page_size):
            break
    return NewsFetchResult(
        tuple(out),
        ProviderTrace(
            provider=PROVIDER_EASTMONEY,
            capability="directional_news",
            status="success" if out else "empty",
            detail="Eastmoney title search",
            result_count=len(out),
        ),
    )


def fetch_eastmoney_news(
    keyword: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    within_days: int = DEFAULT_WITHIN_DAYS,
    timeout: float = 8.0,
) -> list[NewsItem]:
    return list(
        fetch_eastmoney_news_result(
            keyword,
            page_size,
            within_days,
            timeout,
        ).items
    )


_REL_TIME_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(\d+)\s*分钟前"), "minutes"),
    (re.compile(r"(\d+)\s*小时前"), "hours"),
    (re.compile(r"(\d+)\s*天前"), "days"),
    (re.compile(r"(\d+)\s*min(?:ute)?s?\s*ago", re.I), "minutes"),
    (re.compile(r"(\d+)\s*h(?:our)?s?\s*ago", re.I), "hours"),
    (re.compile(r"(\d+)\s*d(?:ay)?s?\s*ago", re.I), "days"),
)
_ABS_CN_DATE_RE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_ABS_US_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def _normalize_time_text(text: str) -> str:
    """把 Bing 的相对时间（「3 小时前」/「2 days ago」）best-effort 转成日期字符串；
    无法解析时原样保留（展示层直接透传，不伪造精度）。"""
    text = str(text or "").strip()
    if not text:
        return ""
    for pattern, unit in _REL_TIME_PATTERNS:
        m = pattern.search(text)
        if m:
            delta = timedelta(**{unit: int(m.group(1))})
            dt = datetime.now() - delta
            if unit == "days":
                return dt.strftime("%Y-%m-%d")
            return dt.strftime("%Y-%m-%d %H:%M:00")
    if "昨天" in text or text.lower().startswith("yesterday"):
        return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    m = _ABS_CN_DATE_RE.search(text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = _ABS_US_DATE_RE.search(text)
    if m:  # Bing 英文卡片的 M/D/YYYY
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    if not any(ch.isdigit() for ch in text):
        return ""  # 非时间文本（如栏目标签「Opinion」），不充当日期
    return text


_BING_EXTRACT_JS = """
JSON.stringify(Array.from(document.querySelectorAll('.news-card')).map(c => ({
  title: c.getAttribute('data-title') || '',
  url: c.getAttribute('data-url') || '',
  source: c.getAttribute('data-author') || '',
  time: (c.querySelector('span[aria-label]') || {getAttribute: () => ''}).getAttribute('aria-label') || ''
})))
""".strip()


def _proxy_request(
    proxy_url: str, path: str, body: str | None = None, timeout: float = 8.0
) -> str:
    req = urllib.request.Request(
        proxy_url.rstrip("/") + path,
        data=body.encode("utf-8") if body is not None else None,
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_web_access_news_result(
    keyword: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    within_days: int = DEFAULT_WITHIN_DAYS,
    timeout: float = 20.0,
    proxy_url: str | None = None,
) -> NewsFetchResult:
    """#2b 第二 provider：经 web-access CDP proxy（真实 Chrome）搜 Bing News 全网/海外源。

    Best-effort：proxy 不可达/页面结构变化/任何异常都返回空列表，不影响东财主通道。
    英文/海外标题不做「关键词在标题内」硬过滤（跨语种无法子串匹配），靠搜索引擎
    相关性排序 + 小 page_size 控噪；条目带 provider=web 标记供展示层区分。
    """
    kw = str(keyword or "").strip()
    if not kw:
        return NewsFetchResult(
            (),
            ProviderTrace(
                provider=PROVIDER_WEB,
                capability="directional_news",
                status="empty",
                detail="empty keyword",
            ),
        )
    proxy = (proxy_url or os.environ.get(PROXY_URL_ENV) or _DEFAULT_PROXY_URL).strip()
    target_id = ""
    try:
        _proxy_request(proxy, "/health", timeout=2.0)
    except Exception:  # noqa: BLE001
        return NewsFetchResult(
            (),
            ProviderTrace(
                provider=PROVIDER_WEB,
                capability="directional_news",
                status="proxy_unavailable",
                detail="CDP proxy health check failed",
            ),
        )
    try:
        search_url = f"{_BING_NEWS_URL}?q={urllib.parse.quote(kw)}"
        created = json.loads(
            _proxy_request(proxy, f"/new?url={urllib.parse.quote(search_url, safe='')}", timeout=timeout)
        )
        target_id = str(created.get("targetId") or "").strip()
        if not target_id:
            return NewsFetchResult(
                (),
                ProviderTrace(
                    provider=PROVIDER_WEB,
                    capability="directional_news",
                    status="request_error",
                    detail="missing target id",
                ),
            )
        # 新闻卡片是页面 load 之后异步渲染的，轮询直到出现或超时
        rows: list[Any] = []
        for _ in range(5):
            evaled = json.loads(
                _proxy_request(proxy, f"/eval?target={target_id}", body=_BING_EXTRACT_JS, timeout=timeout)
            )
            rows = json.loads(evaled.get("value") or "[]")
            if rows:
                break
            time.sleep(1.5)
    except json.JSONDecodeError:
        return NewsFetchResult(
            (),
            ProviderTrace(
                provider=PROVIDER_WEB,
                capability="directional_news",
                status="parse_error",
                detail="proxy response was not JSON",
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return NewsFetchResult(
            (),
            ProviderTrace(
                provider=PROVIDER_WEB,
                capability="directional_news",
                status="request_error",
                detail=type(exc).__name__,
            ),
        )
    finally:
        if target_id:
            try:
                _proxy_request(proxy, f"/close?target={target_id}", timeout=5.0)
            except Exception:
                pass
    out: list[NewsItem] = []
    for row in rows if isinstance(rows, list) else []:
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        if not title or not url:
            continue
        date_str = _normalize_time_text(str(row.get("time") or ""))
        if not _within_days(date_str, within_days):
            continue
        out.append(
            NewsItem(
                date=date_str or "未标注",
                source=str(row.get("source") or "").strip() or "未标注",
                title=title,
                url=url,
                provider=PROVIDER_WEB,
            )
        )
        if len(out) >= int(page_size):
            break
    return NewsFetchResult(
        tuple(out),
        ProviderTrace(
            provider=PROVIDER_WEB,
            capability="directional_news",
            status="success" if out else "empty",
            detail="Bing News results via CDP proxy",
            result_count=len(out),
        ),
    )


def fetch_web_access_news(
    keyword: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    within_days: int = DEFAULT_WITHIN_DAYS,
    timeout: float = 20.0,
    proxy_url: str | None = None,
) -> list[NewsItem]:
    return list(
        fetch_web_access_news_result(
            keyword,
            page_size,
            within_days,
            timeout,
            proxy_url,
        ).items
    )


def merge_news_items(
    primary: list[NewsItem], secondary: list[NewsItem]
) -> list[NewsItem]:
    """双 provider 合并去重（URL/标题归一化后去重，东财优先保留），按日期新→旧排序；
    日期不可解析的条目排末尾（保留不丢，不伪造时间）。"""
    seen: set[str] = set()
    merged: list[NewsItem] = []
    for item in list(primary) + list(secondary):
        keys = {k for k in (item.url.strip().rstrip("/"), item.title.strip()) if k}
        if keys & seen:
            continue
        seen |= keys
        merged.append(item)

    def _has_date(it: NewsItem) -> bool:
        try:
            datetime.strptime(it.date[:10], "%Y-%m-%d")
        except ValueError:
            return False
        return True

    dated = sorted((it for it in merged if _has_date(it)), key=lambda it: it.date, reverse=True)
    undated = [it for it in merged if not _has_date(it)]
    return dated + undated


def build_news_block(
    keyword: str,
    items: list[NewsItem],
    within_days: int = DEFAULT_WITHIN_DAYS,
    fetch_disabled: bool = False,
    web_keyword: str | None = None,
) -> str:
    """生成 W7 web 事件检索块（注入 compose）；缺数时仍返回带显式缺口的块。"""
    lines = ["## web 事件检索块 [W7]（东财资讯 + web-access 全网检索，可溯源；只列标题/来源/链接，不代为解读）"]
    if fetch_disabled:
        lines.append(f"- ⚠事件取数已被 {FETCH_ENV_FLAG}=0 关闭：消息面按缺口处理，需说明数据不可得。")
        return "\n".join(lines)
    if not items:
        lines.append(
            f"- ⚠缺消息面：东财资讯与 web-access 全网检索均未取到「{keyword}」近 {within_days} 天内相关资讯，"
            "事件/催化按缺口处理，不得编造。"
        )
        return "\n".join(lines)
    n_web = sum(1 for it in items if it.provider == PROVIDER_WEB)
    web_note = f"，web 检索词「{web_keyword}」" if web_keyword and web_keyword != keyword else ""
    lines.append(
        f"- 检索词「{keyword}」{web_note}，近 {within_days} 天资讯 {len(items)} 条"
        f"（东财 {len(items) - n_web} + web {n_web}，按时间新→旧）："
    )
    for it in items:
        url = f"（{it.url}）" if it.url else ""
        lines.append(f"- [{it.provider}] | {it.date} | {it.source} | {it.title} |{url}")
    lines.append(
        "- 使用要求：仅可引用上列标题/来源/时间作为消息面存在性证据；事件影响/因果/概率须条件化表述，"
        "禁止把标题当结论或编造未列出的事件。[web] 条目来自搜索引擎相关性排序（含海外/英文源），"
        "相关性弱于标题命中的 [东财] 条目，引用时须注意甄别。"
    )
    return "\n".join(lines)


def news_block_for_keyword(
    keyword: str | None,
    page_size: int = DEFAULT_PAGE_SIZE,
    within_days: int = DEFAULT_WITHIN_DAYS,
    fetcher: Callable[..., list[NewsItem]] | None = None,
    web_fetcher: Callable[..., list[NewsItem]] | None = None,
) -> str:
    """给定关键词，双 provider 取数合并后渲染 W7 块；关键词为空返回空串（不追加块）。"""
    return news_block_result_for_keyword(
        keyword,
        page_size,
        within_days,
        fetcher,
        web_fetcher,
    ).block


def news_block_result_for_keyword(
    keyword: str | None,
    page_size: int = DEFAULT_PAGE_SIZE,
    within_days: int = DEFAULT_WITHIN_DAYS,
    fetcher: Callable[..., list[NewsItem]] | None = None,
    web_fetcher: Callable[..., list[NewsItem]] | None = None,
    timeout: float = 20.0,
) -> NewsBlockResult:
    kw = (keyword or "").strip()
    if not kw:
        return NewsBlockResult("", ())
    if not fetch_enabled():
        return NewsBlockResult(
            build_news_block(kw, [], within_days, fetch_disabled=True),
            (
                ProviderTrace(
                    provider=PROVIDER_EASTMONEY,
                    capability="directional_news",
                    status="disabled",
                    detail=f"{FETCH_ENV_FLAG}=0",
                ),
                ProviderTrace(
                    provider=PROVIDER_WEB,
                    capability="directional_news",
                    status="disabled",
                    detail=f"{FETCH_ENV_FLAG}=0",
                ),
            ),
        )
    if fetcher is None:
        eastmoney_result = fetch_eastmoney_news_result(
            kw,
            page_size,
            within_days,
            timeout=min(timeout, 8.0),
        )
        items = list(eastmoney_result.items)
        traces = [eastmoney_result.trace]
    else:
        try:
            items = fetcher(kw, page_size, within_days)
        except Exception as exc:  # noqa: BLE001
            items = []
            traces = [
                ProviderTrace(
                    provider=PROVIDER_EASTMONEY,
                    capability="directional_news",
                    status="request_error",
                    detail=type(exc).__name__,
                )
            ]
        else:
            traces = [
                ProviderTrace(
                    provider=PROVIDER_EASTMONEY,
                    capability="directional_news",
                    status="success" if items else "empty",
                    detail="injected Eastmoney fetcher",
                    result_count=len(items),
                )
            ]
    web_kw: str | None = None
    if web_fetch_enabled():
        web_kw = english_alias(kw) or kw
        if web_fetcher is None:
            web_result = fetch_web_access_news_result(
                web_kw,
                page_size,
                within_days,
                timeout=timeout,
            )
            web_items = list(web_result.items)
            traces.append(web_result.trace)
        else:
            try:
                web_items = web_fetcher(web_kw, page_size, within_days)
            except Exception as exc:  # noqa: BLE001
                web_items = []
                traces.append(
                    ProviderTrace(
                        provider=PROVIDER_WEB,
                        capability="directional_news",
                        status="request_error",
                        detail=type(exc).__name__,
                    )
                )
            else:
                traces.append(
                    ProviderTrace(
                        provider=PROVIDER_WEB,
                        capability="directional_news",
                        status="success" if web_items else "empty",
                        detail="injected web news fetcher",
                        result_count=len(web_items),
                    )
                )
        items = merge_news_items(items, web_items)
    else:
        traces.append(
            ProviderTrace(
                provider=PROVIDER_WEB,
                capability="directional_news",
                status="disabled",
                detail=f"{WEB_FETCH_ENV_FLAG}=0",
            )
        )
    return NewsBlockResult(
        build_news_block(kw, items, within_days, web_keyword=web_kw),
        tuple(traces),
    )
