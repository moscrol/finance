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


class CliWiringTests(unittest.TestCase):
    def test_cli_registers_dream_collect_subcommand(self) -> None:
        from intelligence import cli

        parser = cli.build_parser()
        args = parser.parse_args(["dream-collect", "--events", "x.jsonl"])
        self.assertEqual(args.func, cli.cmd_dream_collect)
        self.assertEqual(args.source, "feishu")


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
