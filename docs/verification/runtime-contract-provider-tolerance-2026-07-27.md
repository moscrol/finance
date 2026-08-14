# Runtime Contract and Provider Tolerance Verification

Date: 2026-07-27

Branch: `feat/agent-runtime-backends-verify`

Product commits:

- `af395f81` — initial answer-element floor and monotonic plan revisions
- `27fc5d50` — configured legacy deep ceiling raised from 8 to 24
- `9163a143` — bounded Eastmoney natural-query fallback
- `6e3ba053` — post-smoke correction: natural initial plans plus balanced reserve
- `f4f6fc9d` — safe benchmark diagnostics projection
- `80af2878` — provider-compatible FinanceQuery schema and cutoff-aware news
- `c327395d` — natural semantic metric alias normalization
- `06b8285c` — deterministic research timeout policy in the A/B runner

## Result

The pre-Phase-3 seams from the independent review are closed and the previously
opaque live failure is now attributable from one artifact. The model still owns
hypotheses, candidate actions, query wording, tool order, and when to stop. Code
owns only the immutable minimum task, budget ceiling, provider adaptation,
information cutoff, and audit truth.

## Verification

```text
234 focused tests passed
26 invariant regression tests passed
Full suite: 2775 passed, 2 skipped, 11 known userspace/subconscious failures
Ruff passed
git diff --check passed
```

The focused suite covered semantic finance queries, Eastmoney market news, the
legacy `agent_research` loop, the continuous Episode, turn adapter, benchmark
contract, runner integration, and the permanent repair/session invariants.

## Observed behavior

- An initial plan may express answer elements in natural model-owned language.
  A revision may add elements but cannot remove a previously published element;
  final task coverage remains independently enforced by the immutable contract.
- `ASK_AGENT_MAX_STEPS=24` now yields 24; 25 clamps to 24, zero clamps to one,
  and invalid/unset values preserve the default of four. No task is promoted to
  deep mode by this change.
- `上周A股下跌原因` attempts the exact query, then narrower provider-compatible
  candidates. `低空经济 商业航天` attempts each explicit keyword and merges
  distinct results. Duplicate URL/title entries collapse deterministically.
- Eastmoney fallback is bounded, shares one timeout, and does not retry a
  provider request/parse error. The title-contains-keyword relevance gate is
  unchanged.
- The first live smoke exposed a 75/15 synthesis-to-research split on a 90
  second standard task. The composition root now caps synthesis reserve at
  two-thirds of the effective timeout, leaving at least one-third for research.
- `RuntimeArmResult.diagnostics` exports bounded tool events, ProviderTrace,
  invalid-action reasons, structural gaps, bindings, cutoff rejection, and the
  final root budget. It removes prompts, messages, internal SQL/schema/table,
  local paths, and secret-bearing keys or values.
- The provider-facing `finance_query` schema is one orthogonal semantic object
  instead of six large top-level `oneOf` branches. Dataset-field compatibility
  and physical query compilation remain code-owned and fail-closed. Natural
  `limit_up_count`/`limit_down_count` names are normalized to equivalent
  `market_daily` semantic fields before compilation.
- `news_search` receives the Episode's immutable information cutoff. Historical
  queries use bounded pagination, discard future items before model context,
  and retain the title relevance gate. Spaced causal queries preserve a narrow
  `主体+方向` candidate before falling back to a broad subject.

## Live smoke diagnosis

Question: `这一周行情下跌的主要原因是什么`

Input: `/Users/a77/.finance-runtime/evals/weekly-market-cause-smoke-input.json`

Before the proven fixes (`r3`):

```text
artifact: weekly-market-cause-smoke-2026-07-27-r3.json
status: partial / structural partial / semantic repaired
latency: 66.47s
llm/tool/invalid: 4 / 6 / 1
stop: semantic_repair
```

The diagnostic artifact proved that `finance_query` was selected with an empty
argument object, Eastmoney returned only post-cutoff first-page items, one tool
call was wasted, and the six-call initial budget reached the eight-call hard
cap without closing the causal gap.

After the fixes (`r4`):

```text
artifact: weekly-market-cause-smoke-2026-07-27-r4.json
status: partial / structural partial / semantic passed
latency: 50.56s
llm/tool/invalid: 3 / 6 / 0
provider attempts: 4
stop: model_finish
future_of_cutoff: 0
mandatory missing capabilities: 0
```

The answer is no longer a generic evidence-gap template. It first checks the
user premise against structured data: 2026-07-20 through 2026-07-24 was up
0.47%, while 2026-07-24 alone fell 1.61% amid a roughly 28% weekly contraction
in turnover. It then separates verified market facts from public-web candidate
causes and reports the remaining same-window causal evidence gap.

`partial` is correct for this frozen cutoff because two causal outputs still
lack same-window hard evidence. The artifact also exposes an answer-changing
ambiguity: if the user intended 2026-07-13 through 2026-07-17 rather than the
latest completed week, one clarification or explicit assumption is required.
This becomes an input to Phase 3 ModeGovernor/AmbiguityResolver work rather than
another deterministic intent route.

Token counts for `continuous_glm` remain unavailable and are still a Phase 3
delivery-contract item; no claim about attention cost is made from this smoke.

## Explicit non-actions

- The frozen nine-case benchmark was not run.
- Canonical runtime 8792 was not switched or restarted.
- `main` was not merged.
- No review-harness code was added or changed.
- No frozen nine-case benchmark was used as a development loop.
- No further live rerun was made after the final metric-alias normalization;
  that narrow compatibility change is covered deterministically.
