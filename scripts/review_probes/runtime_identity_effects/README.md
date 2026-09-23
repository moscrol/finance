# Runtime Identity / Effects Probe

Explicit opt-in test tool, derived from the preserved K3 probes and repaired by
Codex on 2026-09-23. This is host-authored code, not a K3 independent approval.
The two newly authorized K3 writer requests failed before any tool execution
(first request timeout, then upstream HTTP 504); their evidence is retained.

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
Only this explicit runner selects them, preventing uncontrolled mutation probes
or external-candidate environment requirements during ordinary full-tree tests.

The runner clears inherited environment credentials, disables bytecode/cache
writes, and redirects user state to each stage's temporary directory. It is not
an OS sandbox by itself. The recorded 2026-09-23 runs additionally used macOS
`sandbox-exec` to prohibit network and all writes outside the output root.

Scope is limited to identity binding and unknown-effect budget protection. It
does not certify save-failure fencing, writer contention, reentry, inbox drain,
all public projections, production billing, or a cross-process resume driver.
No runtime product source is patched by this tool.
