# Round 04 Log Supplement

Round 04's filesystem archive contained 421 selected artifacts. At published
commit 10a21cff and discovery commit ddc0d35b, 129 listed .log files were absent
from Git: .gitignore ignores them and the commit hook forbids that suffix.
The prior filesystem hash check did not establish a complete committed archive.
The older 241-file and 23-file archives passed the discovery Git-blob check.

This append-only supplement preserves those 129 original payloads under .log.txt.
MAPPING.json binds their new repository paths to the unchanged original manifest
(hash 7b528c677c4d286a855bfa637f3633660e2233bf5497dcbe3b51c0a92fc55b25).
No old manifest, report, failure, model session or original byte was rewritten.
This does not recreate the complete model stdout sessions or change the BLOCKED
engineering/independent result. Original paths still do not exist in a clean Git
checkout: consumers must resolve them with this mapping, not pretend the old
archive alone is complete.

Verify this supplement with scripts/check_evidence_archive.py against an exact
commit. The round-05 closure verifier additionally checks all 421 old manifest
entries through Git data plus this mapping. Do not force-add ignored logs or
relax the repository-wide forbidden-file hook.
