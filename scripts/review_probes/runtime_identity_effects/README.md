# Runtime Identity / Effects Probe

Explicit opt-in test tool, derived from the preserved K3 probes and repaired by
Codex on 2026-09-23. This is host-authored code, not a K3 independent approval.
The first two K3 writer attempts failed before any tool execution
(first request timeout, then upstream HTTP 504); their evidence is retained.
A subsequent K3 writer session authored `probe/inbox_checks.py` and ran its six
baseline cases successfully. That session hit its deadline before completing
mutations or a final report. The file is preserved unchanged; host acceptance
and the K3 session's incomplete self-check are separate records.

Run using the project interpreter, an exact clean candidate checkout, and a new
output directory outside that checkout:

```bash
/path/to/project/.venv-workbench/bin/python -B \
  scripts/review_probes/runtime_identity_effects/run_checks.py \
  --candidate /path/to/clean/candidate \
  --expect-revision FULL_COMMIT_SHA \
  --output /path/to/new/output
```

The runner performs four subprocess stages:

| Stage | Expected Result |
| --- | --- |
| Baseline | 16 passed |
| Identity guard removed in memory | 7 named failures, 4 positive controls passed |
| Budget guard removed in memory | 2 named failures, 3 controls passed |
| Restored baseline, fresh process | 16 passed |

A failure only counts if its exact test name matches and pytest reports
`Failed: DID NOT RAISE`. Collection/import/setup errors, timeouts, survivors,
unexpected failures, skips, and a changed denominator fail the run. Existing
output directories are rejected; logs/JUnit/commands/input hashes are retained.

Mutation targets must match source text exactly once. Shadow modules register
before dataclass evaluation, use their own exception type, and never replace the
real modules. Identity and budget mutations have independent selectors.

The fixtures distinguish a valid but wrong owner (`RestoreUnavailable`) from
an internally inconsistent episode identity (`ValueError`). Both must leave the
persisted event/checkpoint/budget bytes unchanged; `.writer.lock` is excluded.
This does not establish the complete exception contract of every caller.

`probe/*_checks.py` are intentionally outside pytest's default filename pattern.
Explicit runners select them, preventing uncontrolled mutation probes or
external-candidate environment requirements during ordinary full-tree tests.

The runner clears inherited environment credentials, disables bytecode/cache
writes, and redirects user state to each stage's temporary directory. It is not
an OS sandbox by itself. The recorded 2026-09-23 runs additionally used macOS
`sandbox-exec` to prohibit network and all writes outside the output root.

Scope is limited to identity binding and unknown-effect budget protection. It
does not certify save-failure fencing, writer contention, reentry, inbox drain,
all public projections, production billing, or a cross-process resume driver.
No runtime product source is patched by this tool.

## Additional Contract Replays

`../run_runtime_contract_checks.py` reuses the repository's committed mutation
runner, with sandboxed pytest processes and stricter named-witness checks:

```bash
/path/to/project/.venv-workbench/bin/python -B \
  scripts/review_probes/run_runtime_contract_checks.py \
  --candidate /path/to/clean/candidate \
  --expect-revision FULL_COMMIT_SHA \
  --group inbox \
  --output /path/to/new/output
```

Groups: `runtime` (save failures, truncation, terminal delivery), `writer`
(process ownership and drain), `reentry` (runner ownership), `inbox` (the six
K3-authored spool cases). Each group gets a separate output directory. The
candidate must contain the selected committed definitions and tests.

All mutation anchors and compilation are checked before test execution.
Mutations only touch disposable worktrees under output, never the candidate.
Each selected target must have a named failure; missing tests, collection
errors, unrelated exceptions and survivors are rejected. The required
`_finish_reason` key has one exact, test-scoped KeyError witness, not a blanket
exception allowance. Inbox drain must fail because close returned too soon,
not because an instrumented lock hook disappeared.

This command requires macOS `sandbox-exec`: network and writes outside output
are denied, credentials are not inherited, and each stage gets a fresh user
root. Tests and their children are terminated as a process group on timeout;
raw output survives even without JUnit. Existing output is never overwritten.
`inbox` uses a directory-permission fault and must run as a non-root user.

The spool test demonstrates at-least-once delivery in an injected unlink-failure
window, not exactly-once delivery or a complete process-restart driver. These
host replays do not turn the historical K3 independent verdict into PASS.
