"""W7 web 事件检索数据块：东财免费全文资讯搜索（标题/来源/时间/链接，可溯源）。

- 取数走东财免费全文搜索 `search-api-web.eastmoney.com`，无需 key，与 D5/D7 同一条东财免费路线。
- **只列不编**：仅输出「日期 | 来源媒体 | 标题 | 链接」原文事实，不做 LLM 摘要、不下结论、
  不推断事件影响；取不到写显式缺口。规避 Knevo 无溯源印象流（如拍脑袋切换概率）的软肋。
- 补的缺口：横向联想/事件题里 PQC、涨价、海外对标等消息面全靠 web，工作台此前完全缺失。
- 关键词优先用实体锚定名 > 匹配题材名；命中「事件/消息/催化/进展/涨价/制裁/中标/量产…」
  意图词且能拿到关键词才追加本块，否则行为不变。
- 单源东财（中文财媒聚合）；海外英文源/通用搜索作 #2b 加固项（接 web-access 通用搜索）后续再补。
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

FETCH_ENV_FLAG = "FINANCE_NEWS_FETCH"
_SEARCH_URL = "https://search-api-web.eastmoney.com/search/jsonp"

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


def fetch_enabled() -> bool:
    return os.environ.get(FETCH_ENV_FLAG, "1").strip().lower() not in {"0", "false", "off"}


def parse_news_intent(query: str) -> bool:
    """确定性意图路由：命中事件/消息/催化/涨价/对标类词面即触发。"""
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return False
    return any(term in text for term in _NEWS_TERMS)


def resolve_news_keyword(
    query: str, theme: str | None = None, entity: str | None = None
) -> str | None:
    """检索关键词：实体锚定名 > 匹配题材名（都无则不检索）。"""
    for cand in (entity, theme):
        cand = (cand or "").strip()
        if cand:
            return cand
    return None


def _within_days(date_str: str, within_days: int) -> bool:
    if within_days <= 0:
        return True
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
    except ValueError:
        return True  # 日期不可解析时保留，交由上层展示原始日期
    return dt >= datetime.now() - timedelta(days=within_days)


def fetch_eastmoney_news(
    keyword: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    within_days: int = DEFAULT_WITHIN_DAYS,
    timeout: float = 8.0,
) -> list[NewsItem]:
    """Best-effort 东财全文资讯搜索（按时间排序）；网络/字段异常时返回空列表。"""
    kw = str(keyword or "").strip()
    if not kw:
        return []
    param = {
        "uid": "",
        "keyword": kw,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
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
    except Exception:
        return []
    try:
        body = raw[raw.find("(") + 1 : raw.rfind(")")]
        articles = ((json.loads(body).get("result")) or {}).get("cmsArticleWebOld") or []
    except Exception:
        return []
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
    return out


def build_news_block(
    keyword: str,
    items: list[NewsItem],
    within_days: int = DEFAULT_WITHIN_DAYS,
    fetch_disabled: bool = False,
) -> str:
    """生成 W7 web 事件检索块（注入 compose）；缺数时仍返回带显式缺口的块。"""
    lines = ["## web 事件检索块 [W7]（东财资讯搜索，可溯源；只列标题/来源/链接，不代为解读）"]
    if fetch_disabled:
        lines.append(f"- ⚠事件取数已被 {FETCH_ENV_FLAG}=0 关闭：消息面按缺口处理，需说明数据不可得。")
        return "\n".join(lines)
    if not items:
        lines.append(
            f"- ⚠缺消息面：东财资讯搜索未取到「{keyword}」近 {within_days} 天内相关资讯，"
            "事件/催化按缺口处理，不得编造。"
        )
        return "\n".join(lines)
    lines.append(f"- 检索词「{keyword}」，近 {within_days} 天资讯 {len(items)} 条（按时间新→旧）：")
    for it in items:
        url = f"（{it.url}）" if it.url else ""
        lines.append(f"- | {it.date} | {it.source} | {it.title} |{url}")
    lines.append(
        "- 使用要求：仅可引用上列标题/来源/时间作为消息面存在性证据；事件影响/因果/概率须条件化表述，"
        "禁止把标题当结论或编造未列出的事件。海外/英文源暂未覆盖（待 #2b web-access 通用搜索加固）。"
    )
    return "\n".join(lines)


def news_block_for_keyword(
    keyword: str | None,
    page_size: int = DEFAULT_PAGE_SIZE,
    within_days: int = DEFAULT_WITHIN_DAYS,
    fetcher: Callable[..., list[NewsItem]] | None = None,
) -> str:
    """给定关键词，取数并渲染 W7 块；关键词为空返回空串（不追加块）。"""
    kw = (keyword or "").strip()
    if not kw:
        return ""
    if not fetch_enabled():
        return build_news_block(kw, [], within_days, fetch_disabled=True)
    fetch = fetcher or fetch_eastmoney_news
    items = fetch(kw, page_size, within_days)
    return build_news_block(kw, items, within_days)
