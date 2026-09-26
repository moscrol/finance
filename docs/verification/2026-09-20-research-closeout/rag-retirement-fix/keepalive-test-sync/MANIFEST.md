# Keepalive test synchronization evidence

- Spec PASS candidate: `c4f33c5bcd6835bcc9b15536dc2d0eb1bf6f1279`
- Frozen production code: `cb4bbf1ce6cd9b1af4b71dcbb13668877dbc54be`
- Test synchronization commit: `292d78f3afe1513725eb91baa5e65d6ab554ec9d`
- Final docs/head: `ad839d2e0254061a6c7c6a562cec365f2186671f`
- Branch: `fix/rag-retirement-closeout-0920`

The test now waits within the existing `_wait_until` 3-second deadline until both `keepalive_sent >= 2` and `queries_served >= 3`. It retains the PID, model-load count, served count, timeout count, and ready-state assertions. No production counter, timeout, sleep, or service code changed.

## Verification

- Receipt: `final-directed-292d78f3.log.txt` = `a423d439b34fc04d543cbc40d73486d9656a618c3873c9b0f1c833931243c402`.
- The receipt starts and ends at `292d78f3afe1513725eb91baa5e65d6ab554ec9d`.
- Exact pytest modules: `intelligence/tests/test_rag_worker_keepalive.py`, `intelligence/tests/test_rag_worker.py`, and `intelligence/tests/test_rag_worker_generation.py`.
- Result: 85 passed; Ruff passed for the same three files.
- Every test process used `env -i` with only HOME, PATH, LANG, TMPDIR, FWP_TEST_RECEIPT=0, PYTHONDONTWRITEBYTECODE=1, and PYTHONPATH.
- `git diff --quiet cb4bbf1ce6cd9b1af4b71dcbb13668877dbc54be..ad839d2e0254061a6c7c6a562cec365f2186671f -- intelligence/services` exited 0, confirming no production service diff after the frozen code commit.

The earlier flaky receipt remains under `capture-repair/` unchanged. No real scratch, full repository, frontend, production index, BGE, network, port 8792, launchd, PR, merge, or deployment was run.
