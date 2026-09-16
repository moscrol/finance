from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONEYFLOW = ROOT / "scripts" / "moneyflow"
sys.path.insert(0, str(MONEYFLOW))

from l2_paths import archive_name, month_dir, yyyymmdd  # noqa: E402

NIGHTLY = ROOT / "skills" / "daily-full-review" / "scripts" / "nightly_full_review.sh"
PIPELINE = ROOT / "scripts" / "moneyflow" / "run_l2_pipeline.sh"


def test_archive_name_and_month_dir_come_from_the_trade_date():
    assert yyyymmdd("2026-09-10") == "20260910"
    assert month_dir("2026-09-10") == "202609"
    assert archive_name("2026-09-10") == "20260910.7z"
    assert month_dir("2026-10-08") == "202610"


def test_run_l2_pipeline_is_file_source_only():
    text = PIPELINE.read_text(encoding="utf-8")
    assert "clickhouse.env" not in text
    assert "CH_PASSWORD" not in text
    assert "scan_limitup.py" not in text
    assert "run_l2_from_share.py" in text
    assert "l2-baidu-share.json" in text


def test_nightly_finalize_calls_data_root_l2_and_drops_pause_flag():
    text = NIGHTLY.read_text(encoding="utf-8")
    assert "if [ -f \"$L2_PAUSED_FLAG\" ]" not in text
    assert "L2_PAUSED_FLAG=" not in text
    assert "clickhouse.env" not in text
    assert "CH_PASSWORD" not in text
    assert 'L2_LOCK_HELD=1 "$DATA_ROOT/scripts/moneyflow/run_l2_pipeline.sh"' in text
    assert "$CODE_ROOT/scripts/moneyflow/run_l2_pipeline.sh" not in text
