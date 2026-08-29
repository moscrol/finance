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
BASELINE: dict[str, str] = {
    "DB-6:MARKET_DAILY": (
        "注册块绕开 enabled_providers 门控：既不经 DataBlockProvider 构造面，"
        "全仓也无 provider_enabled(options, \"MARKET_DAILY\") 调用——块文本在"
        " ask.py ~L1929（mainline_current 档 agent 取数路径）直接生成，注册表"
        "「调用方只通过 enabled_providers 限制」的公开承诺对它落空，裁剪/检索"
        "计划均无法关掉它。2026-08-29 登记（套件首跑抓到的阳性对照，证明装配"
        "对账有牙）。修复属生产改动，另立单，不在本套件顺手修。"
    ),
}


def ratchet(request: pytest.FixtureRequest, invariant: str, block_name: str) -> None:
    """在测试体开头调用：登记在案的红转 strict xfail。"""

    key = f"{invariant}:{block_name}"
    reason = BASELINE.get(key)
    if reason:
        request.applymarker(
            pytest.mark.xfail(reason=f"[baseline] {reason}", strict=True)
        )


__all__ = ["BASELINE", "ratchet"]
