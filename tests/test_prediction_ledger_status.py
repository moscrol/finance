"""预测台账体检脚本：只数 Open 主表、取值去注解、连击按时间序、口径与 crosswalk 同源。"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(name: str):
    if str(REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # 与 test_ledger_spec_crosswalk.py 同一取法：dataclass 要在 sys.modules 里找到所属模块。
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


status = _load("prediction_ledger_status")

HEADER = "| ID | 来源 | fix_type | verification_prediction | 怎么验 | outcome |\n|---|---|---|---|---|---|\n"


def _ledger(tmp_path: Path, open_rows: list[str], backfill_rows: list[str] = ()) -> Path:
    body = "# Prediction Ledger\n\n### Open（pending）\n\n" + HEADER + "\n".join(open_rows) + "\n\n"
    body += "### 2026-08-16 回填\n\n| ID | 新证据 | outcome | 处理 |\n|---|---|---|---|\n" + "\n".join(backfill_rows) + "\n"
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "prediction-ledger.md").write_text(body, encoding="utf-8")
    return tmp_path


def _row(rid: str, fix_type: str, outcome: str, source: str = "溯源 docs/x.md") -> str:
    return f"| `{rid}` | {source} | {fix_type} | 预测 | 怎么验 | {outcome} |"


def test_counts_only_open_table_and_strips_annotations(tmp_path):
    root = _ledger(
        tmp_path,
        [
            _row("R-20260801-01", "`HARNESS_FIX`（候，W2b 未派）", "`pending`"),
            _row("R-20260802-01", "`DATA_CONTRACT_FIX`", "`confirmed`（2026-09-01 复算）"),
            _row("R-20260803-01", "`EVAL_ONLY`", "**`refuted`**"),
        ],
        backfill_rows=["| `R-20260801-01` | 新证据 | `confirmed` | 保持 Open |"],
    )
    report = status.build_report(root, as_of=date(2026, 9, 30), stale_days=14)
    assert report["open_rows"] == 3
    assert report["outcomes"] == {"pending": 1, "confirmed": 1, "refuted": 1}
    assert report["fix_types"] == {"HARNESS_FIX": 1, "DATA_CONTRACT_FIX": 1, "EVAL_ONLY": 1}
    assert report["invalid_fix_types"] == []


def test_escaped_pipes_do_not_shift_columns(tmp_path):
    root = _ledger(tmp_path, [_row("R-20260801-01", "`ROUTING_FIX`", "`pending`", source=r"a \| b \| c")])
    row = status.parse_open_rows(root)[0]
    assert (row.fix_type, row.outcome) == ("ROUTING_FIX", "pending")


def test_unescaped_pipe_in_source_falls_back_to_enum_search(tmp_path):
    root = _ledger(tmp_path, [_row("R-20260801-01", "`TOOL_DESCRIPTION_FIX`", "`pending`", source="a | b")])
    row = status.parse_open_rows(root)[0]
    assert (row.fix_type, row.outcome) == ("TOOL_DESCRIPTION_FIX", "pending")


def test_invented_fix_type_is_reported_and_strict_fails(tmp_path, capsys):
    root = _ledger(tmp_path, [_row("R-20260801-01", "`CONTROL_FLOW_FIX`", "`pending`")])
    report = status.build_report(root, as_of=date(2026, 9, 30), stale_days=14)
    assert report["invalid_fix_types"] == ["CONTROL_FLOW_FIX"]
    assert status.main(["--root", str(root), "--as-of", "2026-09-30"]) == 0
    assert status.main(["--root", str(root), "--as-of", "2026-09-30", "--strict"]) == 1
    assert "CONTROL_FLOW_FIX" in capsys.readouterr().out


def test_stale_pending_is_aged_from_the_id_date(tmp_path):
    root = _ledger(
        tmp_path,
        [
            _row("R-20260901-01", "`HARNESS_FIX`", "`pending`"),
            _row("R-20260925-01", "`HARNESS_FIX`", "`pending`"),
            _row("R-20260801-01", "`HARNESS_FIX`", "`confirmed`"),
        ],
    )
    report = status.build_report(root, as_of=date(2026, 9, 30), stale_days=14)
    assert report["stale_pending"] == [{"id": "R-20260901-01", "fix_type": "HARNESS_FIX", "age_days": 29}]
    assert report["newest"] == {"id": "R-20260925-01", "age_days": 5}


def test_refuted_streak_follows_id_order_and_skips_unresolved(tmp_path):
    # 行序故意打乱；中间夹一条 pending（未结案不打断也不计入）
    root = _ledger(
        tmp_path,
        [
            _row("R-20260803-01", "`HARNESS_FIX`", "`refuted`"),
            _row("R-20260801-01", "`HARNESS_FIX`", "`refuted`"),
            _row("R-20260802-01", "`HARNESS_FIX`", "`pending`"),
            _row("R-20260804-01", "`HARNESS_FIX`", "`refuted`"),
            _row("R-20260805-01", "`EVAL_ONLY`", "`refuted`"),
        ],
    )
    report = status.build_report(root, as_of=date(2026, 9, 30), stale_days=14)
    assert report["refuted_streaks"]["HARNESS_FIX"] == {"current": 3, "longest": 3}
    assert report["streak_alerts"] == [{"fix_type": "HARNESS_FIX", "current": 3, "longest": 3}]
    assert status.main(["--root", str(root), "--strict"]) == 1


def test_confirmed_breaks_the_streak(tmp_path):
    root = _ledger(
        tmp_path,
        [
            _row("R-20260801-01", "`HARNESS_FIX`", "`refuted`"),
            _row("R-20260802-01", "`HARNESS_FIX`", "`refuted`"),
            _row("R-20260803-01", "`HARNESS_FIX`", "`confirmed`"),
            _row("R-20260804-01", "`HARNESS_FIX`", "`refuted`"),
        ],
    )
    streak = status.build_report(root, as_of=date(2026, 9, 30), stale_days=14)["refuted_streaks"]["HARNESS_FIX"]
    assert streak == {"current": 1, "longest": 2}


def test_nonconforming_ids_are_named_not_counted(tmp_path):
    root = _ledger(
        tmp_path,
        [
            _row("R-20260801-01", "`HARNESS_FIX`", "`pending`"),
            _row("R-20260801-01a", "`HARNESS_FIX`", "`refuted`"),
            _row("R-20260823-SPTTECH-04", "`EVAL_ONLY`", "`pending`"),
        ],
    )
    report = status.build_report(root, as_of=date(2026, 9, 30), stale_days=14)
    assert report["open_rows"] == 1
    assert report["nonconforming_ids"] == ["R-20260801-01a", "R-20260823-SPTTECH-04"]


def test_missing_ledger_exits_2(tmp_path):
    assert status.main(["--root", str(tmp_path)]) == 2


def test_real_ledger_agrees_with_crosswalk_and_uses_frozen_enum(capsys):
    crosswalk = _load("audit_ledger_spec_crosswalk")
    _all_rows, open_rows = crosswalk._ledger_rows(REPO)
    report = status.build_report(REPO, as_of=date(2026, 9, 30), stale_days=14)
    assert report["open_rows"] == len(open_rows) > 0
    assert sum(report["outcomes"].values()) == report["open_rows"]
    # 台账规则写死的 7 个值；真实台账里一旦混进第 8 个，这里先红。
    assert report["invalid_fix_types"] == []
    assert status.main(["--json", "--as-of", "2026-09-30"]) == 0
    assert json.loads(capsys.readouterr().out)["open_rows"] == len(open_rows)


def test_enum_matches_the_ledger_rules_section():
    text = (REPO / "docs" / "prediction-ledger.md").read_text(encoding="utf-8")
    rule = next(line for line in text.splitlines() if "fix_type` 只能取这 7 个值" in line)
    for name in status.FIX_TYPES:
        assert f"`{name}`" in rule
    assert len(status.FIX_TYPES) == 7


@pytest.mark.parametrize(
    ("cell", "expected"),
    [("`HARNESS_FIX`（候）", "HARNESS_FIX"), ("**`refuted`**", "refuted"), ("未达标（见 §3）", "未达标"), ("", "")],
)
def test_first_token(cell, expected):
    assert status._first_token(cell) == expected
