"""PR 773 review probe: corrupt partial extraction must not become complete.

All source selection/network boundaries are stubbed. Parsing, aggregation, database
writers, the review checker and the next-run skip decision use candidate code.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(sys.argv[1]).expanduser().resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/moneyflow"))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="pr773-partial-") as temp:
        data = Path(temp)
        db_path = data / "market.duckdb"
        os.environ["MARKET_FEATURE_STORE_DB"] = str(db_path)
        os.environ["FINANCE_DATA_ROOT"] = str(data)
        os.environ["L2_CACHE_DIR"] = str(data / "cache")
        for name in ("L2_FORCE_RESCAN", "L2_PAUSED", "L2_ALLOW_ALL_EMPTY"):
            os.environ.pop(name, None)

        import duckdb
        import process_l2_archive as archive_module
        import run_l2_from_share as runner
        from market_feature_store.db import init_db
        from scripts import check_daily_review_data as checker

        con = duckdb.connect(str(db_path))
        init_db(con)
        con.close()
        archive = data / "20260916.7z"
        archive.touch()
        codes = [f"{600000 + index:06d}" for index in range(100)]
        day = "20260916"

        def corrupt_extraction(cmd, **kwargs):
            outdir = Path(next(arg[2:] for arg in cmd if arg.startswith("-o")))
            tick_file = outdir / day / "600000.SH" / "逐笔成交.csv"
            tick_file.parent.mkdir(parents=True)
            tick_file.write_bytes(
                (
                    "时间,成交价格,成交数量,叫买序号,叫卖序号\n"
                    "093000000,100000,200000,2,1\n"
                ).encode("gb18030")
            )
            return subprocess.CompletedProcess(cmd, 2, "ERROR: CRC Failed", "Data Error")

        with (
            patch.object(archive_module, "prev_trade_date", return_value="2026-09-15"),
            patch.object(archive_module, "duck_limitup_codes", return_value=[codes[0]]),
            patch.object(archive_module, "duck_top_turnover_codes", return_value=codes),
            patch.object(archive_module, "duck_pct_chg_map", return_value={c: 1.0 for c in codes}),
            patch.object(archive_module, "stock_info", return_value={c: {"name": c, "cap": 100.0} for c in codes}),
            patch.object(archive_module, "_seven_zip", return_value="stub-7zz"),
            patch.object(archive_module.subprocess, "run", side_effect=corrupt_extraction),
        ):
            result = archive_module.process_date("2026-09-16", archive)

        with (
            patch.object(checker, "is_trading_day", return_value=True),
            patch.object(checker, "_connect_read_only", side_effect=lambda: duckdb.connect(str(db_path), read_only=True)),
        ):
            problems = checker.check_l2("2026-09-16")
        con = duckdb.connect(str(db_path), read_only=True)
        ledger = con.execute(
            "SELECT step, status, row_count, input_count, processed_count, failed_count "
            "FROM ops_pipeline_run_daily WHERE pipeline='l2-moneyflow' ORDER BY step"
        ).fetchall()
        con.close()
        skipped = runner.already_complete("2026-09-16")
        print(json.dumps({"result": result, "ledger": ledger, "quality_problems": problems, "next_run_skips": skipped}, indent=2))
        assert result["top100"] == 1
        assert not problems
        assert skipped
        print("REPRODUCED: corrupt 1/100 extraction accepted; future ordinary run skips repair")


if __name__ == "__main__":
    main()
