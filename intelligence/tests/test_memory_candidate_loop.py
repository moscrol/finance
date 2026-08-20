"""书距 S6：user_memory 离线候选环——验收判据逐条钉住。

1. 夹具台账跑出 ≥1 条候选，归因链字段完整；dry-run 不落盘；
2. 幂等：同一台账重跑，第二次零新候选；
3. gate 拒绝的候选留档带理由；没有任何路径绕过 memory_gate 直写；
4. 归因可反查：给任一 accepted 经验，一步查到来源记录 ids。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from intelligence.services import memory_candidate_loop as loop
from intelligence.services.memory_gate import MemoryGate


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _repeated_correction_fixture(root: Path) -> None:
    _write_jsonl(
        root / "corrections.jsonl",
        [
            {
                "ts": "2026-08-01T10:00:00+00:00",
                "correction": "不是放量就算发酵",
                "principle": "双红确认后才算题材发酵",
                "themes": ["液冷"],
            },
            {
                "ts": "2026-08-05T09:00:00+00:00",
                "correction": "又把单日脉冲当发酵了",
                "principle": "双红确认后才算题材发酵",
                "themes": ["机器人"],
            },
            {
                "ts": "2026-08-06T09:00:00+00:00",
                "correction": "只出现一次的原则，不该成候选",
                "themes": ["单次"],
            },
        ],
    )


def _overturned_verdict_fixture(root: Path) -> None:
    _write_jsonl(
        root / "checkpoints.jsonl",
        [
            {
                "id": "ck-2026-08-01-abc123",
                "ts": "2026-08-01T08:00:00+00:00",
                "claim": "液冷板块本月出现主升段",
                "due": "2026-08-10",
                "category": "题材节奏",
                "themes": ["液冷"],
                "stocks": ["英维克"],
            }
        ],
    )
    _write_jsonl(
        root / "verdicts.jsonl",
        [
            {
                "id": "ck-2026-08-01-abc123",
                "checked_at": "2026-08-10T20:00:00+00:00",
                "verdict": "hit",
                "score": 1.0,
                "data_source": "duckdb",
                "auto": True,
            },
            {
                "id": "ck-2026-08-01-abc123",
                "checked_at": "2026-08-11T09:00:00+00:00",
                "verdict": "miss",
                "score": 0.0,
                "data_source": "manual",
                "auto": False,
                "reason": "涨的是储能逻辑，不是液冷主升",
            },
        ],
    )


# --------------------------------------------------------------------------- #
# 验收 1：夹具跑出候选 + 归因链完整；dry-run 不落盘
# --------------------------------------------------------------------------- #
def test_repeated_correction_produces_accepted_candidate(tmp_path: Path) -> None:
    _repeated_correction_fixture(tmp_path)

    report = loop.run_candidate_loop(users_root=tmp_path)

    assert report["produced"] == 1
    assert report["accepted"] == 1
    row = report["candidates"][0]
    assert row["rule"] == loop.RULE_REPEATED_CORRECTION
    assert row["kind"] == "user_preference"
    assert row["status"] == "accepted"
    assert row["content"] == "双红确认后才算题材发酵"
    # 归因链三要素齐且来源指向两条原始纠偏
    attribution = row["attribution"]
    assert attribution["rule"] == loop.RULE_REPEATED_CORRECTION
    assert attribution["generated_at"]
    assert len(attribution["source_record_ids"]) == 2
    assert all(
        ref.startswith("corrections:") for ref in attribution["source_record_ids"]
    )
    # durable 落盘经 gate 适配器：晋升行带绑定内容哈希的 promotion 元数据
    written = [
        rec
        for rec in _read_jsonl(tmp_path / "corrections.jsonl")
        if isinstance(rec.get("promotion"), dict)
    ]
    assert len(written) == 1
    promo = written[0]["promotion"]
    assert promo["candidate_id"] == row["id"]
    assert promo["content_sha256"] == hashlib.sha256(
        written[0]["correction"].encode("utf-8")
    ).hexdigest()
    # 候选台账留档
    ledger = _read_jsonl(tmp_path / loop.CANDIDATES_FILENAME)
    assert [r["id"] for r in ledger] == [row["id"]]


def test_verdict_overturned_produces_decision_lesson(tmp_path: Path) -> None:
    _overturned_verdict_fixture(tmp_path)

    report = loop.run_candidate_loop(users_root=tmp_path)

    assert report["produced"] == 1
    row = report["candidates"][0]
    assert row["rule"] == loop.RULE_VERDICT_OVERTURNED
    assert row["kind"] == "decision_lesson"
    assert row["status"] == "accepted"
    assert "机判「命中」被人工改判「落空」" in row["content"]
    assert "涨的是储能逻辑" in row["content"]
    # gate 溯源用的是最新（人工）终态判
    assert row["gate_provenance"] == {
        "checkpoint_id": "ck-2026-08-01-abc123",
        "verdict": "miss",
    }
    refs = row["attribution"]["source_record_ids"]
    assert refs[0] == "checkpoints:ck-2026-08-01-abc123"
    assert len(refs) == 3
    # 教训落 judgments，带题材/个股标签
    written = _read_jsonl(tmp_path / "judgments.jsonl")
    assert len(written) == 1
    assert written[0]["memo"] == row["content"]
    assert written[0]["themes"] == ["液冷"]
    assert written[0]["stocks"] == ["英维克"]
    assert written[0]["promotion"]["candidate_id"] == row["id"]


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    _repeated_correction_fixture(tmp_path)
    _overturned_verdict_fixture(tmp_path)
    before = {
        name: (tmp_path / name).read_text(encoding="utf-8")
        for name in ("corrections.jsonl", "checkpoints.jsonl", "verdicts.jsonl")
    }

    report = loop.run_candidate_loop(users_root=tmp_path, dry_run=True)

    assert report["dry_run"] is True
    assert report["produced"] == 2
    assert report["accepted"] == 2
    assert not (tmp_path / loop.CANDIDATES_FILENAME).exists()
    assert not (tmp_path / "judgments.jsonl").exists()
    for name, text in before.items():
        assert (tmp_path / name).read_text(encoding="utf-8") == text


# --------------------------------------------------------------------------- #
# 验收 2：幂等——同一台账重跑两次，第二次零新候选
# --------------------------------------------------------------------------- #
def test_rerun_on_same_ledger_produces_zero_new_candidates(tmp_path: Path) -> None:
    _repeated_correction_fixture(tmp_path)
    _overturned_verdict_fixture(tmp_path)

    first = loop.run_candidate_loop(users_root=tmp_path)
    snapshot = {
        name: (tmp_path / name).read_text(encoding="utf-8")
        for name in (
            "corrections.jsonl",
            "judgments.jsonl",
            loop.CANDIDATES_FILENAME,
        )
    }
    second = loop.run_candidate_loop(users_root=tmp_path)

    assert first["produced"] == 2
    assert second["produced"] == 0
    assert second["skipped_existing"] == 2
    for name, text in snapshot.items():
        assert (tmp_path / name).read_text(encoding="utf-8") == text


def test_promoted_rows_do_not_feed_rules(tmp_path: Path) -> None:
    """晋升副本不算用户信号：一条原始纠偏 + 它的晋升行 ≠ 两票。"""
    _write_jsonl(
        tmp_path / "corrections.jsonl",
        [
            {
                "ts": "2026-08-01T10:00:00+00:00",
                "correction": "双红确认后才算题材发酵",
                "principle": "双红确认后才算题材发酵",
            },
            {
                "ts": "2026-08-07T02:00:00+00:00",
                "correction": "双红确认后才算题材发酵",
                "principle": "双红确认后才算题材发酵",
                "promotion": {"candidate_id": "memcand-x", "reason": "explicit_user_correction"},
            },
        ],
    )

    report = loop.run_candidate_loop(users_root=tmp_path)

    assert report["produced"] == 0


def test_archived_corrections_do_not_count(tmp_path: Path) -> None:
    """memory_status 归档的纠偏不参与候选生成（走既有 loader 的状态过滤）。"""
    _write_jsonl(
        tmp_path / "corrections.jsonl",
        [
            {
                "ts": "2026-08-01T10:00:00+00:00",
                "principle": "双红确认后才算题材发酵",
                "correction": "双红确认后才算题材发酵",
            },
            {
                "ts": "2026-08-05T09:00:00+00:00",
                "principle": "双红确认后才算题材发酵",
                "correction": "双红确认后才算题材发酵",
            },
            {
                "record_type": "memory_status",
                "ts": "2026-08-06T09:00:00+00:00",
                "target_ts": "2026-08-05T09:00:00+00:00",
                "status": "archived",
                "reason": "过时",
            },
        ],
    )

    report = loop.run_candidate_loop(users_root=tmp_path)

    assert report["produced"] == 0


def test_maintained_or_machine_latest_verdicts_are_not_overturned(tmp_path: Path) -> None:
    """人工维持原判、最新仍是机判、人工判非终态——都不算翻案。"""
    _write_jsonl(
        tmp_path / "checkpoints.jsonl",
        [
            {"id": f"ck-{i}", "ts": "2026-08-01T08:00:00+00:00", "claim": f"判断{i}", "due": "2026-08-10"}
            for i in (1, 2, 3)
        ],
    )
    _write_jsonl(
        tmp_path / "verdicts.jsonl",
        [
            # ck-1：人工复核维持原判
            {"id": "ck-1", "checked_at": "t1", "verdict": "hit", "auto": True},
            {"id": "ck-1", "checked_at": "t2", "verdict": "hit", "auto": False},
            # ck-2：人工先判，机判在后（最新是机判）
            {"id": "ck-2", "checked_at": "t1", "verdict": "miss", "auto": False},
            {"id": "ck-2", "checked_at": "t2", "verdict": "hit", "auto": True},
            # ck-3：机判后只有非终态人工记录
            {"id": "ck-3", "checked_at": "t1", "verdict": "hit", "auto": True},
            {"id": "ck-3", "checked_at": "t2", "verdict": "unverifiable", "auto": False},
        ],
    )

    report = loop.run_candidate_loop(users_root=tmp_path)

    assert report["produced"] == 0


# --------------------------------------------------------------------------- #
# 验收 3：gate 拒绝留档带理由；没有任何路径绕过 memory_gate 直写
# --------------------------------------------------------------------------- #
def test_gate_rejection_is_archived_with_reason(tmp_path: Path) -> None:
    """同秒同文重复行让 gate 溯源歧义（matches != 1）→ 拒绝留档，零 durable 写。"""
    _write_jsonl(
        tmp_path / "corrections.jsonl",
        [
            {
                "ts": "2026-08-01T10:00:00+00:00",
                "correction": "同秒重复的原则",
                "principle": "同秒重复的原则",
            },
            {
                "ts": "2026-08-01T10:00:00+00:00",
                "correction": "同秒重复的原则",
                "principle": "同秒重复的原则",
            },
        ],
    )
    before = (tmp_path / "corrections.jsonl").read_text(encoding="utf-8")

    report = loop.run_candidate_loop(users_root=tmp_path)

    assert report["produced"] == 1
    assert report["rejected"] == 1
    row = report["candidates"][0]
    assert row["status"] == "rejected"
    assert row["gate_reason"] == "correction_provenance_mismatch"
    # 拒绝在档、durable 台账零变化
    ledger = _read_jsonl(tmp_path / loop.CANDIDATES_FILENAME)
    assert ledger[0]["status"] == "rejected"
    assert ledger[0]["gate_reason"] == "correction_provenance_mismatch"
    assert (tmp_path / "corrections.jsonl").read_text(encoding="utf-8") == before
    assert not (tmp_path / "judgments.jsonl").exists()


def test_all_durable_writes_go_through_gate(tmp_path: Path, monkeypatch) -> None:
    """把 gate 换成全拒：本会产生 accepted 的夹具必须零 durable 写入。

    这钉住「写入只经 gate API」：环里不存在任何绕过 ``MemoryGate.decide``
    结果直写台账的路径。
    """
    _repeated_correction_fixture(tmp_path)
    _overturned_verdict_fixture(tmp_path)
    before_corrections = (tmp_path / "corrections.jsonl").read_text(encoding="utf-8")

    def reject_all(self, candidate, *, checkpoints, verdicts, corrections):  # noqa: ANN001
        from intelligence.services.memory_gate import PromotionDecision

        return PromotionDecision(
            candidate.candidate_id,
            False,
            "none",
            "test_forced_rejection",
            hashlib.sha256(candidate.content.encode("utf-8")).hexdigest(),
        )

    monkeypatch.setattr(MemoryGate, "decide", reject_all)

    report = loop.run_candidate_loop(users_root=tmp_path)

    assert report["produced"] == 2
    assert report["accepted"] == 0
    assert report["rejected"] == 2
    assert (tmp_path / "corrections.jsonl").read_text(encoding="utf-8") == before_corrections
    assert not (tmp_path / "judgments.jsonl").exists()
    assert all(
        row["status"] == "rejected" and row["gate_reason"] == "test_forced_rejection"
        for row in _read_jsonl(tmp_path / loop.CANDIDATES_FILENAME)
    )


def test_loop_module_never_calls_raw_writers() -> None:
    """源级双保险：环模块只允许 validated 写入口，不得引用原始 append 写入器。"""
    source = Path(loop.__file__).read_text(encoding="utf-8")
    assert "record_correction(" not in source
    assert "record_judgment(" not in source
    assert "record_validated_preference(" in source
    assert "record_validated_judgment(" in source


# --------------------------------------------------------------------------- #
# 验收 4：归因可反查——accepted 经验一步查到来源记录 ids
# --------------------------------------------------------------------------- #
def test_trace_from_accepted_experience_to_source_ids(tmp_path: Path) -> None:
    _repeated_correction_fixture(tmp_path)
    report = loop.run_candidate_loop(users_root=tmp_path)
    candidate = report["candidates"][0]
    promoted = [
        rec
        for rec in _read_jsonl(tmp_path / "corrections.jsonl")
        if isinstance(rec.get("promotion"), dict)
    ][0]

    # 三个入口都能一步到来源：候选 id / 晋升行 ts / 内容哈希前缀
    for query in (
        promoted["promotion"]["candidate_id"],
        promoted["ts"],
        candidate["content_sha256"][:12],
    ):
        matches = loop.trace_candidate(query, users_root=tmp_path)
        assert len(matches) == 1, query
        assert (
            matches[0]["attribution"]["source_record_ids"]
            == candidate["attribution"]["source_record_ids"]
        )

    assert loop.trace_candidate("memcand-missing", users_root=tmp_path) == []
