"""dream-mine（Workbench 会话夜间挖掘）测试。

覆盖设计稿（docs/superpowers/specs/2026-08-26-dream-loop-repoint-design.md）的判别变量：
- 提案带 conv 溯源、引句已脱敏；
- suggest-only：无人工 commit 时 judgments/interactions 字节不动（这里断言：根本不创建）；
- 幂等：同窗口重跑不新增 buffer 行、vault md 字节一致；
- 无 LLM key 降级：提案 0、水位不推进、降级标记可见。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest import mock

from intelligence import userspace
from intelligence.dream import collector, miner
from intelligence.services import subconscious

TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 8, 26, 4, 5, tzinfo=TZ)
RECENT_TS = "2026-08-25T22:00:00+08:00"
OLD_TS = "2026-07-01T10:00:00+08:00"


def _write_conversation(
    root: Path,
    cid: str,
    updated_at: str,
    messages: List[Dict[str, Any]],
    *,
    broken_meta: bool = False,
) -> None:
    conv_dir = root / cid
    conv_dir.mkdir(parents=True, exist_ok=True)
    meta_path = conv_dir / "conversation.json"
    if broken_meta:
        meta_path.write_text("{not json", encoding="utf-8")
    else:
        meta_path.write_text(
            json.dumps(
                {
                    "conversation_id": cid,
                    "user_id": "tester",
                    "created_at": updated_at,
                    "updated_at": updated_at,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    lines = [json.dumps(m, ensure_ascii=False) for m in messages]
    (conv_dir / "messages.jsonl").write_text(
        "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
    )


def _msg(
    cid: str,
    role: str,
    content: str,
    *,
    status: str = "completed",
    ts: str = RECENT_TS,
) -> Dict[str, Any]:
    return {
        "message_id": f"msg-{role}-{abs(hash(content)) % 10_000}",
        "conversation_id": cid,
        "role": role,
        "content": content,
        "created_at": ts,
        "status": status,
    }


def _fake_llm(payload: Dict[str, Any]):
    calls: List[List[Dict[str, str]]] = []

    def complete(
        messages: List[Dict[str, str]], **_kwargs: Any
    ) -> Tuple[Optional[str], Any, str]:
        calls.append(messages)
        return json.dumps(payload, ensure_ascii=False), None, ""

    return complete, calls


def _degraded_llm(reason: str = "未配置 LLM key。"):
    def complete(
        _messages: List[Dict[str, str]], **_kwargs: Any
    ) -> Tuple[Optional[str], Any, str]:
        return None, None, reason

    return complete


class NormalizeWorkbenchTests(unittest.TestCase):
    def test_user_message_maps_to_record(self) -> None:
        recs = collector.normalize_workbench_message(
            _msg("conv_a", "user", "液冷板块怎么看")
        )
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(
            (rec.source, rec.session_id, rec.role, rec.text),
            ("workbench", "conv_a", "user", "液冷板块怎么看"),
        )
        self.assertEqual(rec.ts, RECENT_TS)

    def test_pending_or_empty_rows_skipped(self) -> None:
        self.assertEqual(
            collector.normalize_workbench_message(
                _msg("conv_a", "assistant", "", status="pending")
            ),
            [],
        )
        self.assertEqual(
            collector.normalize_workbench_message(
                _msg("conv_a", "assistant", "半截流式文本", status="pending")
            ),
            [],
        )
        self.assertEqual(
            collector.normalize_workbench_message(_msg("conv_a", "user", "")),
            [],
        )


class ReadWorkbenchConversationsTests(unittest.TestCase):
    def test_window_filters_by_updated_at_and_skips_broken_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "conversations"
            _write_conversation(root, "conv_new", RECENT_TS, [_msg("conv_new", "user", "新会话")])
            _write_conversation(root, "conv_old", OLD_TS, [_msg("conv_old", "user", "旧会话", ts=OLD_TS)])
            _write_conversation(root, "conv_bad", RECENT_TS, [_msg("conv_bad", "user", "坏元数据")], broken_meta=True)
            events = collector.read_workbench_conversations(
                str(root), since_days=7, now=NOW
            )
            cids = {str(e.get("conversation_id")) for e in events}
            self.assertEqual(cids, {"conv_new"})

    def test_no_window_returns_all_parsable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "conversations"
            _write_conversation(root, "conv_new", RECENT_TS, [_msg("conv_new", "user", "新")])
            _write_conversation(root, "conv_old", OLD_TS, [_msg("conv_old", "user", "旧", ts=OLD_TS)])
            events = collector.read_workbench_conversations(str(root), since_days=None)
            cids = {str(e.get("conversation_id")) for e in events}
            self.assertEqual(cids, {"conv_new", "conv_old"})


class CollectWorkbenchTests(unittest.TestCase):
    def test_collect_redacts_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "conversations"
            store = Path(tmp) / "store"
            _write_conversation(
                root,
                "conv_a",
                RECENT_TS,
                [_msg("conv_a", "user", "我手机 13912345678，液冷怎么看")],
            )
            options = collector.CollectOptions(
                store_dir=str(store),
                source="workbench",
                conversations_dir=str(root),
                since_days=None,
            )
            summary = collector.run_collect(options)
            self.assertEqual(summary["records_written"], 1)
            files = collector.session_store_files(store, "workbench", "conv_a")
            self.assertEqual(len(files), 1)
            first_bytes = files[0].read_bytes()
            self.assertIn(b"[REDACTED:phone_cn]", first_bytes)
            self.assertNotIn(b"13912345678", first_bytes)
            collector.run_collect(options)
            self.assertEqual(files[0].read_bytes(), first_bytes)


_JUDGMENT_PAYLOAD = {
    "signals": [
        {
            "kind": "judgment",
            "memo": "液冷进入分歧期，回调才看",
            "themes": ["液冷"],
            "stocks": [],
            "quote": "我觉得液冷该出分歧了",
            "confidence": 0.8,
        },
        {
            "kind": "ask",
            "question": "算力回调后怎么接回来",
            "themes": ["算力"],
            "confidence": 0.6,
        },
    ]
}


class RunMineTests(unittest.TestCase):
    def _mine(
        self,
        tmp: str,
        llm_complete,
        *,
        conversations: Optional[List[Tuple[str, str, List[Dict[str, Any]]]]] = None,
        **option_overrides: Any,
    ) -> Dict[str, Any]:
        root = Path(tmp) / "conversations"
        if conversations is None:
            conversations = [
                (
                    "conv_a",
                    RECENT_TS,
                    [
                        _msg("conv_a", "user", "我觉得液冷该出分歧了"),
                        _msg("conv_a", "assistant", "从盘面看确实有分歧迹象" * 10),
                    ],
                )
            ]
        for cid, updated, msgs in conversations:
            _write_conversation(root, cid, updated, msgs)
        options = miner.MineOptions(
            conversations_dir=str(root),
            store_dir=str(Path(tmp) / "store"),
            user="tester",
            vault=str(Path(tmp) / "vault"),
            **option_overrides,
        )
        return miner.run_mine(options, llm_complete=llm_complete, now=NOW)

    def test_mine_appends_proposals_suggest_only_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp) / "users"):
                complete, calls = _fake_llm(_JUDGMENT_PAYLOAD)
                summary = self._mine(tmp, complete)
                us = userspace.user_space("tester")

                self.assertEqual(summary["signals_appended"], 2)
                self.assertEqual(summary["session_id"], "dream-2026-08-26")
                buffer = subconscious.load_buffer(us, "dream-2026-08-26")
                self.assertEqual(len(buffer), 2)
                notes = {str(rec.get("note")) for rec in buffer}
                self.assertIn("dream-mine conv:conv_a", notes)

                # suggest-only：台账文件根本不该被创建。
                self.assertFalse(us.judgments_path.exists())
                self.assertFalse(us.interactions_path.exists())

                # vault 人读 md：溯源 + 复核命令可见。
                note_path = Path(summary["vault_note"])
                self.assertTrue(note_path.exists())
                md_bytes = note_path.read_bytes()
                md_text = md_bytes.decode("utf-8")
                self.assertIn("conv_a", md_text)
                self.assertIn("液冷进入分歧期", md_text)
                self.assertIn("subconscious commit --session dream-2026-08-26", md_text)

                # 水位：mining manifest 记了 (cid, updated_at)。
                manifest = miner._read_mining_manifest(Path(tmp) / "store")
                self.assertEqual(manifest["conv_a"]["updated_at"], RECENT_TS)
                self.assertEqual(manifest["conv_a"]["signals"], 2)

                # 幂等重跑：水位一致 → 不再调 LLM、buffer 不增行、md 字节一致。
                n_calls = len(calls)
                summary2 = self._mine(tmp, complete)
                self.assertEqual(len(calls), n_calls)
                self.assertEqual(summary2["sessions_selected"], 0)
                self.assertEqual(summary2["signals_appended"], 0)
                self.assertEqual(
                    len(subconscious.load_buffer(us, "dream-2026-08-26")), 2
                )
                self.assertEqual(note_path.read_bytes(), md_bytes)

    def test_degrade_without_key_keeps_watermark_and_marks_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp) / "users"):
                summary = self._mine(tmp, _degraded_llm("未配置 LLM key。"))
                us = userspace.user_space("tester")

                self.assertEqual(summary["signals_appended"], 0)
                self.assertIn("未配置 LLM key", str(summary["degraded_reason"]))
                # 降级不推进水位：manifest 不存在，下晚重试。
                self.assertEqual(miner._read_mining_manifest(Path(tmp) / "store"), {})
                self.assertEqual(subconscious.load_buffer(us, "dream-2026-08-26"), [])
                md_text = Path(summary["vault_note"]).read_text(encoding="utf-8")
                self.assertIn("降级", md_text)
                self.assertIn("未配置 LLM key", md_text)

    def test_max_signals_cap(self) -> None:
        payload = {
            "signals": [
                {
                    "kind": "judgment",
                    "memo": f"判断{i}",
                    "themes": [f"题材{i}"],
                    "confidence": 0.9 - i * 0.1,
                }
                for i in range(3)
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp) / "users"):
                complete, _calls = _fake_llm(payload)
                summary = self._mine(tmp, complete, max_signals=2)
                us = userspace.user_space("tester")
                self.assertEqual(summary["signals_appended"], 2)
                buffer = subconscious.load_buffer(us, "dream-2026-08-26")
                memos = [rec.get("memo") for rec in buffer]
                # 按 confidence 降序截断，留置信度最高的两条。
                self.assertEqual(memos, ["判断0", "判断1"])

    def test_assistant_only_conversation_skipped_without_llm_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp) / "users"):
                complete, calls = _fake_llm(_JUDGMENT_PAYLOAD)
                summary = self._mine(
                    tmp,
                    complete,
                    conversations=[
                        (
                            "conv_bot",
                            RECENT_TS,
                            [_msg("conv_bot", "assistant", "纯助手输出的会话")],
                        )
                    ],
                )
                self.assertEqual(len(calls), 0)
                self.assertEqual(summary["signals_appended"], 0)
                manifest = miner._read_mining_manifest(Path(tmp) / "store")
                self.assertEqual(manifest["conv_bot"]["reason"], "no-user-text")

    def test_dry_run_writes_nothing_but_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp) / "users"):
                complete, _calls = _fake_llm(_JUDGMENT_PAYLOAD)
                summary = self._mine(tmp, complete, dry_run=True)
                us = userspace.user_space("tester")
                self.assertEqual(summary["signals_appended"], 2)
                self.assertTrue(summary["dry_run"])
                self.assertIsNone(summary["vault_note"])
                self.assertEqual(subconscious.load_buffer(us, "dream-2026-08-26"), [])
                self.assertEqual(miner._read_mining_manifest(Path(tmp) / "store"), {})
                self.assertFalse((Path(tmp) / "vault").exists())
                # store（采集半）照常写入：采集本身幂等且无提案副作用。
                self.assertTrue(
                    collector.session_store_files(Path(tmp) / "store", "workbench", "conv_a")
                )

    def test_quote_redaction_survives_into_proposal(self) -> None:
        payload = {
            "signals": [
                {
                    "kind": "judgment",
                    "memo": "记住这个判断",
                    "themes": ["液冷"],
                    "quote": "我手机 [REDACTED:phone_cn]，液冷怎么看",
                    "confidence": 0.7,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp) / "users"):
                complete, calls = _fake_llm(payload)
                summary = self._mine(
                    tmp,
                    complete,
                    conversations=[
                        (
                            "conv_a",
                            RECENT_TS,
                            [_msg("conv_a", "user", "我手机 13912345678，液冷怎么看")],
                        )
                    ],
                )
                # 送 LLM 的 prompt 来自已脱敏 store，原始号码不可见。
                prompt_text = json.dumps(calls[0], ensure_ascii=False)
                self.assertNotIn("13912345678", prompt_text)
                self.assertIn("[REDACTED:phone_cn]", prompt_text)
                md_text = Path(summary["vault_note"]).read_text(encoding="utf-8")
                self.assertNotIn("13912345678", md_text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
