"""KC-10：到期裁决 job。接线已有 checkpoint recheck，不回改判断原文。"""
from __future__ import annotations

import json
from pathlib import Path

from intelligence import cli
from intelligence.services import checkpoints
from intelligence.services.judgment_adjudicate import run_adjudication_job


ORIGINAL_CLAIM = "若 60 日涨幅 >= 15% 则升级为核心受益"
ORIGINAL_MEMO = "判断原文：若 60 日涨幅 >= 15% 则升级为核心受益"


def _write_judgment(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "ts": "2026-05-01T00:00:00",
                "id": "j-accepted-1",
                "record_type": "foresight_judgment",
                "status": "accepted",
                "memo": ORIGINAL_MEMO,
                "claim": ORIGINAL_CLAIM,
                "verify_by": {"due": "2026-06-01", "criterion": "60 日涨幅 >= 15%"},
                "confidence": "中",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _seed_ledger(tmp: Path) -> tuple[Path, Path, Path, str, str, str]:
    judgments = tmp / "judgments.jsonl"
    cpath = tmp / "checkpoints.jsonl"
    vpath = tmp / "verdicts.jsonl"
    _write_judgment(judgments)
    _, hit_ck = checkpoints.register_checkpoint(
        cpath,
        claim="铜冠铜箔 60 日涨幅 >= 15%",
        due="2026-06-01",
        category="前瞻判断",
        source="foresight_judgment",
        stocks=["铜冠铜箔"],
        metric={"type": "stock_return", "op": ">=", "target": 15, "window_days": 60},
        session_id="j-accepted-1",
        ts="2026-05-01T00:00:00",
    )
    _, miss_ck = checkpoints.register_checkpoint(
        cpath,
        claim="英维克 60 日涨幅 >= 15%",
        due="2026-06-01",
        category="前瞻判断",
        source="foresight_judgment",
        stocks=["英维克"],
        metric={"type": "stock_return", "op": ">=", "target": 15, "window_days": 60},
        ts="2026-05-01T00:00:01",
    )
    _, manual_ck = checkpoints.register_checkpoint(
        cpath,
        claim="公司级硬证据升级",
        due="2026-06-01",
        category="前瞻判断",
        source="foresight_judgment",
        metric={"type": "manual"},
        ts="2026-05-01T00:00:02",
    )
    checkpoints.register_checkpoint(
        cpath,
        claim="未到期不该进队",
        due="2099-01-01",
        metric={"type": "manual"},
        ts="2026-05-01T00:00:03",
    )
    return judgments, cpath, vpath, hit_ck["id"], miss_ck["id"], manual_ck["id"]


def _returns(stocks, start, end):
    table = {
        "铜冠铜箔": {"interval_gain": 22.5},
        "英维克": {"interval_gain": 3.0},
    }
    return {name: table[name] for name in stocks if name in table}


def test_machine_readable_due_items_are_adjudicated(tmp_path: Path) -> None:
    judgments, cpath, vpath, hit_id, miss_id, manual_id = _seed_ledger(tmp_path)
    report = run_adjudication_job(
        judgments_path=judgments,
        checkpoints_path=cpath,
        verdicts_path=vpath,
        today="2026-06-18",
        apply=True,
        market_returns_fn=_returns,
    )
    by_id = {item.id: item for item in report.auto}
    assert by_id[hit_id].verdict == "hit"
    assert by_id[miss_id].verdict == "miss"
    assert manual_id not in by_id
    rows = [json.loads(line) for line in vpath.read_text(encoding="utf-8").splitlines()]
    verdicts = {row["id"]: row["verdict"] for row in rows}
    assert verdicts[hit_id] == "hit"
    assert verdicts[miss_id] == "miss"
    assert all(row["auto"] is True for row in rows)
    assert "returns" in rows[0]["observed"]


def test_manual_due_item_goes_to_human_queue(tmp_path: Path) -> None:
    judgments, cpath, vpath, hit_id, miss_id, manual_id = _seed_ledger(tmp_path)
    report = run_adjudication_job(
        judgments_path=judgments,
        checkpoints_path=cpath,
        verdicts_path=vpath,
        today="2026-06-18",
        apply=True,
        market_returns_fn=_returns,
    )
    queued_ids = {item.id for item in report.queued}
    assert queued_ids == {manual_id}
    assert all(item.verdict is None for item in report.queued)
    rows = [json.loads(line) for line in vpath.read_text(encoding="utf-8").splitlines()]
    assert manual_id not in {row["id"] for row in rows}


def test_judgment_original_text_is_not_rewritten(tmp_path: Path) -> None:
    judgments, cpath, vpath, *_ = _seed_ledger(tmp_path)
    before = judgments.read_bytes()
    report = run_adjudication_job(
        judgments_path=judgments,
        checkpoints_path=cpath,
        verdicts_path=vpath,
        today="2026-06-18",
        apply=True,
        market_returns_fn=_returns,
    )
    assert report.judgments_unchanged is True
    assert judgments.read_bytes() == before
    payload = json.loads(judgments.read_text(encoding="utf-8").splitlines()[0])
    assert payload["claim"] == ORIGINAL_CLAIM
    assert payload["memo"] == ORIGINAL_MEMO


def test_empty_due_job_is_idempotent(tmp_path: Path) -> None:
    judgments = tmp_path / "judgments.jsonl"
    cpath = tmp_path / "checkpoints.jsonl"
    vpath = tmp_path / "verdicts.jsonl"
    _write_judgment(judgments)
    judgments.write_text(
        json.dumps(
            {
                "ts": "2026-05-01T00:00:00",
                "id": "j-future",
                "record_type": "foresight_judgment",
                "status": "accepted",
                "memo": ORIGINAL_MEMO,
                "claim": ORIGINAL_CLAIM,
                "verify_by": {"due": "2099-01-01", "criterion": "空到期日不应触发"},
                "confidence": "中",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    checkpoints.register_checkpoint(
        cpath,
        claim="未到期",
        due="2099-01-01",
        metric={"type": "stock_return", "op": ">=", "target": 15, "window_days": 60},
        stocks=["铜冠铜箔"],
        ts="2026-05-01T00:00:00",
    )
    before_j = judgments.read_bytes()
    before_c = cpath.read_bytes()
    first = run_adjudication_job(
        judgments_path=judgments,
        checkpoints_path=cpath,
        verdicts_path=vpath,
        today="2026-06-18",
        apply=True,
        market_returns_fn=_returns,
    )
    after_first_v = vpath.read_bytes() if vpath.exists() else b""
    second = run_adjudication_job(
        judgments_path=judgments,
        checkpoints_path=cpath,
        verdicts_path=vpath,
        today="2026-06-18",
        apply=True,
        market_returns_fn=_returns,
    )
    assert first.auto == ()
    assert first.queued == ()
    assert first.verdicts_appended == 0
    assert second.verdicts_appended == 0
    assert judgments.read_bytes() == before_j
    assert cpath.read_bytes() == before_c
    assert (vpath.read_bytes() if vpath.exists() else b"") == after_first_v


def test_second_apply_does_not_duplicate_terminal_verdict(tmp_path: Path) -> None:
    judgments, cpath, vpath, hit_id, miss_id, manual_id = _seed_ledger(tmp_path)
    run_adjudication_job(
        judgments_path=judgments,
        checkpoints_path=cpath,
        verdicts_path=vpath,
        today="2026-06-18",
        apply=True,
        market_returns_fn=_returns,
    )
    first_bytes = vpath.read_bytes()
    second = run_adjudication_job(
        judgments_path=judgments,
        checkpoints_path=cpath,
        verdicts_path=vpath,
        today="2026-06-18",
        apply=True,
        market_returns_fn=_returns,
    )
    assert {item.id for item in second.auto} == set()
    assert {item.id for item in second.queued} == {manual_id}
    assert vpath.read_bytes() == first_bytes
    assert hit_id in first_bytes.decode("utf-8")
    assert miss_id in first_bytes.decode("utf-8")


def test_cli_adjudicate_queues_manual_without_writing_verdict(tmp_path: Path, capsys) -> None:
    judgments = tmp_path / "judgments.jsonl"
    cpath = tmp_path / "checkpoints.jsonl"
    vpath = tmp_path / "verdicts.jsonl"
    _write_judgment(judgments)
    _, manual = checkpoints.register_checkpoint(
        cpath,
        claim="公司级硬证据升级",
        due="2026-06-01",
        metric={"type": "manual"},
        ts="2026-05-01T00:00:00",
    )
    code = cli.main(
        [
            "checkpoint",
            "adjudicate",
            "--date",
            "2026-06-18",
            "--apply",
            "--json",
            "--judgments-file",
            str(judgments),
            "--checkpoints-file",
            str(cpath),
            "--verdicts-file",
            str(vpath),
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert [item["id"] for item in payload["queued"]] == [manual["id"]]
    assert payload["auto"] == []
    assert payload["judgments_unchanged"] is True
    assert not vpath.exists()
