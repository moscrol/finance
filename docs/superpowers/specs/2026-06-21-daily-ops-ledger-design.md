# Daily Ops Ledger Design

## Goal

Build a lightweight orchestration ledger that aligns the finance repo and the knowledge repo around the user's daily workflow: full market review, evening sell-side ingest, morning briefing ingest, IMA stock-card ingest, and old report ingest.

The first version is read-only. It must not move files, rewrite source notes, repair relations, or run ingest scripts. Its job is to show what exists, what is missing, and what the next operational queue should be.

## Repo Responsibilities

The finance repo owns market data, market review outputs, market-triggered theme discovery, and future performance measurement. Its canonical outputs live under `market_feature_store/exports` and `复盘/daily`.

The knowledge repo owns raw/source traceability, entity cards, concept cards, relations, catalyst calendar, sell-side cross analysis, morning briefings, and IMA stock logic cards. Its canonical vault root is `wiki`.

The ledger sits in the finance repo because it is closer to the daily review workflow, but it reads both repos through `intelligence.paths.default_paths()`.

## Daily Workflow Mapping

### Full Market Review

Expected finance outputs for a date:

- `market_feature_store/exports/<date>-daily-review.md`
- `market_feature_store/exports/<date>-advancers-ma5.png`
- `market_feature_store/exports/<date>-theme-candidates.json`
- `market_feature_store/exports/<date>-theme-candidates.md`
- `market_feature_store/exports/<date>-theme-backfill-queue.json`
- `market_feature_store/exports/<date>-theme-backfill-review-queue.json`
- `market_feature_store/exports/<date>-theme-backfill-review-queue.md`
- `复盘/daily/<date>/<date>-daily-review.html`
- `复盘/daily/<date>/<date>-theme-candidates.html`
- `market_feature_store/exports/<date>-daily-workflow-summary.json`

Missing files here mean the market side is incomplete for the day.

### Morning Briefing

Expected knowledge outputs are date-prefixed files under `wiki/briefings`. This may include the briefing itself and cross-analysis files such as `三维交叉`.

Missing files here mean the morning logic source has not been captured or rendered into the vault.

### Evening Sell-side / Old Reports

The ledger does not ingest reports in v1. It only checks whether the knowledge vault has the relations surfaces that downstream workflows need: `evidence_index.json`, `entity_exposures.json`, `concept_graph.json`, `theme_signals.json`, `catalyst_calendar.json`, and `mention_frequency.json`.

Future versions can add source batches for sell-side folders once the folder convention is fixed.

### IMA Stock Cards

The ledger counts raw IMA stock files under `wiki/raw/ima-stock/ingested/<date>` and watches operational folders next to the knowledge repo:

- `未入库`
- `已入库`
- `待人工确认`

This keeps the old IMA card flow visible without re-running ingest.

### Structural Debt

The ledger reads existing audit JSON when present:

- `wiki/raw/theme-radar/missing-concept-audit.json`
- `wiki/raw/theme-radar/missing-evidence-source-audit.json`
- latest `wiki/raw/ima-stock/audits/entity-stock-ima-coverage-*.json`

These debts do not block the daily ledger, but they should appear as quality flags because they affect traceability and concept matching.

## Output Contract

For each date, the script writes:

- `market_feature_store/exports/<date>-daily-ops-ledger.json`
- `market_feature_store/exports/<date>-daily-ops-ledger.md`

The JSON is for the future agent and the other Mac with DuckDB. The Markdown is for the user-facing daily checklist.

Each ledger contains:

- `status`: `PASS`, `WARN`, or `FAIL`
- `sections`: per-workflow checks
- `counts`: repo-level inventory numbers
- `debts`: known structural debts
- `next_actions`: concrete operational actions

## Status Rules

`PASS` means all expected market review outputs exist and there are no immediate inbox files waiting in `未入库`.

`WARN` means the day is usable but incomplete, such as missing morning briefing, missing theme candidate outputs, pending manual-review files, or structural debt.

`FAIL` means the date is invalid, paths are missing, or the script cannot write the requested outputs.

## Non-goals

V1 does not calculate CAR, p-values, half-life, narrative-fact divergence, or logic state transitions. Those require a durable event model and DuckDB market data access. V1 creates the daily operational surface that those metrics can attach to later.

