# EXPLORE notes — FinanceQuery.run absolute deadline / cancellation review

Candidate `1de68567e740a9a5d9c25bea91142741ad12aa10` (base `c9dd71df`). Packet read once; static analysis only in this phase. **No execution available here; no PASS declared.** The probe below is immutable and will be run by the next host phase.

## Scope reviewed (from packet)
- `FinanceQuery.run` (L2189–2321), `_fetch_rows` (L2380–2424), `_rows_to_evidence` (L2748–2792) in `intelligence/services/finance_query.py`; `ResearchDeadline` (L359–401) and `InformationCutoff` (L1241+) in `intelligence/services/research_contract.py`.

## Probe design (real candidate functions, fresh fixtures)
- Real: `FinanceQuery.run`, `FinanceQuerySpec.from_arguments` (market_daily empty-result query per packet guidance), `FinanceQueryLimits`, `ResearchDeadline.from_timeout`/`stage_timeout`/`bounded_stage` (exercised inside `run`), `InformationCutoff(date(2026,7,24),"requested")`. SQL compilation is real. No production DB / network / model calls; author tests never imported.
- Fixtures: `FakeConnection`/`EmptyCursor` implementing `execute(sql, parameters)->cursor`, `cursor.fetchmany(n)->[]`, `interrupt()`, `close()`, injected via the `connect` constructor parameter; `connect` asserts `read_only=True`.
- **Control**: happy path → empty `FinanceQueryResult`, exactly one `execute`, zero interrupts, exactly one `close`.
- **Adversarial 1 (setup must not renew grant; reserve respected)**: parent `from_timeout(5.0, synthesis_reserve=4.8)`, `limits.timeout=8.0` → bounded grant ≈ 0.2s (asserted `0 < stage_timeout(8.0) <= 0.25`). `connect` sleeps 0.4s → expect `FinanceQueryTimedOut`; `execute_calls == []` (no late SQL), `interrupt_calls == 0` (expiry caught before monitor scheduling), `close_calls == 1`.
- **Adversarial 2 (late SQL success after timeout interrupt rejected)**: `execute` blocks on an `Event` that only `interrupt()` sets (5s safety timeout), grant 0.5s → monitor interrupts, then SQL "succeeds" → expect `FinanceQueryTimedOut` post-fetch; `execute_calls == 1`, `interrupt_calls >= 1`, `close_calls == 1`. Event gating makes the interrupt→return ordering deterministic rather than sleep-raced.
- **Adversarial 3 (cancellation beats late setup success)**: `is_cancelled` returns False for the entry/pre-connect checks and True from the pre-execute check → expect `FinanceQueryCancelled`, no SQL, `close_calls == 1`.

## Static observations (dynamically unverified in this phase)
- The grant is fixed once (`deadline.bounded_stage(self._limits.timeout)`, L2209) **before** connection setup and monitor scheduling, so setup consumes the absolute grant; `bounded_stage` intersects with `parent.expires_at - synthesis_reserve`, and the child grant carries no reserve of its own. Setup cannot renew the timeout.
- Grants with `remaining() <= 0.001` are rejected upfront (L2210) even if not yet expired.
- Cause preservation: the first `interrupted_for` marker ("cancelled"/"timeout") decides the mapping in both the except path (L2261–2267) and the post-fetch check (L2276–2279); the final `query_deadline.expired` check (L2287) rejects success landing after the last check. Late SQL/fetch success after an interrupt is discarded.
- Outer `finally` (L2282) always sets `stop_monitor` and closes a non-None connection; monitor is a daemon thread joined with `timeout=0.2`.
- Except-mapping can remap a fetch-loop `FinanceQueryLimitExceeded` (or fetch-loop `Cancelled`) to `TimedOut`/`Cancelled` when the monitor already recorded a cause — cause priority belongs to the monitor marker.

## Untested subclaims (honest)
- **No preemption of connect()/close()**: a `connect` that blocks forever still blocks `run()` forever. The probe's 0.4s connect only verifies deadline accounting, not unblocking (packet explicitly disclaims preemption).
- Real DuckDB `interrupt()` semantics, close-under-interrupt behavior, and the root cause of historical wall-clock CI failures are untested / not inferred, per packet.
- Fetch-loop cancellation between `fetchmany` batches, byte-limit (`FinanceQueryLimitExceeded`) paths, `reverse_after_fetch`, `dataset_max_date` swallowing `FinanceQueryError`, `_rows_to_evidence` content/evidence hashing, and monitor-thread leak when `interrupt()` blocks (join timeout 0.2s, daemon) — all untested.
- The pure monitor-recorded "cancelled" → `FinanceQueryCancelled` mapping is not isolated (adversarial 3 may raise at the pre-execute check before the monitor records; outcome is the same exception type either way).
- Timing margins are generous (0.2s grant vs 0.4s connect; 0.5s grant with event-gated execute) but adversarial 1/2 still depend on real scheduling; under extreme host load the sanity bound `stage_timeout(8.0) <= 0.25` could in principle flake, and adversarial 2 relies on the monitor's ≤10ms polling to fire before the 5s gate timeout.

## Verdict
Pending execution of the immutable probe by the next host phase. No PASS declared pre-execution.
