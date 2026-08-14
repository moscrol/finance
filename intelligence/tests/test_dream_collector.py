from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.dream import collector


class RedactTests(unittest.TestCase):
    def test_clean_text_unchanged(self) -> None:
        res = collector.redact("今天大盘小幅震荡，关注半导体板块。")
        self.assertFalse(res.redacted)
        self.assertEqual(res.categories, [])
        self.assertEqual(res.text, "今天大盘小幅震荡，关注半导体板块。")

    def test_empty_text(self) -> None:
        res = collector.redact("")
        self.assertFalse(res.redacted)
        self.assertEqual(res.text, "")
        self.assertIsNotNone(collector.redact(None).text)

    def test_github_pat_masked(self) -> None:
        secret = "ghp_" + "a" * 36
        res = collector.redact(f"我的 token 是 {secret} 千万别泄露")
        self.assertNotIn(secret, res.text)
        self.assertIn("[REDACTED:github_token]", res.text)
        self.assertTrue(res.redacted)

    def test_openai_key_and_assignment_masked(self) -> None:
        key = "sk-" + "B" * 32
        res = collector.redact(f"export API_KEY={key}")
        self.assertNotIn(key, res.text)
        self.assertTrue(res.redacted)
        # assignment 保留键名、掩码值
        self.assertIn("API_KEY=[REDACTED:secret]", res.text)

    def test_pii_masked(self) -> None:
        res = collector.redact("联系 zhangsan@example.com 或 13812345678")
        self.assertNotIn("zhangsan@example.com", res.text)
        self.assertNotIn("13812345678", res.text)
        self.assertIn("[REDACTED:email]", res.text)
        self.assertIn("[REDACTED:phone_cn]", res.text)

    def test_holdings_masked(self) -> None:
        res = collector.redact("我的持仓 600519 浮盈 35%，成本价 1500")
        self.assertIn("[REDACTED:holdings]", res.text)
        self.assertTrue(res.redacted)
        self.assertIn("holdings", res.categories)


class NormalizeFeishuTests(unittest.TestCase):
    def test_text_event_yields_user_and_assistant(self) -> None:
        raw = {
            "ts": "2026-06-17T10:00:00+08:00",
            "chat_id": "oc_demo",
            "message_type": "text",
            "text": "你好",
            "reply": "你好",
        }
        recs = collector.normalize_feishu_event(raw)
        self.assertEqual([r.role for r in recs], ["user", "assistant"])
        self.assertEqual(recs[0].session_id, "oc_demo")
        self.assertEqual(recs[0].source, "feishu")
        self.assertIn("feishu", recs[0].tags)
        self.assertIn("type:text", recs[0].tags)

    def test_non_text_event_uses_placeholder(self) -> None:
        raw = {
            "ts": "2026-06-17T10:01:00+08:00",
            "chat_id": "oc_demo",
            "message_type": "image",
            "text": None,
            "reply": "[回声 bot S0] 已收到「image」类型消息；当前仅回声文本。",
        }
        recs = collector.normalize_feishu_event(raw)
        self.assertEqual(recs[0].role, "user")
        self.assertIn("非文本消息", recs[0].text)
        self.assertEqual(recs[1].role, "assistant")


class RunCollectTests(unittest.TestCase):
    def _write_events(self, path: Path) -> str:
        secret = "ghp_" + "c" * 36
        events = [
            {
                "ts": "2026-06-17T09:00:00+08:00",
                "chat_id": "oc_a",
                "message_type": "text",
                "text": f"帮我存一下 token {secret}",
                "reply": "好的",
            },
            {
                "ts": "2026-06-17T09:05:00+08:00",
                "chat_id": "oc_a",
                "message_type": "text",
                "text": "我的持仓 600519 成本价 1500，浮盈 35%",
                "reply": "收到",
            },
            {
                "ts": "2026-06-17T09:10:00+08:00",
                "chat_id": "oc_b",
                "message_type": "image",
                "text": None,
                "reply": "[回声 bot S0] 已收到「image」类型消息；当前仅回声文本。",
            },
        ]
        path.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n",
            encoding="utf-8",
        )
        return secret

    def test_collect_writes_store_manifest_digest_and_redacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            events = tmp_path / "events.jsonl"
            secret = self._write_events(events)
            store = tmp_path / "store"

            summary = collector.run_collect(
                collector.CollectOptions(events_path=str(events), store_dir=str(store))
            )

            # 正文 jsonl
            jsonl_files = sorted(store.glob("2026-06-17/*.jsonl"))
            self.assertEqual(len(jsonl_files), 2)  # oc_a + oc_b 两个会话
            # manifest
            manifest = (store / "manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(manifest), 2)
            # digest 存在且脱敏（无密钥 / 无持仓明文）
            digest_path = store / "digest-2026-06-17.md"
            self.assertTrue(digest_path.is_file())
            digest = digest_path.read_text(encoding="utf-8")
            self.assertNotIn(secret, digest)
            self.assertNotIn("600519 成本价 1500", digest)
            self.assertIn("[REDACTED", digest)
            # summary
            self.assertEqual(summary["dates"], ["2026-06-17"])
            self.assertGreaterEqual(int(summary["records_redacted"]), 2)

            # 正文里也不存明文密钥（防御性脱敏）
            all_jsonl = "\n".join(p.read_text(encoding="utf-8") for p in jsonl_files)
            self.assertNotIn(secret, all_jsonl)

    def test_idempotent_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            events = tmp_path / "events.jsonl"
            self._write_events(events)
            store = tmp_path / "store"
            opts = collector.CollectOptions(events_path=str(events), store_dir=str(store))

            collector.run_collect(opts)
            manifest1 = (store / "manifest.jsonl").read_text(encoding="utf-8")
            digest1 = (store / "digest-2026-06-17.md").read_text(encoding="utf-8")

            collector.run_collect(opts)
            manifest2 = (store / "manifest.jsonl").read_text(encoding="utf-8")
            digest2 = (store / "digest-2026-06-17.md").read_text(encoding="utf-8")

            # 重跑字节一致（无重复 manifest 行、digest 不变）
            self.assertEqual(manifest1, manifest2)
            self.assertEqual(digest1, digest2)
            self.assertEqual(len(manifest2.strip().splitlines()), 2)

    def test_digest_only_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            events = tmp_path / "events.jsonl"
            self._write_events(events)
            store = tmp_path / "store"
            collector.run_collect(
                collector.CollectOptions(events_path=str(events), store_dir=str(store))
            )
            (store / "digest-2026-06-17.md").unlink()

            summary = collector.run_collect(
                collector.CollectOptions(store_dir=str(store), digest_only=True)
            )
            self.assertEqual(summary["mode"], "digest-only")
            self.assertTrue((store / "digest-2026-06-17.md").is_file())


class CoerceTsTests(unittest.TestCase):
    def test_iso_passthrough(self) -> None:
        self.assertEqual(collector._coerce_ts("2026-06-17T08:00:00+08:00"), "2026-06-17T08:00:00+08:00")

    def test_epoch_seconds_and_ms(self) -> None:
        a = collector._coerce_ts(1_750_000_000)
        b = collector._coerce_ts(1_750_000_000_000)  # 毫秒
        self.assertIsNotNone(a)
        self.assertIn("T", a or "")
        self.assertEqual(a, b)  # 秒 / 毫秒 归一化到同一时刻

    def test_bool_and_none(self) -> None:
        self.assertIsNone(collector._coerce_ts(True))
        self.assertIsNone(collector._coerce_ts(None))
        self.assertIsNone(collector._coerce_ts(""))


class NormalizeClaudeCodeTests(unittest.TestCase):
    def test_user_str_content_and_repo_from_cwd(self) -> None:
        raw = {
            "type": "user",
            "sessionId": "sess-1",
            "timestamp": "2026-06-17T08:00:00+08:00",
            "cwd": "/Users/x/finance-workspace-private",
            "message": {"role": "user", "content": "帮我看下 theme-radar"},
        }
        recs = collector.normalize_claude_code_event(raw)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].role, "user")
        self.assertEqual(recs[0].source, "claude-code")
        self.assertEqual(recs[0].session_id, "sess-1")
        self.assertEqual(recs[0].repo, "finance-workspace-private")
        self.assertIn("claude-code", recs[0].tags)

    def test_assistant_content_blocks_with_tool_use(self) -> None:
        raw = {
            "type": "assistant",
            "sessionId": "sess-1",
            "timestamp": "2026-06-17T08:00:05+08:00",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "我来分析一下"},
                    {"type": "tool_use", "name": "Bash"},
                ],
            },
        }
        recs = collector.normalize_claude_code_event(raw)
        self.assertEqual(recs[0].role, "assistant")
        self.assertIn("我来分析一下", recs[0].text)
        self.assertIn("[tool_use Bash]", recs[0].text)

    def test_empty_content_skipped(self) -> None:
        raw = {"type": "summary", "sessionId": "s", "message": {"role": "assistant", "content": []}}
        self.assertEqual(collector.normalize_claude_code_event(raw), [])

    def test_epoch_timestamp_coerced(self) -> None:
        raw = {
            "type": "user",
            "sessionId": "s",
            "timestamp": 1_750_000_000,
            "message": {"role": "user", "content": "hi"},
        }
        recs = collector.normalize_claude_code_event(raw)
        self.assertIn("T", recs[0].ts)


class NormalizeClaudeMemTests(unittest.TestCase):
    def test_observation_title_text_and_obs_tag(self) -> None:
        raw = {
            "id": "2546",
            "timestamp": "2026-06-17T08:10:00+08:00",
            "type": "feature",
            "title": "Source note pipeline",
            "text": "completed for 2026-04-29 batch",
            "session_id": "S1393",
        }
        recs = collector.normalize_claude_mem_observation(raw)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].role, "assistant")
        self.assertEqual(recs[0].session_id, "S1393")
        self.assertIn("Source note pipeline", recs[0].text)
        self.assertIn("completed", recs[0].text)
        self.assertIn("claude-mem", recs[0].tags)
        self.assertIn("obs:feature", recs[0].tags)

    def test_session_id_falls_back_to_id(self) -> None:
        raw = {"id": "9001", "title": "x", "text": "y"}
        recs = collector.normalize_claude_mem_observation(raw)
        self.assertEqual(recs[0].session_id, "9001")

    def test_no_text_skipped(self) -> None:
        self.assertEqual(collector.normalize_claude_mem_observation({"id": "1"}), [])


class NormalizeWindsurfTests(unittest.TestCase):
    def test_conversation_with_messages(self) -> None:
        raw = {
            "id": "conv-1",
            "workspace": "/home/u/myrepo",
            "messages": [
                {"role": "user", "content": "写个脚本", "timestamp": "2026-06-17T09:00:00+08:00"},
                {"role": "assistant", "content": "好的", "timestamp": "2026-06-17T09:00:03+08:00"},
            ],
        }
        recs = collector.normalize_windsurf_event(raw)
        self.assertEqual([r.role for r in recs], ["user", "assistant"])
        self.assertEqual(recs[0].source, "windsurf")
        self.assertEqual(recs[0].session_id, "conv-1")
        self.assertEqual(recs[0].repo, "myrepo")

    def test_single_message_fallback(self) -> None:
        raw = {"session_id": "conv-2", "role": "user", "text": "在吗", "ts": "2026-06-17T09:05:00+08:00"}
        recs = collector.normalize_windsurf_event(raw)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].session_id, "conv-2")
        self.assertEqual(recs[0].text, "在吗")


class NormalizeDevinTests(unittest.TestCase):
    def test_session_message_roles(self) -> None:
        raw = {
            "session_id": "devin-abc",
            "messages": [
                {"type": "user_message", "message": "复盘一下", "timestamp": "2026-06-17T10:00:00+08:00"},
                {"type": "devin_message", "message": "好的，开始", "timestamp": "2026-06-17T10:00:09+08:00"},
                {"type": "shell", "message": "$ ls", "timestamp": "2026-06-17T10:00:20+08:00"},
            ],
        }
        recs = collector.normalize_devin_session(raw)
        self.assertEqual([r.role for r in recs], ["user", "assistant", "tool"])
        self.assertEqual(recs[0].source, "devin")
        self.assertEqual(recs[0].session_id, "devin-abc")
        self.assertIn("type:user_message", recs[0].tags)

    def test_no_messages_returns_empty(self) -> None:
        self.assertEqual(collector.normalize_devin_session({"session_id": "x"}), [])


class RunCollectMultiSourceTests(unittest.TestCase):
    def test_collect_claude_code_source_redacts_and_tags_source(self) -> None:
        secret = "ghp_" + "d" * 36
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            events = tmp_path / "cc.jsonl"
            lines = [
                {
                    "type": "user",
                    "sessionId": "sess-1",
                    "timestamp": "2026-06-17T08:00:00+08:00",
                    "cwd": "/Users/x/finance-workspace-private",
                    "message": {"role": "user", "content": "帮我存 token"},
                },
                {
                    "type": "assistant",
                    "sessionId": "sess-1",
                    "timestamp": "2026-06-17T08:00:05+08:00",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": f"用 {secret}"}]},
                },
            ]
            events.write_text(
                "\n".join(json.dumps(e, ensure_ascii=False) for e in lines) + "\n", encoding="utf-8"
            )
            store = tmp_path / "store"
            summary = collector.run_collect(
                collector.CollectOptions(
                    events_path=str(events), store_dir=str(store), source="claude-code"
                )
            )

            self.assertEqual(summary["source"], "claude-code")
            jsonl_files = sorted(store.glob("2026-06-17/*.jsonl"))
            self.assertEqual([p.name for p in jsonl_files], ["claude-code-sess-1.jsonl"])
            manifest = collector._read_manifest(store)
            self.assertEqual(manifest[0]["source"], "claude-code")
            digest = (store / "digest-2026-06-17.md").read_text(encoding="utf-8")
            self.assertNotIn(secret, digest)
            self.assertIn("[REDACTED:github_token]", digest)


class CliWiringTests(unittest.TestCase):
    def test_cli_registers_dream_collect_subcommand(self) -> None:
        from intelligence import cli

        parser = cli.build_parser()
        args = parser.parse_args(["dream-collect", "--events", "x.jsonl"])
        self.assertEqual(args.func, cli.cmd_dream_collect)
        self.assertEqual(args.source, "feishu")

    def test_cli_accepts_new_sources(self) -> None:
        from intelligence import cli

        parser = cli.build_parser()
        for src in ("claude-code", "claude-mem", "windsurf", "devin"):
            args = parser.parse_args(["dream-collect", "--source", src, "--events", "x.jsonl"])
            self.assertEqual(args.source, src)


class FeishuTranscriptSinkTests(unittest.TestCase):
    def test_build_config_picks_transcript_log_flag(self) -> None:
        from intelligence.chat import feishu_bot

        parser = __import__("argparse").ArgumentParser()
        feishu_bot.add_arguments(parser)
        args = parser.parse_args(
            ["--app-id", "a", "--app-secret", "b", "--transcript-log", "/tmp/t.jsonl"]
        )
        config = feishu_bot.build_config(args)
        self.assertEqual(config.transcript_log, "/tmp/t.jsonl")

    def test_default_transcript_log_off(self) -> None:
        from intelligence.chat import feishu_bot

        parser = __import__("argparse").ArgumentParser()
        feishu_bot.add_arguments(parser)
        args = parser.parse_args(["--app-id", "a", "--app-secret", "b"])
        config = feishu_bot.build_config(args)
        self.assertIsNone(config.transcript_log)

    def test_append_transcript_writes_parseable_line(self) -> None:
        from intelligence.chat import feishu_bot

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "events.jsonl"
            event = feishu_bot.build_transcript_event("om_1", "oc_1", "text", "你好", "你好")
            feishu_bot.append_transcript(str(path), event)
            line = path.read_text(encoding="utf-8").strip()
            obj = json.loads(line)
            self.assertEqual(obj["source"], "feishu")
            self.assertEqual(obj["text"], "你好")
            self.assertEqual(obj["reply"], "你好")
            self.assertEqual(obj["message_type"], "text")


if __name__ == "__main__":
    unittest.main()
