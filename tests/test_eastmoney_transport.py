"""东财快照取数的**传输层**：断连必须被接住，fake-IP 劫持必须绕得过。

2026-09-22 夜跑（以及 09-21 同形）的事故链：`sync-stock-daily-snapshot` 失败 →
兜底无源 → 其后 11 个本地计算步骤全红 → same-day-gate rc=2 → finalize 守卫中止、
staging 不晋升 → 主库停在 09-18、readiness 一直 503。**一次取数失败拖垮整晚。**

实测两个独立缺陷（`~/.finance-runtime/reviews/market-source-probe-20260922T1840/`）：

1. **`RemoteDisconnected` 从重试里漏出去**。`_get_json` 文档写着「6 次退避 + 双 host
   兜底」，但捕获子句是 `(URLError, TimeoutError, ValueError)`，而
   `http.client.RemoteDisconnected` **不是** `URLError`——urllib 只把「发请求阶段」的
   OSError 包装成 URLError，连接是在 `getresponse()` 阶段断的，异常原样抛出。
   证据：6/6 个探针样本 `caught_by_pipeline_except_clause: false`；日志里也确实
   没有重试耗尽才会抛的那句 `东财快照请求失败`。**翻页途中一次断连就整段崩**，
   重试和备用 host 一次都没启用过。

2. **本机代理 fake-IP 劫持**。系统 DNS 把 `push2delay/push2/push2his` 全解析到
   `198.18.0.x`（代理伪地址段），表现为 TCP 建连成功、随即 `RemoteDisconnected`、
   耗时 ~90ms（不是超时，也不是 429）。同一时刻用公共 DNS 取真实 IP 直连、SNI 仍填
   域名，两个 host 都 200 且 `f297=20260922`——**源是好的，坏在本机链路**。
   `sync_eastmoney_fund_flow` 2026-09-11 已为 push2his 踩过同一个坑并写下
   「别再误判成限流」，但快照模块没用上那套绕法。

所以这里钉三件事：断连被当作瞬时错误重试；被劫持的 host 走直连真实 IP + SNI；
链路正常时**不改变**既有行为（仍走 urllib，不平白多打上游）。
"""

from __future__ import annotations

import http.client
import json
import socket
import urllib.error
import urllib.request

import pytest

from market_feature_store.sync import sync_eastmoney_stock_snapshot as em

REAL_IP = "203.0.113.7"  # TEST-NET-3，保证不是真实可连地址
FAKE_IP = "198.18.0.177"  # 代理伪地址段，实测本机解析结果
PAYLOAD = {"data": {"total": 1, "diff": [{"f12": "600000", "f297": 20260922}]}}


@pytest.fixture(autouse=True)
def _reset_transport_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """清掉进程级缓存并掐掉退避睡眠——否则用例之间会互相串味、还平白慢 20 秒。"""
    # 走公共的 reset_transport_state() 而不是逐个摸私有变量: 新增一个进程级状态
    # 就得记得改那里, 漏了就是用例间串味 (熔断补丁开发时已踩过一次)。
    em.reset_transport_state()
    monkeypatch.setattr(em.time, "sleep", lambda _s: None)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _urlopen_script(*outcomes):
    """按序返回/抛出预设结果，并记录每次请求的 URL。"""
    calls: list[str] = []
    queue = list(outcomes)

    def urlopen(req, timeout=None):
        calls.append(req.full_url if hasattr(req, "full_url") else str(req))
        outcome = queue.pop(0) if queue else outcomes[-1]
        if isinstance(outcome, Exception):
            raise outcome
        return _FakeResponse(outcome)

    urlopen.calls = calls
    return urlopen


class _FakeConnection:
    """替身 HTTPSConnection：记录请求并回放固定响应，不碰网络。"""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.requests: list[tuple[str, dict]] = []
        self.closed = False

    def request(self, method: str, path: str, headers: dict) -> None:
        self.requests.append((path, headers))

    def getresponse(self) -> _FakeResponse:
        return _FakeResponse(self.payload)

    def close(self) -> None:
        self.closed = True


class TestDisconnectIsTreatedAsTransient:
    def test_remote_disconnected_is_retried_instead_of_escaping(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """核心回归：断连必须进重试，而不是穿透整个调用栈。

        旧代码在这里直接把 RemoteDisconnected 抛给 fetch_snapshot，翻页中断、
        整晚的复盘随之停摆。
        """
        urlopen = _urlopen_script(
            http.client.RemoteDisconnected("closed"),
            http.client.RemoteDisconnected("closed"),
            PAYLOAD,
        )
        monkeypatch.setattr(em, "_system_ip", lambda _h: REAL_IP)
        monkeypatch.setattr(em, "_direct_ip", lambda _h: None)
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)

        assert em._get_json(f"{em.EM_URL}?pn=1", timeout=5) == PAYLOAD
        assert len(urlopen.calls) == 3

    def test_second_host_is_actually_tried_after_disconnects(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """双 host 兜底必须真的发生——旧代码对这类错误从未走到备用 host。"""
        monkeypatch.setattr(em, "_system_ip", lambda _h: REAL_IP)
        monkeypatch.setattr(em, "_direct_ip", lambda _h: None)

        def urlopen(req, timeout=None):
            if em.EM_URL_FALLBACK in req.full_url:
                return _FakeResponse(PAYLOAD)
            raise http.client.RemoteDisconnected("closed")

        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)

        assert em._get_json(f"{em.EM_URL}?pn=1", timeout=5) == PAYLOAD

    def test_exhausted_retries_raise_runtime_error_with_cause(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """全打不通仍要收敛成带因由的 RuntimeError，别把底层异常直接丢给调用方。"""
        monkeypatch.setattr(em, "_system_ip", lambda _h: REAL_IP)
        monkeypatch.setattr(em, "_direct_ip", lambda _h: None)
        monkeypatch.setattr(
            em.urllib.request,
            "urlopen",
            _urlopen_script(http.client.RemoteDisconnected("closed")),
        )

        with pytest.raises(RuntimeError, match="东财快照请求失败") as excinfo:
            em._get_json(f"{em.EM_URL}?pn=1", timeout=5, retries=2)
        assert isinstance(excinfo.value.__cause__, http.client.RemoteDisconnected)

    @pytest.mark.parametrize(
        "error",
        [
            http.client.RemoteDisconnected("closed"),
            urllib.error.URLError("unreachable"),
            TimeoutError("slow"),
            ConnectionResetError("reset"),
            http.client.BadStatusLine("garbage"),
            ValueError("not json"),
        ],
    )
    def test_transient_error_shapes_all_retry(
        self, monkeypatch: pytest.MonkeyPatch, error: Exception
    ) -> None:
        """瞬时错误家族逐个钉：只补 RemoteDisconnected 挡不住下一个近亲。"""
        urlopen = _urlopen_script(error, PAYLOAD)
        monkeypatch.setattr(em, "_system_ip", lambda _h: REAL_IP)
        monkeypatch.setattr(em, "_direct_ip", lambda _h: None)
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)

        assert em._get_json(f"{em.EM_URL}?pn=1", timeout=5) == PAYLOAD
        assert len(urlopen.calls) == 2


class TestFakeIpHijackIsBypassed:
    def test_hijacked_host_connects_to_real_ip_with_domain_sni(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """系统解析落在代理伪地址段时直连真实 IP，SNI/Host 仍填域名。"""
        seen: dict[str, object] = {}
        conn = _FakeConnection(PAYLOAD)

        def tls_connection(ip: str, host: str, timeout: float):
            seen.update(ip=ip, host=host, timeout=timeout)
            return conn

        monkeypatch.setattr(em, "_system_ip", lambda _h: FAKE_IP)
        monkeypatch.setattr(em, "_direct_ip", lambda _h: REAL_IP)
        monkeypatch.setattr(em, "_tls_connection", tls_connection)
        monkeypatch.setattr(
            em.urllib.request,
            "urlopen",
            lambda *a, **k: pytest.fail("被劫持的 host 不该再走系统解析"),
        )

        assert em._get_json(f"{em.EM_URL}?pn=1&pz=1", timeout=5) == PAYLOAD
        assert seen == {"ip": REAL_IP, "host": "push2delay.eastmoney.com", "timeout": 5}
        path, headers = conn.requests[0]
        assert path == "/api/qt/clist/get?pn=1&pz=1"
        assert headers["Host"] == "push2delay.eastmoney.com"
        assert headers["User-Agent"] == em.EM_HEADERS["User-Agent"]
        assert conn.closed is True

    def test_healthy_host_keeps_using_system_resolution(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """链路正常时行为不变：仍走 urllib，不平白多打上游、也不多做一次 DNS。"""
        urlopen = _urlopen_script(PAYLOAD)
        monkeypatch.setattr(em, "_system_ip", lambda _h: REAL_IP)
        monkeypatch.setattr(
            em, "_direct_ip", lambda _h: pytest.fail("正常链路不该去查公共 DNS")
        )
        monkeypatch.setattr(
            em, "_tls_connection", lambda *a, **k: pytest.fail("正常链路不该直连 IP")
        )
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)

        assert em._get_json(f"{em.EM_URL}?pn=1", timeout=5) == PAYLOAD
        assert len(urlopen.calls) == 1

    def test_broken_urllib_demotes_to_direct_once_not_every_page(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """劫持没被 DNS 认出来时，靠失败学一次就够——不是每页都白打一发。"""
        conn = _FakeConnection(PAYLOAD)
        urlopen = _urlopen_script(http.client.RemoteDisconnected("closed"))
        monkeypatch.setattr(em, "_system_ip", lambda _h: REAL_IP)
        monkeypatch.setattr(em, "_direct_ip", lambda _h: REAL_IP)
        monkeypatch.setattr(em, "_tls_connection", lambda *a, **k: conn)
        monkeypatch.setattr(em.urllib.request, "urlopen", urlopen)

        first = em._get_json(f"{em.EM_URL}?pn=1", timeout=5)
        second = em._get_json(f"{em.EM_URL}?pn=2", timeout=5)

        assert first == second == PAYLOAD
        assert len(urlopen.calls) == 1, "第二页不该再去试已知坏掉的传输"


class TestPublicDnsResolution:
    def test_proxy_fake_addresses_are_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """公共 DNS 也可能被劫持，198.18/15 必须当作「没解析到」。"""
        monkeypatch.setattr(
            em.subprocess,
            "run",
            lambda *a, **k: type("R", (), {"stdout": f"{FAKE_IP}\n{REAL_IP}\n"})(),
        )
        assert em._direct_ip("push2delay.eastmoney.com") == REAL_IP

    def test_all_fake_means_no_real_ip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            em.subprocess,
            "run",
            lambda *a, **k: type("R", (), {"stdout": f"{FAKE_IP}\n198.18.0.9\n"})(),
        )
        assert em._direct_ip("push2.eastmoney.com") is None

    def test_cname_lines_are_not_mistaken_for_addresses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """dig 会先吐 CNAME 行（实测 push2delay.aligtm.eastmoney.com.），别当成 IP。"""
        monkeypatch.setattr(
            em.subprocess,
            "run",
            lambda *a, **k: type(
                "R", (), {"stdout": f"push2delay.aligtm.eastmoney.com.\n{REAL_IP}\n"}
            )(),
        )
        assert em._direct_ip("push2delay.eastmoney.com") == REAL_IP

    def test_dig_failure_falls_back_to_system_resolution(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """没有 dig / 查询超时都不是致命的——返回 None，调用方退回系统解析。"""

        def boom(*a, **k):
            raise FileNotFoundError("dig not installed")

        monkeypatch.setattr(em.subprocess, "run", boom)
        assert em._direct_ip("push2.eastmoney.com") is None

    def test_result_is_cached_per_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """每页都 fork 一次 dig 会把 60 页的快照拖慢，解析结果按 host 缓存。"""
        calls: list[tuple] = []

        def run(cmd, **kwargs):
            calls.append(tuple(cmd))
            return type("R", (), {"stdout": f"{REAL_IP}\n"})()

        monkeypatch.setattr(em.subprocess, "run", run)
        assert em._direct_ip("push2.eastmoney.com") == REAL_IP
        assert em._direct_ip("push2.eastmoney.com") == REAL_IP
        assert len(calls) == 1


class TestSystemResolution:
    def test_hijack_detection_reads_system_resolver(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """判据取自系统解析本身——这正是 urllib 会用的那条路径。"""
        monkeypatch.setattr(em.socket, "gethostbyname", lambda _h: FAKE_IP)
        assert em._system_ip("push2.eastmoney.com") == FAKE_IP
        assert em._looks_hijacked("push2.eastmoney.com") is True

    def test_resolution_failure_is_not_read_as_hijack(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """解析不出来是另一种故障，不能顺手当成劫持。"""

        def boom(_host):
            raise socket.gaierror("no such host")

        monkeypatch.setattr(em.socket, "gethostbyname", boom)
        assert em._system_ip("push2.eastmoney.com") is None
        assert em._looks_hijacked("push2.eastmoney.com") is False
