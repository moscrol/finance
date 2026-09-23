"""Author-side boundary probe, not independent QC. Writes only in-memory fixtures.

Run with the pinned candidate on PYTHONPATH. Fixture helpers come from its own
unit tests; this is an adversarial input extension, not a new reviewer identity.
"""
import importlib.util
import json
from pathlib import Path

import market_feature_store.sync.compute_local_stats as target

root = Path(target.__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("fixtures", root / "tests/test_compute_local_stats.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)

results = []
for label, close in [("null", None), ("nan", float("nan")), ("infinity", float("inf")),
                     ("negative_infinity", float("-inf")), ("zero", 0.0), ("negative", -1.0)]:
    with fixtures._db() as con:
        fixtures._seed_two_days(con)
        fixtures._seed_universe_and_members(con)
        declared = {"990001.FP": ["600001.SH", "300001.SZ", "000001.SZ"], "990002.FP": ["002514.SZ"]}
        target.compute_limit_stats_local("2026-09-02", con=con, recovery_members=declared)
        tables = ("fact_theme_limit_heat_daily", "fact_theme_limit_stock_daily",
                  "fact_limit_advance_daily", "fact_leader_height_daily")
        before = {t: con.execute(f"SELECT * FROM {t} ORDER BY ALL").fetchall() for t in tables}
        con.execute("UPDATE fact_stock_daily SET close=? WHERE trade_date='2026-09-02' AND stock_ts_code='000001.SZ'", [close])
        try:
            result = target.compute_limit_stats_local("2026-09-02", con=con, recovery_members=declared)
            outcome = {"accepted": True, "action": result["action"],
                       "coverage": result["recovery_member_coverage"]["990001.FP"]}
        except (ValueError, RuntimeError) as exc:
            outcome = {"accepted": False, "error": str(exc)}
        after = {t: con.execute(f"SELECT * FROM {t} ORDER BY ALL").fetchall() for t in tables}
        results.append({"case": label, **outcome, "derived_rows_unchanged": before == after})
print(json.dumps({"module": str(Path(target.__file__).resolve()), "author_side": True,
                  "production_database_opened": False, "results": results}, indent=2))
