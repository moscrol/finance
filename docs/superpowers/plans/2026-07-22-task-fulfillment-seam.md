# Task Fulfillment Seam Implementation Plan

> **For agentic workers:** Inline execution in this session. Follow each task in order and keep the red→green evidence in the commit history.

**Goal:** Make long-tail answer quality a verified semantic outcome instead of treating transport completion or evidence presence as success.

**Architecture:** Keep deterministic head owners unchanged. For the remaining lanes, preserve one TurnContract/ResearchTaskContract, evaluate required outputs at the final public-answer seam, and keep truth/grounding gates separate from task fulfillment. The first implementation is deterministic and evidence-ID based; semantic judge integration remains an adapter after the red bar is reliable.

**Tech Stack:** Python 3.9+, dataclasses, pytest, existing `AnswerSpec`/`EvidenceAtom`/`ResearchTaskContract`, SSE run store.

---

### Task 1: Add the semantic red-bar fixtures at public seams

**Files:**
- Modify: `intelligence/tests/test_generic_research_owner.py`
- Modify: `intelligence/tests/test_conversation_orchestrator.py`
- Modify: `intelligence/tests/test_workbench_api.py`
- Modify: `scripts/smoke_workbench_self_use.py`

- [ ] **Step 1: Add a deterministic fulfillment fixture**

Create a small helper in the test module that builds a `ResearchTaskContract`, two `AgentEvidence` items, and an `AnswerSpec`/final text for a mainline and forecast question. The expected output is independent of implementation: a mainline sentence must contain a direct current-mainline assessment; a forecast must contain baseline, rebound, decline, and invalidation sections.

- [ ] **Step 2: Add the H2 counterexample test**

Call the public completion interface with a `market_data` evidence item whose content is unrelated to the question and an arbitrary assessment. Assert that the semantic verdict is missing/partial even if structural completion is true.

- [ ] **Step 3: Add the public-answer test**

Feed a candidate-source-list answer into the final answer seam and assert that it cannot be `answer_status=complete`, while a bounded gap mentioning the missing direct assessment is `answer_status=partial`.

- [ ] **Step 4: Run only the new tests**

Run:

```bash
pytest -q intelligence/tests/test_task_fulfillment.py intelligence/tests/test_generic_research_owner.py -k 'fulfillment or counterexample'
```

Expected: FAIL because `task_fulfillment.py` and the final answer verdict do not exist yet.

- [ ] **Step 5: Commit the red tests**

```bash
git add intelligence/tests/test_task_fulfillment.py intelligence/tests/test_generic_research_owner.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_workbench_api.py scripts/smoke_workbench_self_use.py
git commit -m "test: add semantic answer red bars"
```

### Task 2: Implement the deep TaskFulfillmentGate

**Files:**
- Create: `intelligence/services/task_fulfillment.py`
- Create: `intelligence/tests/test_task_fulfillment.py`
- Modify: `intelligence/services/research_contract.py`

- [ ] **Step 1: Define the small public interface**

Add immutable dataclasses:

```python
@dataclass(frozen=True)
class FulfillmentItem:
    output_id: str
    status: Literal["fulfilled", "partial", "missing"]
    evidence_ids: tuple[str, ...] = ()
    answer_spans: tuple[str, ...] = ()
    gap: str = ""

@dataclass(frozen=True)
class FulfillmentVerdict:
    status: Literal["complete", "partial", "missing"]
    items: tuple[FulfillmentItem, ...]
    reason: str = ""
```

Export one function:

```python
def evaluate_task_fulfillment(
    *, question: str, required_outputs: tuple[RequiredOutput, ...],
    answer_text: str, evidence_ids: frozenset[str],
    claim_bindings: Mapping[str, tuple[str, ...]] = MappingProxyType({}),
) -> FulfillmentVerdict
```

- [ ] **Step 2: Implement deterministic checks only**

For each required output, locate its required claim marker or registered output token in the final text, verify that its claim binding intersects the supplied evidence IDs, and preserve an explicit output-specific gap as `partial`. A list of URLs, source titles, or generic “仍缺少资料” text cannot fulfill `direct_assessment`.

- [ ] **Step 3: Add unit tests through the function interface**

Cover: complete mainline, complete forecast, technical passthrough, unrelated evidence, candidate-source list, explicit gap, and stale evidence IDs. Tests must assert the literal verdict, not recompute the implementation’s logic.

- [ ] **Step 4: Run the focused unit tests**

Run:

```bash
pytest -q intelligence/tests/test_task_fulfillment.py
```

Expected: PASS.

- [ ] **Step 5: Commit the deep module**

```bash
git add intelligence/services/task_fulfillment.py intelligence/tests/test_task_fulfillment.py intelligence/services/research_contract.py
git commit -m "feat: add final task fulfillment gate"
```

### Task 3: Wire the gate after final grounded repair

**Files:**
- Modify: `intelligence/services/ask_synthesis.py:1176-1276`
- Modify: `intelligence/services/conversation_orchestrator.py:2320-2535, 2800-2865`
- Modify: `intelligence/services/ask.py:1220-1305`
- Modify: `intelligence/tests/test_grounded_presenter_general.py`
- Modify: `intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 1: Add a final-verdict hook**

After `promote_grounded_answer()` and any repair pass, call `evaluate_task_fulfillment()` with the final public text and claim/evidence registry. Do not call it against the pre-repair draft.

- [ ] **Step 2: Keep transport and semantic state separate**

Attach `answer_status` and the serialized `FulfillmentVerdict` to the run report. Preserve the existing transport status for protocol compatibility. A failed final verdict must not be relabeled as `verified_fallback`.

- [ ] **Step 3: Gate final snapshot publication**

Allow progress snapshots while research is running, but only mark the final snapshot as complete/verified when the verdict is complete. Emit `partial` or `evidence_gap` for a truthful gap.

- [ ] **Step 4: Add regression tests**

Assert that the existing market-technical answer remains validated, the mainline candidate list is partial, and the forecast daily-review prose is not complete.

- [ ] **Step 5: Run focused presentation tests**

```bash
pytest -q intelligence/tests/test_task_fulfillment.py intelligence/tests/test_grounded_presenter_general.py intelligence/tests/test_conversation_orchestrator.py -k 'fulfillment or snapshot or grounded'
```

- [ ] **Step 6: Commit the wire-up**

```bash
git add intelligence/services/ask_synthesis.py intelligence/services/conversation_orchestrator.py intelligence/services/ask.py intelligence/tests/test_grounded_presenter_general.py intelligence/tests/test_conversation_orchestrator.py
git commit -m "fix: gate final answer on task fulfillment"
```

### Task 4: Make owner and capability decisions contract-driven

**Files:**
- Modify: `intelligence/services/conversation_orchestrator.py:1604-1645, 2120-2160`
- Modify: `intelligence/services/research_contract.py`
- Modify: `intelligence/services/retrieval_planner.py`
- Modify: `intelligence/services/evidence_capabilities.py`
- Modify: `intelligence/tests/test_conversation_orchestrator.py`
- Modify: `intelligence/tests/test_generic_research_owner.py`

- [ ] **Step 1: Add an immutable owner assertion**

When the controller supplies a non-head research contract, route-skills may select provider adapters but must not replace `answer_owner` or `required_outputs`. Trace both the requested and selected owner and fail closed on incompatibility.

- [ ] **Step 2: Make mainline and forecast capabilities mandatory**

Resolve `market_data` plus `mainline_context` for current-mainline questions and latest market data plus scenario evidence for forecasts. Keep the capability registry as the single source; do not add another per-skill whitelist.

- [ ] **Step 3: Add compatibility tests**

Controller `market_forecast` must not be handed to `daily-review` as sole owner. Mainline contracts must include the mandatory capability pair. Existing deterministic head routes must remain unchanged.

- [ ] **Step 4: Run route/contract tests and commit**

```bash
pytest -q intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_generic_research_owner.py -k 'forecast or mainline or owner or capability'
git add intelligence/services/conversation_orchestrator.py intelligence/services/research_contract.py intelligence/services/retrieval_planner.py intelligence/services/evidence_capabilities.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_generic_research_owner.py
git commit -m "fix: preserve research owner and evidence capabilities"
```

### Task 5: Decouple finish from assessment and unify ledgers

**Files:**
- Modify: `intelligence/services/agent_research.py:538-620`
- Modify: `intelligence/services/generic_research_owner.py:161-350`
- Modify: `intelligence/services/conversation_orchestrator.py:1570-1600`
- Modify: `intelligence/tests/test_agent_research.py`
- Modify: `intelligence/tests/test_generic_research_owner.py`

- [ ] **Step 1: Preserve evidence on finish failure**

Keep collected `AgentEvidence` and `ResearchState` when the finish response is missing/invalid. Mark the loop degraded and attach a gap to the specific direct-assessment output.

- [ ] **Step 2: Separate stop and draft fields**

Represent finish as a stop decision plus an optional assessment draft. Do not set `sufficient=True` merely because evidence exists; only a bounded, boundable draft can become fulfilled.

- [ ] **Step 3: Make the execution ledger count all real attempts**

Emit one turn ledger event for every LLM provider attempt and every research tool execution. Replace the pre-owner zero-count budget snapshot with the shared ledger summary after owner execution, retaining backward-compatible fields.

- [ ] **Step 4: Add timeout and ledger tests**

Mock a finish timeout and assert evidence remains, the direct assessment is degraded/missing rather than fabricated, and query/tool/LLM counts agree.

- [ ] **Step 5: Commit**

```bash
git add intelligence/services/agent_research.py intelligence/services/generic_research_owner.py intelligence/services/conversation_orchestrator.py intelligence/tests/test_agent_research.py intelligence/tests/test_generic_research_owner.py
git commit -m "fix: preserve research state across finish failures"
```

### Task 6: Add semantic smoke acceptance and runtime provenance

**Files:**
- Modify: `scripts/smoke_workbench_self_use.py:700-815`
- Modify: `intelligence/api/app.py` or the existing health route
- Create: `scripts/semantic_acceptance.py`
- Create: `intelligence/tests/test_semantic_acceptance.py`

- [ ] **Step 1: Add explicit semantic assertions**

The script must replay the three exact user questions and inspect the final answer snapshot plus `answer_status`. Exit 0 only when transport and semantic status pass. Keep `--transport-only` for protocol debugging.

- [ ] **Step 2: Add runtime provenance assertions**

Fail fast if the API health revision differs from the expected candidate commit or if the runtime path and dependency fingerprint are missing.

- [ ] **Step 3: Run the acceptance script**

```bash
python3 scripts/semantic_acceptance.py --base-url http://127.0.0.1:8795 --user task-fulfillment
```

Expected on a candidate service after Tasks 1–5: technical pass; mainline and forecast either semantic pass with required outputs or explicit, question-bound partial (never a misleading complete/template pass).

- [ ] **Step 4: Run the full intelligence suite**

```bash
pytest -q intelligence/tests
```

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_workbench_self_use.py scripts/semantic_acceptance.py intelligence/api/app.py intelligence/tests/test_semantic_acceptance.py
git commit -m "test: make semantic acceptance a release gate"
```

### Task 7: Remove redundant completion paths and document handoff

**Files:**
- Modify: `intelligence/services/generic_research_owner.py`
- Modify: `intelligence/services/answer_model.py`
- Modify: `intelligence/services/output_review.py`
- Modify: `docs/verification/task-fulfillment-final-2026-07-22.md`
- Modify: `/Users/a77/agent-memory/20_projects/finance-workspace-private.md`

- [ ] **Step 1: Delete only duplicated task-completion checks**

Keep evidence truth/permission/contamination gates. Move duplicate “required output complete” decisions to `TaskFulfillmentGate`, and leave adapters that serialize legacy fields.

- [ ] **Step 2: Run the full suite and inspect public snapshots**

Confirm no control-plane sections leak into the public answer and no technical head regression appears.

- [ ] **Step 3: Write verification evidence**

Record commit, test counts, semantic verdicts, runtime provenance, known gaps, and the fact that main/8792 were not merged or cut over.

- [ ] **Step 4: Commit the cleanup and verification record**

```bash
git add intelligence/services/generic_research_owner.py intelligence/services/answer_model.py intelligence/services/output_review.py docs/verification/task-fulfillment-final-2026-07-22.md
git commit -m "docs: record task fulfillment verification"
```
