"""棘轮 baseline：规则同参照套件（红入账带原因、绿逼清账、只缩不涨）。"""

from __future__ import annotations

import pytest

# key: "LT-N:transport" → 原因（含代码出处与登记日期）
BASELINE: dict[str, str] = {}


def ratchet(request: pytest.FixtureRequest, invariant: str, transport: str) -> None:
    key = f"{invariant}:{transport}"
    reason = BASELINE.get(key)
    if reason:
        request.applymarker(
            pytest.mark.xfail(reason=f"[baseline] {reason}", strict=True)
        )


__all__ = ["BASELINE", "ratchet"]
