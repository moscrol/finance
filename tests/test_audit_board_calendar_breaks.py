from __future__ import annotations

from datetime import date
from pathlib import Path

from intelligence.tests.test_board_calendar import _candidate_db, _quote_table
from scripts.audit_board_calendar_breaks import audit, main, to_markdown


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "audit.duckdb"
    _candidate_db(db)
    _quote_table(
        db,
        [
            ("2026-09-23", "600001.SH", "真断", 10.99, 10.00, 9.9, 3.2e8),
            ("2026-09-23", "600003.SH", "*ST戴帽", 10.30, 10.00, 3.0, 1.0e8),
            ("2026-09-23", "600004.SH", "漏名单", 11.00, 10.00, 10.0, 5.0e8),
        ],
    )
    return db


def test_audit_reuses_calendar_verdicts_and_lists_raw_rows(tmp_path: Path) -> None:
    report = audit(_db(tmp_path), date(2026, 9, 1), date(2026, 9, 30))

    assert report["counts"] == {"closed_at_limit": 1, "no_trade": 1, "st_scope": 1, "traded": 1}
    by_name = {item["stock_name"]: item for item in report["items"]}
    # 收盘离涨停价 1 分：已判断板，但标记给人复核取整。
    assert by_name["真断"]["kind"] == "break"
    assert by_name["真断"]["quote"]["up_px"] == 11.0
    assert set(by_name["真断"]["flags"]) == {"near_limit_price", "high_pct_but_not_sealed"}
    assert by_name["漏名单"]["flags"] == ["verify_list_completeness"]
    # 停牌：无行情行保持 None，不补零。
    assert by_name["停牌股"]["quote"] is None
    assert by_name["停牌股"]["list_previous"]["boards"] == 6
    assert by_name["停牌股"]["list_day"] is None
    assert report["flagged"] == 2


def test_markdown_marks_missing_as_dash_and_cli_writes_files(tmp_path: Path) -> None:
    db = _db(tmp_path)
    md = to_markdown(audit(db, date(2026, 9, 1), date(2026, 9, 30)))
    assert "待核:no_trade" in md and "| — |" in md

    out_json, out_md = tmp_path / "r.json", tmp_path / "r.md"
    assert main(["--db", str(db), "--start", "2026-09-01", "--end", "2026-09-30",
                 "--json", str(out_json), "--md", str(out_md)]) == 0
    assert out_json.read_text(encoding="utf-8").startswith("{")
    assert out_md.read_text(encoding="utf-8").startswith("# 连板日历断板抽样核对")


def test_missing_database_fails_closed(tmp_path: Path) -> None:
    assert main(["--db", str(tmp_path / "none.duckdb"), "--start", "2026-09-01", "--end", "2026-09-30"]) == 1
