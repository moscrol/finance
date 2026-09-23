# FQ Stage Report Spec — FinanceQuery.run Absolute Query Deadlines

Candidate `1de68567e740a9a5d9c25bea91142741ad12aa10` (base `c9dd71dfd678855b61662100ec74625b92ad1f1b`). Independent review of claim **FQ**. **Verdict: PASS_WITH_LIMITS.**

## 1. Claim under review

`FinanceQuery.run` must enforce absolute query deadlines such that:
1. Connection **setup and monitor scheduling must not renew the timeout** — the grant is fixed once, before `connect()`.
2. The **parent synthesis reserve is respected** — pre-synthesis stages cannot consume the P0 reserve.
3. **Cancellation vs timeout is preserved** — the recorded cause (not exception arrival order) decides `FinanceQueryCancelled` vs `FinanceQueryTimedOut`.
4. **Late SQL/fetch/close success is rejected** — success landing after an interrupt or expiry must not publish a result.
5. **Connections are cleaned up** in all outcomes.

**Out of scope (per packet):** forcibly preempting `connect()`/`close()`; hard real-time OS scheduling; inferring the root cause of historical wall-clock test failures.

## 2. Mechanism (candidate source)

| Requirement | Implementation | Location |
|---|---|---|
| R1 one-shot grant | `query_deadline = deadline.bounded_stage(self._limits.timeout)` fixed before connect & monitor | `finance_query.py:2209` |
| R2 reserve respect | `bounded_stage` → `min(parent.expires_at - synthesis_reserve, now + limit)`; child carries no reserve | `research_contract.py:393-401` |
| R3 cause preservation | `interrupted_for[0]` ("cancelled" before "timeout") decides mapping in except and post-fetch paths | `finance_query.py:2225-2279` |
| R4 late-success rejection | post-fetch `interrupted_for` check + trailing `query_deadline.expired` check | `finance_query.py:2276-2279, 2287-2288` |
| R5 cleanup | outer `finally`: `stop_monitor.set()` + `connection.close()` | `finance_query.py:2282-2285` |
| Early guard | reject `remaining() <= 0.001` before any IO | `finance_query.py:2210-2211` |

## 3. Verification matrix

| # | Probe (independent, sandboxed, fresh fixtures) | Requirement | Result |
|---|---|---|---|
| 1 | Control: happy path empty result | sanity | ✅ PASS — rows `()`, row_count 0, 1 execute, 0 interrupts, 1 close |
| 2 | 0.4s connect inside ~0.2s grant (parent 5.0s, reserve 4.8s, limit 8.0) | R1+R2 | ✅ PASS — `FinanceQueryTimedOut`, 0 executes, 0 interrupts, 1 close; `0 < stage_timeout(8.0) <= 0.25` |
| 3 | Event-gated `execute` released only by `interrupt()`; SQL "succeeds" post-interrupt | R3+R4 | ✅ PASS — `FinanceQueryTimedOut`, 1 execute, ≥1 interrupt, 1 close |
| 4 | `is_cancelled` flips True at pre-execute check | R3 | ✅ PASS — `FinanceQueryCancelled`, 0 executes, 1 close |

Independent probe counts: **4 tests, 4 passed, 0 failures, 0 errors, exit 0**. Positive control: intentional red assertion detected (1 failure, exit 1) → classified **probe_bug** (harness detects failures correctly; not a product defect).

Author suites (`test_finance_query_deadline.py`, `test_finance_query.py`, `test_research_contract.py`, `test_episode_tools.py`): **exit 4, collection error** — `PermissionError: Operation not permitted` on `candidate/intelligence/users` under `sandbox-exec`; **0 author tests executed** → **BLOCKED_PROBE** (harness/sandbox issue, not a product bug); all author-side assertions are **not_verified**.

## 4. Verified vs not verified

**Verified (dynamic):** R1 no grant renewal across setup/monitor scheduling; R2 synthesis-reserve intersection (child grant ≈ parent window minus reserve); R4 late **SQL** success after timeout interrupt rejected; R3 cancellation beating late setup success (pre-execute check); R5 unconditional connection cleanup in all four scenarios; upfront rejection of nearly-exhausted grants; happy-path control.

**Not verified (unexecuted → not_verified):**
- Late **fetch**-loop success with populated rows post-interrupt (empty cursor only).
- Late **close**-success rejection semantics (close always runs in `finally`; not deadline-gated).
- Isolated monitor-recorded `"cancelled"` → `FinanceQueryCancelled` mapping (probe cancelled before the monitor recorded).
- Fetch-loop cancellation between `fetchmany` batches; `FinanceQueryLimitExceeded` byte-limit path; monitor-priority remap of fetch-loop errors (L2261-2267).
- Real DuckDB `interrupt()`/`close-under-interrupt` semantics (fake connection + Event gating only).
- Monitor thread lifecycle when `interrupt()` blocks (0.2s join, daemon).
- Entire author regression suite (blocked collection).

## 5. Verdict rationale

Core deadline architecture (R1, R2, R4-SQL, R5, partial R3) is dynamically verified by adversarial probes that passed 4/4 under sandbox, with a working positive control (probe_bug). However, part of the claim (late fetch/close success edges, monitor-recorded cancellation in isolation, fetch-loop paths) was not executed, and the author regression suite is blocked (BLOCKED_PROBE). Per policy — only part of the claim tested, author tests unexecuted — the verdict is **PASS_WITH_LIMITS**. No full-repo or production acceptance is claimed.
