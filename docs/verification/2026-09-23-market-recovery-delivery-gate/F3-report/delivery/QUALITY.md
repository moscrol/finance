# K3 Quality Assessment — F3 — candidate 4dd5e66601084962697c5d78e9f6bb58eefc14c8

## Evidence quality: HIGH for the executed scope

### Independence & provenance
- Probe authored in the isolated explore phase (provenance:
  `.../delivery-gate-4dd5e66/F3-explore/delivery`), immutable into execute phase;
  sha256 recorded (`probe.py=24cd07a4…`, `positive_control.py=5aafcdf0…`),
  `inputs_unchanged: true` after execution.
- Author tests were **withheld during probe design** — the probe is genuinely
  independent, then the author suite (28 tests) was run afterwards and agrees.
- No author verdicts were provided; none were assumed.

### Execution hygiene
- OS-sandboxed (`sandbox-exec -f tools.sb`), `python -B`, `-p no:cacheprovider`,
  `--confcutdir` isolation, `-o addopts=` to neutralize repo pytest config,
  junit XML captured, deadlines not hit, exit codes recorded.
- Probe and author runs: exit 0, **zero collection/import errors** → no
  BLOCKED_PROBE condition. Positive run: exit 1 by design.
- No production DB access (sandbox denies; fixtures are fresh `:memory:`).

### Positive control (harness sensitivity)
- `test_intentional_red_probe_bug` (`assert 1 == 2`) failed exactly as designed.
- **Classification: probe_bug** (intentional red assertion). It is NOT a product
  defect. It confirms the harness really executes assertions and reports reds.

### Corroboration
- Static read of `bridge_hithink_stock_daily.py` matches every dynamic result:
  BEGIN (L260) precedes recheck (L262–265); identity guard `is not True` (L264);
  refusal raised inside `try` with `ROLLBACK` + re-raise (L289–291);
  drift/gone guard (L277–283); final-count guard (L284–287).
- Probe uses the real `BridgePolicy().as_dict()` and the exact 14-column tuple
  shape `executemany` consumes — no mocks of the unit under test.

### Weaknesses / honesty notes
1. "Inside its transaction" is proven statically + behaviorally on a single
   connection; the tests cannot distinguish in-tx from pre-tx recheck, and true
   concurrent interleaving is out of scope and untested.
2. Rollback is only exercised on the pre-write refusal path (nothing to undo);
   rollback after a mid-transaction failure is untested.
3. The drift/gone guard is asserted only via its end-to-end property; it cannot
   be triggered through the public API without an internal bug.
4. Plans are hand-built; `build_bridge_day` and `preview_stock_calculation` are
   not exercised (correctly out of claim scope).
5. Static observation (info, not a defect on tested paths): `_day_fingerprints`
   (L243–247) covers row count + hash(code, close, amount, pre_close) only —
   a write touching exclusively open/high/low/volume/pct_chg/stock_name on
   another day would evade the guard.
6. `policy=None` (vs absent key) would raise AttributeError instead of
   BridgeRefused; caught and rolled back, so no corruption, but untyped. Not
   part of the claim.

### Conclusion
Evidence is sufficient, independent, executed, and internally consistent for
every in-scope subclaim. Verdict **PASS_WITH_LIMITS** — no full-repo, no
production, and no concurrency acceptance is claimed or implied.
