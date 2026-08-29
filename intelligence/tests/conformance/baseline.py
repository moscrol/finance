"""棘轮 baseline：存量后端当前红的登记在案，只许缩不许涨。

规则（工单第 3 条目标）：

- 红且在 baseline → xfail（strict marker：失败计 xfail，不阻塞合并）；
- 红且不在 baseline → 正常 fail（新增回归必须当场处理，不许静默入账）；
- 绿但在 baseline → XPASS 报错（strict=True 逼人删行清账）。

每行必须带原因与日期；不允许「不明原因 xfail」。新增后端不得进本表
（新后端必须全绿，见 README「怎么加新后端」）。
"""

from __future__ import annotations

import pytest

# key: "INV-N:backend_name" → 原因（含代码出处与登记日期）
BASELINE: dict[str, str] = {
    "INV-5:codex_headless": (
        "修复静默跳过：continuous_turn_adapter._resume_for_gap 对无 resume 的"
        " session 返回 None，无任何收据（L1181-1184）；codex 档判官照跑、修复"
        "缺席不可观测。2026-08-29 登记（阳性对照，证明套件能抓静默缺席）。"
    ),
}


def ratchet(request: pytest.FixtureRequest, invariant: str, backend_name: str) -> None:
    """在测试体开头调用：登记在案的红转 strict xfail。

    strict=True 的含义：断言真失败 → 记 xfail（棘轮容忍存量）；断言通过
    → XPASS 报错（说明缺口已修复，必须从 BASELINE 删行清账）。
    """

    key = f"{invariant}:{backend_name}"
    reason = BASELINE.get(key)
    if reason:
        request.applymarker(
            pytest.mark.xfail(reason=f"[baseline] {reason}", strict=True)
        )


__all__ = ["BASELINE", "ratchet"]
