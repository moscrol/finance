# Quality Assessment — FQ (FinanceQuery.run absolute query deadlines)

Candidate `1de68567e740a9a5d9c25bea91142741ad12aa10` (base `c9dd71df`). Independent GLM review, stage report. No author verdicts were provided or relied upon.

## Overall verdict: **PASS_WITH_LIMITS**

## Code quality (candidate, from packet source)

**Strengths**
- Correct one-shot grant semantics: `query_deadline` is fixed exactly once (L2209) before any connection work or monitor scheduling; there is no code path that re-derives or renews the grant, so every later check (`L2210, L2222, L2231, L2246, L2287`) compares against the same absolute instant. This structurally closes the "setup renews the timeout" failure mode.
- Parent synthesis reserve is respected by construction: `bounded_stage` intersects `min(parent.expires_at - reserve, now + limit)` and the child grant carries no reserve, so pre-synthesis stages cannot eat the P0 reserve.
- Cause preservation is well designed: a single `interrupted_for[0]` marker ("cancelled" before "timeout") deterministically maps both the except path (L2261–2267) and the post-fetch success path (L2276–2279), so a late success cannot launder an interrupt into a result. The trailing `query_deadline.expired` check (L2287) also rejects success that lands after the last in-loop check.
- Cleanup is unconditional: the outer `finally` (L2282–2285) sets `stop_monitor` and closes any non-None connection regardless of outcome; the monitor is a daemon thread with a bounded 0.2s join.
- Upfront rejection of nearly-exhausted grants (`remaining() <= 0.001`, L2210) avoids racing a monitor thread against an already-blown deadline.

**Weaknesses / risks (observed, untested or low-impact)**
- **Except-mapping remaps structured fetch-loop errors**: if the monitor has recorded a cause, a fetch-loop `FinanceQueryLimitExceeded` (L2417) or fetch-loop `FinanceQueryCancelled` (L2392) is re-mapped to `TimedOut`/`Cancelled` at L2261–2267 before the `isinstance(exc, FinanceQueryError)` re-raise. This is arguably intentional cause-priority, but it can mask the byte-limit error type; untested dynamically.
- **No preemption of `connect()`/`close()`**: a blocking `connect` still blocks `run()` indefinitely (packet explicitly disclaims this; verified only as an accounting property, not unblocking).
- **Monitor join is bounded (0.2s) and daemon**: if `connection.interrupt()` blocks, the monitor thread can linger; leak behavior untested.
- **Monitor polls at ≤10ms** (`stop_monitor.wait(min(0.01, remaining))`): interrupt latency is best-effort, not hard real-time (disclaimed by the packet).

## Evidence quality

| Evidence | Outcome | Assessment |
|---|---|---|
| Independent probe (4 tests, sandboxed, fresh fixtures) | 4 passed, exit 0, 1.44–1.77s | Sound: event-gated adversarial 2 makes interrupt→return ordering deterministic rather than sleep-raced; adversarial 1 uses 0.2s grant vs 0.4s connect (2× margin); connect asserts `read_only=True`; no author tests imported; no DB/network/model access |
| Positive control | 1 intentional failure, exit 1, detected | Harness correctly detects failures → classified `probe_bug` (control working), not a product defect |
| Author tests (4 files) | exit 4, collection error, 0 executed | `PermissionError` on `candidate/intelligence/users` under sandbox — sandbox/collection problem (BLOCKED_PROBE), **not** a product bug; author-side regressions remain unexecuted (not_verified) |

## Coverage gaps (drive the LIMITS in the verdict)
1. Late **fetch** success after interrupt (populated `fetchmany` batches post-interrupt) — adversarial 2's cursor returns `[]`.
2. Pure monitor-recorded `"cancelled"` → `FinanceQueryCancelled` mapping — adversarial 3 raises at the pre-execute check before the monitor records.
3. Byte-limit `FinanceQueryLimitExceeded` path and its interaction with the monitor-priority remap.
4. Fetch-loop cancellation between `fetchmany` batches (L2391).
5. Monitor-thread lifecycle when `interrupt()` blocks (0.2s join, daemon).
6. Real DuckDB `interrupt()`/`close-under-interrupt` semantics (fake connection only).
7. Entire author regression suite (blocked collection).

## Risk assessment
- Timing-based adversarial tests (1, 2) have generous margins but still depend on host scheduling; extreme load could in principle flake the `stage_timeout(8.0) <= 0.25` sanity bound or the 5s gate timeout. Low risk on an idle host (observed runs: 1.44s total, no flakes).
- The except-mapping remap (weakness #1) is the only candidate-behavior concern that could warrant a future change; it was not dynamically observed to misfire and does not block this claim.

## Guardrails honored
- No claim of forcibly preempting connect/close; no hard real-time scheduling claim.
- No inference of the root cause of historical wall-clock CI failures.
- No full-repo, author-suite, or production acceptance claimed; scope limited to the FQ claim.
- Test collection/import error classified BLOCKED_PROBE, not a product bug; unexecuted claims recorded as not_verified.

## Rationale
Independent dynamic probes verify the heart of the claim — no grant renewal across setup/monitor scheduling, synthesis-reserve respect, cancellation-vs-timeout cause preservation (pre-execute case), late-SQL-success rejection, and unconditional connection cleanup — with a working positive control. Author tests were blocked (sandbox), and several declared subclaims (late fetch/close-success edges, monitor-recorded cancel mapping, fetch-loop paths) were not executed. Partial claim coverage + blocked author suite ⇒ **PASS_WITH_LIMITS**, not PASS.
