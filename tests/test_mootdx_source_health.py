"""mootdx 源健康探针的回归测试。

钉住 2026-09-22 复盘的核心教训：**「连得上」不等于「行情可用」**。
通达信免费主站在 2026-09-07 后对行情命令只回 2 字节 body，元数据命令却完全正常；
旧代码把这种协议级故障吞成 "empty"，导致断供两周无人发现。

全部用假客户端，不触网、不连库。
"""
from __future__ import annotations

import pandas as pd
import pytest

from market_feature_store.mootdx_source import (
    PROBE_CODE,
    VERDICT_EMPTY_PAYLOAD,
    VERDICT_METADATA_ONLY,
    VERDICT_NO_ROUTE,
    VERDICT_OK,
    MootdxSourceUnavailable,
    open_checked_client,
    probe_source_health,
)

#: 生产实测样本：15/15 台可连主站对 GetSecurityBarsCmd 返回的完整 body。
#: 前 2 字节 little-endian = 0x0320 = 800，即「声称 800 根 K 线」却没有任何 K 线体。
REAL_STUB_BODY = bytes.fromhex("2003")


class _FakeClient:
    """鸭子类型的 mootdx StdQuotes 替身。"""

    server = ("203.0.113.1", 7709)

    def __init__(self, *, count=24296, count_exc=None, bars=None, bars_exc=None):
        self._count = count
        self._count_exc = count_exc
        self._bars = bars
        self._bars_exc = bars_exc
        self.bars_calls: list[dict] = []

    def stock_count(self, market=0):
        if self._count_exc is not None:
            raise self._count_exc
        return self._count

    def bars(self, symbol=None, frequency=None, offset=None, **kwargs):
        self.bars_calls.append({"symbol": symbol, "frequency": frequency, "offset": offset})
        if self._bars_exc is not None:
            raise self._bars_exc
        return self._bars


def _ok_frame(rows=8):
    return pd.DataFrame({"open": [1.0] * rows, "close": [1.0] * rows})


def test_healthy_source_reports_ok():
    client = _FakeClient(bars=_ok_frame())
    health = probe_source_health(client)

    assert health.ok is True
    assert health.verdict == VERDICT_OK
    assert health.security_count == 24296
    assert health.probe_rows == 8
    # 探针必须真的问了 K 线，而不是只看连接状态
    assert client.bars_calls == [{"symbol": PROBE_CODE, "frequency": 9, "offset": 8}]


def test_metadata_failure_is_no_route():
    client = _FakeClient(count_exc=ConnectionResetError("connection reset"))
    health = probe_source_health(client)

    assert health.ok is False
    assert health.verdict == VERDICT_NO_ROUTE
    assert "ConnectionResetError" in health.detail


def test_metadata_ok_but_bars_broken_is_metadata_only():
    """本次事故的精确形态：证券数量查得到，K 线命令抛解析异常。"""
    client = _FakeClient(bars_exc=Exception("unpack requires a buffer of 4 bytes"))
    health = probe_source_health(client)

    assert health.ok is False
    assert health.verdict == VERDICT_METADATA_ONLY
    # 元数据成功这件事必须留在证据里，否则会被误判成网络问题而白折腾
    assert health.security_count == 24296
    assert "unpack requires a buffer" in health.detail
    # 处置建议要指向「换源」而不是「换服务器」
    assert "供应商侧停供" in health.message()


def test_empty_bars_for_liquid_probe_is_empty_payload():
    client = _FakeClient(bars=pd.DataFrame())
    health = probe_source_health(client)

    assert health.ok is False
    assert health.verdict == VERDICT_EMPTY_PAYLOAD
    assert health.security_count == 24296


def test_none_bars_is_empty_payload_not_crash():
    """raise_exception=False 的客户端会返回 None；探针不能因此炸掉。"""
    health = probe_source_health(_FakeClient(bars=None))
    assert health.verdict == VERDICT_EMPTY_PAYLOAD


def test_raise_if_unhealthy_carries_structured_diagnosis():
    health = probe_source_health(_FakeClient(bars=pd.DataFrame()))
    with pytest.raises(MootdxSourceUnavailable) as excinfo:
        health.raise_if_unhealthy()

    assert excinfo.value.health.verdict == VERDICT_EMPTY_PAYLOAD
    payload = excinfo.value.health.as_dict()
    assert payload["ok"] is False
    assert payload["server"] == ["203.0.113.1", 7709]


def test_healthy_probe_raise_if_unhealthy_is_noop():
    health = probe_source_health(_FakeClient(bars=_ok_frame()))
    assert health.raise_if_unhealthy() is health


def test_open_checked_client_forces_raise_exception():
    """调用方传 raise_exception=False 会让护栏失效——必须被强制覆盖。"""
    seen: dict = {}

    def factory(**kwargs):
        seen.update(kwargs)
        return _FakeClient(bars=_ok_frame())

    client, health = open_checked_client(factory=factory, raise_exception=False)

    assert seen["raise_exception"] is True
    assert health.ok is True
    assert client is not None


def test_open_checked_client_fails_closed_on_broken_source():
    def factory(**kwargs):
        return _FakeClient(bars_exc=Exception("unpack requires a buffer of 4 bytes"))

    with pytest.raises(MootdxSourceUnavailable) as excinfo:
        open_checked_client(factory=factory)
    assert excinfo.value.health.verdict == VERDICT_METADATA_ONLY


def test_open_checked_client_connect_failure_is_no_route():
    def factory(**kwargs):
        raise OSError("timed out")

    with pytest.raises(MootdxSourceUnavailable) as excinfo:
        open_checked_client(factory=factory)
    assert excinfo.value.health.verdict == VERDICT_NO_ROUTE


def test_real_tdxpy_parser_chokes_on_production_stub_body():
    """上游行为钉子：真实 2 字节 body 会让 tdxpy 抛异常，而非返回空列表。

    这解释了为什么护栏必须用 raise_exception=True——否则这个异常会被吞成 None。
    """
    mod = pytest.importorskip("tdxpy.parser.std.get_security_bars")

    cmd = mod.GetSecurityBarsCmd(client=None)
    cmd.category = 9  # 日线

    # 服务器自称 800 根
    import struct

    (ret_count,) = struct.unpack("<H", REAL_STUB_BODY[:2])
    assert ret_count == 800

    with pytest.raises(Exception) as excinfo:
        cmd.parseResponse(REAL_STUB_BODY)
    assert "buffer" in str(excinfo.value)


def test_failure_histogram_separates_outage_from_delisted():
    from market_feature_store.sync.sync_mootdx_stock_daily import _failure_histogram

    hist = _failure_histogram([
        ("000001.SZ", "empty"),
        ("000002.SZ", "empty"),
        ("000003.SZ", "timeout:30s"),
        ("000004.SZ", "bars:TdxFunctionCallError"),
    ])
    assert hist == {"empty": 2, "timeout": 1, "bars": 1}
