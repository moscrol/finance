# #832 / #75 batch preparation

- Candidate `d1b30e1a068ccd0559f091f3c664ca2ca82f1e7c`; baseline `626d8a508c1c988ff094110b371987e6afdcdd15`.
- Fresh detached candidate, separate spec/quality roots, unchanged shared Python interpreter. No old reviewer reports or probes copied into either axis.
- Existing GLM tooling copied from `pr868-glm-qc-20260923-1707`; original-copy hashes and absolute source paths in `tooling-provenance.json`. `prepare.py` materializes the initial state, not the amended final state.
- Per-axis config and sandbox paths rebound to this candidate. No production source or production configuration edits. Provider route and request limits unchanged.
- Both initial offline `sandbox-preflight-04` runs exited 1: their forbidden-read control named the old task's `docs/handoffs/2026-09-22-adaptive-deadline-transport.md`, absent in this candidate. Raw commands, full FileNotFoundError and stdout/stderr retained. No model request had been made.
- Amendment: in each `sandbox_preflight.mjs`, change only that target to the existing `docs/handoffs/inflight/fix-react-trace-qc-0921.md`. In each `run_control.py` and `run_stage.py`, change receipt selector from `sandbox-preflight-04/receipt.json` to fresh `sandbox-preflight-05/receipt.json`. Do not overwrite failed preflight output, do not accept FileNotFoundError as a permission denial, do not weaken sandbox rules.
- Both `sandbox-preflight-05/receipt.json` are PASS with real_model_requests=0: candidate import/work writes allowed, private paths/source writes/symlink escape/external network/gateway/8792 denied, intentional assert-1-equals-2 returns true exit 1 with full output, request/time closeout controls tested.
- Credential shape/reference check READY using the existing launcher Keychain reference; no key logged or persisted. Model provider price fields are placeholders, not a billing receipt.
- Spec gateway completed 4 requests (tiny plus real read/write tool roundtrip), no retries, status PASS, accounting agrees and relay shutdown complete. That is admission evidence, not an independent QC verdict.

Final runtime and artifact identities belong to each stage's execution.json and controller receipt. No stage or batch verdict is asserted here.
