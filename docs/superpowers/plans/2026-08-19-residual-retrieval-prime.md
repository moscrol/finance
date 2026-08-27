# Residual Retrieval Prime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让已经需要检索的 `general_finance_qa` 残差题在授权里同时有行情、新闻、用户先验，并用窄 `evidence_types` 的 `prime_*` 槽逼模型消费。

**Architecture:** 改 `_RUNTIME_CAPABILITY_FLOOR["general_finance_evidence"]` 与控制器同 policy 地板；在 `build_episode_context` 能力定稿后按工具是否在授权里注入三个新槽；`produces` 补声明。不改 task_frame 默认产出，不改 episode 指令指纹。

**Tech Stack:** Python, pytest, 现有 `TaskFrame` / `runtime_capabilities_for_frame` / `build_episode_context`。

**Spec:** `docs/superpowers/specs/2026-08-19-residual-retrieval-prime-design.md`

**Worktree:** `/Users/a77/fwp-wt-residual-prime` on `feat/residual-retrieval-prime`

**Git:** 用户未要求 commit；本计划所有 Commit 步跳过。

---

## File map

| File | Responsibility |
|---|---|
| `intelligence/tests/test_residual_retrieval_prime.py` | 公开缝：能力地板 + 契约槽 |
| `intelligence/services/evidence_capabilities.py` | residual policy 运行时地板 |
| `intelligence/services/turn_controller.py` | 控制器词表地板对齐 |
| `intelligence/services/episode_factory.py` | 描述、注入、窄 evidence_types、grounding、required 旗标 |
| `intelligence/services/research_tool_registry.py` | `produces` |
| `intelligence/tests/test_tool_produces_satisfiability.py` | memory_lookup 不再空 produces |
| `intelligence/tests/test_episode_factory.py` | `RUNTIME_CAPABILITIES` 补 `memory_lookup` |

---

### Task 1: Failing tests at the public seams

**Files:**
- Create: `intelligence/tests/test_residual_retrieval_prime.py`

- [ ] **Step 1: Write the failing tests**

Create `intelligence/tests/test_residual_retrieval_prime.py` with the full file from the executing session (helper `_residual_frame` + five story tests). Do not import private `_with_*` helpers. Construct `TaskFrame` with `question_type="general_finance_qa"` explicitly.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/a77/fwp-wt-residual-prime
python -m pytest intelligence/tests/test_residual_retrieval_prime.py -q
```

Expected: FAIL — capabilities missing `market_data`/`news_search`/`memory_lookup`, and no `prime_*` slots.

- [ ] **Step 3: Implement** — see Task 2–4.

- [ ] **Step 4: Re-run the new file** — Expected: PASS after Tasks 2–4.

- [ ] **Step 5: Commit** — skip (user did not ask).

---

### Task 2: Runtime + controller floors

**Files:**
- Modify: `intelligence/services/evidence_capabilities.py` (`_RUNTIME_CAPABILITY_FLOOR["general_finance_evidence"]` and the `memory_lookup` budget comment)
- Modify: `intelligence/services/turn_controller.py` (`capability_floor["general_finance_evidence"]`)

- [ ] **Step 1:** Change the runtime tuple to:

```python
"general_finance_evidence": (
    "market_data",
    "news_search",
    "memory_lookup",
    "kb_search",
    "web_search",
),
```

Extend the existing `memory_lookup` comment: residual floor **accepts** slot crowding vs Knevo's parallel three-way; this is not an accidental fourth policy.

- [ ] **Step 2:** Change the controller tuple to:

```python
"general_finance_evidence": ("memory", "market_quote", "market_news", "web_search"),
```

Do not add `memory_lookup` here — controller namespace has no such name; `memory` still maps to `kb_search`.

- [ ] **Step 3:** Re-run `test_residual_retrieval_prime.py::test_financial_residual_runtime_includes_knevo_shaped_floor` and `test_market_forecast_runtime_menu_is_unchanged`.

- [ ] **Step 4:** Confirm `intelligence/tests/test_turn_control_core.py::test_market_forecast_runtime_uses_current_structure_without_causal_web_tools` still expects `("market_data", "mainline_context")`.

- [ ] **Step 5: Commit** — skip.

---

### Task 3: Contract slots

**Files:**
- Modify: `intelligence/services/episode_factory.py`

- [ ] **Step 1:** Add `_OUTPUT_DESCRIPTIONS` keys:

```python
"prime_quote": "给出本次问答所依据的最新可用行情要点与数据日期；取不到则在证据边界中写明缺口",
"prime_news": "给出与问题相关的最新财经消息要点；未检索到则写明未取得",
"prime_memory": "复述用户此前对该主体的判断或纠偏原则；台账为空则跳过，不编造",
```

- [ ] **Step 2:** Import `task_frame_requires_retrieval`. After `_with_prior_recall`, call `_with_residual_prime(output_ids, frame, capability_tuple)`.

`_with_residual_prime` only runs when `question_type == "general_finance_qa"` and `task_frame_requires_retrieval(frame)`. Append `prime_quote` / `prime_news` / `prime_memory` independently iff the matching capability is in the tuple.

- [ ] **Step 3:** Narrow `_required_output_evidence_types` for the three ids (same pattern as `prior_recall`). `_grounding_mode("prime_memory")` → `user_premise`. `required=output_id not in {"prior_recall", "prime_memory"}`.

Do **not** add a paragraph to `build_episode_instructions`.

- [ ] **Step 4:** Run `intelligence/tests/test_residual_retrieval_prime.py` — slot tests should pass.

- [ ] **Step 5: Commit** — skip.

---

### Task 4: Registry produces + fixture honesty

**Files:**
- Modify: `intelligence/services/research_tool_registry.py`
- Modify: `intelligence/tests/test_tool_produces_satisfiability.py`
- Modify: `intelligence/tests/test_episode_factory.py` (`RUNTIME_CAPABILITIES` add `"memory_lookup"`)
- Modify: `intelligence/tests/test_episode_factory.py` docstring on `test_prior_recall_slot_is_scoped_to_subject_bearing_question_types` — memory_lookup is no longer only three policies; `prior_recall` injection still is.

- [ ] **Step 1:** `market_data.produces` add `prime_quote`; `news_search.produces` add `prime_news`; `memory_lookup.produces` become `frozenset({"prime_memory", "prior_recall"})` or at least `prime_memory`. Prefer `frozenset({"prime_memory"})` if `prior_recall` was intentionally undeclared — actually prior_recall is filled by memory_lookup. Add both `prime_memory` and `prior_recall` for honesty.

Wait: the existing design left memory_lookup produces empty even after prior_recall existed. Adding prior_recall now could make `check_satisfiability` treat missing prior_recall as covered when the tool is in the registry globally, not per-authorization. That's fail-open covered vs unknown — adding prior_recall to produces is more honest. Spec said `memory_lookup += prime_memory` only. **Do not add prior_recall** unless we want to change that historical choice. Spec: `memory_lookup += prime_memory` only.

- [ ] **Step 2:** Rewrite `test_memory_lookup_declares_nothing_by_design` to `test_memory_lookup_declares_prime_memory` asserting `prime_memory in spec.produces` and that it still does not declare market-fact ids like `supporting_evidence`.

- [ ] **Step 3:** Add `"memory_lookup"` to `RUNTIME_CAPABILITIES` in `test_episode_factory.py`.

- [ ] **Step 4:** Run:

```bash
cd /Users/a77/fwp-wt-residual-prime
python -m pytest intelligence/tests/test_residual_retrieval_prime.py intelligence/tests/test_retrieval_floor_holes.py intelligence/tests/test_turn_control_core.py intelligence/tests/test_episode_factory.py intelligence/tests/test_tool_produces_satisfiability.py intelligence/tests/test_evidence_capabilities.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit** — skip.

---

## Spec coverage

- 5.1 trigger → Task 3
- 5.2 floors → Task 2
- 5.3 slots → Task 3
- 5.4 produces → Task 4
- 5.5 fingerprint → Task 3 (no instruction edit)
- §6 stories → Task 1 tests
- Out of scope → no tasks for rewrite / longtail / 8792 / D-blocks

## Placeholder scan

No TBD. Commit steps explicitly skipped per user git rule.
