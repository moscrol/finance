"""数值门标签 A/B 回放脚本：改标签只动指定数据集的完整字段名，消失 / 新增点得准，新增即红。

背景：#986 / #988 改 finance_query 标签前都在 950 个存证 run 上做过 A/B（原样臂、模拟改标签臂），
做法只在会话里。PR #10 再改三个百分数标签，合并前要同样量一次，于是固化成脚本。
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from intelligence.runtime.continuous_turn_adapter import _private_outcome
from intelligence.services.finance_query import _DATASETS
from intelligence.tests.test_episode_semantic_verifier import _structural

REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("numeric_gate_label_ab", REPO / "scripts" / "numeric_gate_label_ab.py")
ab = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("numeric_gate_label_ab", ab)
_SPEC.loader.exec_module(ab)

OLD_ROW = "交易日=2026-09-29；强势股加权涨幅=5.32；强势股成交占比=14.93"
NEW_ROW = "交易日=2026-09-29；强势股加权涨幅%=5.32；强势股成交占比%=14.93"
RESTATEMENT = "若强势股成交占比回到 14.93%（E1）以上则情绪回暖。"


def _write_receipt(
    root: Path,
    draft: str,
    detail: str,
    *,
    dataset: str = "market_daily",
    tool: str = "finance_query",
    user: str = "u1",
    run: str = "run_20260929_120000_000001",
) -> Path:
    """按生产存证的形状落一份 continuous-episode.json：contract.to_dict()，outcome 走生产同一个
    序列化（continuous_turn_adapter._private_outcome）。"""

    _, verified = _structural(draft, detail=detail)
    label = _DATASETS[dataset].label if dataset in _DATASETS else "别的数据"
    evidence = dataclasses.replace(
        verified.outcome.evidence[0],
        tool=tool,
        title=f"{label}（2026-09-29）",
        source_date="2026-09-29",
        independent_key=f"duckdb:{dataset}:2026-09-29",
    )
    outcome = dataclasses.replace(verified.outcome, evidence=(evidence,))
    payload = {
        "task_frame": {"raw_question": "强势股情绪怎么看"},
        "contract": verified.contract.to_dict(),
        "outcome": _private_outcome(outcome),
    }
    path = root / user / "runs" / run / "continuous-episode.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def test_relabel_clears_a_faithful_restatement(tmp_path, capsys):
    path = _write_receipt(tmp_path, RESTATEMENT, OLD_ROW)
    row = ab.replay_ab(path, ab.DEFAULT_RELABELS)
    assert row["error"] is None
    assert row["touched_evidence"] == 1
    assert [t for tokens in row["asis"].values() for t in tokens] == ["14.93%"]
    assert row["relabeled"] == {}
    assert [item["tokens"] for item in row["disappeared"]] == [["14.93%"]]
    assert row["new"] == []
    assert ab.main(["--users-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "消失 1 处，新增 0 处" in out
    assert "u1/run_20260929_120000_000001" in out
    assert "✅ 新增 0" in out


@pytest.mark.parametrize("dataset, tool", [("sector_daily", "finance_query"), ("market_daily", "market_data")])
def test_only_finance_query_cards_of_the_named_dataset_are_relabeled(tmp_path, dataset, tool):
    path = _write_receipt(tmp_path, RESTATEMENT, OLD_ROW, dataset=dataset, tool=tool)
    row = ab.replay_ab(path, ab.DEFAULT_RELABELS)
    assert row["error"] is None
    assert row["touched_evidence"] == 0
    assert row["asis"] == row["relabeled"]
    assert row["disappeared"] == row["new"] == []


def test_old_receipts_without_independent_key_fall_back_to_the_title(tmp_path):
    path = _write_receipt(tmp_path, RESTATEMENT, OLD_ROW)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["outcome"]["evidence"][0]["independent_key"] = ""
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert ab.replay_ab(path, ab.DEFAULT_RELABELS)["touched_evidence"] == 1


def test_only_whole_field_names_are_renamed():
    targets = [ab.Relabel("sector_period_rank_daily", "区间涨幅", "区间涨幅%")]
    detail = "板块名称=算力；近5日区间涨幅=3.20；区间涨幅=8.80；备注=区间涨幅居前"
    assert ab.relabel_detail(detail, targets) == "板块名称=算力；近5日区间涨幅=3.20；区间涨幅%=8.80；备注=区间涨幅居前"
    assert ab.relabel_detail("区间涨幅: 8.80", targets) == "区间涨幅%: 8.80"


def test_relabeled_card_keeps_its_identity(tmp_path):
    path = _write_receipt(tmp_path, RESTATEMENT, OLD_ROW)
    payload = json.loads(path.read_text(encoding="utf-8"))
    outcome = ab._load_replay_module()._rebuild_outcome(payload["outcome"])
    evidence, touched = ab.relabel_evidence(tuple(outcome.evidence), ab.DEFAULT_RELABELS)
    assert touched == 1
    assert evidence[0].detail == NEW_ROW
    # 模拟的是「同一张卡换了标签」：身份不变，绑定才继续指得到它。
    assert evidence[0].content_hash == outcome.evidence[0].content_hash


def test_new_doubts_fail_the_gate(tmp_path, capsys):
    # 反方向改名（去掉 %）在 #988 之后的存证上必然新增待核：用来证明「新增」那一臂真能红。
    _write_receipt(tmp_path, RESTATEMENT, NEW_ROW)
    code = ab.main(["--users-root", str(tmp_path), "--relabel", "market_daily:强势股成交占比%=强势股成交占比"])
    out = capsys.readouterr().out
    assert code == 1
    assert "新增 1 处" in out
    assert "新增（必须为 0）" in out and "「14.93%」" in out


def test_replay_errors_are_reported_not_hidden(tmp_path, capsys):
    _write_receipt(tmp_path, RESTATEMENT, OLD_ROW)
    broken = tmp_path / "u1" / "runs" / "run_20260929_130000_000002" / "continuous-episode.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{not json", encoding="utf-8")
    assert ab.main(["--users-root", str(tmp_path)]) == 2
    out = capsys.readouterr().out
    assert "存证 episode：2 个；重放失败 1 个" in out
    assert "重放失败 u1/run_20260929_130000_000002" in out


def test_users_and_since_filters(tmp_path):
    _write_receipt(tmp_path, RESTATEMENT, OLD_ROW, user="a", run="run_20260901_090000_000001")
    _write_receipt(tmp_path, RESTATEMENT, OLD_ROW, user="b", run="run_20260929_090000_000001")
    found = ab.iter_receipts([], users_root=tmp_path, users=None, since="20260915")
    assert [p.parents[2].name for p in found] == ["b"]
    assert ab.iter_receipts([], users_root=tmp_path, users=["a"], since=None)[0].parents[2].name == "a"


def test_baseline_drift_in_the_unchanged_arm_fails(tmp_path, capsys):
    _write_receipt(tmp_path / "users", RESTATEMENT, OLD_ROW)
    base = tmp_path / "base.json"
    assert ab.main(["--users-root", str(tmp_path / "users"), "--json", str(base)]) == 0
    assert ab.main(["--users-root", str(tmp_path / "users"), "--baseline", str(base)]) == 0
    assert "漂移 0 个 run" in capsys.readouterr().out
    rows = json.loads(base.read_text(encoding="utf-8"))
    rows[0]["asis"] = {}
    base.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    assert ab.main(["--users-root", str(tmp_path / "users"), "--baseline", str(base)]) == 1
    assert "漂移 1 个 run" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [["--relabel", "market_daily"], ["--relabel", "no_such_dataset:a=b"],
                                  ["--relabel", "market_daily:量比=量比"]])
def test_bad_relabel_arguments_exit_2(tmp_path, argv):
    assert ab.main([*argv, "--users-root", str(tmp_path)]) == 2


def test_nothing_to_scan_exits_2(tmp_path):
    assert ab.main(["--users-root", str(tmp_path / "missing")]) == 2


def test_default_relabels_track_the_current_finance_query_labels():
    """默认改标签集要与 finance_query 现行标签对得上：新名在、旧名不在。再改一次标签时这里会红。"""

    for item in ab.DEFAULT_RELABELS:
        labels = {field.label for field in _DATASETS[item.dataset].fields.values()}
        assert item.new in labels, item
        assert item.old not in labels, item


def test_real_archived_receipts_replay(capsys):
    """仓里的真实存证：重建与重放走得通（没有这三处标签，所以零改动）。"""

    roots = [REPO / "docs/verification/2026-09-21-judge-mode-k3/evidence", REPO / "intelligence/tests/fixtures/live_products"]
    rows = [ab.replay_ab(path, ab.DEFAULT_RELABELS) for path in ab.iter_receipts(roots, users_root=None, users=None, since=None)]
    replayed = [row for row in rows if row["error"] is None]
    assert len(replayed) >= 2
    assert all(row["touched_evidence"] == 0 and row["new"] == [] for row in replayed)


def test_all_replay_failures_are_not_zero_regressions(tmp_path, capsys):
    path = tmp_path / "continuous-episode.json"
    path.write_text("{bad json")
    assert ab.main([str(path)]) == 2
    assert "✅" not in capsys.readouterr().out


def test_baseline_scope_mismatch_blocks_admission(tmp_path, capsys):
    path = _write_receipt(tmp_path / "users", RESTATEMENT, OLD_ROW)
    base = tmp_path / "baseline.json"
    base.write_text("[]")
    assert ab.main([str(path), "--baseline", str(base)]) == 2
    assert "✅" not in capsys.readouterr().out
