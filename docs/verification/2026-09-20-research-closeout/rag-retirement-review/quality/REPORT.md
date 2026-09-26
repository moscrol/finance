# PersistentRagWorker generation retirement · Quality review

## Verdict

**QUALITY FAIL** at `ad839d2e0254061a6c7c6a562cec365f2186671f`.

One approved runtime-damage boundary is still open: after a managed worker has captured its interpreter identity, a downstream interpreter symlink can become a loop while the pinned entry inode remains unchanged. The read-only status path then raises a bare `RuntimeError` instead of reporting `failed / interpreter_replaced`.

The keepalive test synchronization itself is sound and did not weaken its oracle. The targeted existing suite is green, but it does not cover the failing post-capture symlink-chain shape.

## Findings

### P1 · Runtime interpreter-chain loop escapes managed classification

- Location: `/Users/a77/fwp-wt-rag-retirement-closeout-0920/intelligence/services/rag_generation_identity.py:191`; its handler at line 197 catches only `OSError`.
- Trigger: capture a valid managed interpreter shaped as `venv/bin/python -> venv/bin/python3 -> host-python`; then replace only `python3` with a self-loop. The pinned `python` entry inode is unchanged, so `_check()` reaches `path.resolve(strict=True)`, which raises `RuntimeError` on the loop.
- Observed result: `PersistentRagWorker.status()` raises `RuntimeError: Symlink loop ...`; it does not return a failed generation state. Aggregate readiness can therefore error instead of becoming non-ready. The same unchecked `_check()` is also used by keepalive/recovery gates.
- Contract impact: runtime interpreter corruption must be recognized by the small read-only status check before new work, without spawn/kill/model/index activity, and must map to the dedicated managed-generation failure boundary.
- Narrow repair: at this specific runtime `python_entry.resolve(strict=True)` operation, classify `(OSError, RuntimeError)` as `interpreter_replaced`, matching the already-correct capture-time handling at lines 331–334. Do not add a broad outer `RuntimeError` catch.
- Required regression: preserve the red probe shape and assert `status()` returns `state=failed`, `active=false`, `generation_status=invalid`, `generation_reason=interpreter_replaced`; also assert no spawn/kill/recovery.

Evidence:

- Probe: `probes/post_capture_interpreter_chain_loop.py`, SHA256 `d3e5016024b15407ade0f90546537e8b0ed91a15ab6630fc77812b0b1574da94`
- Red log: `probes/post_capture_interpreter_chain_loop.log`, SHA256 `adc8d1c0c96a206af86b253a70d5b797c6c9ed1bdbd83f19b8413b9b0200b967`
- Result: exit `2`, JSON outcome `exception`, type `RuntimeError`.

### P2 · Managed-launch unit test does not assert the executable argv

- Location: `/Users/a77/fwp-wt-rag-retirement-closeout-0920/intelligence/tests/test_rag_worker_generation.py:208-222`.
- The test asserts that `worker.python` retains the entry path and checks the spawned environment, but it never checks `Popen` argv. A regression from `self.python` to `Path(self.python).resolve()` at launch could pass this unit test.
- Add a direct assertion that the first spawned argv element is the pinned venv entry. A chained-symlink fixture would lock the reason for this contract. This is a regression-strength gap; the current production launch at `rag_worker.py:386` is correct, and the preserved real scratch evidence previously exercised it.

## Keepalive oracle review

Commit `292d78f3afe1513725eb91baa5e65d6ab554ec9d` changes only the wait predicate in `test_keepalive_touches_an_idle_warm_worker_without_reloading`.

- Production increments `keepalive_sent` before `_serve`, while `queries_served` increments only after a complete response. Waiting for both `keepalive_sent >= 2` and `queries_served >= 3` removes the observed race.
- The original three-second `_wait_until` deadline remains.
- PID, model-load count, served count, timeout count, and final state assertions remain unchanged.
- `cb4bbf1c...ad839d2e -- intelligence/services` is empty, so the synchronization did not alter production code.

Conclusion: **keepalive synchronization PASS; oracle strength preserved**.

## Independent checks

All subprocesses used this clean environment only: `HOME`, `PATH`, `LANG`, `TMPDIR`, `FWP_TEST_RECEIPT=0`, `PYTHONDONTWRITEBYTECODE=1`, and `PYTHONPATH`. The interpreter was `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`; pytest used `-p no:cacheprovider`. No network, model, BGE, production index, 8792, launchd, or KB mutation was used.

Targeted test command:

```text
env -i HOME=<quality/home> PATH=/usr/bin:/bin:/usr/sbin:/sbin LANG=C.UTF-8 TMPDIR=<quality/test-tmp> FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/a77/fwp-wt-rag-retirement-closeout-0920 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -p no:cacheprovider -q intelligence/tests/test_rag_worker_keepalive.py intelligence/tests/test_rag_worker.py intelligence/tests/test_rag_worker_generation.py --basetemp=<quality/test-tmp/pytest-85> --junitxml=<quality/pytest-rag-targeted.xml>
```

Actual result: **85 passed, 0 failed, 0 skipped, 0 deselected in 5.20s**. JUnit SHA256: `339a587b9a80e96fb10706d5e34485231dda67db609ff1b4315287d79b5e0437`.

The red probe used the same environment and interpreter and only created a temporary fake RAG generation. It performed no worker spawn, model load, or index scan before calling status.

## Scope and repository state

- Diff reviewed: `4ace5ec2e9b7735d90eb15bc2351fa193c1120b8...ad839d2e0254061a6c7c6a562cec365f2186671f`, all 8 changed files.
- Production code boundary: `cb4bbf1ce6cd9b1af4b71dcbb13668877dbc54be`; later service diff is empty.
- KB protocol was read only at `/Users/a77/kb-wt-guarded-maintenance-0920@3a21010323eababb54ce8519093fd60dbacb9451`; no KB code was imported into status and no KB files were changed.
- Prior real scratch evidence was treated as historical evidence bound to `d6812e62`, not as a rerun at this HEAD.
- Whole repository, frontend, real models, production indexes, 8792, and launchd were intentionally outside this review.
- Initial state: HEAD `ad839d2e0254061a6c7c6a562cec365f2186671f`, upstream same, clean.
- Final state: HEAD `ad839d2e0254061a6c7c6a562cec365f2186671f`, upstream same, clean.

**Final verdict: QUALITY FAIL.** Repair the operation-local runtime `RuntimeError` classification and its regression guard, then rerun the preserved red probe plus the focused generation/status tests. Keepalive synchronization needs no further change.
