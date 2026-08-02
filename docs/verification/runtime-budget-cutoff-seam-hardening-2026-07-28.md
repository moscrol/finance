# Runtime Budget and Cutoff Seam Hardening Verification

Date: 2026-07-28
Baseline: `69f9cf17cadbe750aea03d5858d1b30f5af3b21d`
Branch: `feat/agent-runtime-backends-verify`

## Scope

This batch repairs shared continuous-runtime seams exposed by the frozen
five-case SDK-GPT benchmark. It does not add question-specific routes, modify
the canonical 8792 runtime, switch 8799, merge `main`, or change private data.

## Implemented invariants

1. Raw SDK/headless benchmarks retain a 30-second semantic-verifier reserve
   and receive 60 seconds of standard research budget.
2. Production SDK/headless Adapters use the existing outer verifier reserve
   and an explicit zero inner synthesis reserve; continuous GLM keeps its
   internal-finalizer policy.
3. Every Episode model input contains the immutable `information_cutoff`.
4. Market, cause-window, mainline, and valuation providers select real rows at
   or before the cutoff instead of selecting the latest row and filtering it
   afterwards.
5. A known future realtime valuation snapshot is not requested in a frozen
   episode; the local cutoff-date market-cap anchor is used and unavailable
   historical multiples remain explicit gaps.
6. Only the user-owned `TaskFrame` can authorize a historical FinanceQuery.
7. Saved provider credentials are read through Security.framework rather than
   a three-second `/usr/bin/security` subprocess.

## Deterministic real-data replay

Using the frozen 2026-07-24 cases with local data metadata at 2026-07-27:

- rebound: `market_data` served 2026-07-24 with 16 evidence atoms;
- weekly cause: `market_data` served 2026-07-24 with 8 evidence atoms;
- current mainline: `market_data` and `mainline_context` both served
  2026-07-24; mainline returned 7 atoms;
- all three FinanceQuery replays served rows ending 2026-07-24;
- valuation served 3 evidence atoms dated 2026-07-24, used the local market-cap
  anchor, contained no 2026-07-27 evidence, and made no unusable live request;
- each SDK context reported a 60-second root research budget.

## Tests

```text
Focused runtime/protocol/tool/API suite: 189 passed
Continuous Adapter + answer/conversation orchestrators: 179 passed
Executable full suite: 2916 passed, 1 skipped
```

The executable full suite excludes only:

- `test_codex_headless_runtime.py`
- `test_headless_tool_gateway.py`

Those files bind ephemeral localhost ports. The current Codex sandbox rejects
all socket binds with `PermissionError: [Errno 1] Operation not permitted`.
Running the unfiltered suite produced 13 socket-only failures plus passing
results elsewhere after unsetting the host-level `FORESIGHT_USERS_DIR` that
otherwise invalidates userspace test isolation.

Static validation:

- `git diff --check`: pass;
- changed modules excluding the pre-existing large `ask_blocks.py` F401 set:
  Ruff pass;
- `ask_blocks.py` and its tests: Ruff undefined-name/syntax selectors pass.

## Two-axis review

### Standards

No hard repository-standard violations found. The batch preserves the read-only
tool contract, uses parameterized DuckDB queries, keeps credentials out of argv
and artifacts, and adds no risk files. The main judgement-call smell is that
`ask_blocks.py` remains a broad legacy module; this batch deepens existing
interfaces with optional `as_of` rather than introducing another wrapper or
performing unrelated refactoring.

### Spec

All seven acceptance items in
`2026-07-28-runtime-budget-cutoff-seam-hardening-design.md` are implemented and
covered by deterministic tests. Self-review found and repaired two initially
partial items before freeze:

1. `callback=None` still inherited the default 20-second inner reserve in the
   production SDK path; it now receives an explicit zero reserve.
2. Frozen valuation discarded future snapshots only after requesting them; it
   now skips requests known in advance to be unusable.

Historical PE/PB is still unavailable in the local database. The implementation
reports that gap rather than deriving or relabeling future multiples, matching
the fail-closed requirement.

## Release discipline

The live five-case SDK-GPT benchmark is allowed exactly once after this
document is committed and the revision is clean. Its JSON artifact remains
outside Git. A runtime switch or merge requires a separate decision after the
hard benchmark gate is inspected.
