# Runtime interpreter-loop repair evidence

- Quality-failed candidate: `ad839d2e0254061a6c7c6a562cec365f2186671f`
- Quality report SHA256: `a8dc6cc9e796331355b137a41ff233a3962077dcf8d4c57529e01eb571d9b589`
- Frozen code and tests: `b860ecc8c02c92b77f41bf5d896d732414bbcc6a`
- Final docs/head: `1931b3a32237489bcdf21f51bf8523d697398b92`
- Branch: `fix/rag-retirement-closeout-0920`

## Preserved post-capture probe

- Copied original: `post_capture_interpreter_chain_loop.original.py` = `d3e5016024b15407ade0f90546537e8b0ed91a15ab6630fc77812b0b1574da94`, identical to the Quality input.
- Before repair: `red-ad839d2e.log.txt` = `d728c60d0c206a929b804300f554d5b20243221a150ac2da1e4cdb42ebd6f1c2`, exit 2 with a bare `RuntimeError`.
- After repair: `final-probe-b860ecc8.log.txt` = `3469c4c5b99b01c03d131a5593e53dff64ab266f48b0e654cfec6623b4a99baf`, exit 0 with `state=failed`, `active=false`, `generation_status=invalid`, and `generation_reason=interpreter_replaced`.

The repository regression additionally keeps the pinned interpreter entry inode unchanged, asserts status performs no spawn/kill/recovery, and verifies query and prewarm both raise `RagGenerationUnavailable(reason="interpreter_replaced")`. Only the temporary test symlink chain is modified.

## Launch-argv mutation

- Temporary mutation changed only the `Popen` executable from `self.python` to `Path(self.python).resolve()`.
- `mutation-resolved-launch.log.txt` = `3a935e03de624b67013b6714267cd104c1bda71f94a34b8e39018e28dc43f33b`, 1 failed because argv[0] was the host interpreter instead of the declared venv entry.
- After exact restoration: `post-mutation-launch-green.log.txt` = `e8c2ebdecc6c68bd31c948de0b0c1dd4c57dd47d093194a6c1d241c65727824d`, 1 passed. `rag_worker.py` has no final diff from the pre-mutation candidate.

## Final directed regression

- `final-directed-b860ecc8.log.txt` = `e8f210e69fed63542929612c7d8e371e84b78355d2c683a9819fa58f411cec38`.
- Start and end SHA: `b860ecc8c02c92b77f41bf5d896d732414bbcc6a`.
- Exact pytest modules: `test_rag_worker.py`, `test_rag_worker_generation.py`, `test_rag_worker_keepalive.py`; result 86 passed.
- Ruff passed for the two service files and the same three test files.
- Every probe/test process used `env -i` with only HOME, PATH, LANG, TMPDIR, FWP_TEST_RECEIPT=0, PYTHONDONTWRITEBYTECODE=1, and PYTHONPATH.

No real venv/Homebrew link, full scratch, whole repository, frontend, production index, BGE, network, port 8792, launchd, PR, merge, or deployment was touched.
