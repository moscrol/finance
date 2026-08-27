"""spec↔台账双向对账：spec 引的号必须在台账有且仅有一行。

失败形状（2026-08-27 工单 §P1-b，实测）：`R-20260824-25/-26/-27` 对应的实施 PR
#359 早已合并，spec §8 写明三条验收判据，台账里却一行都没有——它不是 pending，
它不存在，任何「pending 太久」的扫描都捞不出来。另有 `R-20260821-03` 一号两行
（一 confirmed 一 pending），按号取状态拿到不确定答案。

- 正向（error）：specs/** 里每个 ``R-YYYYMMDD-NN`` 引用 → 台账有且仅有一行。
- 重号（error）：台账同号多行直接红，不给 warning 档。
- 反向（默认 warning）：台账每行应能回指 spec / handoff / verification 之一；
  升 error 那天要在调用处显式传 ``--reverse-severity error``（脚本内注明生效
  revision），不长期停在 warning。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "audit_ledger_spec_crosswalk.py"
)
_spec = importlib.util.spec_from_file_location("audit_ledger_spec_crosswalk", _SCRIPT)
xwalk = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("audit_ledger_spec_crosswalk", xwalk)
_spec.loader.exec_module(xwalk)


@pytest.fixture()
def site(tmp_path: Path) -> Path:
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (tmp_path / "docs").mkdir(exist_ok=True)
    return tmp_path


def _write_ledger(
    root: Path, rows: list[str], history_rows: list[str] | None = None
) -> None:
    body = "\n".join(
        [
            "# Prediction Ledger",
            "",
            "### Open（pending）",
            "",
            "| ID | 来源 | outcome |",
            "|---|---|---|",
            *rows,
            "",
            "### 2026-08-01 历史回填段",
            "",
            *(history_rows or []),
        ]
    )
    (root / "docs" / "prediction-ledger.md").write_text(body + "\n", encoding="utf-8")


def test_spec_ref_with_matching_row_passes(site: Path):
    (site / "docs/superpowers/specs/a.md").write_text(
        "台账 `R-20260801-01` 立案。", encoding="utf-8"
    )
    _write_ledger(
        site, ["| `R-20260801-01` | spec `docs/superpowers/specs/a.md` | `pending` |"]
    )
    report = xwalk.crosswalk(site)
    assert report.missing == {}
    assert report.duplicated == {}


def test_spec_ref_without_row_is_reported_with_location(site: Path):
    (site / "docs/superpowers/specs/a.md").write_text(
        "第一行\n判据在 `R-20260801-02`。", encoding="utf-8"
    )
    _write_ledger(site, [])
    report = xwalk.crosswalk(site)
    assert "R-20260801-02" in report.missing
    where = report.missing["R-20260801-02"][0]
    assert "a.md" in where and ":2" in where  # 点名哪份 spec 第几行引的


def test_duplicated_ledger_id_is_error(site: Path):
    (site / "docs/superpowers/specs/a.md").write_text(
        "`R-20260801-03`", encoding="utf-8"
    )
    _write_ledger(
        site,
        [
            "| `R-20260801-03` | spec `docs/superpowers/specs/a.md` | `pending` |",
            "| `R-20260801-03` | 后继实施 | `confirmed` |",
        ],
    )
    report = xwalk.crosswalk(site)
    assert report.duplicated == {"R-20260801-03": 2}


def test_history_backfill_rows_are_not_duplicates(site: Path):
    """历史回填段的同号复行是过程记录：既不算重号，也满足正向存在性。"""
    (site / "docs/superpowers/specs/a.md").write_text(
        "`R-20260801-08` 与 `R-20260801-09`", encoding="utf-8"
    )
    _write_ledger(
        site,
        ["| `R-20260801-08` | spec `docs/superpowers/specs/a.md` | `pending` |"],
        history_rows=[
            "| `R-20260801-08` | 本轮无新证据 | 保持 Open |",
            "| `R-20260801-08` | 又一轮回填 | 保持 Open |",
            "| `R-20260801-09` | 历史段有行、主表没有（已归档号） | `refuted` |",
        ],
    )
    report = xwalk.crosswalk(site)
    assert report.duplicated == {}  # 历史段复行不算重号
    assert "R-20260801-08" not in report.missing
    assert "R-20260801-09" not in report.missing  # 任何段有行即算存在


def test_orphan_ledger_row_is_reverse_finding(site: Path):
    """台账行回指不了任何 spec/handoff/verification → 反向发现（默认 warning）。"""
    (site / "docs/superpowers/specs/a.md").write_text("无引用", encoding="utf-8")
    _write_ledger(site, ["| `R-20260801-04` | 只有口头来源 | `pending` |"])
    report = xwalk.crosswalk(site)
    assert "R-20260801-04" in report.orphans


def test_row_pointing_at_handoff_is_not_orphan(site: Path):
    (site / "docs/superpowers/specs/a.md").write_text("无引用", encoding="utf-8")
    _write_ledger(
        site,
        ["| `R-20260801-05` | `docs/handoffs/2026-08-01-x.md` 分诊 | `pending` |"],
    )
    report = xwalk.crosswalk(site)
    assert "R-20260801-05" not in report.orphans


def test_exit_code_contract(site: Path):
    """缺号/重号 → 2；只有反向 warning → 0；升 error 后反向也 → 2。"""
    (site / "docs/superpowers/specs/a.md").write_text(
        "`R-20260801-06`", encoding="utf-8"
    )
    _write_ledger(site, ["| `R-20260801-07` | 口头 | `pending` |"])
    assert xwalk.run(site, reverse_severity="warning") == 2  # 缺 -06
    _write_ledger(
        site,
        [
            "| `R-20260801-06` | spec `docs/superpowers/specs/a.md` | `pending` |",
            "| `R-20260801-07` | 口头 | `pending` |",
        ],
    )
    assert xwalk.run(site, reverse_severity="warning") == 0  # 孤儿仅 warning
    assert xwalk.run(site, reverse_severity="error") == 2  # 升档后红
