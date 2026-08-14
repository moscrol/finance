# Headless Local-Exec Loopback Seam Verification

Date: 2026-07-29
Status: shared transport defect fixed; original A/B/C/D artifacts invalidated

## Failure evidence

The first live A/B/C/D execution produced twelve identical protocol failures:

```text
tool_calls=0
stop_reason=headless_protocol_rejected
gaps=[headless_command_failed]
protocol_issues=[runtime_invalid_actions:1]
```

A single-case captured Codex JSONL repro proved that the model selected the authorized
`finance-tool` wrapper. The wrapper failed before reaching `HeadlessToolGateway` because the
nested Codex `read-only` sandbox rejected `socket.connect(127.0.0.1, gateway_port)` with
`PermissionError: [Errno 1] Operation not permitted`.

Therefore the four budget profiles did not exercise any budget mechanism. Their artifacts are
valid failure receipts but invalid evidence for A→B→C→D quality interpretation. Profile D is
also mechanically `invalid_not_physically_exercised` with zero observed calls.

## Least-privilege probe

The exact local binary `codex-cli 0.146.0-alpha.3.1` was tested with:

```text
--sandbox workspace-write
-c sandbox_workspace_write.network_access=true
-c sandbox_workspace_write.exclude_tmpdir_env_var=true
-c sandbox_workspace_write.exclude_slash_tmp=true
```

Observed inside the child sandbox:

```text
CWD_WRITABLE True
SIBLING_WRITABLE False
FINANCE_WRITABLE False
KB_WRITABLE False
LOOPBACK_ERROR HTTPError HTTP Error 401: Unauthorized
```

The 401 is the expected unauthenticated application response and proves TCP/HTTP reachability.
Only the ephemeral run directory is writable; sibling temp, finance, and Wiki roots remain
read-only. No `danger-full-access`, `--add-dir`, credential copy, or global config mutation is
used.

## Implementation

For `local_exec` only, `CodexHeadlessRuntime` now uses the least-privilege configuration above.
Subprocess transport keeps its existing workspace-write behavior and does not receive the
network override.

The public command seam has a regression test that requires all three config flags and rejects
dangerous sandbox bypass or extra writable roots.

## Verification

RED before implementation:

```text
test_local_exec_command_enables_loopback_without_widening_tmp_roots
expected workspace-write, observed read-only
```

GREEN after implementation:

```text
46 passed, 1 skipped
Ruff: passed
git diff --check: passed
```

The original live single-case repro then executed `market_data` successfully:

```text
tool_calls=1
provider trace=market_data/success/16 results
gaps=[headless_timeout]
```

`headless_timeout` is now a genuine profile-A budget outcome, not a gateway transport failure.

## Experiment consequence

The first four live artifacts must not be overwritten or interpreted as the preregistered
budget experiment. A new preregistration amendment must pin the fixed source revision and new
output paths before rerunning A→B→C→D.
