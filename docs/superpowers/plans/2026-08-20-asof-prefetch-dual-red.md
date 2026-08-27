# 问句日预取 + 双红戳记 Implementation Plan

> **For agentic workers:** 本会话按最优路径 inline 执行。Spec：`docs/superpowers/specs/2026-08-20-asof-prefetch-dual-red-design.md`。

**Goal:** Engine A 进场前桌上已有分析师第一刀事实：问句日日历、forecast 双红个数、发酵精确名+双红戳；预取证据能满足必填能力。

**Architecture:** 不开放 SQL/Shell。扩展 `requested_information_cutoff`；纯函数模块 `asof_prefetch.py` 生成观察值与 `AgentEvidence`；forecast/发酵接到 `_market_block` 与 episode 开场 user 消息；判官对未绑定但未剔除的证据工具认账。

**Tech Stack:** Python、DuckDB、pytest、现有 `theme_lifecycle_timeline.is_double_red`。

---

## 文件

- Create: `intelligence/services/asof_prefetch.py`
- Create: `intelligence/tests/test_asof_prefetch_dual_red.py`
- Modify: `intelligence/services/honesty_gates.py`（站立日）
- Modify: `intelligence/tests/test_honesty_gates.py`
- Modify: `intelligence/services/episode_tools.py`（`_market_block` 附加）
- Modify: `intelligence/runtime/agent_episode.py`（开场注入证据+user 消息）
- Modify: `intelligence/services/episode_verifier.py`（第 4 刀）
- Modify: `intelligence/tests/test_episode_verifier.py`

### Task 1–4

见 spec §4。测试锁：发酵问句 cutoff=问句日；区间题仍 runtime；双红计数 2/1/0；锂矿精确名 7/23 双红=是；未绑定的 market_data 证据满足 mandatory；stripped 测试仍红。
