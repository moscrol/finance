"""预测台账周报（2026-10-01 质检 P0④）：只读统计 + 过期 + 沉默闸。"""

from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ledger_status", REPO / "scripts" / "prediction_ledger_status.py")
assert _spec and _spec.loader
ledger_status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ledger_status)

LEDGER = """# x
### Open（pending）

| ID | 来源 | fix_type | verification_prediction | 怎么验 | outcome |
|---|---|---|---|---|---|
| `R-20260901-01` | a | `HARNESS_FIX` | p | v | `confirmed` |
| `R-20260902-01` | a | `HARNESS_FIX`（候） | p | v | `refuted`（归因升格） |
| `R-20260903-01` | a | `HARNESS_FIX` | p | v | `refuted` |
| `R-20260904-01` | a | `HARNESS_FIX` | p | v | **`refuted`** |
| `R-20260910-01` | a | `ROUTING_FIX` | p | v | `pending` |
| `R-20260928-01` | a | `EVAL_ONLY` | p | v | `pending`（首读 ✓） |
| `R-20260929-01` | a | `EVAL_ONLY` | p | v | 未达标 |

### 2026-08-16 回填
| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260801-01` | x | `confirmed` | y |
"""


def test_counts_expiry_and_streak() -> None:
    report = ledger_status.summarize(LEDGER, date(2026, 10, 1), expire_days=14)
    assert report["total"] == 7  # 回填段不算当前态
    assert report["counts"] == {"confirmed": 1, "refuted": 3, "expired": 1, "pending": 1, "other": 1}
    assert report["expired_ids"] == ["R-20260910-01"]
    assert report["refuted_streak_by_fix_type"] == {"HARNESS_FIX": 3}
    assert report["escalation_triggered"] == ["HARNESS_FIX"]
    assert report["days_since_latest_id"] == 2


def test_silence_gate_exit_code(tmp_path: Path) -> None:
    path = tmp_path / "ledger.md"
    path.write_text(LEDGER, encoding="utf-8")
    args = ["--ledger", str(path), "--today", "2026-10-01"]
    assert ledger_status.main([*args, "--max-silence-days", "7"]) == 0
    assert ledger_status.main([*args, "--max-silence-days", "1"]) == 1


def test_real_ledger_parses() -> None:
    report = ledger_status.summarize(
        (REPO / "docs" / "prediction-ledger.md").read_text(encoding="utf-8"), date(2026, 10, 1), 14
    )
    assert report["total"] > 100
    assert report["by_fix_type"].get("?") is None, "有 fix_type 不在冻结枚举里"
