# PR884 Round 05: Preparation and Archive Repair

Final status: BLOCKED, not ready to merge or deploy. No full engineering gate or
new independent-model request ran in this round. No production mutation occurred.

## Candidate

- Integrated main: `3bb81b9638f97b4773ce0f338df3a505b7c0162f`.
- Branch merge: `06b7c5883fed634e4303823cbb41763ccd1be13c`.
- Resource-probe code: `ddc0d35b053f25ac74b10a3e4c62ab5502bae5ea`.
- Archive repair: `5344d8b0f87a9dcf14b08d87a19f63c7c3a25a1a`, pushed to Gitea.
- Subsequent documentation heads do not acquire a full-gate receipt.

## Completed

1. Fixed a definite admission false negative: the old driver only noticed pytest
   commands containing --junitxml=. The new committed gate_resources.py recognizes
   module/console invocations independently of reporting flags. It is conservative
   about detected targeted tests, checks disk, and only excludes explicit owned
   groups. It is an observation, not a host-wide resource reservation.
2. Host unit baseline 9 passed; injecting the old report-required filter produced
   the named negative assertion failure; restored 9 passed. Driver unit checks 5
   passed. The first unsupported pytest-3 case failed and remains recorded.
3. Prepared verbose full pytest output, duration diagnostics and a 60-second
   faulthandler dump. These options did not run, because admission never passed.
4. Found 129 round-04 .log artifacts listed in its manifest but absent from Git.
   The filesystem copy was correct; that did not prove committed completeness.
   Original 10a and discovery ddc have identical round-04 Git contents. The existing
   ignore rule and forbidden-file hook explain why force-adding logs is unsuitable.
5. Appended 129 identical payloads (403320 bytes) under .log.txt with a mapping to
   the unchanged original manifest, in
   docs/verification/2026-09-24-pr884-round04-log-supplement/. Existing archive
   preview/commit checkers passed 133 members and identical preview/commit trees.
   Immutable Git archive validation resolved all 241 + 23 + 421 historical items;
   round 04 is 292 direct blobs plus 129 supplement blobs. Deleting or altering one
   supplemental payload is rejected, and restored validation passes.

## Stopped Work and Limits

The ddc admission controller was stopped after the archive defect was discovered,
while still waiting, with zero leaf processes launched. operator-stop.json is the
terminal observation; the original controller-result.json is intentionally kept
as its last waiting snapshot, not rewritten. There is no live round-05 controller.
The repaired candidate also failed resource observation: three foreign pytest
roots and 5215031296 bytes free at 2026-09-23T17:57:36Z, below 12 GiB admission.
No other process was signaled and no old or foreign scratch was deleted.

Full engineering status is NOT_RUN, with counts/collected null. Round 04's timed
out Python remains UNKNOWN; old frontend/registry and host mutation passes do
not transfer. Independent C1-C8 gaps are unchanged. review-plan-proposed.md is a
proposal for at most four batches and 84 provider requests, not authorization or
an execution record. Model fallback, retries, quota purchases, merging and
production operations have not been performed.

## Evidence and Reuse

verification.json binds the completed checks and the stopped attempt. The prepared
run.py and launch.py remain tied to ddc and are not restartable; use a fresh run
root and freeze the then-current candidate after resource/plan confirmation.
The source helper is committed under scripts/review_probes/gate_resources.py.
Archive validation reuses scripts/check_evidence_archive.py and
scripts/preview_evidence_archive.py; verify_archive_closure.py adds only the
historical-manifest mapping check for this repair. It reads Git, never ignored
filesystem logs. This is host verification, not independent runtime approval.

The selected round-05 archive excludes credentials, dependency trees and user
state. The existing round-04 manifest and failures were not changed. Its old
standalone Git archive is still incomplete at original .log paths; the supplement
must be resolved through MAPPING.json. The supplement repairs reproducibility,
not any historical acceptance verdict.
