# Headless Budget Ablation Preregistration

Date: 2026-07-28
Status: preregistered; dry-run validated; no live ablation executed

## Question and boundary

This experiment asks whether the current Codex headless control is degraded by
two independent budget mechanisms:

1. the gateway's dynamic 65% finalization floor;
2. the six-tool-call cap after the wall-clock envelope is made long enough to
   reach a seventh call.

It does not test App Server, does not change production `ResearchPolicy`
defaults, and does not run the 28-case product board. The typed profile is
accepted only by the benchmark and only when `codex_headless` is the sole
backend.

## Frozen execution identity

- Source code revision:
  `803367f16c90cf3b0a0526d4224e4acb55a7a79d`
- Source tree requirement: clean detached checkout of that revision.
- Input cases:
  `/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json`
- Input SHA-256:
  `bec6d6944ced127166bd41cb80a09a9f9fb0d816e45cee3be13a900bda2966fe`
- Selected cases, in source order:
  `rebound-duration`, `ruihuatai-valuation`, `weekly-market-cause`.
- Finance root: `/Users/a77/finance-workspace-private`
- Wiki root for this ablation: `/Users/a77/知识库/wiki`, matching the eight
  historical headless artifacts. Phase C, not this ablation, decides which of
  the two non-alias Wiki roots becomes canonical.
- Information cutoff: each case's frozen `as_of=2026-07-24`; registry-owned
  cutoff filtering remains enabled.
- Runtime binary:
  `/Applications/ChatGPT.app/Contents/Resources/codex`
- Observed binary version: `codex-cli 0.146.0-alpha.3.1`.
- Model: `gpt-5.6-sol`.
- Transport: `local_exec` through the existing `CC_EXEC_PORT=28080` route.
- Prompt, tool registry, structural verifier, semantic verifier, data roots,
  and model settings must remain identical across A/B/C/D.
- Credentials remain ambient process state and must not enter commands,
  artifacts, or Git.

If the binary version, source revision, input hash, model, cutoff, or data roots
do not match, stop before A rather than silently updating this preregistration.

## Deriving `T_long`

The ten observed inter-result intervals recorded from the historical
`0d260bda`, `4b9730a3`, and `4a2fb783` traces were:

```text
9.04  8.72  7.81  6.15  5.89  8.60  6.98  9.52  7.90  8.56 seconds
```

Their mean is 7.917 seconds and inclusive p90 is 9.088 seconds. The conservative
exercise envelope is:

```text
10s initial model/tool setup
+ 12 × 9.088s p90 inter-result time
+ 30s delivery and semantic-verification reserve
+ 10s transport/scheduling jitter
= 159.056s
```

Because 159.056 seconds is not safely below 150 seconds, `T_long` is frozen at
180 seconds. This is a diagnostic envelope, not a proposed product SLA.

## Frozen profiles

| ID | Total | Tool calls | Synthesis reserve | Gateway ratio | Exercise condition |
|---|---:|---:|---:|---:|---|
| `a_control` | 90s | 6 | 30s | 0.65 | current control |
| `b_floor_ablation` | 90s | 6 | 30s | 0.0 | A→B isolates dynamic floor; 5s minimum delivery buffer remains |
| `c_long_capped` | 180s | 6 | 30s | 0.0 | B→C isolates wall-clock room at six calls |
| `d_long_expanded` | 180s | 12 | 30s | 0.0 | C→D isolates call cap; at least 7 observed calls required |

The code records the exact profile in every artifact. For D, fewer than seven
observed tool calls produces `budget_ablation_validity =
invalid_not_physically_exercised`; it must not be interpreted as an answer
quality failure.

## Frozen live artifact paths

```text
/Users/a77/.finance-runtime/evals/headless-budget-ablation-2026-07-28-a-control.json
/Users/a77/.finance-runtime/evals/headless-budget-ablation-2026-07-28-b-floor-ablation.json
/Users/a77/.finance-runtime/evals/headless-budget-ablation-2026-07-28-c-long-capped.json
/Users/a77/.finance-runtime/evals/headless-budget-ablation-2026-07-28-d-long-expanded.json
```

Run sequentially in A→B→C→D order. Do not inspect and tune prompts, cases,
tools, or gates between cells. A single bounded confirmation run is allowed
only if the first result would change the product decision; its filename must
end in `-confirmation.json` and reuse this exact contract.

## Frozen command shape

For each cell, set these non-secret environment values:

```text
CODEX_HEADLESS_TRANSPORT=local_exec
CODEX_HEADLESS_BIN=/Applications/ChatGPT.app/Contents/Resources/codex
CODEX_HEADLESS_MODEL=gpt-5.6-sol
PYTHONDONTWRITEBYTECODE=1
```

Then invoke `scripts/run_agent_runtime_benchmark.py` with:

```text
--backend codex_headless
--headless-budget-profile <profile-id>
--case rebound-duration
--case weekly-market-cause
--case ruihuatai-valuation
--questions-file /Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json
--finance-root /Users/a77/finance-workspace-private
--knowledge-wiki /Users/a77/知识库/wiki
--output <the frozen path above>
```

## Measurements and pairwise interpretation

For each case/cell, record from the immutable artifact and diagnostics:

- intended next tool admitted or rejected, including rejection reason;
- total tool calls and useful evidence gained per call;
- repeated same-tool request rate;
- duplicate query/content rate;
- unique evidence hashes per call;
- output bindings, structural status, semantic status, and public status;
- latency, unsupported claims, directness/usefulness under blind review;
- whether research continued after sufficient evidence was already present.

Interpret only the preregistered pairwise differences:

| Observation | Interpretation |
|---|---|
| B improves over A | dynamic 65% floor/double reservation is causal |
| C improves over B | wall-clock room matters while call cap stays fixed |
| D improves over C | six-call cap is independently causal |
| D adds repeated calls without unique evidence or quality | tool-result quality or finish/progress judgment is primary |
| D observes fewer than 7 calls | D is invalid; enlarge only the diagnostic envelope |
| only long profiles help | product needs explicit quick/deep latency modes |
| valuation stays useful but flips completed/partial | completion contract/verifier is misaligned with answer quality |
| no profile improves material quality | repo discovery/generic harness remains a stronger App Server hypothesis |

Truth failures—future data, unsupported numbers, missing lineage, or leaked
control data—cannot be offset by improved prose.

## Dry-run proof

Four non-live plan artifacts were generated from the clean frozen revision.
All contain exactly the three selected cases and
`budget_ablation_validity=not_executed`:

| Profile | Plan artifact SHA-256 |
|---|---|
| A | `e3e284aef0c199444f34d904f6f2b24270201438d4ddd62203f6ce0c90231739` |
| B | `c6773e9e6ccd359e2cbc655c22def31aa36abefa5a081dd6dfa8a0a067251abe` |
| C | `779443f60dff8d0049d3611ffee60a0ffb13d16c07e212032587e8c02ac6d172` |
| D | `d62cad2aea6ce67185badb7c80c037c3f860f9857eb5075bf6a1818426664d03` |

This proves the experiment is executable and recorded, not that any budget
hypothesis is true. No live output has been observed.

## Phase C entry

After the preregistered A/B/C/D run is interpreted—or if a later owner elects
to defer live headless spend—Phase C begins with evidence identity, not a new
tool:

1. select and pin one canonical Wiki root, proving the two roots are not aliases;
2. generate a pinned dry-run contract artifact with allowed capabilities;
3. directly replay `evidence_search` for 瑞华泰 and the weekly causal query;
4. separate index recall, cutoff filtering, result latency, model selection,
   and completion-contract disagreement.

No App Server implementation is authorized at this boundary.

