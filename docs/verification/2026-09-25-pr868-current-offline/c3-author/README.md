# C3 author replay, not independent review

Candidate: fb41cebdaa6a186c14bd402f0f2dd83705f64421
Base: fe9fdbfd70a637efc5bcf0cfecf74080a8d6a90c
Tree: /Users/a77/fwp-wt-pr868-current-0925
Interpreter: /Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python

The sealed reviewer probe remains untouched under pr868-glm-qc-20260925-c3c7/spec/work/probes/.
original.py is a byte-for-byte copy. corrected.py changes only the event observer signature.
replay.py runs both variants, captures complete events, and separately enforces the original 0.8 + 0.2 second contract, exact one request/ledger entry, positive control, and root time consumption.
No paid model requests, real credentials, production ports, old batch authorization, or independent verdicts are used or inherited. The HTTP endpoint is a local fixture in the original approved 26001-26008 range; occupied ports are not reclaimed.
