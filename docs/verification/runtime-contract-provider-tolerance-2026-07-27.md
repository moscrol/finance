# Runtime Contract and Provider Tolerance Verification

Date: 2026-07-27

Branch: `feat/agent-runtime-backends-verify`

Product commits:

- `af395f81` — immutable answer-element floor and monotonic plan revisions
- `27fc5d50` — configured legacy deep ceiling raised from 8 to 24
- `9163a143` — bounded Eastmoney natural-query fallback

## Result

The three pre-Phase-3 seams from the independent review are closed. The model
still owns hypotheses, candidate actions, query wording, tool order, and when
to stop. Code owns only the immutable minimum task, budget ceiling, provider
adaptation, and audit truth.

## Verification

```text
179 passed
Ruff passed
git diff --check passed
```

The focused suite covered `research_plan`, the legacy `agent_research` loop,
Eastmoney market news, the continuous Episode, and the turn adapter.

## Observed behavior

- An initial plan missing a required contract output receives the existing
  same-Episode protocol repair and no tool authority. A revision may add answer
  elements but cannot remove a previously published element.
- `ASK_AGENT_MAX_STEPS=24` now yields 24; 25 clamps to 24, zero clamps to one,
  and invalid/unset values preserve the default of four. No task is promoted to
  deep mode by this change.
- `上周A股下跌原因` attempts the exact query, then `A股下跌`, then `A股`, and
  succeeds through the fallback path in the scripted provider test.
- `低空经济 商业航天` attempts each explicit single keyword and merges both
  result sets. Duplicate URL/title entries collapse through the existing
  deterministic merge rule.
- Eastmoney fallback is limited to three simpler terms, shares the caller's
  total timeout, and runs only after an honest `empty`. A request or parse error
  stops immediately rather than multiplying provider load.
- The low-level title-contains-keyword relevance gate is unchanged. Input
  tolerance therefore increases recall without weakening evidence relevance.
- ProviderTrace distinguishes exact success, `fallback_success`, empty, and
  provider error, and lists the attempted query sequence.

## Explicit non-actions

- The frozen nine-case benchmark was not run.
- Canonical runtime 8792 was not switched or restarted.
- `main` was not merged.
- No review-harness code was added or changed.
- The next external check is one `weekly-market-cause` live smoke only.
