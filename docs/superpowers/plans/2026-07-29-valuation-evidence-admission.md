# Valuation Evidence Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep bare cross-entity co-occurrence out of anchored valuation evidence while preserving explicit relationship clues and direct comparable valuation assertions.

**Architecture:** Extend `EvidenceSearchPolicy` with an opt-in subject-local admission mode. Classify closed-loop buckets before semantic judging into direct model evidence, relation-only inspector clues, and discarded co-occurrence; inject this mode only from valuation Episode contracts and reuse the frame-owned entity anchor when the model's tool query omits the company name.

**Tech Stack:** Python 3.12, frozen dataclasses and typed Literals, existing Hybrid RAG buckets, pytest, BGE-m3/BM25/RRF replay.

---

### Task 1: Add subject-local admission at the EvidenceSearch seam

**Files:**
- Modify: `intelligence/services/evidence_search.py`
- Test: `intelligence/tests/test_evidence_search.py`

- [ ] **Step 1: Write the failing tri-state public-interface test**

Create four same-query hits returned by the first retrieval call:

```python
subject = _hit("subject", "瑞华泰（688323）", "瑞华泰估值基础资料")
bare = _hit("bare", "天奈科技（688116）", "[[汉威科技]] · [[瑞华泰]]")
relation = _hit(
    "relation",
    "方邦股份（688020）",
    "[[瑞华泰]] — PI薄膜企业，同属功能薄膜赛道",
)
comparable = _hit(
    "comparable",
    "功能薄膜可比估值",
    "瑞华泰与方邦股份属于可比公司，当前PB估值分别为4.3倍与3.1倍",
)
```

Run `EvidenceSearch(..., policy=EvidenceSearchPolicy(anchor_admission="subject_local"))`
with `EntityAnchor("瑞华泰", "688323.SH", ("PI薄膜",))`. Assert:

```python
assert [item.title for item in result.evidence] == [
    "瑞华泰（688323）",
    "功能薄膜可比估值",
]
assert result.coverage.clue_count == 1
assert result.coverage.discarded_count == 1
assert "anchor_admission=direct:2,relation_clue:1,rejected:1" in result.diagnostics
```

Use empty responses for broad/counter calls so the test isolates admission rather
than query expansion.

- [ ] **Step 2: Add a capture-judge ordering assertion**

Pass a semantic judge that records candidate titles and returns all received
indexes. Assert it sees only the subject and direct-comparable candidates, never
天奈科技 or the relation-only 方邦 chunk.

- [ ] **Step 3: Add default compatibility coverage**

Run the same retriever with the default policy and assert all four hits remain
eligible. This protects non-valuation callers.

- [ ] **Step 4: Run RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_evidence_search.py -q
```

Expected: construction fails because `EvidenceSearchPolicy` has no
`anchor_admission` field.

- [ ] **Step 5: Implement the typed policy and classifier**

In `evidence_search.py`, define:

```python
AnchorEvidenceAdmission: TypeAlias = Literal["open", "subject_local"]

@dataclass(frozen=True)
class EvidenceSearchPolicy:
    ...
    anchor_admission: AnchorEvidenceAdmission = "open"
```

Add a pre-judge helper that returns a new
`ClosedLoopRetrievalResult`. Under `subject_local` with an anchor:

```python
source_identity = f"{hit.title} {hit.file_path}".casefold()
body = str(hit.llm_evidence or hit.display_excerpt or hit.excerpt or "")
```

Classify as:

```text
direct:
  anchor entity/full ticker/raw ticker in source_identity
  OR anchored identity in body AND a valuation assertion cue
relation_clue:
  anchored identity in body AND an explicit relation cue
reject:
  everything else
```

Valuation assertion cues: `估值`, `市值`, `市盈率`, `市净率`, `市销率`,
`可比估值`, `目标价`, `合理价格`, boundary-safe `PE/PB/PS/EV`, or a numeric
multiple. Relation cues: `同属`, `可比公司`, `同行`, `竞争`, `上游`, `下游`,
`供应商`, `客户`, `替代`, `产业链`. Do not treat `相关实体` alone as a relation.

Direct hits remain in their original conclusion/counter bucket. Relation hits
move only to `clues`; rejects move to `discarded`. Remove rejected/demoted counter
hits from both `counter_clues` and the counter-derived entries already present in
`clues`. Append one deterministic diagnostic:

```text
anchor_admission=direct:N,relation_clue:N,rejected:N
```

Call this helper after closed-loop retrieval and before `_apply_semantic_judge`.

- [ ] **Step 6: Run GREEN and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_evidence_search.py \
  intelligence/tests/test_closed_loop_retrieval.py -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/ruff check \
  intelligence/services/evidence_search.py \
  intelligence/tests/test_evidence_search.py
git diff --check
git add intelligence/services/evidence_search.py \
  intelligence/tests/test_evidence_search.py
git commit -m "fix: admit only subject-local valuation evidence"
```

### Task 2: Inject valuation admission from Episode composition

**Files:**
- Modify: `intelligence/services/episode_tools.py`
- Test: `intelligence/tests/test_episode_tools.py`

- [ ] **Step 1: Write the failing valuation registry test**

Build `_valuation_frame()` and an Episode context with cutoff/latest date
`2026-07-24`. Stub `kb_rag.retrieve` so the first call returns:

```text
瑞华泰（688323） / 瑞华泰估值基础资料
天奈科技（688116） / [[汉威科技]] · [[瑞华泰]]
方邦股份（688020） / [[瑞华泰]] — PI薄膜企业，同属功能薄膜赛道
```

Execute the public registry tool with the intentionally generic model query
`"合理估值证据"`. Assert only 瑞华泰 enters `ToolRunResult.evidence`, proving
the registry reused the frame-owned anchor even though the tool query omitted it.

- [ ] **Step 2: Add a non-valuation compatibility assertion**

Build a non-valuation anchored frame and use the default EvidenceSearch policy.
Assert the registry does not apply `subject_local` merely because an entity anchor
exists.

- [ ] **Step 3: Run RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_episode_tools.py -q
```

Expected: the current valuation registry projects the bare 天奈 hit.

- [ ] **Step 4: Wire the policy and frame-owned anchor**

In the evidence-search runner:

```python
query_anchor = entity_anchor.resolve_entity_anchor(query, knowledge)
if (
    query_anchor is None
    and context.contract.evidence_plan.profile == "valuation_current_anchor"
):
    query_anchor = subject_anchor
```

Choose exactly one policy:

```python
if profile == "time_aligned_market_causal":
    EvidenceSearchPolicy(query_only, source window, require counter)
elif profile == "valuation_current_anchor":
    EvidenceSearchPolicy(anchor_admission="subject_local")
else:
    EvidenceSearchPolicy()
```

Pass `query_anchor` to `search`; do not change other registry tools.

- [ ] **Step 5: Run GREEN and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_evidence_search.py \
  intelligence/tests/test_closed_loop_retrieval.py -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/ruff check \
  intelligence/services/episode_tools.py \
  intelligence/tests/test_episode_tools.py
git diff --check
git add intelligence/services/episode_tools.py \
  intelligence/tests/test_episode_tools.py
git commit -m "fix: enforce valuation evidence admission in episodes"
```

### Task 3: True-Hybrid and semantic-judge replay

**Files:**
- Create: `docs/verification/phase-c-valuation-evidence-admission-2026-07-29.md`

- [ ] **Step 1: Record the pre-change true-Hybrid baseline**

Use the pinned environment:

```text
KB_RAG_PYTHON=/Users/a77/knowledge-base-private/.rag_venv/bin/python3
RAG_BGE_MODEL=/Users/a77/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181
RAG_INDEX_DIR=/Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/.rag_index
HF_HUB_OFFLINE=1
RAG_WORKER_ENABLED=1
```

The already captured direct probe is the red baseline:

```text
rank 5: wiki/entities/天奈科技.md::3
rank 7: wiki/entities/方邦股份.md::6
neighbor_hits=0; requested/effective=hybrid/hybrid
```

- [ ] **Step 2: Replay the closed-loop valuation search**

Prewarm once, clear only the in-process result cache, and run
`EvidenceSearch` with `EntityAnchor("瑞华泰", "688323.SH", ("PI薄膜",))` and
`anchor_admission="subject_local"`. Require:

```text
all executed attempts: hybrid -> hybrid, degraded=false
天奈科技: absent from model evidence
方邦股份 relation-only chunk: absent from model evidence
direct 瑞华泰 pages: present
anchor_admission diagnostic: present
```

- [ ] **Step 3: Replay semantic ordering**

Run a deterministic capture judge and prove its candidate list excludes the two
non-direct chunks. Then call `default_semantic_judge` only if the configured
provider is immediately available without user interaction. Record one of:

```text
live_semantic_judge=completed + verdict/candidate counts
live_semantic_judge=blocked_external + stable reason
```

Do not request or persist a key in this loop.

- [ ] **Step 4: Remove generated access-log lines and audit isolation**

Record the line/hash boundary before replay. Remove only replay-appended JSONL
lines with `apply_patch`. Require the KB clone clean and original KB still
`main@883815c9` with zero dirty indexed page directories.

- [ ] **Step 5: Run proportional gates**

```bash
PYTHONDONTWRITEBYTECODE=1 \
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_kb_rag.py \
  intelligence/tests/test_closed_loop_retrieval.py \
  intelligence/tests/test_evidence_search.py \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_episode_semantic_verifier.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/ruff check \
  intelligence/services/evidence_search.py \
  intelligence/services/episode_tools.py \
  intelligence/tests/test_evidence_search.py \
  intelligence/tests/test_episode_tools.py
git diff --check
```

- [ ] **Step 6: Write and commit verification**

Document the red baseline, post-filter buckets/evidence, semantic ordering,
interpreter/model/index hashes, tests, cleanup, and remaining decision.

```bash
git add docs/verification/phase-c-valuation-evidence-admission-2026-07-29.md
git commit -m "docs: verify valuation evidence admission"
```

### Task 4: Final decision and handoff

**Files:**
- Create: `docs/handoffs/2026-07-29-adaptive-runtime-final-quality-handoff.md`

- [ ] **Step 1: Evaluate the next experiment against evidence**

Use these decision rules:

```text
deterministic seam still contaminated -> do not expand; repair admission
deterministic clean + semantic blocked -> retain deterministic result, record external block
deterministic clean + semantic helps materially -> keep judge as optional second layer
deterministic clean + current five-case failures still budget/protocol dominated -> run only preregistered budget ablation
retrieval/admission clean but answer autonomy remains materially below interactive Codex -> App Server ceiling experiment becomes justified
no same-format Knevo artifact -> do not claim a Knevo win rate
```

- [ ] **Step 2: Write the final handoff**

State completed architecture, exact commits and gates, current total progress,
what remains externally blocked, whether a larger benchmark/App Server/Knevo run
is justified, and all unchanged boundaries. Do not call unknown pass rate zero.

- [ ] **Step 3: Commit and close the goal**

```bash
git add docs/handoffs/2026-07-29-adaptive-runtime-final-quality-handoff.md
git commit -m "docs: hand off adaptive runtime final quality"
```
