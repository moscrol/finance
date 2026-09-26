# RAG retirement fix evidence manifest

- Finance base: `4ace5ec2e9b7735d90eb15bc2351fa193c1120b8`
- Frozen code: `d6812e6220b46ff939dfbcf51ac6c6b93246d361`
- Final docs/head: `bc43ece9fc0550663645c2e8c57d57d7618b8e0d`
- Branch: `fix/rag-retirement-closeout-0920`
- Remote: `gitea/fix/rag-retirement-closeout-0920` = final head
- KB source: `/Users/a77/kb-wt-guarded-maintenance-0920@3a21010323eababb54ce8519093fd60dbacb9451`, clean before/after final probe
- Finance source: `/Users/a77/fwp-wt-rag-retirement-closeout-0920`, clean before/after final probe and after push

## Probe lineage

- Original probe: `a4de73d46ceadb31c17488cb318ca0b8e9ae864789fa72b11f0cc0a545114714`
- Copied-before-edit probe: same hash; recorded in `probe-hashes.txt`
- Baseline extension: `probe_finance_worker.baseline.py` = `fdf194f4c0d6b129d015e1f97045b0ab98b31f1c09578fcb7994a27ebaf39efb`
- Baseline result: `worker-baseline/results.json` = `2130eba97ad0fe77a896693efa6bfc462db4cf5763fcdf66a353c16ebea2fd75`
- First fixed-attempt bytes: `probe_finance_worker.fixed-attempt1.py` = `fbce13bd78cc554ba2889c77e6c95c2f82cae844248f70fd093aa9e6f887d32c`; Finance `3f5d0690cec45bb906d758f4165d1558eda78a26`; failed because resolving the venv launcher bypassed venv dependencies. Log: `real-fixed.log.txt`.
- Final probe: `probe_finance_worker.py` = `83d9fc88f820ba0ae36e00f38f81b9282e0a55536aeb16fc9418811461d347a6`
- Final result: `worker-fixed-d6812e62/results.json` = `9641aab531ec9b100e0c9cc0728683dd59d2edd3b6a6002d60bafff3b5e6dfb9`

The final probe used a new scratch generation root, two pages, hash embedding, BM25, standard/full indexes, alpha→beta activation and explicit alpha rollback. It used no network, real model, production index, service, port, or launchd. Result records 13 stages and confirms all 8 spawned subprocesses closed.

## Test receipts

- `final-code-receipt-d6812e62.log.txt` = `22110ecae3a0b882a3a7e82782c2df0b2087dcb4d0df78a983eb074208e6389e`: 94 passed, 2 skipped, 126 deselected; related Ruff passed; `FWP_TEST_RECEIPT=0` and required workbench interpreter.
- `mutation-remove-current-check.log.txt` = `1e38e693f7b1513300a4040e557de6c0d9bd4a0ceaf914a86266a2ec2dcc8542`: expected exit 1.
- `mutation-ambient-relabel.log.txt` = `1685cd3669785e8e777f623f67f514eeede1852c1e4190d4744af73710a30221`: expected exit 1.
- `red-venv-entry.log.txt` and `red-distinct-venv-entry.log.txt` capture the two interpreter identity regressions before their fixes.

Scope excludes whole-repository/frontend gates, production deployment, BGE, 8792, launchd, production indexes, and KB repository changes. Coordinating review owns independent Spec→Quality review and the frozen four-leaf gate.
