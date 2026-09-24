"""东财取数的**错误形状分类**：不是所有失败都该用同一种方式重试。

2026-09-22 19:2x 起，东财在**应用层**拒绝服务：TCP 连得上、TLS 握手成功、
证书 `*.eastmoney.com` 验证通过、对端确实是真东财，但它接下连接后对
`/api/qt/clist/get` 一个字节响应体都不给（`curl --resolve` 直打真实 IP 同样是
`curl: (52) Empty reply from server`，**与 Python 代码无关**）。

根因修正（09-22 21:55，见 `fix-eastmoney-snapshot-direct-ip-0922` 交接）：**不是按出口 IP
封禁**——同一主机、同一 IP、同一条 TLS 上 `/` 返 404、`ulist.np/get` 返 200 有数据，
只有 `clist/get` 被掉；且 6 连发 clist 后 `ulist.np` 也转空回应，冷却 45–75s 不恢复。
被针对的是端点，而每多打一发都在扩大伤害面。熔断的判据与语义不受此修正影响。

证据链（`~/.finance-runtime/reviews/eastmoney-hotfix-20260922T1917/` 与本轮 21:11 复测）：

- 18:59 同样的单发还能拿到 5918 只；19:2x 起全废，中间隔着 18:30 与 19:21 两轮
  「60 页 × 重试」的密集翻页。20:00 冷却 40 分钟复测仍被拒，21:11 再测仍被拒。
- pz=1 / pz=100、百分号编码、最小字段集、push2 备用域、三家公共 DNS 给的不同真实 IP
  ——全部同形。**换 IP、换域名、缩小请求都救不了。**

所以这类失败与「瞬时抖动」有本质区别：

| | 瞬时抖动 | 上游拒绝服务（连上即空回应） |
|---|---|---|
| 重试有用吗 | 有 | **没有** |
| 继续重试的代价 | 几秒 | **拖垮同主机其他端点**（实测 clist 连发后 ulist.np 也转空回应） |

而 `b1d797593` 把两者归为同一类 `TRANSIENT_FETCH_ERRORS` 无差别重试。该补丁**提高了
重试压力**（snapshot 步骤 41.7s → 90.9s 就是证据），在被拒场景下这是反作用：
明天 18:30 定时会自动用更长的阶梯再打一轮。原补丁作者已在交接里写明这条设计反馈
（「只是建议，未实现、未改代码」），这里实现它。

一并收两个同源问题（都属「错误形状没分清」）：

- JSON 解析失败（上游回挡板页）属内容层，却会去改传输层路由 `_transport_cache`。
- 公共 DNS 查询失败时 `None` 被写进 `_ip_cache` 且用 `in` 判命中 → 一次失败就永久
  退回被劫持的系统解析，失败形态与修复前同形（negative caching without TTL）。
"""

from __future__ import annotations

import http.client
import json
from types import SimpleNamespace

import pytest

from market_feature_store.sync import sync_eastmoney_stock_snapshot as em

REAL_IP = "203.0.113.7"  # TEST-NET-3
PAYLOAD = {"data": {"total": 1, "diff": [{"f12": "600000", "f297": 20260922}]}}
#: autouse fixture 会把 _direct_ip 换成替身，DNS 那组用例要测的却正是它本身。
_REAL_DIRECT_IP = em._direct_ip


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    em.reset_transport_state()
    monkeypatch.setattr(em.time, "sleep", lambda _s: None)
    # 传输选路不是本文件的被测对象：固定走 urllib，避免劫持判据干扰计数
    monkeypatch.setattr(em, "_system_ip", lambda _h: REAL_IP)
    monkeypatch.setattr(em, "_direct_ip", lambda _h: None)


def _counting_urlopen(*outcomes):
    calls: list[str] = []
    queue = list(outcomes)

    def urlopen(req, timeout=None):
        calls.append(req.full_url)
        outcome = queue.pop(0) if queue else outcomes[-1]
        if isinstance(outcome, Exception):
            raise outcome
        return _Resp(outcome)

    urlopen.calls = calls
    return urlopen


class _Resp:
    def __init__(self, payload):
        import json

        self._body = json.dumps(payload).encode() if isinstance(payload, dict) else payload

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _disc() -> http.client.RemoteDisconnected:
    return http.client.RemoteDisconnected("Remote end closed connection without response")


class TestCircuitBreakerOnUpstreamRefusal:
    def test_consecutive_empty_replies_stop_the_round_instead_of_grinding_through_retries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """被拒时必须立刻停手。

        旧行为：6 次退避 × 2 host = 12 发，每发都在给封禁计时器续命，而且 60 页
        里的每一页都会重来一次。
        """
        urlopen = _counting_urlopen(_disc())
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)

        with pytest.raises(em.UpstreamRefusing):
            em._get_json(f"{em.EM_URL}?pn=1", timeout=5)

        # 两个 host 各自独立判定（见 test_breaker_does_not_burn_the_fallback_host），
        # 所以上限是 2×阈值 = 6 发，而不是旧行为的 2×retries = 12 发。
        assert len(urlopen.calls) == 2 * em.EMPTY_REPLY_STREAK_LIMIT, (
            f"被拒后每 host 只该发 {em.EMPTY_REPLY_STREAK_LIMIT} 发，实际共 {len(urlopen.calls)} 发"
        )

    def test_isolated_disconnects_still_retry_and_succeed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """熔断不能把既有的抖动容错吃掉——这是 b1d797593 修好的东西，不许退回去。"""
        urlopen = _counting_urlopen(_disc(), _disc(), PAYLOAD)
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)

        assert em._get_json(f"{em.EM_URL}?pn=1", timeout=5) == PAYLOAD
        assert len(urlopen.calls) == 3

    @pytest.mark.parametrize("other_error", [
        OSError("network unreachable"),
        http.client.HTTPException("bad response"),
        b"<html>blocked</html>",
    ], ids=["network", "http", "non-json"])
    def test_non_empty_reply_error_breaks_the_empty_reply_streak(
        self, monkeypatch: pytest.MonkeyPatch, other_error
    ) -> None:
        """普通网络错误或非 JSON 内容打断空回应序列。"""
        single_host = f"{em.EM_URL_FALLBACK}?pn=1"
        urlopen = _counting_urlopen(_disc(), other_error, _disc(), _disc(), PAYLOAD)
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)

        assert em._get_json(single_host, timeout=5) == PAYLOAD
        assert len(urlopen.calls) == 5
        assert em._refusing_hosts == set()

    def test_success_resets_the_streak_so_it_counts_consecutive_not_cumulative(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """判据是「连续」。整晚翻 60 页，偶发抖动累计超阈值是正常的，不该误熔断。

        **刻意打单 host**（`EM_URL_FALLBACK` 不含 `EM_URL`，不会追加兜底域）：
        带兜底域时，「计数没清零 → 第一个 host 熔断 → 第二个 host 接住」也会
        返回 PAYLOAD 且总请求数同样是 6，断言分辨不出来——变异测试 M5 正是
        这样从本用例手里漏过去的。
        """
        single_host = f"{em.EM_URL_FALLBACK}?pn="
        urlopen = _counting_urlopen(_disc(), _disc(), PAYLOAD, _disc(), _disc(), PAYLOAD)
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)

        assert em._get_json(f"{single_host}1", timeout=5) == PAYLOAD
        assert em._get_json(f"{single_host}2", timeout=5) == PAYLOAD
        assert len(urlopen.calls) == 6
        assert em._refusing_hosts == set(), "连续计数没清零，把正常抖动误判成了上游拒绝"

    def test_request_counts_group_by_host_and_endpoint_not_page_query(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        urlopen = _counting_urlopen(_disc(), PAYLOAD)
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)

        assert em._get_json(f"{em.EM_URL}?pn=1&pz=100", timeout=5) == PAYLOAD
        first_page = em.transport_request_counts()
        assert first_page == {"push2delay.eastmoney.com/api/qt/clist/get": 2}
        assert em._get_json(f"{em.EM_URL}?pn=2&pz=100", timeout=5) == PAYLOAD
        assert em._get_json("https://push2delay.eastmoney.com/api/qt/ulist.np/get?secids=1.600000", 5) == PAYLOAD
        assert len(urlopen.calls) == 4
        assert em.transport_request_counts() == {
            "push2delay.eastmoney.com/api/qt/clist/get": 3,
            "push2delay.eastmoney.com/api/qt/ulist.np/get": 1,
        }
        assert first_page == {"push2delay.eastmoney.com/api/qt/clist/get": 2}

    def test_refusal_is_remembered_so_remaining_pages_fail_fast_without_requests(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """判定被拒之后，后续页一发都不许再打。否则 60 页 = 60×3 发。"""
        urlopen = _counting_urlopen(_disc())
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)

        with pytest.raises(em.UpstreamRefusing):
            em._get_json(f"{em.EM_URL}?pn=1", timeout=5)
        first_round = len(urlopen.calls)
        counts = em.transport_request_counts()
        assert counts == {
            "push2.eastmoney.com/api/qt/clist/get": em.EMPTY_REPLY_STREAK_LIMIT,
            "push2delay.eastmoney.com/api/qt/clist/get": em.EMPTY_REPLY_STREAK_LIMIT,
        }

        with pytest.raises(em.UpstreamRefusing):
            em._get_json(f"{em.EM_URL}?pn=2", timeout=5)

        assert len(urlopen.calls) == first_round, "已判定被拒的 host 不该再发请求"
        assert em.transport_request_counts() == counts
        with pytest.raises(em.UpstreamRefusing):
            em.fetch_snapshot()
        assert em.transport_request_counts() == {}, "新一轮清计数但不能清熔断"
        assert len(urlopen.calls) == first_round

    def test_refusal_error_is_distinguishable_but_still_a_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """调用方要能分辨「上游拒绝」与「重试耗尽」，同时不破坏既有 except RuntimeError。"""
        assert issubclass(em.UpstreamRefusing, RuntimeError)

        urlopen = _counting_urlopen(_disc())
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)
        with pytest.raises(em.UpstreamRefusing) as excinfo:
            em._get_json(f"{em.EM_URL}?pn=1", timeout=5)

        message = str(excinfo.value)
        assert "拒绝" in message and "空回应" in message, "错误信息要说清是哪一类失败"
        assert "出口 IP" not in message, "21:55 已证实不是按 IP 封禁, 别把错误归因写进日志"
        assert isinstance(excinfo.value.__cause__, http.client.RemoteDisconnected)

    def test_breaker_does_not_burn_the_fallback_host_on_the_first_host_verdict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """一个 host 被拒不代表另一个也被拒——备用域仍要给一次机会。"""

        def urlopen(req, timeout=None):
            if em.EM_URL_FALLBACK in req.full_url:
                return _Resp(PAYLOAD)
            raise _disc()

        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)
        assert em._get_json(f"{em.EM_URL}?pn=1", timeout=5) == PAYLOAD


class TestErrorShapesDoNotLeakAcrossLayers:
    def test_json_decode_failure_does_not_reroute_the_transport(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """挡板页是内容层问题，链路可能完全正常，不该据此改传输选路。"""
        urlopen = _counting_urlopen(b"<html>blocked</html>", PAYLOAD)
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)

        assert em._get_json(f"{em.EM_URL}?pn=1", timeout=5) == PAYLOAD
        assert em._transport_cache == {}, "内容层错误把传输判据污染了"

    def test_json_decode_failure_does_not_trip_the_breaker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """挡板页 ≠ 空回应。它走原有的重试耗尽路径，报普通失败。"""
        urlopen = _counting_urlopen(b"<html>blocked</html>")
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)

        with pytest.raises(RuntimeError) as excinfo:
            em._get_json(f"{em.EM_URL}?pn=1", timeout=5)
        assert not isinstance(excinfo.value, em.UpstreamRefusing)

    def test_transport_failures_still_reroute_as_before(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """保护既有行为：真·传输错误仍要把 host 降级到直连，不能连这个一起改没了。"""
        urlopen = _counting_urlopen(OSError("network unreachable"), PAYLOAD)
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)
        monkeypatch.setattr(em, "_direct_get_json", lambda *a, **k: PAYLOAD)

        assert em._get_json(f"{em.EM_URL}?pn=1", timeout=5) == PAYLOAD
        assert em._transport_cache.get("push2delay.eastmoney.com") == "direct"


class TestSnapshotCliRequestCounts:
    def test_success_logs_counts_from_sync_stats(self, monkeypatch, capsys) -> None:
        from market_feature_store.cli import cmd_sync_stock_daily_snapshot

        counts = {"push2delay.eastmoney.com/api/qt/clist/get": 2}
        stats = {
            "trade_date": "2026-09-22", "snapshot_trade_date": "2026-09-22",
            "source": "eastmoney:snapshot", "fetched": 1, "rows_written": 1,
            "skipped": 0, "day_rows": 1, "table_total": 1, "distinct_stocks": 1,
            "distinct_dates": 1, "date_min": "2026-09-22", "date_max": "2026-09-22",
            "transport_requests": counts, "transport_request_total": 2,
        }
        monkeypatch.setattr(em, "sync_fact_stock_daily_snapshot", lambda **kw: stats)
        args = SimpleNamespace(trade_date="2026-09-22", page_size=100, allow_misdated=False)

        assert cmd_sync_stock_daily_snapshot(args) == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        assert "东财请求计数: " + json.dumps(counts, sort_keys=True) + " | total=2" in captured.out

    def test_refusal_logs_counts_and_preserves_the_exception(self, monkeypatch, capsys) -> None:
        from market_feature_store.cli import cmd_sync_stock_daily_snapshot

        urlopen = _counting_urlopen(_disc())
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)
        monkeypatch.setattr(em, "sync_fact_stock_daily_snapshot", lambda **kw: em.fetch_snapshot())
        args = SimpleNamespace(trade_date="2026-09-22", page_size=100, allow_misdated=False)

        with pytest.raises(em.UpstreamRefusing):
            cmd_sync_stock_daily_snapshot(args)
        counts = json.loads(capsys.readouterr().err.removeprefix("东财请求计数: "))
        assert counts == {
            "push2.eastmoney.com/api/qt/clist/get": em.EMPTY_REPLY_STREAK_LIMIT,
            "push2delay.eastmoney.com/api/qt/clist/get": em.EMPTY_REPLY_STREAK_LIMIT,
        }
        assert len(urlopen.calls) == sum(counts.values())

        with pytest.raises(em.UpstreamRefusing):
            cmd_sync_stock_daily_snapshot(args)
        assert json.loads(capsys.readouterr().err.removeprefix("东财请求计数: ")) == {}
        assert len(urlopen.calls) == sum(counts.values())

    def test_failure_before_fetch_does_not_report_old_counts(self, monkeypatch, capsys) -> None:
        from market_feature_store.cli import cmd_sync_stock_daily_snapshot

        monkeypatch.setattr(em.urllib.request, "urlopen", _counting_urlopen(PAYLOAD))
        em._get_json(em.EM_URL, timeout=5)
        assert em.transport_request_counts()
        error = OSError("database unavailable")

        def fail(**kw):
            raise error

        monkeypatch.setattr(em, "sync_fact_stock_daily_snapshot", fail)
        args = SimpleNamespace(trade_date="2026-09-22", page_size=100, allow_misdated=False)
        with pytest.raises(OSError) as caught:
            cmd_sync_stock_daily_snapshot(args)
        assert caught.value is error
        assert json.loads(capsys.readouterr().err.removeprefix("东财请求计数: ")) == {}


class TestFailedDnsLookupIsNotCachedForever:
    def test_failed_lookup_is_retried_on_the_next_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """否则公共 DNS 一次超时就把整个进程钉死在被劫持的系统解析上。"""
        em._ip_cache.clear()
        attempts: list[str] = []

        def run(cmd, **kwargs):
            attempts.append(cmd[-2])

            class _R:
                stdout = ""

            return _R()

        monkeypatch.setattr(em.subprocess, "run", run)

        assert _REAL_DIRECT_IP("push2delay.eastmoney.com") is None
        first = len(attempts)
        assert _REAL_DIRECT_IP("push2delay.eastmoney.com") is None
        assert len(attempts) > first, "失败结果被永久缓存了，第二次调用一个 DNS 都没查"

    def test_successful_lookup_is_still_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """别把缓存修坏：成功结果仍然只查一次。"""
        em._ip_cache.clear()
        attempts: list[str] = []

        def run(cmd, **kwargs):
            attempts.append(cmd[-2])

            class _R:
                stdout = "61.152.229.217\n"

            return _R()

        monkeypatch.setattr(em.subprocess, "run", run)

        assert _REAL_DIRECT_IP("push2delay.eastmoney.com") == "61.152.229.217"
        after_first = len(attempts)
        assert _REAL_DIRECT_IP("push2delay.eastmoney.com") == "61.152.229.217"
        assert len(attempts) == after_first
