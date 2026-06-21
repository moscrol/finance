# Logic Market Match v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only executor that matches market-triggered theme candidates to knowledge-base concepts, entity exposures, evidence, and source trace.

**Architecture:** Add a service under `intelligence/services`, a workflow wrapper under `intelligence/workflows`, a CLI command under `intelligence.cli`, and focused tests with temp fixture data.

**Tech Stack:** Python standard library, existing `KnowledgeAdapter`, existing theme-candidate loaders, `unittest`.

---

### Task 1: Service

**Files:**
- Create: `intelligence/services/logic_market_match.py`

- [x] Load theme candidates via existing `load_theme_candidates`.
- [x] Match candidate via existing `match_candidate`.
- [x] Query knowledge via `KnowledgeAdapter.get_concept_matches`, `get_exposure_matches`, and `get_evidence`.
- [x] Check source page existence for evidence source refs.
- [x] Classify as old wakeup, new candidate, data gap, or noise.
- [x] Render Markdown and JSON.

### Task 2: Workflow

**Files:**
- Create: `intelligence/workflows/logic_match.py`

- [x] Wrap service result in `WorkflowSummary`.
- [x] Emit market, knowledge, and classification steps.
- [x] Preserve warnings and next actions.

### Task 3: CLI

**Files:**
- Modify: `intelligence/cli.py`
- Modify: `intelligence/routing/path_registry.json`

- [x] Add `logic-match` command.
- [x] Support `--date`, `--exports-dir`, `--kb-wiki`, `--top-companies`, `--max-evidence`.
- [x] Support `--json`, `--out-json`, `--out-md`, `--summary-json`.
- [x] Update path registry command template.

### Task 4: Tests and Sample

**Files:**
- Create: `tests/test_logic_market_match.py`
- Create: `market_feature_store/exports/2026-06-11-logic-match-光刻胶.json`
- Create: `market_feature_store/exports/2026-06-11-logic-match-光刻胶.md`

- [x] Test old-logic wakeup when market and knowledge both match.
- [x] Test source trace missing is surfaced as a data gap.
- [x] Test knowledge-missing case is classified as data gap.
- [x] Generate one real sample report for `光刻胶` on `2026-06-11`.

