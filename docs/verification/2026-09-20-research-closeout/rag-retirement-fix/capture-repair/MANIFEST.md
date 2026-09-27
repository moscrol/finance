# Managed capture repair evidence

- Spec-failed candidate: `bc43ece9fc0550663645c2e8c57d57d7618b8e0d`
- Repaired code: `dd76f502fb6da59e3f34806b1b6f48d11a0955fd`
- Branch: `fix/rag-retirement-closeout-0920`
- Scope: first managed capture of missing full/code/wiki/interpreter artifacts and adjacent malformed manifest object fields; no startup protocol change, real scratch rerun, production access, BGE, network, 8792, launchd, PR, or merge.

## Independent consumer probe

- Probe copied without the reviewer's obsolete diagnostic oracle: `test_consumer_no_fallback.py` = `f3d2a1541bfac85446631c4825e590a44709458a9e3a539c28f2573d7e8b5d42`.
- All probe runs used `env -i` with only HOME, PATH, LANG, TMPDIR, FWP_TEST_RECEIPT=0, PYTHONDONTWRITEBYTECODE=1 and PYTHONPATH. Logs contain summaries only.
- Before repair: `red-summary.log.txt` = `541dec251de5c33ef9a47a844e23d103efa3dce8e17d26dc688a738c0f7817d7`, 2 failed.
- Mutation removing both capture translations: `mutation-without-capture-translation.log.txt` = `fb498c7d0bf6898e107a30ab29749c55c2d60eab4749bf1179d4aaba581ee1e1`, 2 failed.
- Final repaired consumer run: `final-consumer-dd76f502-summary.log.txt` = `9b0bdd4f08fe9c2bf5ea1abc33b54c81149fa9f8977fd54dd19a5fbae3201c1f`, 2 passed.

## Repository regression

- `final-directed-dd76f502.log.txt` = `673840fa2b1b127a209d55bfd779956e11396f488d648e7f8adf164bb30d8824`.
- Exact pytest selection in that receipt: `test_rag_worker_generation.py`, `test_rag_worker.py`, `test_rag_worker_keepalive.py`, `test_kb_runtime_roots.py`, `test_kb_filter_receipt.py`.
- Result: 118 passed; related Ruff passed.

The repair maps bounded managed capture filesystem failures to `RagGenerationUnavailable` with `index_directory_replaced`, `code_root_replaced`, `source_root_replaced`, or `interpreter_replaced`. Malformed `sources`, `indexes`, `runtime`, and `path_identities` object shapes map to `managed_binding_mismatch`. Legacy and ordinary protocol failures retain their existing fallback behavior.
