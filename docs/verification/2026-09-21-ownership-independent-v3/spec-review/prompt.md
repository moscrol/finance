Read ../review-common.md first and comply. Axis: SPEC (does behavior meet the contract?).
Candidate checkout: /Users/a77/fwp-wt-ownership-spec-v3-0921
Your current writable evidence directory: /Users/a77/.finance-runtime/reviews/ownership-independent-v3-20260921/spec-review
No shared user memory writes or project handoff workflow: you are the independent reader; root operator handles closeout.

Independently map R1-R4/B1/F1-F3 to implementation and tests. Focus dynamic effort on real shell readback controls (legitimate receipt, failures, wrong/missing tree with baseline/allow-dirty), process-vs-receipt agreement, and current 302132 staging contract. At least one independently authored counterexample attempt per changed subsystem (receipt, board, backfill) if feasible. Existing regression tests may complement, not replace, those attempts. Use only synthetic inputs. All subprocess timeouts <=120 seconds. Preserve unexpected errors as evidence and distinguish fixture/sandbox problems from application bugs. Write report within the 15-minute deadline; absence of a decisive counterexample is not proof of untested behavior.
