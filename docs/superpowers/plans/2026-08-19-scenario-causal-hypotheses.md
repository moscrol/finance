# Scenario-Tree Causal Hypotheses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fifth-round overnight-hybrid `market_forecast` drafts grow mutually exclusive *causal* hypotheses on the existing `scenario_tree` contract, not another A/B/C volume-path restatement.

**Architecture:** Same hang as `track_contract`. Ask path already injects `build_scenario_guidance()` via `ask_synthesis`. Continuous episode (the fifth-round path) does not — it only sees `rebound_case` / `decline_case` after `scenario_tree` is aliased. Add an episode-safe guidance string and concatenate it onto the existing `track_rule` interpolation so the static instruction fingerprint does not change. Do not add a new required output (that fail-closes). Do not add a post-processor stub (sixth-round false green). Do not hard-code “AI 证伪 vs 存储见顶”.

**Tech Stack:** Python, pytest, existing `scenario_tree` + `build_episode_instructions` seams.

**Spec:** `docs/learning/spec-continuous-depth-gap-r1.md` R2 P1-C + P2-E. P0-A/B already closed.

**Seams under test:** `build_scenario_guidance` / `episode_scenario_rule` in `intelligence/services/scenario_tree.py`; `build_episode_instructions` via public call. No private helpers.

**Do not:** relax verification; open news/web for all `market_forecast`; change `memory_gate`; cut 8792; edit the dirty main checkout.

---

### Task 1: Extend the existing guidance text

**Files:**
- Modify: `intelligence/services/scenario_tree.py`
- Test: `intelligence/tests/test_scenario_tree.py`

- [ ] **Step 1: Failing tests** — guidance must contain 互斥因果假说 / 证据不足，两假说并立 / 领跌相对强弱; still ban numeric probability; episode version must not leak `[M]` / `[D6]` / `[W7]`.
- [ ] **Step 2: Run to see red**
- [ ] **Step 3: Minimal text** — add one numbered item to `build_scenario_guidance()`; add `build_scenario_guidance_for_episode()` + `episode_scenario_rule()`.
- [ ] **Step 4: Green**

---

### Task 2: Inject into continuous episode instructions

**Files:**
- Modify: `intelligence/services/episode_protocol.py`
- Modify: `intelligence/services/episode_factory.py` (`_OUTPUT_DESCRIPTIONS["scenario_tree"]` only)
- Test: `intelligence/tests/test_episode_protocol.py`

- [ ] **Step 1: Failing tests** — fifth-round overnight question and a local `market_forecast` both receive the episode contract; a valuation / non-scenario question does not; instruction fingerprint unchanged.
- [ ] **Step 2: Red**
- [ ] **Step 3: Concatenate `episode_scenario_rule(...)` onto the existing `track_rule` variable** (no new string literals inside `build_episode_instructions`).
- [ ] **Step 4: Green**

---

### Task 3: P2-E methodology carrier

**Files:**
- Modify: `intelligence/foresight_methodology.md`

Write 竞争假说排除 / 领跌结构裁决 / 行为模拟 as human-review rules. Do not accept “答案出现框架名”.

---

### Task 4: Commit + PR, no merge, no 8792 cut

Live sidecar is the acceptance, same fifth-round question. Do not treat A/B/C path branches as a pass.
