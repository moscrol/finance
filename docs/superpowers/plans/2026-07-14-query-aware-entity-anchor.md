# Query-aware Entity Anchor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prioritize the entity concepts explicitly named by the user so unrelated stored concepts do not pollute graph and evidence retrieval.

**Architecture:** Resolve the entity exactly as before, then stable-partition its concept list using deterministic explicit seeds derived from the original query. Keep all downstream consumers unchanged because they already share `EntityAnchor.graph_query`.

**Tech Stack:** Python 3.12, dataclasses, Unicode regular expressions, unittest/pytest, existing KnowledgeAdapter fixtures.

---

### Task 1: Specify Query-aware Concept Ordering

**Files:**
- Modify: `intelligence/tests/test_entity_anchor.py`

- [ ] **Step 1: Extend the entity fixture with unrelated and liquid-cooling concepts**

```python
"英维克": {
    "codes": ["002837.SZ"],
    "concepts": {
        "ABF载板": {},
        "AI容器": {},
        "液冷": {},
        "数据中心液冷": {},
        "液冷散热": {},
        "液冷服务器": {},
    },
}
```

- [ ] **Step 2: Add name, code, and no-explicit-concept assertions**

```python
assert resolve_entity_anchor("英维克在液冷产业链位置", kb).concepts == (
    "液冷", "数据中心液冷", "液冷散热", "液冷服务器"
)
assert resolve_entity_anchor("002837 液冷怎么看", kb).concepts[0] == "液冷"
assert resolve_entity_anchor("英维克估值怎么看", kb).concepts == (
    "ABF载板", "AI容器", "液冷", "数据中心液冷"
)
```

- [ ] **Step 3: Run the focused tests and confirm storage-order leakage**

Run: `pytest intelligence/tests/test_entity_anchor.py -q`

### Task 2: Implement Deterministic Stable Partition

**Files:**
- Modify: `intelligence/services/entity_anchor.py`

- [ ] **Step 1: Pass the original query through both resolution paths**

```python
return _build_anchor(rec, matched_by="code", query=text)
return _build_anchor(named[0], matched_by="name", query=text)
```

- [ ] **Step 2: Normalize and find specific explicit seeds**

```python
normalized_query = re.sub(r"[\W_]+", "", query.casefold())
seeds = [
    concept_norm
    for concept_norm in normalized_concepts
    if _is_specific_seed(concept_norm) and concept_norm in normalized_query
]
```

- [ ] **Step 3: Stable-partition matching families before applying the limit**

```python
matched = [concept for concept in concepts if any(seed in norm or norm in seed for seed in seeds)]
unmatched = [concept for concept in concepts if concept not in matched]
ranked = [*matched, *unmatched]
```

- [ ] **Step 4: Re-run entity-anchor tests**

### Task 3: Verify Ask and Retrieval Integration

**Files:**
- Modify: `intelligence/tests/test_answer_orchestrator.py`

- [ ] **Step 1: Add a real-style relation fixture with liquid and unrelated peers**

```python
entities = {
    "英维克": multi_concept_target,
    "SK海力士": {"concepts": {"ABF载板": {}}},
    "东方财富": {"concepts": {"AI容器": {}}},
    "高澜股份": {"concepts": {"液冷": {}}},
    "申菱环境": {"concepts": {"数据中心液冷": {}}},
}
```

- [ ] **Step 2: Spy on evidence targets and run `answer_query` without LLM/modules**

```python
result = answer_query(AskOptions(
    query="英维克在液冷产业链位置",
    kb_wiki=wiki,
    compose=False,
    use_modules=False,
    use_wiki_rag=False,
))
```

- [ ] **Step 3: Assert target and liquid peers remain while unrelated peers disappear**

```python
assert {row.company for row in result.answer_spec.company_table} >= {
    "英维克", "高澜股份", "申菱环境"
}
assert {"SK海力士", "东方财富"}.isdisjoint(evidence_targets)
```

- [ ] **Step 4: Run focused and expanded regressions**

Run: `pytest intelligence/tests/test_entity_anchor.py intelligence/tests/test_answer_orchestrator.py -q`

### Task 4: Static Checks and Single Commit

**Files:** all files above and design/plan documents.

- [ ] **Step 1: Run expanded backend tests and the existing frontend 130-test suite**
- [ ] **Step 2: Run Ruff, frontend typecheck/lint, `git diff --check`, and pre-commit**
- [ ] **Step 3: Create one commit without push or merge**

```bash
git commit -m "fix: focus entity anchors on explicit concepts"
```
