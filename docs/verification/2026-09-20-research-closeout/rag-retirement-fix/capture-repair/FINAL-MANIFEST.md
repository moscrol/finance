# Final managed capture repair evidence

- Spec-failed candidate: `bc43ece9fc0550663645c2e8c57d57d7618b8e0d`
- Repaired code: `cb4bbf1ce6cd9b1af4b71dcbb13668877dbc54be`
- Final docs/head: `c4f33c5bcd6835bcc9b15536dc2d0eb1bf6f1279`
- Branch: `fix/rag-retirement-closeout-0920`
- Scope added after `MANIFEST.md`: residual filesystem failures inside an already complete managed binding, plus an interpreter entry whose `resolve(strict=True)` raises `RuntimeError` because of a symlink loop. No startup protocol changed, so the earlier full real scratch was not rerun.

## Final verification

- Sanitized external consumer probe: `final-consumer-cb4bbf1c-summary.log.txt` = `bfb94aa3bce5e5c9a8e413d4c0b8cbbecf5444cc553dd49310e15bc548c86a10`, 2 passed. It used `env -i` with only HOME, PATH, LANG, TMPDIR, FWP_TEST_RECEIPT=0, PYTHONDONTWRITEBYTECODE=1 and PYTHONPATH.
- Repository receipt: `final-directed-cb4bbf1c.log.txt` = `18aa92fcfc69b9b335206368fc0e60f51b44c9ccb9826697be757ac67a5e5b7c`, 121 passed; related Ruff passed.
- Exact pytest selection: `test_rag_worker_generation.py`, `test_rag_worker.py`, `test_rag_worker_keepalive.py`, `test_kb_runtime_roots.py`, `test_kb_filter_receipt.py`.
- The managed permission-error fixture is classified as `managed_identity_io_error`; its legacy counterpart remains `PermissionError`. The interpreter symlink-loop fixture reaches real `kb_rag.retrieve`, is classified as `interpreter_replaced`, and records zero CLI calls. Ordinary worker protocol fallback remains covered.

## Retained intermediate receipt

`final-directed-8d50a333.log.txt` = `e796dec67728ea7d48f4960000f5797bec7f6fad183339c9e73b802be674c1a8` records 1 failed / 119 passed because the keepalive assertion observed its asynchronous counters between updates; Ruff passed. The unchanged command rerun, `final-directed-8d50a333-attempt2.log.txt` = `d3bf7cea9be9898fdc901445d265314f5bcd822c505c98541c94be23c853b9ef`, records 120 passed and Ruff passed. Both are retained rather than rewriting the first result.

The outer managed fence catches only `OSError`; arbitrary programming errors are not swallowed. `RuntimeError` is caught only at the interpreter path resolution operation. Legacy permission errors and ordinary protocol failures preserve their prior fallback behavior.
