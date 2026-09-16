"""棘轮 baseline（工具注册表缝）。规则同运行时套件：

红且在表 → strict xfail；红且不在 → fail；绿但在表 → XPASS 报错逼清账。
每行带原因与日期；只许缩不许涨。首轮建表为空——注册表层契约由
ResearchToolRegistry 单点强制，没有存量红。
"""

from __future__ import annotations

import pytest

# key: "T-N:tool_name" → 原因（含代码出处与登记日期）
BASELINE: dict[str, str] = {}


def ratchet(request: pytest.FixtureRequest, invariant: str, tool_name: str) -> None:
    key = f"{invariant}:{tool_name}"
    reason = BASELINE.get(key)
    if reason:
        request.applymarker(
            pytest.mark.xfail(reason=f"[baseline] {reason}", strict=True)
        )


__all__ = ["BASELINE", "ratchet"]
