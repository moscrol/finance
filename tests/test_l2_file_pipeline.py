from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

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


def test_nightly_finalize_calls_code_root_l2_and_drops_pause_flag():
    """契约：L2 代码走 CODE_ROOT（冻结快照），状态 / 库走 DATA_ROOT；挂账 flag 随 ClickHouse 退役。

    主检出树里的运营覆盖版曾把 L2 改成从 $DATA_ROOT 执行——那是代码还没进主干时的权宜
    （运行快照里没有这些脚本），不是设计：分享入口 / 日包缓存 / Cookie 都由 l2_paths.py 按
    FINANCE_DATA_ROOT 与家目录解析，与代码根无关。搬进主干后回到与质检闸门同一条纪律。
    """
    text = NIGHTLY.read_text(encoding="utf-8")
    assert "if [ -f \"$L2_PAUSED_FLAG\" ]" not in text
    assert "L2_PAUSED_FLAG=" not in text
    assert "clickhouse.env" not in text
    assert "CH_PASSWORD" not in text
    assert 'L2_LOCK_HELD=1 "$CODE_ROOT/scripts/moneyflow/run_l2_pipeline.sh"' in text
    assert "$DATA_ROOT/scripts/moneyflow/run_l2_pipeline.sh" not in text


def test_run_l2_pipeline_code_root_is_its_own_tree_and_state_is_data_root():
    text = PIPELINE.read_text(encoding="utf-8")
    assert 'CODE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"' in text
    assert 'moneyflow_dir="$CODE_ROOT/scripts/moneyflow"' in text
    assert '"$DATA_ROOT/state/l2-baidu-share.json"' in text
    # 代码走 CODE_ROOT；DATA_ROOT 只留给数据面（outputs / state / db）
    assert '"$CODE_ROOT/scripts/render_moneyflow_html.py"' in text
    assert 'git -C "$CODE_ROOT"' in text
    assert "$DATA_ROOT/scripts/moneyflow/run_l2_from_share.py" not in text
    assert "$DATA_ROOT/scripts/render_moneyflow_html.py" not in text


def test_load_ticks_scales_price_and_keeps_active_side(tmp_path):
    # 属于 L2 日包解包口径（process_l2_archive），从资金面板测试文件迁来：那边不依赖 scripts/moneyflow
    from process_l2_archive import capital_from_ticks, load_ticks

    csv_path = tmp_path / "逐笔成交.csv"
    csv_path.write_bytes(
        (
            "时间,成交价格,成交数量,叫买序号,叫卖序号\n"
            "093000000,100000,1000,2,1\n"
            "093001000,100000,1000,2,1\n"
            "093002000,101000,1000,3,4\n"
        ).encode("gb18030")
    )
    ticks = load_ticks(csv_path)
    assert list(ticks["price"]) == [10.0, 10.0, 10.1]
    assert ticks["buy_no"].iloc[0] > ticks["sell_no"].iloc[0]
    active, total, change = capital_from_ticks(pd.DataFrame(ticks))
    assert change == pytest.approx(1.0)
    assert isinstance(active, float)
    assert isinstance(total, float)
