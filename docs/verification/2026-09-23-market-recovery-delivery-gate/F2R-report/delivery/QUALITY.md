# F2R Quality Assessment — Candidate 4dd5e66

## Verdict: PASS_WITH_LIMITS

Core claim F2 verified by independent execution against the real candidate path; one enumerated claim element (−infinity close) was never executed, so full PASS is not justified. No product defects found.

## Evidence Inventory

| Evidence | Result | Assessment |
|----------|--------|------------|
| `F2R-execute/probe.stdout` | 9 passed in 4.56s, exit 0 | Independent probe, real candidate functions, in-memory fixtures, author tests never imported |
| `F2R-execute/positive.stdout` | 1 failed (`assert 1 == 2`), exit 1 | Intentional red → **probe_bug**, detected; proves harness reports failures |
| `F2R-execute/author.stdout` | 75 passed, exit 0 | Corroborating only; not independently audited; author verdicts withheld |
| `F2R-execute/execution.json` | complete=true, inputs_unchanged=true, positive_control_detected=true, revisions match candidate | Provenance sound; sandbox denies production |
| prior `F2-execute/probe.stdout` | 7 failed (BinderException) | Fully diagnosed fixture defect, not carried over |

## Probe Quality

**Strengths**
- Full-row `SELECT * ORDER BY ALL` snapshots across all four tables (no date filter) — detects value mutation and cross-date deletion, not just count drift. Directly addresses the controller's warning that row counts don't establish unchanged values.
- Correct adversarial targeting: case 3 puts the invalid close on **OUT**, a stock outside the declared sector, which is exactly the "outside-sector bars consumed by market counts" clause; the candidate's scan at `compute_local_stats.py:233-236` iterates all `today` bars, and the probe proves it.
- Seeded `local:seed` rows guarantee the exercised branch is the recovery refusal logic, not the foreign-rows skip (verified against L198–205).
- Fixture root cause of the first failed delivery (9 unnamed values into 14-column `fact_stock_daily`) identified and fixed with named columns; the fix is visible and minimal.

**Weaknesses / gaps**
- Parametrization `[None, -1.0, 0.0, nan, inf]` omits `-inf` although the claim says "+/-infinity". `math.isfinite(-inf)` is False so the same line rejects it, but it was never executed ⇒ not_verified ⇒ the "LIMITS" in the verdict.
- Invalid-close refusal executed only on an outside-sector bar; a member bar with a bad close shares the same scan line but was not separately exercised.
- Success-path verification is shallow (result-dict fields and counters); written row contents (ratios, ladder, leader rows) not deeply asserted.
- Nontrading "dated evidence" provenance is trusted from the caller, as the explore notes concede.

## Positive Control

`positive_control.py:2` — `assert 1 == 2, "intentional positive control: probe_bug"` → AssertionError, exit 1, `positive_control_detected=true`. **Classification: probe_bug** (intentional red assertion, per protocol). Functioned as designed: demonstrates the sandboxed pytest harness surfaces failures, so the probe's 9/9 pass is meaningful signal rather than a collection artifact.

## Prior Failure Disposition

The first delivery's 7/7 failures were a `BinderException` at fixture setup (line 52, unnamed 9-value INSERT into the 14-column table). This was a probe fixture bug — not a product bug and not a collection/import error — so no BLOCKED_* verdict applied then and no behavioral conclusion is carried into this review. The second delivery is evaluated solely on its own execution evidence.

## Limitations

- −infinity close untested (sole reason for PASS_WITH_LIMITS).
- Member-bar invalid close, deep write-content correctness, default path, `force=True`, other-field validation (NaN amount, `pre_close<=0`), concurrency: untested (mostly out of claim scope).
- Author suite (75/75) corroborates but was not independently audited.
- Verdict is scoped to candidate revision `4dd5e66` on in-memory DuckDB fixtures. **No full-repo acceptance and no production acceptance is claimed** (sandbox denies production access).

## Recommendation to Lift Limits

Add `-float("inf")` to the invalid-close parametrization and one member-bar-invalid-close case; both target the same verified line, so a subsequent full PASS should be cheap to establish.
