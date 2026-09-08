from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from intelligence.services.methodology_backtest.stats import mcnemar_exact
from intelligence.services.methodology_backtest.store import open_labels_db
from intelligence.services.teaching_framework.paired import paired_stage_agreement
from scripts.teaching_framework_paired_compare import main, read_sidecar


def test_mcnemar_exact_matches_hand_computed_binomial() -> None:
    # 8 翻转对 2 翻转：双侧 p = 2 × P(X ≤ 2 | n=10, 1/2) = 2 × 56 / 1024
    out = mcnemar_exact(8, 2)
    assert out["discordant"] == 10
    assert out["net_gain"] == 6
    assert out["p_value"] == pytest.approx(112 / 1024)
    # 方向对称：交换 b / c 只翻净值符号，p 不变
    swapped = mcnemar_exact(2, 8)
    assert swapped["net_gain"] == -6
    assert swapped["p_value"] == pytest.approx(out["p_value"])


def test_mcnemar_exact_no_discordant_pairs_is_uninformative() -> None:
    assert mcnemar_exact(0, 0)["p_value"] == 1.0
    with pytest.raises(ValueError):
        mcnemar_exact(-1, 0)


# 六个参照日：前三个训练期、后三个验证期。参照词表里的「承接盘反复」折成我们的「高位震荡」。
_REFERENCE = {
    "2025-06-02": "左底向下",
    "2025-06-03": "承接盘反复",
    "2025-06-04": "共建主线",
    "2026-01-05": "左底向下",
    "2026-01-06": "承接盘反复",
    "2026-01-07": "主流主升",
}
_A = {
    "2025-06-02": "左底向下",  # 对
    "2025-06-03": "ambiguous",  # 未判定
    "2025-06-04": "共建主线",  # 对
    "2026-01-05": "共建主线",  # 错
    "2026-01-06": "高位震荡",  # 对（别名）
    "2026-01-07": "ambiguous",  # 未判定
}
_B = {
    "2025-06-02": "左底向下",  # 对（都对）
    "2025-06-03": "高位震荡",  # 对（A 未判定 → A错B对）
    "2025-06-04": "左底向下",  # 错（A对B错）
    "2026-01-05": "左底向下",  # 对（A错B对）
    "2026-01-06": "高位震荡",  # 对（都对）
    "2026-01-07": "ambiguous",  # 未判定（都错）
}


def test_paired_agreement_counts_unresolved_as_wrong_only_in_all_days_caliber() -> None:
    out = paired_stage_agreement(_A, _B, _REFERENCE, train_until="2025-12-31")
    assert out["overlap_days"] == 6

    train = out["periods"]["train"]
    all_days = train["all_reference_days"]
    assert (all_days["a_correct"], all_days["b_correct"]) == (2, 2)
    assert (all_days["mcnemar"]["a_wrong_b_right"], all_days["mcnemar"]["a_right_b_wrong"]) == (1, 1)
    # 两版都判定：06-03 A 未判定被剔除，只剩 06-02（都对）与 06-04（A对B错）
    both = train["both_resolved"]
    assert both["days"] == 2
    assert (both["mcnemar"]["a_wrong_b_right"], both["mcnemar"]["a_right_b_wrong"]) == (0, 1)
    # 收据口径：A 已判定 2 天全对，B 已判定 3 天对 2 天
    assert train["receipt_caliber"]["a"] == {"resolved_days": 2, "agree_days": 2, "rate": 1.0}
    assert train["receipt_caliber"]["b"] == {"resolved_days": 3, "agree_days": 2, "rate": 0.6667}

    validate = out["periods"]["validate"]
    v_all = validate["all_reference_days"]
    assert (v_all["a_correct"], v_all["b_correct"], v_all["both_correct"], v_all["neither_correct"]) == (1, 2, 1, 1)
    assert v_all["mcnemar"]["net_gain"] == 1
    assert validate["flips_by_reference_stage"] == {"左底向下 × a_wrong_b_right": 1}


def test_paired_agreement_ignores_days_missing_in_either_version() -> None:
    a = dict(_A)
    a.pop("2026-01-07")
    out = paired_stage_agreement(a, _B, _REFERENCE, train_until="2025-12-31")
    assert out["overlap_days"] == 5
    assert out["periods"]["validate"]["all_reference_days"]["days"] == 2


def _write_sidecar(path, version: str, stages: dict[str, str], reference: dict[str, str] | None) -> None:
    con = open_labels_db(path, read_only=False)
    now = datetime(2026, 9, 8, tzinfo=timezone.utc)
    for day, stage in stages.items():
        con.execute(
            "INSERT INTO history_teaching_labels (entity_type, entity_id, trade_date, label, value_text, label_version, framework_version, computed_at) "
            "VALUES ('market', 'market', ?, 'tf.stage_coarse', ?, 'v2', ?, ?)",
            [date.fromisoformat(day), stage, version, now],
        )
    for day, stage in (reference or {}).items():
        con.execute(
            "INSERT INTO history_reference_stages (source, trade_date, cycle_stage, loaded_at) VALUES ('test', ?, ?, ?)",
            [date.fromisoformat(day), stage, now],
        )
    con.close()


def test_cli_reads_two_sidecars_and_reports_versions(tmp_path, capsys) -> None:
    a_path = tmp_path / "a.duckdb"
    b_path = tmp_path / "b.duckdb"
    _write_sidecar(a_path, "tf-v0.2+aaaaaaaa", _A, _REFERENCE)
    _write_sidecar(b_path, "tf-v0.2+bbbbbbbb", _B, None)  # 参照只在一边也能配对

    version, stages, reference = read_sidecar(a_path)
    assert version == "tf-v0.2+aaaaaaaa" and len(stages) == 6 and len(reference) == 6

    assert main(["--a", str(a_path), "--b", str(b_path), "--train-until", "2025-12-31", "--markdown"]) == 0
    out = capsys.readouterr().out
    result = json.loads(out.splitlines()[0])
    assert result["version_a"] == "tf-v0.2+aaaaaaaa"
    assert result["version_b"] == "tf-v0.2+bbbbbbbb"
    assert result["periods"]["validate"]["all_reference_days"]["mcnemar"]["net_gain"] == 1
    assert "| 验证期 | 全部参照日（未判定算错） | 3 |" in out


def test_cli_refuses_mismatched_reference(tmp_path) -> None:
    a_path = tmp_path / "a.duckdb"
    b_path = tmp_path / "b.duckdb"
    _write_sidecar(a_path, "tf-v0.2+aaaaaaaa", _A, _REFERENCE)
    other = dict(_REFERENCE)
    other["2026-01-07"] = "共建主线"
    _write_sidecar(b_path, "tf-v0.2+bbbbbbbb", _B, other)
    with pytest.raises(SystemExit):
        main(["--a", str(a_path), "--b", str(b_path), "--train-until", "2025-12-31"])
