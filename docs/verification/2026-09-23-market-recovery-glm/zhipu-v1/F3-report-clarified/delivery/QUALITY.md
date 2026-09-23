# Quality Review — F3, candidate 50330cf4fa435292bbd555ccc817e62ca5cc45b4

**Verdict: PASS_WITH_LIMITS** (independent evidence quality is good for the tested core; gaps remain in coverage breadth and dynamic boundary verification).

## Evidence quality

### Strengths
- **Immutable, self-contained probe** (`F3-execute/probe.py`, sha256 f9262a29…b144, verified unchanged by the execution driver, `inputs_unchanged: true`): fresh `:memory:` DuckDB per test, real `db.init_db`, real candidate functions only, no author-test imports.
- **Assertion strength matches the expanded scope**: full 14-column `SELECT *` logical row equality on both the target day (2026-09-22) and the seeded other day (2026-09-21) for every refusal case, including the missing-`policy` case; the positive control snapshots the other day before writing and compares after.
- **Positive control worked**: the intentional `assert 1 == 2` red assertion failed (1 failed / exit 1, `positive_control_detected: true`). Classified **probe_bug** by design — it proves the runner reports genuine failures rather than silently green-washing. Not a product bug.
- **Clean execution envelope**: probe 6/6 passed in 1.45s (no deadline hit, no sandbox production access); author suite 28/28 passed (informational — source withheld this phase); no collection or import errors anywhere, so no BLOCKED_PROBE condition arose.
- **Honest scoping in the delivered EXPLORE.md**: the untested subclaims were declared before execution, and the executed artifacts match that declaration.

### Weaknesses / residual risk
1. **Truthy non-boolean coverage is a 3-point sample** (`1`, `"yes"`, `[True]`). `is not True` is total by Python semantics, but e.g. `numpy.bool_(True)`, `0.5`, or `{"a":1}` were never executed against the guard.
2. **Transaction boundary corroboration is indirect.** No instrumentation of BEGIN/ROLLBACK, no injected failure after `DELETE` (line 266) or between `executemany` batches (line 270), no second connection. Mid-transaction crash-rollback is unverified; the observed preservation is consistent with rollback but does not isolate it from "guard fired before any write".
3. **Other-date protection observed on exactly one seeded date.** The in-code integer-hash drift check (lines 243-247, 277-283) is well designed against the documented floating-point-sum nondeterminism, but dynamically it only ever ran over a 2-date dataset.
4. **Stale-plan simulation, not a witnessed workflow**: plans are hand-built dicts; `build_bridge_day` was never run on an empty day and then raced against intervening inserts. The claim's "stale plan" semantics are exercised; the operational path producing one is not.
5. **Equality is logical SQL value equality** (DuckDB `fetchall`); nothing about physical/byte-level storage is inferred.

### Author-test relation
Author tests: 28/28 passed. Their source is withheld in this phase, so no per-test mapping to F3 subclaims is possible; they are counted as corroboration of general module health only and weigh nothing toward the independent verdict.

## Scope discipline (per stage rules)
- This certifies **only the fixed candidate revision** 50330cf4fa435292bbd555ccc817e62ca5cc45b4 (source sha256 2435c350…c119). Main has advanced (f47d464…); **no merge admission is implied**.
- Not a full-repo review, not a production acceptance, and not a statement about `build_bridge_day` gates, fingerprints, concurrency, or mootdx partial flush — all explicitly out of scope for F3 or unexecuted.

## Recommendation
Accept F3 at **PASS_WITH_LIMITS** for the candidate revision. If a follow-up round is cheap, the highest-value additions are: (a) an injected failure between `DELETE` and `INSERT`/after partial `executemany` to dynamically witness rollback, and (b) two or three additional truthy values (e.g. `0.5`, `numpy.bool_(True)`, non-empty dict) on the same one-line guard.
