from __future__ import annotations

import io
import json
from unittest import mock

from intelligence.services import web_research


class _FakeClock:
    """让 ``time.monotonic`` / ``time.sleep`` 在测试里可控，稳定窗按假时钟推进。"""

    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += max(0.0, float(seconds))


def _page_state(*, href: str, ready: str, items: list[dict[str, str]]) -> str:
    return json.dumps({"href": href, "ready": ready, "items": items}, ensure_ascii=False)


def _fake_proxy(eval_values: list[str]):
    """按调用顺序回放 ``/eval`` 的 value；``/health`` ``/new`` ``/close`` 走固定应答。"""

    calls: list[str] = []
    remaining = list(eval_values)

    def urlopen(request, timeout=None):  # noqa: ANN001
        url = request.full_url if hasattr(request, "full_url") else str(request)
        calls.append(url)
        if "/eval" in url:
            value = remaining.pop(0) if len(remaining) > 1 else remaining[0]
            body = json.dumps({"value": value})
        elif "/new" in url:
            body = json.dumps({"targetId": "T1"})
        else:
            body = "{}"
        return io.BytesIO(body.encode("utf-8"))

    return urlopen, calls


_SEARCH_HREF = "https://www.bing.com/search?q=%E5%B0%8F%E7%B1%B3"
_SHELL_ITEMS = [
    {"title": "Xiaomi官方网站", "url": "https://www.mi.com/index.html", "snippet": "小米官网"},
    {"title": "小米商城", "url": "https://www.mi.com/shop", "snippet": "商城"},
]
_REAL_ITEMS = [
    {
        "title": "【小米集团2024财报】史上最强年报，总收入3659亿元",
        "url": "https://xueqiu.com/1/2",
        "snippet": "2024 年总收入 3659 亿元",
    },
]


def test_bing_results_wait_for_rdr_redirect_instead_of_jcache_shell() -> None:
    """``/new`` 返回时页面已 complete 且有结果，但那是 JCache 壳；真结果在 rdr=1 跳转之后。"""

    clock = _FakeClock()
    urlopen, calls = _fake_proxy(
        [
            _page_state(href=_SEARCH_HREF, ready="complete", items=_SHELL_ITEMS),
            _page_state(href=_SEARCH_HREF, ready="complete", items=_SHELL_ITEMS),
            _page_state(href=_SEARCH_HREF + "&rdr=1&rdrig=ABC", ready="loading", items=[]),
            _page_state(href=_SEARCH_HREF + "&rdr=1&rdrig=ABC", ready="complete", items=_REAL_ITEMS),
        ]
    )
    with (
        mock.patch("urllib.request.urlopen", side_effect=urlopen),
        mock.patch.object(web_research.time, "monotonic", clock.monotonic),
        mock.patch.object(web_research.time, "sleep", clock.sleep),
    ):
        result = web_research.fetch_web_search("小米集团 2024年 总收入", timeout=20.0)

    assert [item.title for item in result.items] == [_REAL_ITEMS[0]["title"]]
    assert result.trace.status == "success"
    assert web_research._BING_DETAIL_SETTLED_RDR in (result.trace.detail or "")
    assert any("/close" in url for url in calls)


def test_bing_results_without_redirect_are_accepted_once_stable() -> None:
    """没观察到 rdr 跳转时，结果连续稳定满 settle 窗才收，并在 detail 里说明走的是兜底。"""

    clock = _FakeClock()
    urlopen, _calls = _fake_proxy(
        [_page_state(href=_SEARCH_HREF, ready="complete", items=_REAL_ITEMS)]
    )
    with (
        mock.patch("urllib.request.urlopen", side_effect=urlopen),
        mock.patch.object(web_research.time, "monotonic", clock.monotonic),
        mock.patch.object(web_research.time, "sleep", clock.sleep),
    ):
        result = web_research.fetch_web_search("小米集团 2024年 总收入", timeout=20.0)

    assert [item.title for item in result.items] == [_REAL_ITEMS[0]["title"]]
    assert web_research._BING_DETAIL_SETTLED_STABLE in (result.trace.detail or "")
    assert clock.now - 1000.0 >= web_research._BING_SETTLE_SECONDS


def test_bing_shell_only_until_deadline_is_flagged_unsettled() -> None:
    """一直没跳转、结果又在变（不算稳定），到 deadline 只能把最后一批带 unsettled 标记交出去。"""

    clock = _FakeClock()
    flipping = [
        _page_state(href=_SEARCH_HREF, ready="complete", items=_SHELL_ITEMS),
        _page_state(href=_SEARCH_HREF, ready="complete", items=_SHELL_ITEMS[:1]),
    ]
    urlopen, _calls = _fake_proxy(flipping * 40)
    with (
        mock.patch("urllib.request.urlopen", side_effect=urlopen),
        mock.patch.object(web_research.time, "monotonic", clock.monotonic),
        mock.patch.object(web_research.time, "sleep", clock.sleep),
    ):
        result = web_research.fetch_web_search("小米集团 2024年 总收入", timeout=3.0)

    assert result.items
    assert web_research._BING_DETAIL_UNSETTLED in (result.trace.detail or "")


def test_bing_page_state_script_brackets_balance() -> None:
    """拼接出来的 JS 括号不配平 → 代理回 4xx → request_error，桩掉代理的测试看不见，这里单独钉。"""

    script = web_research._bing_page_state_script(5)
    stack: list[str] = []
    pairs = {")": "(", "}": "{", "]": "["}
    in_quote: str | None = None
    for ch in script:
        if in_quote:
            if ch == in_quote:
                in_quote = None
            continue
        if ch in "'\"":
            in_quote = ch
        elif ch in "({[":
            stack.append(ch)
        elif ch in pairs:
            assert stack and stack.pop() == pairs[ch], script
    assert not stack, script
    assert in_quote is None
    assert "location.href" in script and "document.readyState" in script and "li.b_algo" in script


def test_bing_eval_payload_not_page_state_is_parse_error() -> None:
    urlopen, _calls = _fake_proxy(["not json at all"])
    with mock.patch("urllib.request.urlopen", side_effect=urlopen):
        result = web_research.fetch_web_search("小米集团 2024年 总收入", timeout=2.0)

    assert result.items == ()
    assert result.trace.status == "parse_error"


def test_definition_query_excludes_model_meta_questions() -> None:
    assert web_research.is_definition_query("卫星互联网是什么")
    assert not web_research.is_definition_query("你好，你是什么模型")


def test_proxy_failure_is_observable() -> None:
    with mock.patch(
        "urllib.request.urlopen",
        side_effect=OSError("connection refused"),
    ):
        result = web_research.fetch_web_search("卫星互联网是什么")

    assert result.items == ()
    assert result.trace.status == "proxy_unavailable"
    assert result.trace.provider == web_research.PROVIDER_BING_WEB


def test_bing_redirect_is_decoded_to_direct_source_url() -> None:
    encoded = "a1aHR0cHM6Ly93d3cubWlpdC5nb3YuY24vYXJ0aWNsZS5odG1s"

    assert (
        web_research._direct_result_url(
            f"https://www.bing.com/ck/a?u={encoded}"
        )
        == "https://www.miit.gov.cn/article.html"
    )
