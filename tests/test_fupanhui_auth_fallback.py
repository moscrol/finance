"""2026-08-24 公开端点转登录后的三条韧性补丁的回归测试。

背景（当日实测）：fupanhui 公开 API 开始校验登录（匿名 401），
同时本机代理把新浪/东财 SSL 掐断。当晚补跑靠三条补丁救活：
1. api_get_public 401 → CDP 带登录态回退
2. 批量板块 K 线/成分股的页面内 fetch 带 Bearer
3. sector-daily 抓取清单按当日 published 宇宙过滤（不扫死 .TI 码）
4. index-daily akshare 双源失败 → reviews/market.volume.indices 兜底
"""
from __future__ import annotations

import json
import urllib.error

import pytest

from market_feature_store.sources import fupanhui_source as fs


class TestApiGetPublicAuthFallback:
    @pytest.fixture(autouse=True)
    def _direct_opt_in(self, monkeypatch):
        monkeypatch.setattr(fs, "DIRECT_MODE", True)
        monkeypatch.setenv("FUPANHUI_MIN_INTERVAL", "0")
        fs.reset_session_hygiene()
        yield
        fs.reset_session_hygiene()

    def test_401_falls_back_to_cdp_api_get(self, monkeypatch):
        calls = []

        class _Fake401(urllib.error.HTTPError):
            def __init__(self):
                super().__init__("https://fupanhui.com/x", 401, "Unauthorized", None, None)

        def _fail_open(*_args, **_kwargs):
            calls.append("direct")
            raise _Fake401()

        def _fake_cdp(path, params=None, timeout=60):
            calls.append(("cdp", path))
            return {"panels": []}

        monkeypatch.setattr(fs.urllib.request, "urlopen", _fail_open)
        monkeypatch.setattr(fs, "api_get", _fake_cdp)

        assert fs.api_get_public("/data/theme/panels", {"trade_date": "2026-08-24"}) == {"panels": []}
        assert ("cdp", "/api/v1/client/data/theme/panels") in calls

    def test_other_http_error_no_fallback(self, monkeypatch):
        class _Fake503(urllib.error.HTTPError):
            def __init__(self):
                super().__init__("https://fupanhui.com/x", 503, "unavailable", None, None)

        def _fail_open(*_args, **_kwargs):
            raise _Fake503()

        def _must_not_call(*_a, **_k):
            pytest.fail("5xx 不应走 CDP 回退")

        monkeypatch.setattr(fs.urllib.request, "urlopen", _fail_open)
        monkeypatch.setattr(fs, "api_get", _must_not_call)

        with pytest.raises(fs.FupanhuiError, match="503"):
            fs.api_get_public("/data/theme/panels")

    def test_401_with_dead_cdp_keeps_root_cause(self, monkeypatch):
        class _Fake401(urllib.error.HTTPError):
            def __init__(self):
                super().__init__("https://fupanhui.com/x", 401, "Unauthorized", None, None)

        def _fail_open(*_args, **_kwargs):
            raise _Fake401()

        def _dead_cdp(*_a, **_k):
            raise fs.FupanhuiError("CDP eval 失败: proxy 不可达")

        monkeypatch.setattr(fs.urllib.request, "urlopen", _fail_open)
        monkeypatch.setattr(fs, "api_get", _dead_cdp)

        with pytest.raises(fs.FupanhuiError, match=r"401.*CDP 回退失败"):
            fs.api_get_public("/data/theme/panels")


class TestBatchJsCarriesBearer:
    """批量 JS 必须带 Authorization——2026-08-24 修复的核心。"""

    def _capture_js(self, monkeypatch, builder):
        captured = {}

        def _fake_eval(js, timeout=180, retries=3):
            captured["js"] = js
            return json.dumps({})

        monkeypatch.setattr(fs, "DIRECT_MODE", False)
        monkeypatch.setattr(fs, "cdp_eval", _fake_eval)
        builder()
        return captured["js"]

    def test_klines_batch_js_has_bearer(self, monkeypatch):
        js = self._capture_js(
            monkeypatch,
            lambda: fs.get_sector_klines_batch(["990001.FP"], trade_date="2026-08-24"),
        )
        assert "user_token" in js
        assert "Authorization" in js
        assert "{headers}" in js  # fetch(url, {headers})

    def test_stocks_batch_js_has_bearer(self, monkeypatch):
        js = self._capture_js(
            monkeypatch,
            lambda: fs.get_sector_stocks_batch(["990001.FP"], trade_date="2026-08-24"),
        )
        assert "user_token" in js
        assert "Authorization" in js
        assert "{headers}" in js

    def test_js_is_syntactically_valid(self, monkeypatch):
        """token 为空时 headers={} 仍要可执行——不因拼接产生 {{}} 之类语法错误。"""
        js = self._capture_js(
            monkeypatch,
            lambda: fs.get_sector_stocks_batch(["990001.FP"], trade_date="2026-08-24"),
        )
        assert "{{headers}}" not in js
        assert "({headers})" in js or ",{headers})" in js
