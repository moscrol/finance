# Quality Review — F3 (apply_bridge_day in-transaction recheck)

**Verdict: PASS_WITH_LIMITS** · Candidate `50330cf4fa435292bbd555ccc817e62ca5cc45b4`

## What was independently executed

6/6 independent probes passed (exit 0, 2.21s); positive control classified **probe_bug**
(intentional red assertion `assert 1 == 2` failed, as designed); author suite 28/28 passed
(exit 0) — consistent with, but never substituted for, the independent run.

| Subclaim | Status | Evidence |
|---|---|---|
| In-txn recheck: stale default plan refuses, rows unchanged | ✅ verified | probe + source L262–265 |
| Truthy non-booleans (1, "yes", [True]) refuse | ✅ verified (3 cases) | probe parametrize |
| Missing `policy` key refuses | ✅ verified | probe |
| Literal True replaces; 2nd stale default refuses; written persist | ✅ verified | probe positive control |
| Other dates unchanged | ✅ verified (logical 14-col equality, both days) | probe |
| Empty-rows branch; wider truthy domain; build-side checks; fingerprints; concurrency | ⬜ not verified | not executed |

## Why limits, not full PASS

- **Single connection only** — no concurrency isolation proven (claim itself puts the
  concurrent scheduler out of scope, but the single-connection caveat must stand).
- **Truthy domain sampled** {1, "yes", [True]} — not exhaustive.
- **Empty-rows refusal branch untested.**
- **Logical equality only** — `fetchall()` row comparison; no physical byte preservation
  or storage-level assertion. No production or full-repo execution; no merge admission.

## Reporting-constraint compliance

- Cited exactly the executed cases, seeded dates (2026-09-21 `000001.SZ`, 2026-09-22
  `600000.SH`/`600519.SH`) and the exact 14 compared columns.
- No inference beyond final row equality: no concurrency, no unseen parameter cases,
  no byte-identical storage, no fingerprint/mootdx behavior.
- Unexecuted subclaims recorded as **not_verified**, never as failures.

## Bug classification

None. The only red signal (positive control) is the harness's intentional assertion and is
classified **probe_bug**, not a product defect. No BLOCKED conditions: probe and author
collections both collected and ran without import errors.
