"""§3.6 第 9 条：``web_fetch`` 取页工具的三条契约。

- 来源分档与 as_of 来源：tier 恒为 ``public_web``；``as_of`` 取页面日期，取不到才记抓取日
  且观察值里标明是哪一种；``source`` 为最终 URL。
- 空结果语义：取不到页 → ``trace.status == "error"`` 带原因（HTTP 码 / 异常），不静默回空；
  取到页但无正文 → ``empty``，观察值写明不能当否定证据。
- 参数含义与拒绝条件：一个绝对 http(s) URL；检索词 / 站点名 / 多余键一律拒（T-3 已并入）。

全部离线：``urllib.request.urlopen`` 打桩，CDP 代理健康检查按不可用处理，走直连路径。
"""

from __future__ import annotations

import urllib.error
from datetime import date
from unittest import mock

import pytest

from intelligence.services import agent_research, web_research
from intelligence.services.agent_research import AgentToolContext, page_text_chunks
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.evidence_capabilities import runtime_capabilities_for_frame
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.research_tool_registry import (
    URL_TOOL_PARAMETERS,
    default_registry,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.services.web_research import (
    extract_page_date,
    fetch_web_page,
    html_to_text,
)

SINA_URL = (
    "https://money.finance.sina.com.cn/corp/go.php/vFD_FinancialGuideLine/"
    "stockid/600519/ctrl/2024/displaytype/4.phtml"
)
FETCH_DAY = date(2026, 9, 2)

_SINA_HTML = """<!DOCTYPE html><html><head><meta charset="gb2312">
<title>贵州茅台(600519) 财务指标_新浪财经</title>
<meta property="article:modified_time" content="2025-04-03T18:20:00+08:00">
<script>var x = "不该出现在正文里";</script><style>.a{color:red}</style>
</head><body><!-- 注释也不该出现 -->
<div class="tit">主要财务指标&nbsp;&mdash;&nbsp;贵州茅台</div>
<table><tr><th>报告日期</th><th>2024-12-31</th><th>2024-09-30</th></tr>
<tr><td>营业总收入(万元)</td><td>17414400.00</td><td>12312300.00</td></tr>
<tr><td>归属母公司股东的净利润(万元)</td><td>8622800.00</td><td>6082800.00</td></tr></table>
<p>数据来源：公司公告。</p></body></html>"""


class _FakeHttpResponse:
    def __init__(self, body: bytes, *, url: str, content_type: str) -> None:
        self._body = body
        self._url = url
        self.headers = {"Content-Type": content_type}

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, limit: int | None = None) -> bytes:
        return self._body if limit is None else self._body[:limit]

    def geturl(self) -> str:
        return self._url


def _urlopen_direct_only(page: _FakeHttpResponse | Exception):
    """CDP 代理健康检查不可用 → 走直连；直连返回 page 或抛 page。"""

    def fake_urlopen(request, timeout=None):  # noqa: ARG001
        url = request if isinstance(request, str) else request.full_url
        if url.endswith("/health"):
            raise urllib.error.URLError("proxy down")
        if isinstance(page, Exception):
            raise page
        return page

    return fake_urlopen


def _context(*, cutoff: date = FETCH_DAY) -> AgentToolContext:
    return AgentToolContext(
        ResearchDeadline.from_timeout(30.0),
        lambda: False,
        InformationCutoff(cutoff, "runtime_default"),
    )


# ---------------------------------------------------------------------------
# 剥标签 / 页面日期
# ---------------------------------------------------------------------------


def test_html_to_text_strips_script_style_comments_and_unescapes() -> None:
    title, text = html_to_text(_SINA_HTML)
    assert title == "贵州茅台(600519) 财务指标_新浪财经"
    assert "不该出现在正文里" not in text
    assert "color:red" not in text
    assert "注释也不该出现" not in text
    assert "主要财务指标 — 贵州茅台" in text
    assert "17414400.00" in text


def test_extract_page_date_prefers_meta_then_body_and_rejects_future() -> None:
    assert (
        extract_page_date(_SINA_HTML, "", fetched_on=FETCH_DAY) == "2025-04-03"
    )
    assert (
        extract_page_date("", "发布于2026年8月15日 正文", fetched_on=FETCH_DAY)
        == "2026-08-15"
    )
    assert extract_page_date("", "2030-01-01 倒计时", fetched_on=FETCH_DAY) is None
    assert extract_page_date("<html></html>", "没有日期的正文", fetched_on=FETCH_DAY) is None


def test_page_text_chunks_split_on_lines_and_cap_count() -> None:
    text = "\n".join(f"第{i}行" + "字" * 100 for i in range(60))
    chunks = page_text_chunks(text, chunk_chars=300, max_chunks=4)
    assert len(chunks) == 4
    assert all(len(chunk) <= 300 for chunk in chunks)
    assert chunks[0].startswith("第0行")
    assert page_text_chunks("") == []


# ---------------------------------------------------------------------------
# fetch_web_page：分状态返回
# ---------------------------------------------------------------------------


def test_fetch_web_page_direct_path_reads_gbk_page_and_takes_page_date() -> None:
    page = _FakeHttpResponse(
        _SINA_HTML.encode("gb18030"), url=SINA_URL, content_type="text/html; charset=gb2312"
    )
    with mock.patch("urllib.request.urlopen", _urlopen_direct_only(page)):
        result = fetch_web_page(SINA_URL, today=FETCH_DAY)
    assert result.trace.status == "success"
    assert result.transport == "direct_http"
    assert result.title == "贵州茅台(600519) 财务指标_新浪财经"
    assert "17414400.00" in result.text
    assert result.page_date == "2025-04-03"
    assert result.fetched_on == "2026-09-02"
    assert result.final_url == SINA_URL
    assert "as_of=page:2025-04-03" in result.trace.detail


def test_fetch_web_page_without_a_page_date_records_the_fetch_day_and_says_so() -> None:
    page = _FakeHttpResponse(
        b"<html><head><title>t</title></head><body><p>no dates here</p></body></html>",
        url="https://example.invalid/undated",
        content_type="text/html; charset=utf-8",
    )
    with mock.patch("urllib.request.urlopen", _urlopen_direct_only(page)):
        result = fetch_web_page("https://example.invalid/undated", today=FETCH_DAY)
    assert result.trace.status == "success"
    assert result.page_date is None
    assert "as_of=fetched:2026-09-02" in result.trace.detail


@pytest.mark.parametrize(
    ("failure", "expected_detail"),
    [
        (urllib.error.URLError("nodename nor servname provided"), "URLError"),
        (
            urllib.error.HTTPError(
                "https://example.invalid/404", 404, "Not Found", hdrs=None, fp=None
            ),
            "HTTP 404 Not Found",
        ),
        (TimeoutError("timed out"), "TimeoutError"),
    ],
)
def test_fetch_web_page_unreachable_url_is_an_error_with_a_reason(
    failure: Exception, expected_detail: str
) -> None:
    with mock.patch("urllib.request.urlopen", _urlopen_direct_only(failure)):
        result = fetch_web_page("https://example.invalid/404", today=FETCH_DAY)
    assert result.trace.status == "error"
    assert expected_detail in result.trace.detail
    assert result.text == ""


def test_fetch_web_page_rejects_non_http_urls_without_touching_the_network() -> None:
    with mock.patch("urllib.request.urlopen") as urlopen:
        result = fetch_web_page("ftp://example.invalid/x", today=FETCH_DAY)
        assert not urlopen.called
    assert result.trace.status == "error"
    assert "invalid_url" in result.trace.detail


def test_fetch_web_page_honours_the_kill_switch(monkeypatch) -> None:
    monkeypatch.setenv(web_research.WEB_FETCH_ENV_FLAG, "0")
    with mock.patch("urllib.request.urlopen") as urlopen:
        result = fetch_web_page("https://example.invalid/x", today=FETCH_DAY)
        assert not urlopen.called
    assert result.trace.status == "disabled"


def test_fetch_web_page_empty_body_is_empty_not_error() -> None:
    page = _FakeHttpResponse(
        b"<html><body><script>only()</script></body></html>",
        url="https://example.invalid/blank",
        content_type="text/html",
    )
    with mock.patch("urllib.request.urlopen", _urlopen_direct_only(page)):
        result = fetch_web_page("https://example.invalid/blank", today=FETCH_DAY)
    assert result.trace.status == "empty"


# ---------------------------------------------------------------------------
# runner：证据分档 / as_of 来源 / 失败观察值
# ---------------------------------------------------------------------------


def _runner():
    return agent_research.build_default_tools(lambda *_a, **_k: object())["web_fetch"]


def test_web_fetch_runner_emits_public_web_evidence_dated_by_the_page() -> None:
    page = _FakeHttpResponse(
        _SINA_HTML.encode("gb18030"), url=SINA_URL, content_type="text/html; charset=gb2312"
    )
    with mock.patch("urllib.request.urlopen", _urlopen_direct_only(page)):
        evidence, observation, trace = _runner()(SINA_URL, _context())
    assert trace.status == "success"
    assert evidence
    assert {item.evidence_tier for item in evidence} == {"public_web"}
    assert {item.source for item in evidence} == {SINA_URL}
    assert {item.source_date for item in evidence} == {"2025-04-03"}
    assert {item.independent_key for item in evidence} == {SINA_URL}
    assert any("17414400.00" in item.detail for item in evidence)
    assert "as_of=2025-04-03（页面日期 2025-04-03）" in observation


def test_web_fetch_runner_marks_fetch_day_as_of_when_page_is_undated() -> None:
    page = _FakeHttpResponse(
        b"<html><head><title>t</title></head><body><p>no dates</p></body></html>",
        url="https://example.invalid/undated",
        content_type="text/html",
    )
    with mock.patch("urllib.request.urlopen", _urlopen_direct_only(page)):
        evidence, observation, _trace = _runner()("https://example.invalid/undated", _context())
    assert {item.source_date for item in evidence} == {"2026-09-02"}
    assert "页面无日期，记抓取日 2026-09-02" in observation


def test_web_fetch_runner_reports_failure_reason_instead_of_silent_empty() -> None:
    failure = urllib.error.HTTPError(
        "https://example.invalid/404", 404, "Not Found", hdrs=None, fp=None
    )
    with mock.patch("urllib.request.urlopen", _urlopen_direct_only(failure)):
        evidence, observation, trace = _runner()("https://example.invalid/404", _context())
    assert evidence == []
    assert trace.status == "error"
    assert "取页失败（HTTP 404 Not Found）" in observation
    assert "不是页面没有该信息" in observation


# ---------------------------------------------------------------------------
# 注册表 / 授权
# ---------------------------------------------------------------------------


def test_web_fetch_is_registered_with_a_url_schema_and_a_contract() -> None:
    registry = default_registry({"web_fetch": lambda *a, **k: None})
    spec = registry.resolve("web_fetch")
    assert spec.query_scope == "query"
    assert spec.contract
    definition = registry.tool_definitions(("web_fetch",))[0]["function"]
    assert definition["parameters"] == URL_TOOL_PARAMETERS
    assert definition["parameters"]["required"] == ["url"]
    # §3.6 三条契约各有落点：来源分档（二手）与 as_of 来源（抓取日）、空结果语义（取页失败）、
    # 参数含义（url）。模型看到的是 description+contract 合成的那一份。
    for phrase in ("二手", "抓取日", "取页失败", "url"):
        assert phrase in definition["description"]


def test_web_fetch_authorization_is_derived_from_web_search() -> None:
    maotai = TaskFrame(
        raw_question="2024年贵州茅台营业总收入是多少亿元？",
        user_goal="查证",
        question_type="financial_analysis",
        subject="贵州茅台",
        subject_kind="company",
        market_scope="A股",
        timeframe="2024年报",
        required_outputs=("financial_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_financial_evidence",
        confidence=0.95,
    )
    capabilities = runtime_capabilities_for_frame(maotai)
    assert "web_search" in capabilities
    assert "web_fetch" in capabilities

    forecast = TaskFrame(
        raw_question="昨天的反弹能持续多久",
        user_goal="判断",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("duration_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )
    local_only = runtime_capabilities_for_frame(forecast)
    assert "web_search" not in local_only
    assert "web_fetch" not in local_only

    # 走完 episode 合同：派生出的 web_fetch 是注册表认识的能力，不会被当 unknown 拒掉。
    context = build_episode_context(maotai, task_id="web-fetch-derived", today="2026-09-02")
    assert "web_fetch" in context.contract.allowed_capabilities


def test_web_fetch_through_the_registry_mints_hashes_and_keeps_error_status() -> None:
    frame = TaskFrame(
        raw_question="2024年贵州茅台营业总收入是多少亿元？",
        user_goal="查证",
        question_type="financial_analysis",
        subject="贵州茅台",
        subject_kind="company",
        market_scope="A股",
        timeframe="2024年报",
        required_outputs=("financial_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_financial_evidence",
        confidence=0.95,
    )
    context = build_episode_context(
        frame, task_id="web-fetch-registry", capabilities=("web_fetch",), today="2026-09-02"
    )
    registry = default_registry({"web_fetch": _runner()})

    page = _FakeHttpResponse(
        _SINA_HTML.encode("gb18030"), url=SINA_URL, content_type="text/html; charset=gb2312"
    )
    with mock.patch("urllib.request.urlopen", _urlopen_direct_only(page)):
        observation = registry.execute(
            "web_fetch", {"url": SINA_URL}, context=context, step_id="web-fetch:1"
        )
    assert observation.trace.status == "success"
    assert observation.evidence_hashes
    assert all(item.content_hash for item in observation.evidence)
    assert observation.trace.served_date == "2025-04-03"

    failure = urllib.error.URLError("connection refused")
    with mock.patch("urllib.request.urlopen", _urlopen_direct_only(failure)):
        failed = registry.execute(
            "web_fetch",
            {"url": "https://example.invalid/down"},
            context=context,
            step_id="web-fetch:2",
        )
    assert failed.trace.status == "error"
    assert failed.evidence == ()
    assert "URLError" in failed.trace.detail
