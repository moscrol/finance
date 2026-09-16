"""棘轮 baseline：规则同参照套件（红入账带原因、绿逼清账、只缩不涨）。

首轮为空：attempt/发布契约由 ``sync_market_snapshot`` 编排器单点收口。
"""

from __future__ import annotations

import pytest

# key: "MS-N:provider" → 原因（含代码出处与登记日期）
BASELINE: dict[str, str] = {}


def ratchet(request: pytest.FixtureRequest, invariant: str, provider: str) -> None:
    key = f"{invariant}:{provider}"
    reason = BASELINE.get(key)
    if reason:
        request.applymarker(
            pytest.mark.xfail(reason=f"[baseline] {reason}", strict=True)
        )


__all__ = ["BASELINE", "ratchet"]
