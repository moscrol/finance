# C3 explore (revision 3c5b, axis C3 only)

## Supplied probe provenance
- probes/probe_c3_acceptance_v2.py: prior-reviewer assertions (6 mutations: amount/timestamp/delete/insert/duplicate/other_stock + baseline PASS). Reuses author fixture `_build_e2e_artifacts`; assertions are reviewer's own. Not run this session yet.
- probes/test_seeded_c3.py: HOST wrapper with fixture repairs only (receipt copy to clone-derived filename; other_stock mutated on CAL[0] since OTHER lacks LATER rows). No prior results supplied.
- Candidate `_data_checks` (540-728) confirmed: multiset EXCEPT ALL outside-window check `target_outside_window_allcols` (all cols, fwd/rev), `fact_other_stocks_allcols`, retained-rows full-column identical, keyset oracle from baseline prod source. Duplicate CTAS disclosure: PK removed clone-only.
- Planned extra reviewer mutation (not in supplied set): update a technical/feature protected table row outside window OR trade_date shift on outside-window row -> expect technical_protected_allcols / outside-window catch. Simpler: mutate fact_market_daily (market_daily_untouched). But C3 scope = outside-window target rows; choose a pct/amount mutation on an inside-window retained row covered by retained check already. Extra: swap trade_date of two outside-window rows (timestamp-like but key-level).
## Counts so far: explore 3 requests.
