# H-02 Trusted Permission Inheritance Repair

## Identity and Verdict

- Source: `fix/history-forward-boundary-0921@7c99f389e9c72668663449dedeacd7fe4830cbdd`, WIP #845.
- Parent: `d91aff9d8437fe903f3e643b65d4805aa4cf243c` (H-01). Original #833 remains `7edfe24e76afbd5c365fbf97dd2414847b086f88`.
- Focused operator verdict: H-02's two reproduced elliptical continuations now inherit the trusted user read ceiling, including multi-turn replay and the real run_turn entry.
- Overall historical acceptance: **CHANGES_REQUIRED**. Two adjacent input-boundary assertions remain red in the normal source. Full gates, independent final review and natural four-question acceptance are not complete.
- No merge, deployment, production backfill or external review restart was performed.

## Implementation

`ConversationMaterials` replays historical intent together with material axes from completed original user messages. Its compiler requires a present, untruncated historical chain for history permission recovery. Assistant prose is never a source of authorization. `compile_material_contract(history_continuation=...)` reuses the existing independent-axis compiler; it does not copy an arbitrary old contract.

The real orchestrator supplies this typed replay for recognized history continuations. The controller compiles it before ordinary routing; TaskFrame carries it through serialization and Episode projection. Generic pronoun history backfill must recover the same read ceiling or clarify. Injected legacy controllers cannot replace the trusted scope with a stale full frame. Explicit current-user scope changes remain supported. New tasks, cancellation and material_only reset/isolate the old research scope.

The generic backfill test with trusted typed history proves its direct-controller ceiling. It does not claim all generic natural follow-ups are supported by the real entry; absent typed replay is conservative clarification.

## Frozen Checks

Four disjoint pytest file groups on the clean fixed SHA:

| Group | Result |
| --- | --- |
| history-controller | 168 passed |
| material-honesty | 169 passed |
| history-assembly | 242 passed |
| conversation-delivery | 191 passed |
| Total | 770 passed |

The 242 group includes the 41 existing H-01 cases and 49 new H-02 cases. The separate 90-pass probe run overlaps and must not be added to 770. Whole-repository Ruff and git diff --check exited 0. Exact commands, timestamps, interpreter and before/after HEAD/status are in frozen-check-*/receipt.json.

Frozen mutation runs replace function code objects only within one process, restore in finally, use independent temp directories, and verify before/after source identities and hashes:

| Mutation | Failed / passed | Fixture or collection errors |
| --- | --- | --- |
| partition | 24 / 17 | 0 |
| history-infer | 15 / 26 | 0 |
| follow-up | 6 / 35 | 0 |
| resolution-hint | 1 / 40 | 0 |
| cutoff | 4 / 37 | 0 |
| history-contract | 42 / 7 | 0 |
| history-replay | 2 / 47 | 0 |
| history-authority | 17 / 32 | 0 |
| history-delivery | 3 / 46 | 0 |
| history-backfill | 1 / 48 | 0 |

Each killed mutant includes actual call-phase AssertionError failures. A runner's exit 0 means the expected mutant outcome was observed; it does not mean the mutated product passed.

H-01/H-02 fixtures forbid and count socket/DuckDB connection attempts. H-02 also forbids and counts unexpected llm_refine.complete calls; the intended controller is an offline substitute. The registry execution-denial tests attempt external tool dispatch but never reach their fake runners. History tools are registered, not executed. The broader 770 regression groups include temporary DB tests; do not claim all 770 perform zero DB IO.

## Unresolved Normal-Source Counterexamples

`frozen-check-adjacent-unresolved/pytest.txt`: **2 failed**, expected as retained defect evidence, not green acceptance.

- A short material lead-in followed by the elliptical succession question.
- An unclosed Chinese opening quote followed by the same question.

The existing source partition does not flag either as uncertain. Both can restore history_query. On this SHA their contract stays local_only with only memory_lookup/finance_query, the original window and cutoff; the evidence does not show external authorization or actual tool execution. Full query text and projections are in the log and `test_adjacent_input_boundary.py.txt`. No xfail or changed expectation hides these failures.

## Process Failures and Limits

- First new test collection used an incorrect import path (ModuleNotFoundError); corrected to tests.test_history_control_boundary. It is not product evidence and the original terminal traceback was not recreated here.
- Three legacy positive tests initially passed only a prior intent, with no original user chain. They now supply original user records. Missing-chain negative tests remain.
- dirty-normal-01 preserved the initial 72 passed / 2 failed discovery. Subsequent normal runs use only confirmed uncertain-boundary cases; the original two red inputs are preserved and rerun separately above, not declared fixed.
- dirty-history-delivery-01 selected the wrapper run_turn rather than _run_turn_ledgered: mutation anchor error, no valid receipt. Its empty output is kept, not invented as a product failure.
- dirty-history-delivery-02 hit the external 120-second bound (exit 124), with incomplete output and no result.json. It is invalid evidence. A legacy-controller test had no early stop when the mutation bypassed revalidation. Do not infer zero model/IO attempts for that aborted run.
- Added a stop before research-plan creation and an unexpected-model-call counter. dirty-history-delivery-03 and the frozen replacement completed with real assertions and zero errors. No background probe remained after the timeout.
- A temporary redundant `parts.regions or history_continuation` condition was withdrawn after confirming regions is always an object; it is absent from the candidate.
- Dirty runs are process evidence only. No old full-gate receipt is transferred to this source revision.

## Archive Contract

The manifest covers every regular archive member except itself. Runtime .py helpers are archived as .py.txt to prevent accidental pytest collection. candidate.patch is the exact Git diff from d91aff9d8 to 7c99f389e. Cache/temp contents are excluded. Post-publication receipts belong outside this sealed directory.

Re-run focused source checks with the workbench Python and FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1. Each command is bounded at 120 seconds; probe output directories must be new. This package is not an independent Spec/Quality report, full CI, a live-model run or joint-candidate acceptance.
