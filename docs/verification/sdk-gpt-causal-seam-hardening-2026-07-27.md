# SDK-GPT Causal Seam Hardening

Date: 2026-07-27

Branch: `feat/agent-runtime-backends-verify`

Verified tip: `ed2e1d89`

Canonical 8792 and `main`: untouched.

## Why this slice exists

The frozen causal canary `这一周行情下跌的主要原因是什么` failed at run
`run_20260727_213048_327023`. The failure was not missing market evidence:

- the Episode had nine evidence atoms;
- the evidence corrected the premise: 2026-07-20 through 2026-07-24 was
  approximately `+0.47%`, with only one down day;
- the last trading day was approximately `-1.61%`, while weekly turnover fell
  approximately `28.37%`;
- the task cutoff rejected fourteen future-dated news results.

The failure was delivery control. Reworded searches returned the same news
again, the initial SDK turn timed out before producing bindings, and two
tool-closed delivery repairs entered with the same logical cycle because only
successful repairs consumed the cycle counter.

## Shared-seam changes

### Evidence novelty at the model boundary

`_AgentsRunState._publish_observation` now returns only content hashes that are
new to the current Episode. A provider result whose evidence is already in the
Episode returns `status=duplicate_evidence`, an empty evidence payload, and a
bounded instruction to change evidence type or finish from existing evidence.

ProviderTrace remains `success` when the provider call itself succeeded.
Evidence novelty is recorded on the tool-result event; provider health and
evidence novelty are deliberately separate observability dimensions.

### One repair owner

Invalid SDK finish output no longer starts a hidden model retry inside
`OpenAIAgentsRuntime._run_episode`. It returns `sdk_invalid_finish`; the
`ContinuousTurnAdapter` then creates the same explicit `RepairGoal` used by
structural, semantic, timeout, and coverage gaps.

`repair_attempts` counts admitted work and enforces the tier cap. The historical
`repair_cycles` field remains the narrower count of successful repairs. A grant
therefore consumes an attempt even when the provider times out or the repair
finish is invalid.

### Delivery versus research continuation

A tool-closed delivery repair:

- receives zero tool calls;
- may use at most 30 seconds;
- may be admitted only once per Episode;
- uses GPT low reasoning with medium verbosity only when the caller did not
  supply explicit model settings.

Deep research is not globally stopped by `sdk_timeout`. If a tool-enabled
repair added independent evidence and covered a new required output, the ledger
progress predicate may admit the next deep cycle. A delivery timeout adds no
coverage, so it cannot loop.

## Independent review closure

The two-axis review raised four material questions:

1. hidden invalid-finish recovery bypassed the shared cycle pool — fixed by
   deleting the private retry and adding an Adapter-level RepairGoal test;
2. terminalizing every SDK timeout would suppress valid deep progress — fixed
   by separating one-shot delivery repair from tool-enabled research repair;
3. default delivery settings could overwrite caller-supplied settings — fixed
   and covered by a parameterized request-boundary test;
4. duplicate evidence retained a successful ProviderTrace — intentionally
   retained because the provider succeeded; the tool-result novelty status is
   the correct audit field.

No verifier threshold, route, skill, output template, or review harness was
added or loosened.

## Deterministic verification

- Modified runtime modules: `83 passed, 1 skipped`.
- Episode, verifier, RunStore, SSE, and Workbench API combination: `449 passed`.
- Clean full `intelligence/tests`: `2919 passed, 2 skipped`.
- Ruff: passed.
- `git diff --check`: passed.
- Secret/large-file pre-commit gates: passed.

The clean full-suite command unsets production-only path overrides
`FORESIGHT_USERS_DIR`, `SUBCONSCIOUS_VAULT`, and `AGENT_MEMORY_VAULT`; no test
or product acceptance rule was relaxed.

## Runtime boundary

Port 8799 still serves revision `4842292b` with a session-only SDK-GPT
credential. Restarting is required to load `ed2e1d89`, and restart intentionally
clears the session credential. Per the user instruction, live work is deferred
instead of stopping for another credential prompt.

Therefore this slice is deterministic-green but not live-release-green. Do not
switch 8792, merge `main`, or claim Codex/Knevo parity. The next provider-ready
action is exactly one replay of the causal canary on `ed2e1d89`, followed by
artifact inspection; it is not another repeated multi-question batch.
