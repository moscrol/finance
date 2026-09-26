"""复盘会会话卫生：默认不直连、公开 API 不先打 urllib、429 熔断、批量串行。

账号封禁根因（2026-09 诊断，离线源码）：
1. FUPANHUI_DIRECT 默认开，Python urllib UA=Mozilla/5.0 与 Chrome TLS 双通道。
2. api_get_public 无论 DIRECT_MODE 都先 urllib，401 后再 CDP（流量翻倍）。
3. 板块 K 线/成分股 Promise.all 默认 12/8 路并发。
4. 429/超限没有进程级闩，cdp_eval 还会指数重试把号打穿。

本文件只测 fupanhui_source 的公开缝，不打 fupanhui.com。
"""
from __future__ import annotations

import json
import urllib.error

import pytest

from market_feature_store.sources import fupanhui_source as fs


@pytest.fixture(autouse=True)
def _reset_hygiene():
    fs.reset_session_hygiene()
    yield
    fs.reset_session_hygiene()


def test_direct_mode_default_is_off(monkeypatch):
    monkeypatch.delenv("FUPANHUI_DIRECT", raising=False)
    assert fs._read_direct_mode() is False


def test_direct_mode_opt_in(monkeypatch):
    monkeypatch.setenv("FUPANHUI_DIRECT", "1")
    assert fs._read_direct_mode() is True


def test_public_skips_urllib_when_direct_off(monkeypatch):
    monkeypatch.setattr(fs, "DIRECT_MODE", False)
    monkeypatch.setenv("FUPANHUI_MIN_INTERVAL", "0")

    def boom(*_a, **_k):
        pytest.fail("DIRECT_MODE=0 时 api_get_public 不得先打 urllib")

    monkeypatch.setattr(fs.urllib.request, "urlopen", boom)
    monkeypatch.setattr(fs, "api_get", lambda *_a, **_k: {"ok": 1})
    assert fs.api_get_public("/data/theme/panels") == {"ok": 1}


def test_429_trips_latch_and_blocks_next_call(monkeypatch):
    monkeypatch.setattr(fs, "DIRECT_MODE", True)
    monkeypatch.setenv("FUPANHUI_MIN_INTERVAL", "0")
    hits = []

    class _Fake429(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("https://fupanhui.com/x", 429, "Too Many Requests", None, None)

    def fail(*_a, **_k):
        hits.append(1)
        raise _Fake429()

    monkeypatch.setattr(fs.urllib.request, "urlopen", fail)
    with pytest.raises(fs.FupanhuiRateLimitError):
        fs._direct_api_get("/api/v1/client/x")
    with pytest.raises(fs.FupanhuiRateLimitError):
        fs._direct_api_get("/api/v1/client/x")
    assert len(hits) == 1


def test_json_over_quota_trips_latch(monkeypatch):
    monkeypatch.setattr(fs, "DIRECT_MODE", True)
    monkeypatch.setenv("FUPANHUI_MIN_INTERVAL", "0")

    class _Resp:
        def read(self):
            return json.dumps({"code": -1, "message": "用户使用工具已超限"}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(fs.urllib.request, "urlopen", lambda *_a, **_k: _Resp())
    with pytest.raises(fs.FupanhuiRateLimitError, match="超限"):
        fs._direct_api_get("/api/v1/client/x")
    with pytest.raises(fs.FupanhuiRateLimitError):
        fs.api_get_public("/reviews/summary")


def test_401_does_not_trip_latch(monkeypatch):
    monkeypatch.setenv("FUPANHUI_MIN_INTERVAL", "0")

    class _Fake401(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("https://fupanhui.com/x", 401, "Unauthorized", None, None)

    monkeypatch.setattr(fs.urllib.request, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(_Fake401()))
    with pytest.raises(urllib.error.HTTPError) as ei:
        fs._direct_api_get("/api/v1/client/x")
    assert ei.value.code == 401
    assert fs.rate_limit_tripped() is False


def test_klines_batch_default_is_serial(monkeypatch):
    captured = {}

    def _fake_eval(js, timeout=180, retries=3):
        captured["js"] = js
        return json.dumps({})

    monkeypatch.setattr(fs, "DIRECT_MODE", False)
    monkeypatch.setattr(fs, "cdp_eval", _fake_eval)
    fs.get_sector_klines_batch(["990001.FP"], trade_date="2026-09-03")
    assert "const BATCH=1;" in captured["js"]
    assert "Promise.all" not in captured["js"] or "BATCH=1" in captured["js"]


def test_stocks_batch_default_is_serial(monkeypatch):
    captured = {}

    def _fake_eval(js, timeout=180, retries=3):
        captured["js"] = js
        return json.dumps({})

    monkeypatch.setattr(fs, "DIRECT_MODE", False)
    monkeypatch.setattr(fs, "cdp_eval", _fake_eval)
    fs.get_sector_stocks_batch(["990001.FP"], trade_date="2026-09-03")
    assert "const BATCH=1;" in captured["js"]


def test_cdp_fetch_js_checks_rate_limit_status(monkeypatch):
    captured = {}

    def _fake_eval(js, timeout=60, retries=3):
        captured["js"] = js
        return json.dumps({"code": 0, "data": {}})

    monkeypatch.setattr(fs, "DIRECT_MODE", False)
    monkeypatch.setattr(fs, "cdp_eval", _fake_eval)
    fs.api_get("/api/v1/client/reviews/latest-date")
    assert "__fph_rate_limit" in captured["js"]
    assert "r.status===429" in captured["js"] or "r.status == 429" in captured["js"]


def test_direct_batch_propagates_rate_limit(monkeypatch):
    monkeypatch.setenv("FUPANHUI_MIN_INTERVAL", "0")
    calls = []

    def one(ts):
        calls.append(ts)
        if ts == "b":
            raise fs.FupanhuiRateLimitError("超限")
        return ts, {}

    with pytest.raises(fs.FupanhuiRateLimitError):
        fs._direct_batch(["a", "b", "c"], one, 1)
    assert "c" not in calls
