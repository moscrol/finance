# Deep Sub-Research Branches Verification

Date: 2026-07-27  
Branch: `feat/agent-runtime-backends-verify`  
Final product commit: `6692926c`

## Result

An approved deep `ResearchPlan` may now request up to three explicit
`branch_goals`. Branches run through one bounded coordinator, inherit the
parent ContextVar state, consume the same root ledger, and return only public
evidence/traces/gaps. The primary episode remains the sole final-answer owner.

Product commits:

- `717cc8a8` — branch-facing append-only evidence facade;
- `c41807d5` — optional model-owned `branch_goals` plan state;
- `fb776193` — bounded, failure-isolated coordinator and child budget views;
- `2b32e686` — continuous branch worker and same-history primary integration;
- `6692926c` — Continuous GLM input/output token accounting, including branch
  calls.

## Invariants proved

- branch facade exposes `append()` and `snapshot()` only;
- branch evidence cannot close/open a primary gap or mark output coverage;
- first-writer branch ownership is retained per evidence hash;
- only an approved deep decision can execute branch goals;
- zero to three goals are allowed; duplicates execute once; four are refused;
- child budget views cannot grant or promote themselves;
- all tool/time consumption debits the one parent root ledger;
- worker-reported tool usage is ignored in favor of actual ledger consumption;
- branch threads inherit parent ContextVars, preserving the global LLM-call
  ledger and provider overrides;
- an expired parent deadline launches zero branches;
- one branch failure does not remove another branch's evidence;
- branch draft prose and internal errors never enter the primary answer;
- the same primary message history receives sanitized `SUB_RESEARCH_RESULTS`;
- branch/model token usage is measurable when the provider reports it and
  remains unknown rather than zero when the provider does not.

## Verification

Focused branch/mode/episode/adapter/permanent-invariant suites:

```text
232 passed in 0.85s
51 passed, 2 skipped in 8.93s
```

Token/runtime suites:

```text
211 passed in 1.57s
```

Full deterministic `intelligence/tests` suite:

```text
2818 passed, 2 skipped, 11 failed in 199.97s
```

The same 11 local `subconscious/userspace` failures remain. Their assertions
are polluted by the machine's shared Agent Memory paths and accumulated live
records; none touches the changed branch, episode, budget, GLM, or diagnostic
modules. Ruff and `git diff --check` passed on every changed slice.

## Non-actions

- no frozen nine-case live benchmark;
- no MemoryGate in this milestone;
- no UI/canonical canary switch;
- no 8792 restart;
- no `main` merge;
- no review-harness modification;
- no Claude review before the complete approved target is ready.

## Alignment compliance

`ALIGNMENT.md` S6 is now enforced by construction: a branch never receives the
full `EvidenceLedger`. Provider traces, structural partial reasons, cutoff
rejections, mode decisions, branch events, repair IDs, and Continuous token
usage are all available to the final audit without exporting prompts, messages,
SQL, secrets, or local paths.
