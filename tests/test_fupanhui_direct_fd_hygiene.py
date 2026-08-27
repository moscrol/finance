"""fd 卫生：直连批量失败时，HTTPError 携带的 socket 必须确定性关闭。

生产事故（2026-08-26 夜跑，台账 R-20260826-04）：fupanhui 自 08-24 起对
匿名直连返回 401，`get_sector_klines_batch` 直连臂对 403 个板块逐个拿到
``urllib.error.HTTPError``。该异常对象本身是 file-like、持有响应 socket；
`_direct_batch` 把异常收进 ``failures`` 列表，异常→traceback→frame→列表
构成引用环，fd 只能等周期 GC——403 个悬挂 socket 顶爆 launchd 256 软上限，
CDP 兜底抓数成功后 ``duckdb.connect`` 反而以
``IO Error: ... Too many open files`` 死掉（sector-daily 两次尝试同形）。

与同日 WorkbenchDB sqlite 泄漏（R-20260826-03）同族：fd 生命周期不得交给
GC 时机。修法：`_direct_api_get` 在 HTTPError 逃逸前先 ``e.close()`` 再原样
重抛——语义不变（401 仍由 api_get 回退 CDP、批量调用方仍按缺失重试），
只是 socket 不再挂在异常对象上等回收。

测试口径：gc.disable 下模拟 N 次 401（HTTPError 挂真实 fd），批量调用后
fd 不得随 N 增长。
"""
from __future__ import annotations

import gc
import os
import urllib.error
import urllib.request

import pytest

from market_feature_store.sources import fupanhui_source as fs


def _open_fds() -> int:
    return len(os.listdir("/dev/fd"))


def _raise_401(req, timeout=0):
    fp = open("/dev/null", "rb")
    url = getattr(req, "full_url", str(req))
    raise urllib.error.HTTPError(url, 401, "Unauthorized", None, fp)


def test_mass_401_does_not_pile_open_fds(monkeypatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _raise_401)

    codes = [f"c{i}" for i in range(50)]
    gc.disable()
    try:
        base = _open_fds()
        with pytest.raises(fs.FupanhuiError):
            fs._direct_batch(
                codes,
                lambda ts: fs._direct_api_get(f"/api/v1/client/reviews/sector-cycle/{ts}/kline"),
                12,
            )
        grown = _open_fds() - base
    finally:
        gc.enable()
        gc.collect()
    assert grown <= 3, (
        f"50 次直连 401 后 fd 增长 {grown}（>3）：HTTPError 持有的 socket 未确定性"
        "关闭，403 板块规模下会顶爆 launchd fd 上限，随后 duckdb.connect 以"
        "「Too many open files」失败（2026-08-26 夜跑 sector-daily 事故形状）"
    )


def test_http_error_still_propagates_for_cdp_fallback(monkeypatch) -> None:
    """关 socket 不得改变异常语义：401 仍以 HTTPError 逃逸，api_get 靠它回退 CDP。"""

    monkeypatch.setattr(urllib.request, "urlopen", _raise_401)
    with pytest.raises(urllib.error.HTTPError):
        fs._direct_api_get("/api/v1/client/reviews/sector-cycle/x/kline")
