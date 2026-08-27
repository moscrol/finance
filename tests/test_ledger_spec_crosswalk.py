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


# ---------------------------------------------------------------------------
# 第三向：spec 声明订正过，同号在途交接却没有订正痕迹
#
# 失败形状（2026-08-27 实测，本轮自己犯的）：停更工单 `R-20260827-09` 的两条
# 结论被撤回，spec 与台账都改了，`docs/handoffs/inflight/` 那份**一字未动**，
# 仍逐字传播「本单是那句预言的兑现」与「改 episode_tools.py:212」——而按仓规
# 接手者**先读交接**。同一结论存三处、订正只覆盖两处。
#
# 判据刻意收窄到「spec 自称订正过」：只在 spec 出现订正标记时才比对，
# 普通迭代（补章节、改错字）不触发。代价写在 docstring 里：不写标记就没保护。
# ---------------------------------------------------------------------------


def _write_inflight(root: Path, name: str, body: str) -> None:
    d = root / "docs" / "handoffs" / "inflight"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")


def test_corrected_spec_with_unmarked_inflight_handoff_is_flagged(site: Path):
    """spec 说自己订正过，同号交接无订正痕迹 → 报（本轮 A 的最小复现）。"""
    (site / "docs/superpowers/specs/a.md").write_text(
        "`R-20260801-10` 判据。\n⚠ 本单初稿把 X 写成目标，那是错的，**已订正**。",
        encoding="utf-8",
    )
    _write_inflight(site, "feat-x.md", "`R-20260801-10`：按 X 施工即可。")
    _write_ledger(
        site, ["| `R-20260801-10` | spec `docs/superpowers/specs/a.md` | `pending` |"]
    )
    report = xwalk.crosswalk(site)
    assert "R-20260801-10" in report.stale_handoffs
    assert "feat-x.md" in report.stale_handoffs["R-20260801-10"][0]


def test_corrected_spec_with_marked_handoff_passes(site: Path):
    """交接也带订正痕迹 → 不报（订正已传播到位）。"""
    (site / "docs/superpowers/specs/a.md").write_text(
        "`R-20260801-11`\n本单初稿写错，**已订正**。", encoding="utf-8"
    )
    _write_inflight(
        site, "feat-y.md", "`R-20260801-11`\n⚠ 旧稿结论已**撤回**，勿照旧稿施工。"
    )
    _write_ledger(site, ["| `R-20260801-11` | spec `docs/superpowers/specs/a.md` | `pending` |"])
    assert xwalk.crosswalk(site).stale_handoffs == {}


def test_uncorrected_spec_does_not_flag_handoff(site: Path):
    """spec 没自称订正 → 不比对（防止普通迭代变成稳定误报）。"""
    (site / "docs/superpowers/specs/a.md").write_text(
        "`R-20260801-12` 判据与变异点。", encoding="utf-8"
    )
    _write_inflight(site, "feat-z.md", "`R-20260801-12`：照 spec 施工。")
    _write_ledger(site, ["| `R-20260801-12` | spec `docs/superpowers/specs/a.md` | `pending` |"])
    assert xwalk.crosswalk(site).stale_handoffs == {}


def test_archived_handoff_is_not_checked(site: Path):
    """只查 inflight/：已归档交接是历史快照，本就不该跟着 spec 走。"""
    (site / "docs/superpowers/specs/a.md").write_text(
        "`R-20260801-13`\n初稿有误，**已订正**。", encoding="utf-8"
    )
    (site / "docs" / "handoffs").mkdir(parents=True, exist_ok=True)
    (site / "docs/handoffs/2026-08-01-done.md").write_text(
        "`R-20260801-13` 旧结论", encoding="utf-8"
    )
    _write_ledger(site, ["| `R-20260801-13` | spec `docs/superpowers/specs/a.md` | `pending` |"])
    assert xwalk.crosswalk(site).stale_handoffs == {}


def test_stale_handoff_is_warning_not_error(site: Path):
    """默认 warning：不阻塞提交，避免变成噪声源被训练成忽略。"""
    (site / "docs/superpowers/specs/a.md").write_text(
        "`R-20260801-14`\n**已订正**。", encoding="utf-8"
    )
    _write_inflight(site, "feat-w.md", "`R-20260801-14` 旧结论")
    _write_ledger(site, ["| `R-20260801-14` | spec `docs/superpowers/specs/a.md` | `pending` |"])
    # 既要 exit 0（不阻塞），又要真的说出来（否则「不阻塞」等于「没实现」也过）
    assert xwalk.run(site) == 0
    assert xwalk.crosswalk(site).stale_handoffs != {}
