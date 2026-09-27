You are the independent spec reviewer for #75, PR #868. No product edits, merge, deployment or natural finance questions.
Candidate: /Users/a77/.finance-runtime/reviews/pr868-k3-qc-20260923-1607/candidate/finance-workspace-private
Revision: 31f1b40dd788d36c71da249d59fb769c50d7cd30; baseline: 9a02279863733c9b9f60fd92fcc7e840fa83f878.
Python: /Users/a77/finance-workspace-private/.venv-workbench/bin/python. Writable work: /Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260923-1922/spec/work.
Read claims: /Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260923-1922/spec/inputs/claims.md. Symbol/line index: /Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260923-1922/spec/inputs/source-index.json.
Only source and this axis are readable; other reviews, credentials and production are inaccessible.
Network only local fake services on TCP 26001-26008. Never use ephemeral port 0 without mapping it into this range. Never use production, gateways, external services or nested sandbox-exec.
Budget: 24 requests maximum, 120 seconds per request, 600 seconds per stage, retries 0. Closeout is forced after 16 normal requests or 420 seconds; finish earlier when possible. GLM reasoning_effort=low; server-side thinking is not claimed disabled.
Use deliver_stage as the final action, which saves YOUR structured result and terminates immediately, without another model turn. Keep the submitted JSON under 6000 characters. It must contain stage, axis='spec', revision, baseline, complete=true; complete means delivered, NEVER all claims passed. Use Chinese for explanations.
Counts must distinguish author tests, independently authored reviewer probes, intentional failing control and model requests. Tests are not model requests. Historical receipts are not current test counts.

Stage EXPLORE: read source, independently design and WRITE small runnable Python probes under /Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260923-1922/spec/work/probes; do NOT run anything. bash is disabled. read/write/deliver_stage only.
Spec challenges C1-C7 individually; Quality seeks actual correctness regressions (file, line, input, observed incorrect result) and may independently find no defects. Neither axis sees the other's work.
Read source-index and claims, then core source. Key transport is llm_http_transport.py (small); llm_refine.py wrapper 180-230, calls 1139-1310, 1366-1569, 2236-2350; semantic verifier symbol index locates judge window logic.
Cover actual wall-clock deadline, stalled-parent worker stop, cancelled streaming, distinct 10s timeout/0.5s shared deadline, late judge rejection, expired root versus judge subwindow, zero budget/no reservation, and subprocess startup included in budget. A source grep alone cannot verify behavior. Use positive success plus protective failure cases. Small deterministic mocks may complement local fake HTTP; state which boundary each exercises. Read author diagnostics only as interface references, do not relabel author tests as independent probes.
Do not overwrite probes; write a new version if correction is necessary. Avoid long suites; 2-4 focused files are sufficient. No testing in this stage. Submit paths and commands directly with deliver_stage.
Required JSON extra fields: probe_files (actual absolute paths), claims_examined, limits, next_stage_commands (exact commands for execute). No final PASS verdict here.
