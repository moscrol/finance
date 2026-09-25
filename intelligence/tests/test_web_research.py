from __future__ import annotations

from unittest import mock

from intelligence.services import web_research


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
