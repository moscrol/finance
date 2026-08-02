from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from intelligence import userspace
from intelligence.services import interactions, judgments, subconscious

NOW = datetime(2026, 6, 18, 15, 30, tzinfo=timezone.utc)


class SessionIdTests(unittest.TestCase):
    def test_default_session_id_format(self) -> None:
        self.assertEqual(subconscious.default_session_id(NOW), "2026-06-18-1530")

    def test_safe_session_id_rejects_traversal(self) -> None:
        for bad in ["..", ".", "a/b", "a\\b", "  ", "-leading", "_leading", "x" * 82]:
            with self.assertRaises(ValueError):
                subconscious._safe_session_id(bad)

    def test_safe_session_id_accepts_valid(self) -> None:
        for ok in ["2026-06-18-1530", "abc", "a.b_c-1", "A1"]:
            self.assertEqual(subconscious._safe_session_id(ok), ok)


class StartAndBufferTests(unittest.TestCase):
    def _us(self, tmp: str, user: str = "tester") -> userspace.UserSpace:
        return userspace.user_space(user)

    def test_start_writes_active_and_buffer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = self._us(tmp)
                us.ensure_dir()
                state = subconscious.start_session(us, vault="/some/vault", now=NOW)
                self.assertEqual(state["session_id"], "2026-06-18-1530")
                self.assertEqual(state["vault"], "/some/vault")
                self.assertTrue(subconscious._buffer_path(us, state["session_id"]).exists())
                active = subconscious.load_active(us)
                self.assertIsNotNone(active)
                self.assertEqual(active["session_id"], "2026-06-18-1530")

    def test_append_resolves_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = self._us(tmp)
                us.ensure_dir()
                subconscious.start_session(us, now=NOW)
                subconscious.append_signal(us, kind="click", themes=["液冷"], stocks=["中际旭创"])
                buf = subconscious.load_buffer(us, "2026-06-18-1530")
                self.assertEqual(len(buf), 1)
                self.assertEqual(buf[0]["kind"], "click")
                self.assertEqual(buf[0]["themes"], ["液冷"])
                self.assertEqual(buf[0]["stocks"], ["中际旭创"])

    def test_append_stores_memo_and_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = self._us(tmp)
                us.ensure_dir()
                subconscious.start_session(us, now=NOW)
                subconscious.append_signal(
                    us, kind="click", themes=["液冷"],
                    question="液冷会否结构性错配", memo="**核心判断**：二次侧卡脖子",
                )
                buf = subconscious.load_buffer(us, "2026-06-18-1530")
                self.assertEqual(buf[0]["question"], "液冷会否结构性错配")
                self.assertEqual(buf[0]["memo"], "**核心判断**：二次侧卡脖子")

    def test_append_without_session_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = self._us(tmp)
                us.ensure_dir()
                with self.assertRaises(ValueError):
                    subconscious.append_signal(us, kind="click", themes=["液冷"])


class ConsolidateTests(unittest.TestCase):
    def _buffer(self) -> list[dict]:
        return [
            {"kind": "click", "themes": ["液冷"], "stocks": ["中际旭创"],
             "question": "液冷渗透率拐点对中际旭创毛利率意味着什么", "quote": "想深挖液冷"},
            {"kind": "click", "themes": ["液冷"], "stocks": []},  # 同 (液冷, click) -> 去重计数
            {"kind": "dismiss", "themes": ["钠电"], "stocks": []},
            {"kind": "click", "themes": ["液冷"], "stocks": [],
             "question": "液冷渗透率拐点对中际旭创毛利率意味着什么"},  # 重复问题 -> 去重
        ]

    def test_dedup_count_and_weights(self) -> None:
        prop = subconscious.consolidate(self._buffer(), user_id="tester", session_id="2026-06-18-1530", now=NOW)
        rows = {(r.target, r.label): r for r in prop.rows}
        self.assertEqual(rows[("theme", "液冷")].kind, "click")
        self.assertEqual(rows[("theme", "液冷")].weight, 1.0)
        self.assertEqual(rows[("theme", "液冷")].count, 3)  # 三条 click 命中液冷
        self.assertEqual(rows[("stock", "中际旭创")].weight, 1.0)
        self.assertEqual(rows[("theme", "钠电")].weight, -1.0)
        self.assertEqual(rows[("theme", "钠电")].kind, "dismiss")
        # 问题去重
        self.assertEqual(prop.questions, ["液冷渗透率拐点对中际旭创毛利率意味着什么"])
        # 引用样本保留
        self.assertEqual(rows[("theme", "液冷")].sample_quote, "想深挖液冷")

    def test_positive_sorted_before_negative(self) -> None:
        prop = subconscious.consolidate(self._buffer(), user_id="tester", session_id="2026-06-18-1530", now=NOW)
        weights = [r.weight for r in prop.rows]
        self.assertEqual(weights, sorted(weights, reverse=True))
        self.assertEqual(prop.rows[-1].label, "钠电")  # 唯一负向排最后

    def test_explicit_weight_and_rating(self) -> None:
        buf = [
            {"kind": "rate", "themes": ["算力"], "stocks": [], "rating": 5},
            {"kind": "click", "themes": ["PCB"], "stocks": [], "weight": 0.42},
        ]
        prop = subconscious.consolidate(buf, user_id="t", session_id="2026-06-18-1530", now=NOW)
        rows = {(r.target, r.label): r for r in prop.rows}
        self.assertEqual(rows[("theme", "算力")].weight, 1.5)  # (5-3)/2*1.5
        self.assertEqual(rows[("theme", "PCB")].weight, 0.42)

    def test_memos_collected_and_deduped(self) -> None:
        buf = [
            {"kind": "ask", "themes": ["液冷"], "question": "Q1"},
            {"kind": "click", "themes": ["液冷"], "memo": "**核心判断**：二次侧卡脖子"},
            {"kind": "click", "themes": ["液冷"], "memo": "**核心判断**：二次侧卡脖子"},  # 同纪要 -> 去重
            {"kind": "click", "themes": ["铜箔"], "memo": "**核心判断**：产能爬坡滞后"},
        ]
        prop = subconscious.consolidate(buf, user_id="t", session_id="2026-06-18-1530", now=NOW)
        self.assertEqual(prop.memos, ["**核心判断**：二次侧卡脖子", "**核心判断**：产能爬坡滞后"])
        self.assertEqual(prop.questions, ["Q1"])

    def test_judgment_items_carry_themes_and_stocks(self) -> None:
        buf = [
            {"kind": "click", "themes": ["铜箔"], "stocks": ["铜冠铜箔"], "memo": "产能爬坡滞后"},
            {"kind": "click", "themes": ["液冷"], "memo": ""},  # 无 memo -> 不成判断
        ]
        prop = subconscious.consolidate(buf, user_id="t", session_id="2026-06-18-1530", now=NOW)
        self.assertEqual(len(prop.judgments), 1)
        self.assertEqual(prop.judgments[0]["memo"], "产能爬坡滞后")
        self.assertEqual(prop.judgments[0]["themes"], ["铜箔"])
        self.assertEqual(prop.judgments[0]["stocks"], ["铜冠铜箔"])

    def test_empty_buffer_yields_no_rows(self) -> None:
        prop = subconscious.consolidate([], user_id="t", session_id="2026-06-18-1530", now=NOW)
        self.assertEqual(prop.rows, [])
        self.assertEqual(prop.judgments, [])
        self.assertIn("（本轮无信号）", prop.markdown)


class MarkdownTests(unittest.TestCase):
    def test_frontmatter_and_backlinks(self) -> None:
        buf = [{"kind": "click", "themes": ["液冷"], "stocks": ["中际旭创"], "question": "Q1"}]
        prop = subconscious.consolidate(buf, user_id="tester", session_id="2026-06-18-1530", now=NOW)
        md = prop.markdown
        self.assertIn("mode: subconscious", md)
        self.assertIn("user: tester", md)
        self.assertIn("session: 2026-06-18-1530", md)
        self.assertIn("# 潜意识对话 2026-06-18", md)
        self.assertIn("[[液冷]]", md)
        self.assertIn("[[中际旭创]]", md)
        self.assertIn("1. Q1", md)

    def test_memo_section_rendered(self) -> None:
        buf = [
            {"kind": "ask", "themes": ["液冷"], "question": "液冷会否错配"},
            {"kind": "click", "themes": ["液冷"], "memo": "**核心判断**：二次侧卡脖子\n**可证伪点**：UL认证8月底"},
        ]
        prop = subconscious.consolidate(buf, user_id="tester", session_id="2026-06-18-1530", now=NOW)
        md = prop.markdown
        self.assertIn("## 它问我的（foresight）", md)
        self.assertIn("## 深挖纪要", md)
        self.assertIn("**核心判断**：二次侧卡脖子", md)
        self.assertIn("**可证伪点**：UL认证8月底", md)
        self.assertIn("## 这轮沉淀的信号", md)
        # 顺序：它问我的 → 深挖纪要 → 这轮沉淀的信号
        self.assertLess(md.index("它问我的"), md.index("深挖纪要"))
        self.assertLess(md.index("深挖纪要"), md.index("这轮沉淀的信号"))

    def test_no_memo_section_when_empty(self) -> None:
        buf = [{"kind": "click", "themes": ["液冷"]}]
        prop = subconscious.consolidate(buf, user_id="tester", session_id="2026-06-18-1530", now=NOW)
        self.assertNotIn("## 深挖纪要", prop.markdown)


class ResolveVaultTests(unittest.TestCase):
    def test_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = userspace.user_space("tester")
                us.ensure_dir()
                # 1) explicit 优先
                path, fb = subconscious.resolve_vault(us, explicit="/explicit")
                self.assertEqual(path, Path("/explicit"))
                self.assertFalse(fb)
                # 2) active.json 次之
                subconscious.start_session(us, vault="/from-active", now=NOW)
                path, fb = subconscious.resolve_vault(us)
                self.assertEqual(path, Path("/from-active"))
                # 3) env 再次
                subconscious.start_session(us, now=NOW)  # active 无 vault
                with mock.patch.dict(os.environ, {subconscious.ENV_VAULT: "/from-env"}):
                    path, fb = subconscious.resolve_vault(us)
                self.assertEqual(path, Path("/from-env"))
                self.assertFalse(fb)
                # 4) 回退：HOME 下没有 agent-memory 时才落 users/<id>/_vault。
                with mock.patch.dict(os.environ, {"HOME": tmp}, clear=False):
                    os.environ.pop(subconscious.ENV_VAULT, None)
                    os.environ.pop(subconscious.ENV_AGENT_MEMORY_VAULT, None)
                    path, fb = subconscious.resolve_vault(us)
                self.assertTrue(fb)
                self.assertEqual(path, us.root / "_vault")

    def test_default_uses_agent_memory_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            vault = home / "agent-memory"
            vault.mkdir(parents=True)
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp) / "users"):
                us = userspace.user_space("tester")
                us.ensure_dir()
                with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False):
                    os.environ.pop(subconscious.ENV_VAULT, None)
                    os.environ.pop(subconscious.ENV_AGENT_MEMORY_VAULT, None)
                    path, fb = subconscious.resolve_vault(us)

        self.assertEqual(path, vault)
        self.assertFalse(fb)


class CommitAndArchiveTests(unittest.TestCase):
    def test_commit_writes_both_layers_then_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = userspace.user_space("tester")
                us.ensure_dir()
                vault = Path(tmp) / "vault"
                subconscious.start_session(us, vault=str(vault), now=NOW)
                subconscious.append_signal(us, kind="click", themes=["液冷"], stocks=["中际旭创"])
                subconscious.append_signal(us, kind="dismiss", themes=["钠电"])
                buf = subconscious.load_buffer(us, "2026-06-18-1530")
                prop = subconscious.consolidate(buf, user_id=us.user_id, session_id="2026-06-18-1530", now=NOW)

                result = subconscious.commit(us, prop, vault=str(vault), now=NOW)
                # 机器层
                self.assertEqual(result.written_records, len(prop.rows))
                records, _ = interactions.load_interactions(us.interactions_path)
                kinds = {r["kind"] for r in records}
                self.assertEqual(kinds, {"click", "dismiss"})
                for r in records:
                    self.assertEqual(r["note"], "subconscious#2026-06-18-1530")
                # 人类层
                self.assertTrue(result.note_path.exists())
                self.assertEqual(result.note_path, vault / subconscious.VAULT_SUBDIR / "2026-06-18-1530.md")
                self.assertIn("[[液冷]]", result.note_path.read_text(encoding="utf-8"))
                self.assertFalse(result.vault_is_fallback)

                # 亲和度闭环：commit 后 interactions 能算出液冷为正、钠电为负
                aff = {a.label: a.score for a in interactions.compute_affinity(records, now=NOW)}
                self.assertGreater(aff["液冷"], 0)
                self.assertLess(aff["钠电"], 0)

                # 归档：buffer 改名 + active 清除
                subconscious.archive_session(us, "2026-06-18-1530")
                self.assertFalse(subconscious._buffer_path(us, "2026-06-18-1530").exists())
                self.assertTrue((subconscious._state_dir(us) / "2026-06-18-1530.buffer.done.jsonl").exists())
                self.assertIsNone(subconscious.load_active(us))

    def test_commit_persists_judgments_to_machine_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = userspace.user_space("tester")
                us.ensure_dir()
                vault = Path(tmp) / "vault"
                subconscious.start_session(us, vault=str(vault), now=NOW)
                subconscious.append_signal(
                    us, kind="click", themes=["铜箔"], stocks=["铜冠铜箔"],
                    memo="**核心判断**：HVLP铜箔产能爬坡滞后",
                )
                buf = subconscious.load_buffer(us, "2026-06-18-1530")
                prop = subconscious.consolidate(buf, user_id=us.user_id, session_id="2026-06-18-1530", now=NOW)
                result = subconscious.commit(us, prop, vault=str(vault), now=NOW)

                self.assertEqual(result.judgments_written, 1)
                self.assertEqual(result.judgments_path, us.judgments_path)
                recs, _ = judgments.load_judgments(us.judgments_path)
                self.assertEqual(len(recs), 1)
                self.assertEqual(recs[0]["memo"], "**核心判断**：HVLP铜箔产能爬坡滞后")
                self.assertEqual(recs[0]["themes"], ["铜箔"])
                self.assertEqual(recs[0]["stocks"], ["铜冠铜箔"])
                self.assertEqual(recs[0]["session_id"], "2026-06-18-1530")

    def test_commit_without_memos_writes_no_judgments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = userspace.user_space("tester")
                us.ensure_dir()
                vault = Path(tmp) / "vault"
                buf = [{"kind": "click", "themes": ["液冷"]}]
                prop = subconscious.consolidate(buf, user_id=us.user_id, session_id="s1", now=NOW)
                result = subconscious.commit(us, prop, vault=str(vault), now=NOW)
                self.assertEqual(result.judgments_written, 0)
                self.assertIsNone(result.judgments_path)
                self.assertFalse(us.judgments_path.exists())

    def test_commit_weight_matches_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = userspace.user_space("tester")
                us.ensure_dir()
                vault = Path(tmp) / "vault"
                buf = [{"kind": "rate", "themes": ["算力"], "rating": 5}]
                prop = subconscious.consolidate(buf, user_id=us.user_id, session_id="s1", now=NOW)
                subconscious.commit(us, prop, vault=str(vault), now=NOW)
                records, _ = interactions.load_interactions(us.interactions_path)
                self.assertEqual(records[0]["weight"], 1.5)
                self.assertEqual(records[0]["themes"], ["算力"])


if __name__ == "__main__":
    unittest.main()
