# Quality Assessment — FQ Independent Review

## Overall rating: GOOD with MODERATE coverage (supports PASS_WITH_LIMITS, not PASS)

## 1. Evidence provenance and integrity — GOOD
- The probe source is traceable end-to-end: `FQ-explore/delivery/manifest.json` lists `probe.py` sha256 `7c0801e2…`, and the executor (`FQ-execute/execution.json`) records the identical input sha with `inputs_unchanged: true`. The earlier draft report miscited provenance as FQ-execute/delivery; corrected to FQ-explore/delivery.
- Before/after revisions in every execution record are identical (`1de68567e740…` on main `c9dd71df`), so no execution mutated the candidate.
- The historical replay reuses the byte-identical probe (`probe_sha256` matches, `probe_unchanged: true`), making it a clean sensitivity comparison rather than new coverage.

## 2. Probe design quality — GOOD
- **Determinism where it matters**: adversarial 2 gates `execute()` on a `threading.Event` that only `interrupt()` sets, converting an interrupt-ordering race into a deterministic handoff (5s safety timeout, well above the 0.5s grant and ≤10ms monitor cadence).
- **Right level of assertion**: the cancellation probe asserts outcome-level observables (exception type, zero executes, one close) without pinning which thread or check site raised — appropriate, since the 4th `cancelled()` invocation can be consumed by the monitor thread or a main-thread check.
- **Real code paths**: real `FinanceQuery.run`, real SQL compilation via `FinanceQuerySpec.from_arguments`, real `ResearchDeadline` semantics (`bounded_stage`, `stage_timeout`) exercised inside `run`; no author tests imported; no production DB/network/model access (sandbox denies).
- **Fake fidelity limits (honest and disclosed)**: `FakeConnection`/`EmptyCursor` cannot speak to real DuckDB `interrupt()` semantics, close-under-interrupt, or connect latency; the report does not overclaim here.

## 3. Coverage — MODERATE; this is the binding limit
Verified dynamically: setup no-renewal + synthesis reserve, late-SQL success rejection after interrupt, cancellation precedence (outcome level), unconditional close, happy-path control. Not executed: upfront ≤0.001 no-connect rejection (setup probe connects and closes first — not counted per reconciliation), late fetch success with populated rows (empty cursor only), late-close-success semantics (L2287 is post-close and static only), fetch-loop cancellation, byte-limit remap interaction, monitor-recorded cancellation mapping in isolation, monitor-thread lifecycle when `interrupt()` blocks. The claim's "reject late SQL/fetch/close success" triad is therefore only one-third dynamically covered.

## 4. Positive control — PASSING AS DESIGNED
`test_intentional_red_probe_bug` (`assert 1 == 2`) produced exactly 1 failure, exit 1, `positive_control_detected: true`. Classified **probe_bug** (control artifact), not a candidate defect. Confirms the harness detects and reports failures rather than silently swallowing them.

## 5. Host/revision sensitivity — NOTED, not inferred
The immutable replay at revision `50330cf4` shows 2 failures of the exact probes that pass on the candidate (timeout DID NOT RAISE; cancellation observed one executed SELECT). This is legitimate sensitivity evidence about wall-clock/check-placement dependence of these probes and of the code paths involved; per packet constraints, no root cause is inferred, and it is neither a second reviewer nor additional candidate coverage.

## 6. Author evidence handling — CORRECT AFTER RECONCILIATION
- Original author run: exit 4, `PermissionError` on `candidate/intelligence/users` during package collection, 0 tests executed — properly classified **BLOCKED_PROBE** (harness/sandbox), not a product bug.
- Recheck: the only profile change permits a metadata stat on the literal `intelligence/users` directory (contents remain denied); 151/151 pass in 5.5s on the same clean candidate. Reported as a **separate** execution, not merged with the blocked run, and explicitly not counted toward independent coverage.

## 7. Reporting hygiene — ADDRESSED
All five reconciliation points are reflected: (1) upfront-rejection downgraded to static/not_verified; (2) L2287 post-close check distinguished from untested delayed-close behavior; (3) cancellation result not pinned to a check site; (4) author runs reported separately; (5) probe provenance corrected and historical replay scoped as sensitivity evidence.

## 8. Residual risks
- Timing probes (0.2s grant vs 0.4s connect; 0.5s grant + 5s gate) have generous margins but are not immune to extreme host load; the sanity bound `stage_timeout(8.0) <= 0.25` could in principle flake.
- Verdict confidence is high for the verified subset, medium overall due to the enumerated untested edges; no full-repo or production acceptance is implied.
