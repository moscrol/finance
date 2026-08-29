"""棘轮 baseline：存量块当前红的登记在案，只许缩不许涨。

规则同参照套件（``conformance_tools.baseline`` / ``conformance.baseline``）：

- 红且在 baseline → strict xfail（失败计 xfail，不阻塞合并）；
- 红且不在 → 正常 fail（新增回归当场处理）；
- 绿但在 baseline → XPASS 报错（strict=True 逼人删行清账）。

首轮为空：注册表/运行器层契约由 ``evidence_registry`` / ``ask_planner``
单点强制（判据见 blocks.py docstring）。装配面的观测性缺口不入本表，
登记在 ``blocks.ASSEMBLY_FINDINGS``（那是缺口不是红）。
"""

from __future__ import annotations

import pytest

# key: "DB-N:block_name" → 原因（含代码出处与登记日期）
#
# 2026-08-29 清账一例（棘轮闭环首次真实运转）：DB-6:MARKET_DAILY——套件首跑
# 抓到的绕门控缺陷（注册块无任何 provider_enabled 调用），R-20260829-02 修复
# 后 strict xfail 转 XPASS 逼删本行；该块现为声明旁路（见 blocks.BYPASS_BLOCKS
# 与 BLOCK_NOTES）。
BASELINE: dict[str, str] = {}


def ratchet(request: pytest.FixtureRequest, invariant: str, block_name: str) -> None:
    """在测试体开头调用：登记在案的红转 strict xfail。"""

    key = f"{invariant}:{block_name}"
    reason = BASELINE.get(key)
    if reason:
        request.applymarker(
            pytest.mark.xfail(reason=f"[baseline] {reason}", strict=True)
        )


__all__ = ["BASELINE", "ratchet"]
