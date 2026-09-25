from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence import cli, userspace
from intelligence.services import perspective_lab, perspective_learning


def _us(tmp: str, uid: str = "tester") -> userspace.UserSpace:
    root = Path(tmp) / uid
    return userspace.UserSpace(
        user_id=uid,
        root=root,
        profile_path=root / "profile.json",
        derived_path=root / "profile.derived.json",
        memory_path=root / "foresight_memory.jsonl",
        interactions_path=root / "interactions.jsonl",
        corrections_path=root / "corrections.jsonl",
        experience_cards_path=root / "experience_cards.jsonl",
        answer_scores_path=root / "answer_scores.jsonl",
        judgments_path=root / "judgments.jsonl",
        checkpoints_path=root / "checkpoints.jsonl",
        verdicts_path=root / "verdicts.jsonl",
        strategy_params_path=root / "strategy_params.json",
    )


ARTICLE_TEXT = (
    "今天复盘：AI硬件高位分歧。我的习惯是先定市场阶段再谈方向。"
    "如果核心股缩量回踩关键均线且题材仍有新高扩散，就是回流机会；"
    "但高位后排放量冲高回落时必须降低仓位假设。"
)


def _fake_llm_payload() -> dict:
    return {
        "claims": [
            {
                "claim": "AI硬件处于高位分歧而非退潮",
                "claim_type": "market_phase",
                "evidence_used": ["核心股承接", "题材新高扩散"],
                "falsifiers": ["核心股跌破关键均线"],
            }
        ],
        "reasoning_moves": ["先定市场阶段再谈方向"],
        "risk_notes": ["高位后排放量冲高回落"],
        "profile_updates": [
            {
                "field": "risk_triggers",
                "value": "高位后排放量冲高回落时降低仓位假设",
                "supporting_quote": "高位后排放量冲高回落时必须降低仓位假设",
            },
            {
                "field": "opportunity_preferences",
                "value": "核心股缩量回踩关键均线且题材仍有新高扩散",
                "supporting_quote": "编造的引文，原文里没有这句话",
            },
            {
                "field": "market_lenses",
                "value": "非法字段应被丢弃",
                "supporting_quote": "先定市场阶段",
            },
        ],
    }


def _fake_llm(payload: dict | None = None, content: str | None = None):
    body = content if content is not None else json.dumps(
        payload if payload is not None else _fake_llm_payload(), ensure_ascii=False
    )

    def call(messages: list[dict]) -> tuple[str | None, str, str, str]:
        call.last_messages = messages  # type: ignore[attr-defined]
        return body, "fake", "fake-model", ""

    return call


def _setup_with_article(tmp: str) -> tuple[userspace.UserSpace, str]:
    us = _us(tmp)
    perspective_lab.init_perspective(us, "blogger_x", display_name="某博主", ptype="blogger")
    art = Path(tmp) / "a.md"
    art.write_text(ARTICLE_TEXT, encoding="utf-8")
    res = perspective_lab.ingest_article(us, "blogger_x", art, title="复盘", date="2026-08-13")
    return us, res["article_id"]


class ExtractCardTests(unittest.TestCase):
    def test_extract_writes_card_and_verifies_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us, article_id = _setup_with_article(tmp)
            summary = perspective_learning.extract_cards(
                us, "blogger_x", llm_complete=_fake_llm()
            )
            self.assertEqual(summary["extracted"], [article_id])
            card = json.loads(
                perspective_learning.card_path(us, "blogger_x", article_id).read_text(encoding="utf-8")
            )
            self.assertEqual(card["schema_version"], 1)
            self.assertEqual(card["claims"][0]["claim_type"], "market_phase")
            updates = {u["value"]: u for u in card["profile_updates"]}
            # 逐字命中的引文核验通过；编造引文核验不过但保留存档
            self.assertTrue(updates["高位后排放量冲高回落时降低仓位假设"]["quote_verified"])
            self.assertFalse(
                updates["核心股缩量回踩关键均线且题材仍有新高扩散"]["quote_verified"]
            )
            # 非白名单字段（market_lenses）整条丢弃
            self.assertNotIn("非法字段应被丢弃", updates)
            self.assertTrue(any("非白名单" in i for i in card["validation_issues"]))

    def test_extract_skips_existing_unless_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us, article_id = _setup_with_article(tmp)
            perspective_learning.extract_cards(us, "blogger_x", llm_complete=_fake_llm())
            again = perspective_learning.extract_cards(us, "blogger_x", llm_complete=_fake_llm())
            self.assertEqual(again["skipped_existing"], [article_id])
            self.assertEqual(again["extracted"], [])
            forced = perspective_learning.extract_cards(
                us, "blogger_x", force=True, llm_complete=_fake_llm()
            )
            self.assertEqual(forced["extracted"], [article_id])

    def test_llm_failure_writes_nothing(self) -> None:
        def broken(messages: list[dict]) -> tuple[str | None, str, str, str]:
            return None, "", "", "未配置 LLM key"

        with tempfile.TemporaryDirectory() as tmp:
            us, article_id = _setup_with_article(tmp)
            summary = perspective_learning.extract_cards(us, "blogger_x", llm_complete=broken)
            self.assertEqual(summary["extracted"], [])
            self.assertIn("未配置 LLM key", summary["failed"][0]["reason"])
            self.assertFalse(perspective_learning.card_path(us, "blogger_x", article_id).exists())

    def test_unparseable_output_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us, article_id = _setup_with_article(tmp)
            summary = perspective_learning.extract_cards(
                us, "blogger_x", llm_complete=_fake_llm(content="抱歉，我无法输出 JSON")
            )
            self.assertIn("无法解析", summary["failed"][0]["reason"])
            self.assertFalse(perspective_learning.card_path(us, "blogger_x", article_id).exists())

    def test_short_quote_not_verified(self) -> None:
        """超短引文（如「复盘」）在任何文章里都能命中，不构成出处 → 不进确认流。"""
        payload = _fake_llm_payload()
        payload["profile_updates"] = [
            {
                "field": "risk_triggers",
                "value": "短引文不该通过核验",
                # 「今天复盘」确实是原文逐字片段，但归一后仅 4 字 < MIN_QUOTE_CHARS
                "supporting_quote": "今天复盘",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            us, article_id = _setup_with_article(tmp)
            perspective_learning.extract_cards(
                us, "blogger_x", llm_complete=_fake_llm(payload=payload)
            )
            card = json.loads(
                perspective_learning.card_path(us, "blogger_x", article_id).read_text(encoding="utf-8")
            )
            self.assertFalse(card["profile_updates"][0]["quote_verified"])
            self.assertTrue(any("过短" in i for i in card["validation_issues"]))
            # 核验不过 → propose 阶段不产生 patch
            summary = perspective_learning.propose_patches(us, "blogger_x")
            self.assertEqual(summary["created"], [])

    def test_all_empty_payload_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us, _ = _setup_with_article(tmp)
            summary = perspective_learning.extract_cards(
                us,
                "blogger_x",
                llm_complete=_fake_llm(
                    payload={"claims": [], "reasoning_moves": [], "risk_notes": [], "profile_updates": []}
                ),
            )
            self.assertIn("全空", summary["failed"][0]["reason"])

    def test_truncation_declared_before_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "blogger_x", ptype="blogger")
            art = Path(tmp) / "long.md"
            art.write_text("行" * (perspective_learning.MAX_ARTICLE_PROMPT_CHARS + 100), encoding="utf-8")
            perspective_lab.ingest_article(us, "blogger_x", art, title="长文", date="2026-08-13")
            fake = _fake_llm(
                payload={
                    "claims": [{"claim": "x", "claim_type": "method"}],
                    "reasoning_moves": [],
                    "risk_notes": [],
                    "profile_updates": [],
                }
            )
            perspective_learning.extract_cards(us, "blogger_x", llm_complete=fake)
            user_prompt = fake.last_messages[1]["content"]  # type: ignore[attr-defined]
            self.assertIn("已截断", user_prompt)
            self.assertLess(user_prompt.index("已截断"), user_prompt.index("行行行"))


class ProposePatchTests(unittest.TestCase):
    def test_propose_groups_verified_updates_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us, _ = _setup_with_article(tmp)
            perspective_learning.extract_cards(us, "blogger_x", llm_complete=_fake_llm())
            summary = perspective_learning.propose_patches(us, "blogger_x")
            # 只有 quote_verified 的那条成为 patch；核验不过的不进入确认流
            self.assertEqual(len(summary["created"]), 1)
            patches = perspective_learning.list_patches(us, "blogger_x", status="pending")
            self.assertEqual(patches[0]["field"], "risk_triggers")
            self.assertEqual(patches[0]["supporting_article_count"], 1)
            self.assertIn("高位后排放量冲高回落", patches[0]["evidence"][0]["quote"])

    def test_propose_idempotent_and_skips_profile_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us, _ = _setup_with_article(tmp)
            perspective_learning.extract_cards(us, "blogger_x", llm_complete=_fake_llm())
            first = perspective_learning.propose_patches(us, "blogger_x")
            second = perspective_learning.propose_patches(us, "blogger_x")
            self.assertEqual(second["created"], [])
            self.assertEqual(second["skipped_existing_patch"], first["created"])
            # 画像已有同值 → 跳过
            profile = perspective_lab.load_profile(us, "blogger_x")
            profile["risk_triggers"].append("高位后排放量冲高回落时降低仓位假设")
            perspective_lab._save_profile(us, profile)
            for pid in first["created"]:
                perspective_learning.patch_path(us, "blogger_x", pid).unlink()
            third = perspective_learning.propose_patches(us, "blogger_x")
            self.assertEqual(third["created"], [])
            self.assertTrue(third["skipped_already_in_profile"])

    def test_rejected_patch_not_revived(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us, _ = _setup_with_article(tmp)
            perspective_learning.extract_cards(us, "blogger_x", llm_complete=_fake_llm())
            created = perspective_learning.propose_patches(us, "blogger_x")["created"]
            perspective_learning.review_patch(us, "blogger_x", created[0], approve=False)
            again = perspective_learning.propose_patches(us, "blogger_x")
            self.assertEqual(again["created"], [])
            patches = perspective_learning.list_patches(us, "blogger_x", status="rejected")
            self.assertEqual([p["patch_id"] for p in patches], created)


class ReviewPatchTests(unittest.TestCase):
    def _pending_patch(self, tmp: str) -> tuple[userspace.UserSpace, str]:
        us, _ = _setup_with_article(tmp)
        perspective_learning.extract_cards(us, "blogger_x", llm_complete=_fake_llm())
        created = perspective_learning.propose_patches(us, "blogger_x")["created"]
        return us, created[0]

    def test_approve_writes_profile_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us, patch_id = self._pending_patch(tmp)
            patch = perspective_learning.review_patch(
                us, "blogger_x", patch_id, approve=True, note="确认"
            )
            self.assertEqual(patch["status"], "approved")
            self.assertTrue(patch["applied"])
            profile = perspective_lab.load_profile(us, "blogger_x")
            self.assertIn("高位后排放量冲高回落时降低仓位假设", profile["risk_triggers"])
            history = profile["patch_history"]
            self.assertEqual(history[0]["patch_id"], patch_id)
            self.assertEqual(history[0]["action"], "approved")

    def test_reject_leaves_profile_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us, patch_id = self._pending_patch(tmp)
            patch = perspective_learning.review_patch(us, "blogger_x", patch_id, approve=False)
            self.assertEqual(patch["status"], "rejected")
            profile = perspective_lab.load_profile(us, "blogger_x")
            self.assertNotIn("高位后排放量冲高回落时降低仓位假设", profile.get("risk_triggers") or [])
            self.assertNotIn("patch_history", profile)

    def test_double_review_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us, patch_id = self._pending_patch(tmp)
            perspective_learning.review_patch(us, "blogger_x", patch_id, approve=True)
            with self.assertRaisesRegex(ValueError, "不可重复评审"):
                perspective_learning.review_patch(us, "blogger_x", patch_id, approve=False)

    def test_missing_patch_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us, _ = _setup_with_article(tmp)
            with self.assertRaises(FileNotFoundError):
                perspective_learning.review_patch(
                    us, "blogger_x", "pp-000000000000", approve=True
                )

    def test_bad_ids_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us, _ = _setup_with_article(tmp)
            with self.assertRaises(ValueError):
                perspective_learning.patch_path(us, "blogger_x", "../escape")
            with self.assertRaises(ValueError):
                perspective_learning.card_path(us, "blogger_x", "../escape")


class CliParseabilityTests(unittest.TestCase):
    def test_learning_subcommands_parse(self) -> None:
        parser = cli.build_parser()
        for argv in (
            ["perspective", "extract-cards", "--perspective", "blogger_x"],
            ["perspective", "extract-cards", "--perspective", "blogger_x", "--article-id", "pa-0", "--limit", "3", "--force"],
            ["perspective", "propose-patches", "--perspective", "blogger_x"],
            ["perspective", "patches", "--perspective", "blogger_x", "--status", "pending"],
            ["perspective", "review-patch", "--perspective", "blogger_x", "--patch-id", "pp-1", "--approve"],
            ["perspective", "review-patch", "--perspective", "blogger_x", "--patch-id", "pp-1", "--reject", "--note", "n"],
        ):
            parser.parse_args(argv)

    def test_review_requires_exactly_one_decision(self) -> None:
        parser = cli.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                ["perspective", "review-patch", "--perspective", "x", "--patch-id", "pp-1"]
            )
        with self.assertRaises(SystemExit):
            parser.parse_args(
                ["perspective", "review-patch", "--perspective", "x", "--patch-id", "pp-1", "--approve", "--reject"]
            )


if __name__ == "__main__":
    unittest.main()
