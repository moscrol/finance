# Path Registry + Question Router Design

## Goal

Add a lightweight routing layer before `ask/chat/agent` so user questions are classified into one of four operational modes:

- `known_workflow`: run or preview an existing deterministic path.
- `planner_analysis`: decompose a flexible research question into a small plan.
- `data_gap`: identify missing source/raw/concept/IMA coverage before analysis.
- `clarification_needed`: ask for more input rather than hallucinating.

This is the first real step from "many tools" toward an orchestrated finance agent.

## Why This Layer Exists

The repo already has many deterministic capabilities: daily review, Theme Radar modules, IMA stock ingest, concept/source backfills, quality audits, and the Daily Ops Ledger. The failure mode is not lack of tools; it is that the agent can enter the wrong tool, skip required checks, or answer a data-gap question as if evidence existed.

The router is a deterministic triage desk. It does not answer the financial question. It says which path should be used, which inputs must exist, and whether the agent should proceed, plan, backfill, or ask a follow-up question.

## Components

### Path Registry

File: `intelligence/routing/path_registry.json`

The registry is a machine-readable list of known paths. Each path defines:

- `id`
- `label`
- `kind`
- `description`
- `triggers`
- `inputs`
- `outputs`
- `command_template`
- `auto_execute`
- `risk_level`
- `notes`

High-risk paths are marked explicitly so the caller can generate a dry-run or human review queue instead of writing blindly.

### Registry Loader

File: `intelligence/services/path_registry.py`

Loads the JSON registry into typed `PathSpec` objects. It has no knowledge of routing rules.

### Question Router

File: `intelligence/services/question_router.py`

Uses deterministic keyword routing for v1:

- Strong known-path hits without analysis intent become `known_workflow`.
- Analysis intent or bare theme words become `planner_analysis`.
- Missing/source/raw/concept/trace wording becomes `data_gap`.
- Empty or too vague queries become `clarification_needed`.

The output is a structured `RouteDecision` with selected paths, plan steps, missing-data checks, next action, confidence, and warnings.

### CLI

Command:

```bash
python3 -m intelligence.cli route "玻璃基板今天为什么动，是旧逻辑唤醒吗"
python3 -m intelligence.cli route "446 个 missing concept 和 21 个 missing source 怎么补" --json
```

The route command is read-only and never runs downstream workflows.

## Current Boundaries

This version does not use LLM classification. That is intentional. Routing should be reproducible before it becomes model-assisted.

This version does not execute `logic_market_match`; it only selects it as the next action. The next implementation step is to build the actual logic-market matching executor.

This version does not use LangGraph. The graph/state-machine step should come after route categories and path outputs are stable.

## Example Decisions

`玻璃基板 deep-dive`:

- `route_type=known_workflow`
- selected path: `deep_dive`

`玻璃基板今天为什么动，是旧逻辑唤醒吗`:

- `route_type=planner_analysis`
- selected paths: `logic_market_match`, `front_map`, `deep_dive`

`446 个 missing concept 和 21 个 missing source 怎么补`:

- `route_type=data_gap`
- selected paths: `daily_ops_ledger`, `source_backfill`, `concept_backfill`

