"""S6 离线候选更新链测试：规则、归因链、幂等、拒绝留档、无旁路直写。

夹具台账全部用各 service 的写入函数在 tmp 目录现场构造（显式 ts，确定性），
不依赖在线服务 / LLM / duckdb。
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from intelligence.services import memory_candidate_loop as loop
from intelligence.services.checkpoints import record_verdict, register_checkpoint
from intelligence.services.corrections import record_correction
from intelligence.services.interactions import record_interaction


PRINCIPLE = "配额兑现是氟化工主线"


def _build_accept_fixture(root: Path) -> dict[str, Any]:
    """两条同主题同向纠偏 + 一次机判被人工翻案：应产 2 条候选且都过 gate。"""
    corrections_path = root / "corrections.jsonl"
    record_correction(
        corrections_path,
        correction="氟化工先看三代制冷剂配额兑现",
        principle=PRINCIPLE,
        themes=["氟化工"],
        ts="2026-08-01T10:00:00+00:00",
    )
    record_correction(
        corrections_path,
        correction="氟化工还是盯配额兑现节奏",
        principle=PRINCIPLE,
        themes=["氟化工"],
        ts="2026-08-03T09:00:00+00:00",
    )
    record_correction(
        corrections_path,
        correction="AI算力别追高",
        themes=["AI算力"],
        ts="2026-08-04T09:00:00+00:00",
    )
    _, checkpoint = register_checkpoint(
        root / "checkpoints.jsonl",
        claim="三代制冷剂Q3提价在验证窗内落地",
        due="2026-08-10",
        category="产能时点",
        themes=["氟化工"],
        stocks=["巨化股份"],
        ts="2026-08-01T11:00:00+00:00",
    )
    record_verdict(
        root / "verdicts.jsonl",
        id=checkpoint["id"],
        verdict="miss",
        auto=True,
        checked_at="2026-08-10T20:00:00+00:00",
        data_source="duckdb",
        reason="窗口内未见提价",
    )
    record_verdict(
        root / "verdicts.jsonl",
        id=checkpoint["id"],
        verdict="hit",
        auto=False,
        checked_at="2026-08-11T08:00:00+00:00",
        data_source="manual",
        reason="人工核实已提价，机检口径漏了经销商报价",
    )
    record_interaction(
        root / "interactions.jsonl",
        kind="like",
        themes=["氟化工"],
        ts="2026-08-04T10:00:00+00:00",
    )
    return {"checkpoint_id": checkpoint["id"]}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.name: p.read_bytes()
        for p in sorted(root.glob("*.jsonl"))
    }


class RepeatedCorrectionRuleTests(unittest.TestCase):
    def test_two_same_theme_same_direction_corrections_produce_candidate(self) -> None:
        records = [
            {"ts": "t1", "correction": "先看配额", "principle": PRINCIPLE, "themes": ["氟化工"]},
            {"ts": "t2", "correction": "还是配额", "principle": PRINCIPLE, "themes": ["氟化工"]},
        ]
        proposals = loop.generate_candidates(records, [], [])

        self.assertEqual(len(proposals), 1)
        proposal = proposals[0]
        self.assertEqual(proposal.kind, "user_correction")
        self.assertEqual(proposal.trigger_rule, loop.RULE_REPEATED_CORRECTION)
        self.assertEqual(proposal.content, PRINCIPLE)
        self.assertEqual(proposal.correction_ts, "t2")
        self.assertEqual(
            proposal.source_record_ids, ("correction:t1", "correction:t2")
        )
        self.assertEqual(proposal.themes, ("氟化工",))

    def test_single_or_cross_theme_or_cross_direction_produces_nothing(self) -> None:
        single = [{"ts": "t1", "correction": "只此一条", "themes": ["氟化工"]}]
        cross_theme = [
            {"ts": "t1", "correction": "同一句话", "themes": ["氟化工"]},
            {"ts": "t2", "correction": "同一句话", "themes": ["AI算力"]},
        ]
        cross_direction = [
            {"ts": "t1", "principle": "先看供给收缩弹性", "correction": "x", "themes": ["氟化工"]},
            {"ts": "t2", "principle": "估值切换需要盈利兑现", "correction": "y", "themes": ["氟化工"]},
        ]
        for records in (single, cross_theme, cross_direction):
            self.assertEqual(loop.generate_candidates(records, [], []), [])

    def test_containment_counts_as_same_direction(self) -> None:
        records = [
            {"ts": "t1", "correction": "默认A股", "themes": ["范围"]},
            {"ts": "t2", "correction": "默认A股，时间歧义才追问", "themes": ["范围"]},
        ]
        proposals = loop.generate_candidates(records, [], [])
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].content, "默认A股，时间歧义才追问")

    def test_promoted_rows_are_not_rule_input(self) -> None:
        records = [
            {"ts": "t1", "correction": "x", "principle": PRINCIPLE, "themes": ["氟化工"]},
            {
                "ts": "t2",
                "correction": PRINCIPLE,
                "principle": PRINCIPLE,
                "themes": ["氟化工"],
                "promotion": {"candidate_id": "mc-old"},
            },
        ]
        self.assertEqual(loop.generate_candidates(records, [], []), [])

    def test_multi_theme_pair_merges_into_one_candidate(self) -> None:
        records = [
            {"ts": "t1", "principle": PRINCIPLE, "correction": "x", "themes": ["氟化工", "制冷剂"]},
            {"ts": "t2", "principle": PRINCIPLE, "correction": "y", "themes": ["氟化工", "制冷剂"]},
        ]
        proposals = loop.generate_candidates(records, [], [])
        self.assertEqual(len(proposals), 1)
        self.assertEqual(set(proposals[0].themes), {"氟化工", "制冷剂"})


class OverturnedVerdictRuleTests(unittest.TestCase):
    CHECKPOINT = {"id": "ck-1", "claim": "Q3提价落地", "category": "产能时点", "themes": ["氟化工"]}

    def test_auto_terminal_overturned_by_manual_produces_lesson(self) -> None:
        verdicts = [
            {"id": "ck-1", "verdict": "miss", "auto": True, "checked_at": "c1"},
            {"id": "ck-1", "verdict": "hit", "auto": False, "checked_at": "c2"},
        ]
        proposals = loop.generate_candidates([], [self.CHECKPOINT], verdicts)

        self.assertEqual(len(proposals), 1)
        proposal = proposals[0]
        self.assertEqual(proposal.kind, "decision_lesson")
        self.assertEqual(proposal.trigger_rule, loop.RULE_VERDICT_OVERTURNED)
        self.assertEqual(proposal.checkpoint_id, "ck-1")
        self.assertIn("机判 miss", proposal.content)
        self.assertIn("人工改判 hit", proposal.content)
        self.assertEqual(
            proposal.source_record_ids,
            ("checkpoint:ck-1", "verdict:ck-1@c1", "verdict:ck-1@c2"),
        )

    def test_confirmation_or_manual_first_or_dangling_produces_nothing(self) -> None:
        confirmation = [
            {"id": "ck-1", "verdict": "hit", "auto": True, "checked_at": "c1"},
            {"id": "ck-1", "verdict": "hit", "auto": False, "checked_at": "c2"},
        ]
        manual_first = [
            {"id": "ck-1", "verdict": "hit", "auto": False, "checked_at": "c1"},
            {"id": "ck-1", "verdict": "miss", "auto": True, "checked_at": "c2"},
        ]
        unverifiable_auto = [
            {"id": "ck-1", "verdict": "unverifiable", "auto": True, "checked_at": "c1"},
            {"id": "ck-1", "verdict": "hit", "auto": False, "checked_at": "c2"},
        ]
        self.assertEqual(
            loop.generate_candidates([], [self.CHECKPOINT], confirmation), []
        )
        self.assertEqual(
            loop.generate_candidates([], [self.CHECKPOINT], manual_first), []
        )
        self.assertEqual(
            loop.generate_candidates([], [self.CHECKPOINT], unverifiable_auto), []
        )
        # 悬空 verdict（checkpoints 里查无此 id）不产候选
        dangling = [
            {"id": "ck-ghost", "verdict": "miss", "auto": True, "checked_at": "c1"},
            {"id": "ck-ghost", "verdict": "hit", "auto": False, "checked_at": "c2"},
        ]
        self.assertEqual(loop.generate_candidates([], [self.CHECKPOINT], dangling), [])


class RunLoopTests(unittest.TestCase):
    def test_run_accepts_candidates_with_full_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = _build_accept_fixture(root)
            summary = loop.run_loop(root, generated_at="2026-08-15T00:00:00+00:00")

            self.assertEqual(summary["proposed"], 2)
            self.assertEqual(summary["accepted"], 2)
            self.assertEqual(summary["rejected"], 0)
            self.assertEqual(summary["scanned"]["interactions"], 1)

            archive = loop.load_candidate_archive(root / loop.CANDIDATES_FILENAME)
            self.assertEqual(len(archive), 2)
            for row in archive:
                # 归因链三要素：来源记录 ids、触发规则、生成时间
                self.assertTrue(row["source_record_ids"])
                self.assertIn(
                    row["trigger_rule"],
                    {loop.RULE_REPEATED_CORRECTION, loop.RULE_VERDICT_OVERTURNED},
                )
                self.assertEqual(row["generated_at"], "2026-08-15T00:00:00+00:00")
                self.assertEqual(row["status"], "accepted")
                self.assertTrue(row["gate"]["eligible"])

            by_rule = {row["trigger_rule"]: row for row in archive}
            self.assertEqual(
                by_rule[loop.RULE_REPEATED_CORRECTION]["source_record_ids"],
                [
                    "correction:2026-08-01T10:00:00+00:00",
                    "correction:2026-08-03T09:00:00+00:00",
                ],
            )
            checkpoint_id = fixture["checkpoint_id"]
            self.assertEqual(
                by_rule[loop.RULE_VERDICT_OVERTURNED]["source_record_ids"],
                [
                    f"checkpoint:{checkpoint_id}",
                    f"verdict:{checkpoint_id}@2026-08-10T20:00:00+00:00",
                    f"verdict:{checkpoint_id}@2026-08-11T08:00:00+00:00",
                ],
            )

            # 晋升行都带 gate 绑定的 promotion 元数据（内容 SHA-256 逐字绑定）
            correction_rows = _read_jsonl(root / "corrections.jsonl")
            self.assertEqual(len(correction_rows), 4)
            promoted_pref = correction_rows[-1]
            self.assertEqual(
                promoted_pref["promotion"]["candidate_id"],
                by_rule[loop.RULE_REPEATED_CORRECTION]["candidate_id"],
            )
            self.assertEqual(
                promoted_pref["promotion"]["content_sha256"],
                hashlib.sha256(promoted_pref["principle"].encode("utf-8")).hexdigest(),
            )
            judgment_rows = _read_jsonl(root / "judgments.jsonl")
            self.assertEqual(len(judgment_rows), 1)
            promoted_lesson = judgment_rows[0]
            self.assertEqual(
                promoted_lesson["promotion"]["candidate_id"],
                by_rule[loop.RULE_VERDICT_OVERTURNED]["candidate_id"],
            )
            self.assertEqual(
                promoted_lesson["promotion"]["content_sha256"],
                hashlib.sha256(promoted_lesson["memo"].encode("utf-8")).hexdigest(),
            )
            self.assertEqual(promoted_lesson["stocks"], ["巨化股份"])

    def test_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_accept_fixture(root)
            before = _snapshot(root)

            summary = loop.run_loop(root, dry_run=True)

            self.assertEqual(summary["accepted"], 2)
            self.assertTrue(summary["dry_run"])
            self.assertEqual(len(summary["candidates"]), 2)
            self.assertFalse((root / loop.CANDIDATES_FILENAME).exists())
            self.assertEqual(_snapshot(root), before)

    def test_second_run_produces_zero_new_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_accept_fixture(root)
            first = loop.run_loop(root)
            after_first = _snapshot(root)

            second = loop.run_loop(root)

            self.assertEqual(first["new"], 2)
            self.assertEqual(second["new"], 0)
            self.assertEqual(second["accepted"], 0)
            self.assertEqual(second["skipped_existing"], 2)
            self.assertEqual(_snapshot(root), after_first)

    def test_gate_rejection_is_archived_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "corrections.jsonl"
            # 同秒双写同一原则：规则会产候选，但 gate 的唯一溯源判据（恰一条匹配）
            # 应拒绝——拒绝路径必须留档带理由。
            record_correction(
                path,
                correction="同秒双写一",
                principle="双写原则需要去重",
                themes=["测试"],
                ts="2026-08-05T10:00:00+00:00",
            )
            record_correction(
                path,
                correction="同秒双写二",
                principle="双写原则需要去重",
                themes=["测试"],
                ts="2026-08-05T10:00:00+00:00",
            )
            before = path.read_bytes()

            summary = loop.run_loop(root)

            self.assertEqual(summary["proposed"], 1)
            self.assertEqual(summary["accepted"], 0)
            self.assertEqual(summary["rejected"], 1)
            archive = loop.load_candidate_archive(root / loop.CANDIDATES_FILENAME)
            self.assertEqual(len(archive), 1)
            self.assertEqual(archive[0]["status"], "rejected")
            self.assertEqual(
                archive[0]["gate"]["reason"], "correction_provenance_mismatch"
            )
            self.assertEqual(archive[0]["source_record_ids"][:1], ["correction:2026-08-05T10:00:00+00:00"])
            # 被拒候选不落 durable 层
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse((root / "judgments.jsonl").exists())

    def test_durable_writes_only_go_through_gate_api(self) -> None:
        """无旁路直写：换掉两个 gate 认证写入口后，durable 台账一个字节都不该变。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_accept_fixture(root)
            before = _snapshot(root)

            pref_stub = mock.Mock(return_value=(root / "corrections.jsonl", {"ts": "stub"}))
            judg_stub = mock.Mock(return_value=(root / "judgments.jsonl", {"ts": "stub"}))
            with mock.patch.object(
                loop, "record_validated_preference", pref_stub
            ), mock.patch.object(loop, "record_validated_judgment", judg_stub):
                summary = loop.run_loop(root)

            self.assertEqual(summary["accepted"], 2)
            self.assertEqual(pref_stub.call_count, 1)
            self.assertEqual(judg_stub.call_count, 1)
            # 两个入口都只收到 gate 裁决通过的 decision
            self.assertTrue(pref_stub.call_args.kwargs["decision"].eligible)
            self.assertTrue(judg_stub.call_args.kwargs["decision"].eligible)
            after = _snapshot(root)
            # 候选档可以写（那是回路自己的台账），durable 台账必须逐字节不变
            after.pop(loop.CANDIDATES_FILENAME, None)
            self.assertEqual(after, before)

    def test_gate_binding_failure_blocks_all_durable_writes(self) -> None:
        """promotion_metadata（gate 内容绑定 API）被拔掉时，任何 durable 写都进行不下去。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_accept_fixture(root)
            before = _snapshot(root)

            def _boom(*args: Any, **kwargs: Any) -> None:
                raise AssertionError("gate binding bypassed")

            with mock.patch(
                "intelligence.services.corrections.promotion_metadata", _boom
            ), mock.patch(
                "intelligence.services.judgments.promotion_metadata", _boom
            ):
                with self.assertRaises(AssertionError):
                    loop.run_loop(root)

            after = _snapshot(root)
            after.pop(loop.CANDIDATES_FILENAME, None)
            self.assertEqual(after, before)


class TraceTests(unittest.TestCase):
    def test_trace_by_candidate_id_and_content_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_accept_fixture(root)
            loop.run_loop(root)

            # 从 accepted 经验（judgments 晋升行）拿 promotion 元数据反查来源
            promoted = _read_jsonl(root / "judgments.jsonl")[0]
            archive = loop.load_candidate_archive(root / loop.CANDIDATES_FILENAME)

            by_id = loop.trace_candidate(
                archive, candidate_id=promoted["promotion"]["candidate_id"]
            )
            self.assertEqual(len(by_id), 1)
            self.assertTrue(
                any(s.startswith("checkpoint:") for s in by_id[0]["source_record_ids"])
            )

            by_sha = loop.trace_candidate(
                archive, content_sha256=promoted["promotion"]["content_sha256"]
            )
            self.assertEqual(by_sha, by_id)

    def test_cli_run_trace_roundtrip(self) -> None:
        from scripts import run_memory_candidate_loop as cli

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_accept_fixture(root)

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cli.main(["run", "--user-dir", str(root), "--json"])
            self.assertEqual(rc, 0)
            summary = json.loads(out.getvalue())
            self.assertEqual(summary["accepted"], 2)

            # 归因可反查：拿 accepted 经验原文，一条命令查到来源记录 ids
            promoted = _read_jsonl(root / "corrections.jsonl")[-1]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cli.main(
                    ["trace", "--user-dir", str(root), "--content", promoted["principle"]]
                )
            self.assertEqual(rc, 0)
            rows = json.loads(out.getvalue())
            self.assertEqual(len(rows), 1)
            self.assertEqual(
                rows[0]["source_record_ids"],
                [
                    "correction:2026-08-01T10:00:00+00:00",
                    "correction:2026-08-03T09:00:00+00:00",
                ],
            )

            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                rc = cli.main(["trace", "--user-dir", str(root), "--candidate-id", "mc-none"])
            self.assertEqual(rc, 2)

    def test_cli_dry_run_writes_nothing(self) -> None:
        from scripts import run_memory_candidate_loop as cli

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_accept_fixture(root)
            before = _snapshot(root)

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cli.main(["run", "--user-dir", str(root), "--dry-run"])

            self.assertEqual(rc, 0)
            self.assertIn("[dry-run]", out.getvalue())
            self.assertEqual(_snapshot(root), before)
            self.assertFalse((root / loop.CANDIDATES_FILENAME).exists())


if __name__ == "__main__":
    unittest.main()
