# PersistentRagWorker generation retirement · Final Quality review

## Verdict

**QUALITY PASS** at `1931b3a32237489bcdf21f51bf8523d697398b92`.

The two findings from the Quality review at `ad839d2e` are closed by code-and-test commit `b860ecc8c02c92b77f41bf5d896d732414bbcc6a`. The prior independent Spec review remains PASS at `c4f33c5b`; this final review covers only the Quality delta and does not claim a new full Spec or real-scratch run.

## Closed findings

### P1 · Post-capture interpreter-chain loop

`intelligence/services/rag_generation_identity.py:187-200` now treats `RuntimeError` only at the `python_entry.resolve(strict=True)` operation as `interpreter_replaced`. The handler for ordinary paths remains `except OSError`; no outer or global `RuntimeError` fence was added.

The original Quality probe was replayed byte-for-byte (input SHA256 `d3e5016024b15407ade0f90546537e8b0ed91a15ab6630fc77812b0b1574da94`). Its result changed from a bare exception to exit 0 with:

- `state=failed`
- `active=false`
- `generation_status=invalid`
- `generation_reason=interpreter_replaced`
- no process, model load, served query, recovery, or keepalive activity

The repository guard additionally preserves the original entry inode, asserts status does not spawn/kill/recover, and verifies query and prewarm both raise `RagGenerationUnavailable(reason="interpreter_replaced")`.

### P2 · Venv launch entry oracle

`intelligence/tests/test_rag_worker_generation.py:215-242` now builds a temporary `python -> python3 -> host-python` chain and asserts the first `Popen` argv element is the declared `python` entry. `intelligence/services/rag_worker.py` has no delta from the failed Quality candidate.

## Boundary review

The exact code/test delta from `ad839d2e` to `b860ecc8` changes only:

- `intelligence/services/rag_generation_identity.py`
- `intelligence/tests/test_rag_worker_generation.py`

The final `b860ecc8...1931b3a3` delta contains no service or test changes. Static inspection confirms:

- legacy capture still re-raises ordinary `PermissionError`;
- normal worker protocol failures still take the legacy CLI fallback;
- a single bad query remains an ordinary query error and does not reclassify the worker as retired;
- capture-time interpreter-loop classification and other path handlers are unchanged;
- `rag_worker.py`, including launch argv and fallback behavior, is unchanged.

## Independent verification

All subprocesses used `/Users/a77/finance-workspace-private/.venv-workbench/bin/python` under `env -i` with only `HOME`, `PATH`, `LANG`, `TMPDIR`, `FWP_TEST_RECEIPT=0`, `PYTHONDONTWRITEBYTECODE=1`, and `PYTHONPATH`. Pytest used `-p no:cacheprovider`. No real venv link, model, BGE, production index, network, 8792, launchd, KB write, or full scratch was touched.

Original probe replay:

```text
env -i <whitelisted environment> /usr/bin/script -q <quality-final/log> /Users/a77/finance-workspace-private/.venv-workbench/bin/python <original-quality-probe>
```

Result: exit `0`; expected failed/invalid/interpreter_replaced payload. Log SHA256: `18800fde8078a75f488d2cd37f40844ac10daf77402d0df9d80556d411f9832c`.

Focused guard command:

```text
env -i <whitelisted environment> /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -p no:cacheprovider -q \
  intelligence/tests/test_rag_worker_generation.py::test_managed_launch_uses_frozen_environment_despite_ambient_rewrite \
  intelligence/tests/test_rag_worker_generation.py::test_post_capture_interpreter_chain_loop_is_unavailable_without_status_side_effects \
  intelligence/tests/test_rag_worker_generation.py::test_legacy_capture_does_not_reclassify_permission_error \
  intelligence/tests/test_rag_worker_generation.py::test_normal_protocol_failure_still_falls_back_to_cli \
  intelligence/tests/test_rag_worker_generation.py::test_single_bad_query_does_not_reclassify_worker_as_retired \
  --basetemp=<quality-final/test-tmp/pytest-guards> --junitxml=<quality-final/pytest-guards.xml>
```

Actual result: **5 passed, 0 failed, 0 skipped, 0 deselected in 0.18s**. JUnit SHA256: `b6acf73e3394afd9a673a2982d73dff3909134870299c02c19eb8757ee7631ce`.

Focused Ruff command:

```text
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check intelligence/services/rag_generation_identity.py intelligence/tests/test_rag_worker_generation.py
```

Actual result: **All checks passed**.

## Repository state and scope

- Base Quality candidate: `ad839d2e0254061a6c7c6a562cec365f2186671f`.
- Frozen repair code/tests: `b860ecc8c02c92b77f41bf5d896d732414bbcc6a`.
- Initial final-review state: HEAD/upstream `1931b3a32237489bcdf21f51bf8523d697398b92`, clean.
- Final final-review state: HEAD/upstream `1931b3a32237489bcdf21f51bf8523d697398b92`, clean.
- Author evidence manifest was read as supporting evidence only: SHA256 `9572618a661dcdde6a07f8ee17e51120d7710a6de904d38ade65176bc904301b`.
- This review intentionally did not rerun the 86-test author set, full repository, frontend, or historical real scratch. It replayed the original blocker and the minimum adjacent guards.

**Final Quality verdict: PASS.** The original runtime-loop defect and the launch-entry regression gap are closed without widening legacy or ordinary protocol exception handling.
