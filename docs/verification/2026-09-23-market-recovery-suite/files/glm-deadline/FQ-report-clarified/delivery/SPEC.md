# Independent Review Spec — FQ: FinanceQuery.run absolute query deadlines

- **Candidate:** `1de68567e740a9a5d9c25bea91142741ad12aa10` (base `c9dd71dfd678855b61662100ec74625b92ad1f1b`)
- **Verdict:** `PASS_WITH_LIMITS` — only part of the claim was tested dynamically
- **Reviewer:** independent (GLM); author verdicts were not provided and none are assumed

## 1. Claim under review

`FinanceQuery.run` absolute query deadlines: setup and monitor scheduling must not renew the timeout; respect parent synthesis reserve; preserve cancellation vs timeout; reject late SQL/fetch/close success and clean up connections; investigate regressions and uncovered deadline/cancellation edges.

Explicit non-goals (per packet): no claim of forcibly preempting `connect()`/`close()`, no hard real-time OS scheduling, no inference of the root cause of historical wall-clock test failures, no full-repo or production acceptance.

## 2. Claim decomposition

| ID | Subclaim | Primary code site |
|----|----------|-------------------|
| S1 | Setup must not renew the fixed absolute grant | finance_query.py L2209, L2222-2223 |
| S2 | Parent synthesis reserve shrinks the child grant | research_contract.py L393-401 |
| S3 | Nearly-exhausted grants rejected upfront (≤0.001s, before connect) | finance_query.py L2210-2211 |
| S4 | Cancellation preserved vs timeout (cause wins by marker) | L2225-2279, L2216-2245 |
| S5 | Late SQL success after interrupt rejected | L2248-2279 |
| S6 | Late fetch success (populated rows) after interrupt rejected | L2380-2424, L2276-2279 |
| S7 | Late close success rejected | L2282-2287 |
| S8 | Connections always cleaned up | L2282-2285 |
| S9 | Regressions / uncovered edges investigated | whole file + suites |

## 3. Methodology

- **Independent probe (immutable):** source `FQ-explore/delivery/probe.py` (sha256 `7c0801e2…`, per `manifest.json`); executed unchanged under an OS sandbox that denies production access in `FQ-execute` (`inputs_unchanged: true`). Real `FinanceQuery.run`, real SQL compilation via `FinanceQuerySpec.from_arguments`, real `ResearchDeadline` semantics; fixtures are an injected `FakeConnection`/`EmptyCursor` (`execute`/`fetchmany`→`[]`/`interrupt`/`close`); `connect` asserts `read_only=True`. No author tests imported; no production DB/network/model calls.
- **Probes:** control happy path; adversarial 1 setup-vs-grant (parent 5.0s window, 4.8s reserve, `limits.timeout=8.0`, connect sleeps 0.4s); adversarial 2 late-SQL success (execute gated on an `Event` only `interrupt()` sets, grant 0.5s); adversarial 3 cancellation precedence (`is_cancelled` false×3 then true).
- **Positive control:** intentional red assertion `assert 1 == 2` — must be classified `probe_bug`.
- **Author suites:** original run (blocked at collection) and a separate recheck run; reported separately.
- **Historical replay:** byte-identical probe at revision `50330cf4` — sensitivity evidence only.

## 4. Verification matrix

| ID | Status | Evidence |
|----|--------|----------|
| S1 | **verified_dynamic** | Adversarial 1: `FinanceQueryTimedOut`; `execute_calls == []`, `interrupt_calls == 0` (expiry at post-connect check), `close_calls == 1`. Note: connects first — this is *not* the upfront no-connect rejection. |
| S2 | **verified_dynamic** | Sanity `0.0 < stage_timeout(8.0) <= 0.25` held; child `expires_at = min(parent.expires_at − reserve, now + limit)`; shrunken grant drove the S1 timeout. |
| S3 | **static only / not verified** | L2210-2211 unexercised; setup probe performed one connect and one close before expiring. |
| S4 | **verified_dynamic (outcome level)** | Adversarial 3: `FinanceQueryCancelled`, zero executes, one close. Thread/check site not recorded — not pinned to a specific check. |
| S5 | **verified_dynamic** | Adversarial 2: SQL "succeeded" post-interrupt, still `FinanceQueryTimedOut`; `execute_calls == 1`, `interrupt_calls >= 1`, `close_calls == 1`. |
| S6 | **not verified** | Empty cursor only; populated-rows post-interrupt path unexecuted. |
| S7 | **static only / not verified** | L2287 checks expiry *after* `close()` in the finally; no dynamic delayed-close probe; author recheck adds no independent coverage. |
| S8 | **verified_dynamic** | `close()` exactly once in all four scenarios; `stop_monitor` always set. |
| S9 | **partial** | See findings: monitor ≤10ms cadence, except-remap priority, `dataset_max_date`, byte-limit path, reverse-after-fetch, monitor-thread lifecycle — static or untested. |

## 5. Execution record summary

| Run | Result |
|-----|--------|
| Independent probe (FQ-execute) | 4/4 passed, exit 0, 1.77s, no deadline hit |
| Positive control | 1 failure as designed, exit 1, `positive_control_detected: true` → **probe_bug** |
| Author suites — original | exit 4, `PermissionError` on `candidate/intelligence/users` at collection, 0 tests → **BLOCKED_PROBE** (not a product bug) |
| Author suites — recheck (separate run) | 151/151 passed, exit 0, 5.512s, same clean candidate; adds no independent coverage |
| Historical replay (rev `50330cf4`) | 2 failed / 2 passed, exit 1, 0 collection errors — host/revision sensitivity evidence only; no root-cause inference |

## 6. Verdict rationale

The core deadline/cancellation observables were dynamically verified with a functioning positive control, but S3, S6, S7 and several S9 edges were not executed, author evidence spans two separate runs (original blocked, recheck passing but not independent), and the historical replay demonstrates timing sensitivity. Only part of the claim was tested → **PASS_WITH_LIMITS**. This verdict covers the FQ claim only; it is not a full-repo review and implies no production acceptance, preemption guarantees, or historical root-cause conclusions.
