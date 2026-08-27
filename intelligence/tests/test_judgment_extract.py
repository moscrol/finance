"""KC-09：前瞻判断抽取 + pending→accept。不建 judgments-ledger.jsonl。"""
from __future__ import annotations

import json
from pathlib import Path

from intelligence.services.judgment_extract import (
    CONFIDENCE_LEVELS,
    extract_foresight_judgments,
    list_pending,
    propose_judgments,
    accept_judgments,
)
from intelligence.services.judgments import load_judgments, record_judgment


def test_extracts_conditional_upgrade_with_quarter_verify_by() -> None:
    found = extract_foresight_judgments(
        "若 Q2 单季营收 ≥25% 则升级为核心受益。",
        as_of="2026-08-18",
        query="长电科技怎么看",
    )
    assert len(found) == 1
    item = found[0]
    assert "升级为核心受益" in item.claim
    assert item.verify_by.due == "2026-06-30"
    assert "25%" in item.verify_by.criterion
    assert item.confidence == "中"
    assert item.confidence in CONFIDENCE_LEVELS


def test_no_forward_judgment_extracts_nothing() -> None:
    assert extract_foresight_judgments(
        "本轮没有形成可回查的盘面或公司级事实，因此只能保留题材框架。",
        as_of="2026-08-18",
        query="固态电池题材怎么看",
    ) == ()


def test_missing_verify_by_does_not_create_record() -> None:
    assert extract_foresight_judgments(
        "若需求恢复则看多，但没有验证时点。",
        as_of="2026-08-18",
        query="PTA怎么看",
    ) == ()


def test_numeric_probability_is_not_stored_as_confidence() -> None:
    found = extract_foresight_judgments(
        "若 2026-09-30 前出现量产公告则升级。置信度 80%。",
        as_of="2026-08-18",
        query="固态电池怎么看",
    )
    assert len(found) == 1
    assert found[0].confidence == "中"
    assert found[0].to_record()["confidence"] == "中"
    assert "80%" not in found[0].claim


def test_upgrade_window_pair_is_a_candidate() -> None:
    text = (
        "**判断升级需要：** 公司级硬证据升级；产业需求或政策边界变化。\n"
        "**复核时间：建议 30 天内复查（至 2026-08-07）；过期引用本结论须先经当下盘面复核。**"
    )
    found = extract_foresight_judgments(text, as_of="2026-07-08", query="英维克怎么看")
    assert len(found) == 1
    assert found[0].verify_by.due == "2026-08-07"
    assert "公司级硬证据升级" in found[0].verify_by.criterion
    assert "**" not in found[0].claim


def test_pending_accept_writes_judgment_and_checkpoint(tmp_path: Path) -> None:
    judgments = tmp_path / "judgments.jsonl"
    checkpoints = tmp_path / "checkpoints.jsonl"
    pending = propose_judgments(
        judgments,
        extract_foresight_judgments(
            "若 2026-09-30 前出现量产公告则升级。",
            as_of="2026-08-18",
            query="爱司凯怎么看",
            citations=(("R1", "wiki/a.md", "source=年报"),),
        ),
    )
    assert len(pending) == 1
    assert pending[0]["status"] == "pending"
    recalled, _ = load_judgments(judgments)
    assert recalled == []
    accepted = accept_judgments(judgments, checkpoints, ids=(pending[0]["id"],))
    assert len(accepted) == 1
    assert accepted[0]["status"] == "accepted"
    assert accepted[0]["confidence"] == "中"
    assert accepted[0]["evidence"][0]["ref"] == "R1"
    assert accepted[0]["evidence"][0]["hash"]
    recalled, _ = load_judgments(judgments)
    assert len(recalled) == 1
    assert "2026-09-30" in recalled[0]["memo"]
    assert "升级" in recalled[0]["memo"]
    ck_lines = [json.loads(line) for line in checkpoints.read_text(encoding="utf-8").splitlines()]
    assert len(ck_lines) == 1
    assert ck_lines[0]["due"] == "2026-09-30"
    assert ck_lines[0]["source"] == "foresight_judgment"
    assert ck_lines[0]["source_judgment_ts"] == accepted[0]["ts"]
    again = accept_judgments(judgments, checkpoints, ids=(pending[0]["id"],))
    assert again == []
    assert len(checkpoints.read_text(encoding="utf-8").splitlines()) == 1


def test_list_pending_and_legacy_memo_still_loads(tmp_path: Path) -> None:
    judgments = tmp_path / "judgments.jsonl"
    record_judgment(judgments, memo="旧核心判断：铜箔产能爬坡滞后", themes=["铜箔"])
    propose_judgments(
        judgments,
        extract_foresight_judgments(
            "若 2026-10-01 前订单落地则升级。",
            as_of="2026-08-18",
            query="铜箔怎么看",
        ),
    )
    pending = list_pending(judgments)
    assert len(pending) == 1
    recalled, _ = load_judgments(judgments)
    assert [row["memo"] for row in recalled] == ["旧核心判断：铜箔产能爬坡滞后"]


def test_does_not_create_judgments_ledger_filename(tmp_path: Path) -> None:
    judgments = tmp_path / "judgments.jsonl"
    propose_judgments(
        judgments,
        extract_foresight_judgments(
            "若 2026-09-30 前出现量产公告则升级。",
            as_of="2026-08-18",
            query="x",
        ),
    )
    assert judgments.exists()
    assert not (tmp_path / "judgments-ledger.jsonl").exists()
