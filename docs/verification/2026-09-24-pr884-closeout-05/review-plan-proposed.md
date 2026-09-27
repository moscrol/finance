# PR884 Next Independent Review Plan (Not Launched)

Status: PROPOSED, awaiting confirmation of this bounded follow-up. The previous
three-batch allocation ended with 83 requests; it is not reopened. Preparation
here makes zero model calls and does not assign an independent PASS.

## Candidate and Budget

- Candidate after the append-only archive repair: `5344d8b0f87a9dcf14b08d87a19f63c7c3a25a1a`, integrated base
  `3bb81b9638f97b4773ce0f338df3a505b7c0162f`. Reconfirm identities before launch;
  any later code change requires a new frozen candidate, not relabeling evidence.
- Suggested provider/model: `mirasim-kimi/kimi-k3`, unchanged from round 04.
  GLM is an available alternative to discuss, not an automatic fallback.
- At most four sequential batches, each owning two contracts. Each batch: at
  most 20 exploration requests plus one tool-free final report request, 900s
  exploration and 1200s total. Combined request ceiling: 84, including reports.
- No automatic retries, continuation batches, quota purchases, or provider
  switching. An upstream failure or missing final report stops later batches
  for host inspection; CLI exit 0 does not override a model error.
- Complete the first independent dynamic probe by request 6; stop adding new
  exploratory branches by request 16. Those are schedule prompts, not evidence.
- Offline tools, cleared credentials, candidate read-only, fresh scratch/users,
  no production data, no nested model/finance calls, no deployment or merge.
- Resource admission before each batch: no foreign pytest, at least 12 GiB;
  stop only this batch below 8 GiB. Admission is not a host-wide reservation.

## Owned Contracts

| Batch | Contracts | Required Dynamic Evidence |
| --- | --- | --- |
| A | C1, C2 | Save-ACK failure prevents model/tool/repair dispatch and fences parent/child; authorization/budget/private-evidence snapshots, v3 io_effect, v1/v2 conservative compatibility, unknown cost/effect gate and server entry identity. |
| B | C3, C4 | Repeated restore preserves phase/reservations/execution prefix and deduplicates by identity; plan is not execution permission. Writer locks before load, retains ownership, keeps flock inode stable; real competing process cannot append/close/consume. |
| C | C5, C6 | Same runner run/resume/callback and step/close exclusion while demonstrably in flight; cleanup and sequential reuse of the same instance; unrelated-instance parallelism. Inbox/spool drain, late input, stale handle, error and close ordering; at-least-once only. |
| D | C7, C8 | Task/store/context/outcome/episode binding and exact stored prefix, no cross-episode recovery. Actual API/SSE projection including delivery_pending and failure/cancel tails; truncation never becomes complete. Include the newly integrated worse-status delivery rule. |

Each owned contract needs an explicit sub-contract coverage table, original
probe files, baseline/negative commands, full raw output, JUnit, and a semantic
protection-removal witness with restored green. Missing sub-contracts remain
NOT_REVIEWED; a positive author suite or source reading does not substitute.
Do not stop at private serializers where an actual caller boundary exists.

## Prior Probe Pitfalls (Not Approval Evidence)

- C1: dummy context needs a real `phase`; otherwise AttributeError is a fixture
  failure, not a persistence-fence counterexample.
- C2: mappingproxy is not deepcopy/pickle data. Use the snapshot's canonical
  from_dict/to_dict roundtrip. A removed digest check must allow a coherent
  tampered value through; rejection by the presentation/original check with a
  different error string is not a valid mutation witness.
- C5: reach model_pending before the in-flight event barrier. Reuse the exact
  same runner object after an exception; constructing episode2 proves another
  property. A model exception may settle as model_error, not propagate.
- Sandbox TMPDIR and user state must point into allowed scratch before testing.
- Preserve the first red and every repaired attempt under new paths. Do not
  tail test output or overwrite the previous report.
- Host repairs in round 04 are setup hints, not independent assertions to copy.

## Acceptance

A host audit checks the exact candidate, probe provenance, full outputs,
sub-contract coverage and mutation semantics after each batch. A model's PASS
is insufficient by itself. Engineering gates, independent approval, merge
permission and production readiness remain separate. No complete crash-resume
driver, cross-host lock, real billing reconciliation or production financial
answer quality is certified by these offline checks.
