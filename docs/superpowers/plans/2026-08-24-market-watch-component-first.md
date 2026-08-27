# Market Watch Component-First Implementation Plan

> **For agentic workers:** 按 spec `docs/superpowers/specs/2026-08-24-market-watch-component-first-design.md` v2。TDD。树 `/Users/a77/fwp-wt-market-watch-component-first`。不合 main。

**Goal:** `market_watch` 拒收 Engine A；四袋在 owner 分叉前跑完；显式日精确命中。

**Architecture:** `run_market_watch_pack`（services）→ 编排器在 `if owner_output` 之前 `bind_market_watch_pack`。daily-review 仍可 own。查询选 spec §6.1 (ii)。

**Tech Stack:** Python, DuckDB, pytest

---

### Task 1: 拒收
- Modify: `continuous_turn_adapter.py` `DETERMINISTIC_OWNER_TYPES`
- Modify: 现役 parametrize 加上 `market_watch`
- Modify: `glm_agent_runtime.py` 移出 synthesis-heavy

### Task 2: 包 + 精确日
- Create: `intelligence/services/market_watch_pack.py`
- Test: `intelligence/tests/test_market_watch_component_first.py`
- Modify: `_resolve_market_data_context`

### Task 3: 汇合处
- Modify: `conversation_orchestrator.py` 分叉前 bind
- Modify: `_answer_market_review` 渲染包
- 休市：`compose=False` + `calendar_disclosure`
