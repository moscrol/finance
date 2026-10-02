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


# ── 过期规则（2026-09-30 质检 ④）：新鲜 ≤14 / 临期 15–30 / 过期 >30；过期 ≠ refuted ──


@pytest.mark.parametrize(
    ("age", "bucket"),
    [(0, "fresh"), (14, "fresh"), (15, "due"), (30, "due"), (31, "expired"), (None, "undated")],
)
def test_age_bucket_boundaries(age, bucket):
    assert status.age_bucket(age, stale_days=14, expire_days=30) == bucket


def test_expiry_buckets_and_verdicts_add_up_to_open_rows(tmp_path, capsys):
    root = _ledger(
        tmp_path,
        [
            _row("R-20260925-01", "`HARNESS_FIX`", "`pending`"),  # 5 天：新鲜
            _row("R-20260910-01", "`HARNESS_FIX`", "`pending`"),  # 20 天：临期
            _row("R-20260816-01", "`EVAL_ONLY`", "`pending`"),  # 45 天：过期
            _row("R-20260801-01", "`HARNESS_FIX`", "`pending`"),  # 60 天：过期（最老，排第一）
            _row("R-20260802-01", "`HARNESS_FIX`", "`confirmed`"),
            _row("R-20260803-01", "`HARNESS_FIX`", "`partially_confirmed`"),
            _row("R-20260804-01", "`ROUTING_FIX`", "`refuted`"),
            _row("R-20260805-01", "`HARNESS_FIX`", "`expired`（前提已变，不再验）"),
            _row("R-20260806-01", "`HARNESS_FIX`", "`held`"),
        ],
    )
    report = status.build_report(root, as_of=date(2026, 9, 30), stale_days=14)
    assert report["pending_age_buckets"] == {"fresh": 1, "due": 1, "expired": 2}
    assert [row["id"] for row in report["expired_pending"]] == ["R-20260801-01", "R-20260816-01"]
    verdicts = report["verdicts"]
    assert verdicts == {
        "confirmed": 1,
        "partially_confirmed": 1,
        "refuted": 1,
        "expired": 3,
        "expired_open": 2,
        "expired_closed": 1,
        "pending": 2,
        "other": 1,
    }
    six = ("confirmed", "partially_confirmed", "refuted", "expired", "pending", "other")
    assert sum(verdicts[key] for key in six) == report["open_rows"] == 9
    # 只读：体检不改台账一个字节
    before = (root / "docs" / "prediction-ledger.md").read_bytes()
    assert status.main(["--root", str(root), "--as-of", "2026-09-30"]) == 0
    assert (root / "docs" / "prediction-ledger.md").read_bytes() == before
    out = capsys.readouterr().out
    assert "结案口径：证实 1 · 部分证实 1 · 证伪 1 · 过期 3（待处理 2 / 已关闭 1） · 待定 2 · 其他 1" in out
    assert "pending 年龄：新鲜（≤14 天）1 · 临期（15–30 天）1 · 过期（>30 天）2" in out
    assert "过期待处理 2 行" in out and "R-20260801-01（60 天）" in out


def test_expired_rows_neither_count_nor_break_a_refuted_streak(tmp_path):
    # 过期 = 没有证据，不能当成 refuted，也不能当成「这次对了」把连击清零
    root = _ledger(
        tmp_path,
        [
            _row("R-20260801-01", "`HARNESS_FIX`", "`refuted`"),
            _row("R-20260802-01", "`HARNESS_FIX`", "`expired`"),
            _row("R-20260803-01", "`HARNESS_FIX`", "`refuted`"),
            _row("R-20260804-01", "`HARNESS_FIX`", "`refuted`"),
        ],
    )
    report = status.build_report(root, as_of=date(2026, 9, 30), stale_days=14)
    assert report["refuted_streaks"]["HARNESS_FIX"] == {"current": 3, "longest": 3}
    assert report["verdicts"]["refuted"] == 3 and report["verdicts"]["expired_closed"] == 1


def test_custom_thresholds_and_invalid_order(tmp_path, capsys):
    root = _ledger(tmp_path, [_row("R-20260910-01", "`HARNESS_FIX`", "`pending`")])  # 20 天
    report = status.build_report(root, as_of=date(2026, 9, 30), stale_days=7, expire_days=19)
    assert report["pending_age_buckets"] == {"fresh": 0, "due": 0, "expired": 1}
    with pytest.raises(ValueError):
        status.build_report(root, as_of=date(2026, 9, 30), stale_days=30, expire_days=14)
    assert status.main(["--root", str(root), "--stale-days", "30", "--expire-days", "14"]) == 2
    assert "不能小于" in capsys.readouterr().err


def test_real_ledger_verdicts_add_up():
    report = status.build_report(REPO, as_of=date(2026, 9, 30), stale_days=14)
    verdicts = report["verdicts"]
    six = ("confirmed", "partially_confirmed", "refuted", "expired", "pending", "other")
    assert sum(verdicts[key] for key in six) == report["open_rows"]
    assert sum(report["pending_age_buckets"].values()) == report["outcomes"].get("pending", 0)


def test_expiry_rule_text_matches_the_code():
    """台账「记账规则」写的档位与关闭值，和脚本常量同一份口径。"""

    text = (REPO / "docs" / "prediction-ledger.md").read_text(encoding="utf-8")
    rule = next(line for line in text.splitlines() if line.startswith("- **过期规则**"))
    assert f"≤{status.DEFAULT_STALE_DAYS} 天新鲜" in rule
    assert f">{status.DEFAULT_EXPIRE_DAYS} 天过期" in rule
    assert f"`{status.CLOSED_UNVERIFIED}`" in rule
    assert "scripts/prediction_ledger_status.py" in rule


# ── 过期分诊表（--worksheet）────────────────────────────────────────────────


def _how_row(rid: str, how: str, outcome: str = "`pending`") -> str:
    return f"| `{rid}` | 溯源 docs/x.md | `HARNESS_FIX` | 预测 | {how} | {outcome} |"


def _worksheet_root(tmp_path: Path) -> Path:
    root = _ledger(tmp_path, [
        _how_row("R-20260801-01", "离线单测 + live 探针（8792 切流后看）"),
        _how_row("R-20260802-02", "离线变异 3/3"),
        _how_row("R-20260803-03", "看下一次复盘"),
        _how_row("R-20260920-04", "离线单测"),  # 新鲜，不进分诊表
    ])
    ver = tmp_path / "docs" / "verification"
    ver.mkdir(parents=True)
    (ver / "2026-08-20-receipt.md").write_text("R-20260801-01 的 live 读数：通过", encoding="utf-8")
    (ver / "2026-07-30-older.md").write_text("R-20260802-02 立项前的草稿", encoding="utf-8")  # 早于开立日，不算
    (ver / "2026-08-21-suffix.md").write_text("R-20260803-03a 是另一条（带后缀）", encoding="utf-8")
    (tmp_path / "docs" / "notes-undated.md").write_text("R-20260803-03 无日期文件不算", encoding="utf-8")
    return root


def test_worksheet_lists_expired_rows_with_later_mentions_only(tmp_path):
    root = _worksheet_root(tmp_path)
    report = status.build_report(root, as_of=date(2026, 10, 2), stale_days=14, expire_days=30)
    sheet = {row["id"]: row for row in status.build_worksheet(root, report)}
    assert set(sheet) == {"R-20260801-01", "R-20260802-02", "R-20260803-03"}
    assert sheet["R-20260801-01"]["later_mentions"] == 1
    assert sheet["R-20260801-01"]["latest_mention"] == "docs/verification/2026-08-20-receipt.md"
    assert sheet["R-20260802-02"]["later_mentions"] == 0  # 只在开立日之前提过
    assert sheet["R-20260803-03"]["later_mentions"] == 0  # 带后缀的号、无日期文件都不算
    assert [sheet[r]["verification"] for r in ("R-20260801-01", "R-20260802-02", "R-20260803-03")] == [
        "要生产读数", "离线可验", "未写明",
    ]


def test_worksheet_cli_renders_and_never_edits_the_ledger(tmp_path, capsys):
    root = _worksheet_root(tmp_path)
    ledger = root / "docs" / "prediction-ledger.md"
    before = ledger.read_text(encoding="utf-8")
    assert status.main(["--root", str(root), "--as-of", "2026-10-02", "--worksheet"]) == 0
    out = capsys.readouterr().out
    assert "过期待定分诊表（as-of 2026-10-02，3 条）" in out
    assert "后续证据，先看它）：1 条；没有：2 条" in out
    first_row = next(line for line in out.splitlines() if line.startswith("| R-"))
    assert first_row.startswith("| R-20260801-01 ")  # 有后续提及的排前面
    assert status.main(["--root", str(root), "--as-of", "2026-10-02", "--worksheet", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 3
    assert ledger.read_text(encoding="utf-8") == before


def test_worksheet_puts_rows_with_later_evidence_first_even_if_younger(tmp_path, capsys):
    root = _ledger(tmp_path, [
        _how_row("R-20260801-01", "离线单测"),   # 更老，但没有后续提及
        _how_row("R-20260810-02", "离线单测"),   # 更新，有后续提及
    ])
    ver = tmp_path / "docs" / "verification"
    ver.mkdir(parents=True)
    (ver / "2026-08-20-receipt.md").write_text("R-20260810-02 复跑通过", encoding="utf-8")
    assert status.main(["--root", str(root), "--as-of", "2026-10-02", "--worksheet"]) == 0
    rows = [line for line in capsys.readouterr().out.splitlines() if line.startswith("| R-")]
    assert [row.split(" | ")[0] for row in rows] == ["| R-20260810-02", "| R-20260801-01"]
