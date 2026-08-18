"""W7 来源可信度分级：权威机构 / 公司公告 / 媒体 / 自披露。

只声明出处硬度，不改「只列不编」，也不把分级当胜率或概率。
口径抄 Knevo 探针信源分层：监管/部委 > 公司法定披露 > 具名媒体 > 自媒体/不明。
"""

from __future__ import annotations

from urllib.parse import urlparse

CRED_AUTHORITY = "权威机构"
CRED_FILING = "公司公告"
CRED_MEDIA = "媒体"
CRED_SELF = "自披露"
CREDIBILITY_LEVELS = (CRED_AUTHORITY, CRED_FILING, CRED_MEDIA, CRED_SELF)

_AUTHORITY_HOSTS = (
    "nist.gov",
    "whitehouse.gov",
    "cisa.gov",
    "congress.gov",
    "federalregister.gov",
    "sec.gov",
    "gov.cn",
    "oscca.gov.cn",
    "cac.gov.cn",
    "miit.gov.cn",
    "csrc.gov.cn",
    "nlc.cn",
)
_FILING_HOSTS = (
    "cninfo.com.cn",
    "sse.com.cn",
    "szse.cn",
    "eastmoney.com/notice",
)
_FILING_HINTS = ("公告", "互动易", "投资者关系", "investor relations", "/ir/", "8-k", "10-k")
_MEDIA_HOSTS = (
    "reuters.com",
    "cnbc.com",
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "nikkei.com",
    "eetimes.com",
    "semi.org",
    "eastmoney.com",
    "stcn.com",
    "cs.com.cn",
    "cls.cn",
    "yicai.com",
    "bbc.com",
    "cnn.com",
    "forbes.com",
    "techcrunch.com",
)
_MEDIA_NAMES = (
    "reuters",
    "cnbc",
    "bloomberg",
    "证券时报",
    "上海证券报",
    "上证报",
    "中国证券报",
    "财联社",
    "新华财经",
    "第一财经",
    "21世纪经济报道",
    "bbc",
    "cnn",
)


def classify_news_credibility(source: str, url: str) -> str:
    host = (urlparse(str(url or "")).hostname or "").lower().removeprefix("www.")
    src = str(source or "").strip().lower()
    blob = f"{host} {src} {str(url or '').lower()}"
    if any(host.endswith(item) or item in host for item in _AUTHORITY_HOSTS):
        return CRED_AUTHORITY
    if any(item in blob for item in _FILING_HINTS) or any(
        host.endswith(item.split("/")[0]) for item in _FILING_HOSTS if "/" not in item
    ):
        return CRED_FILING
    if any(host.endswith(item) or item in host for item in _MEDIA_HOSTS):
        return CRED_MEDIA
    if any(name in src for name in _MEDIA_NAMES):
        return CRED_MEDIA
    return CRED_SELF
