# Valuation evidence reachability

Date: 2026-07-27
Branch: `feat/agent-runtime-backends-verify`
Scope: generic subject resolution for the shared Episode valuation tools.

## Failure reproduced

The self-use valuation run for a company name produced no usable market or
financial evidence. The knowledge base already had a deterministic entity
anchor for the company (`688323`), but `episode_tools` passed only natural
language into the DuckDB name resolver. The market valuation and quarterly
financial blocks therefore returned empty before their external providers could
be called.

## Fix

`build_episode_registry()` now resolves the subject once through the existing
`entity_anchor` capability and passes an internal query containing entity name,
ticker and the original question to both the valuation market runner and the
financial-data runner. No company-specific branch or new route was added. If no
anchor exists, the previous honest empty behavior remains.

## Verification

- RED/GREEN regression:
  `test_valuation_tools_reuse_shared_entity_anchor_for_subject_resolution`.
- Focused tools/factory/entity/valuation tests: `67 passed`.
- Real canonical tool-only replay (no LLM, no question-suite rerun):
  `market_data` returned 5 valuation evidence lines and `financial_data`
  returned 10 quarterly-financial evidence lines for the anchored company;
  both traces were `success` with zero gaps.
- Ruff and `git diff --check`: passed.
- No valuation number is synthesized by this slice; the existing provider and
  scenario calculations remain the source of numeric anchors.
- No 8792 switch and no `main` merge.
