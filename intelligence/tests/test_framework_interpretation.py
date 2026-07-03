from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence import userspace
from intelligence.services import framework_interpretation as fi
from intelligence.services import perspective_lab


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


_DAILY_REVIEW_MD = """# 2026-07-03 每日市场复盘

## 核心看板

- 上证指数 4043.64（+0.37%）
- 量能放大但涨家数收缩

## 目录

- （目录内容不应进入硬事实摘要）

## 15. 市场环境总评

- 主线：人形机器人；双红题材扩散
"""


class ExtractFactsDigestTest(unittest.TestCase):
    def test_extracts_only_fact_sections(self) -> None:
        digest = fi.extract_facts_digest(_DAILY_REVIEW_MD)
        self.assertIn("核心看板", digest)
        self.assertIn("市场环境总评", digest)
        self.assertIn("量能放大但涨家数收缩", digest)
        self.assertNotIn("目录内容不应进入", digest)

    def test_empty_when_no_sections(self) -> None:
        self.assertEqual(fi.extract_facts_digest("# 空\n\n正文"), "")


class FrameworkVersionTest(unittest.TestCase):
    def test_stable_and_content_sensitive(self) -> None:
        p1 = {"market_lenses": [{"name": "a"}], "risk_triggers": ["x"]}
        p2 = json.loads(json.dumps(p1))
        self.assertEqual(fi.framework_version(p1), fi.framework_version(p2))
        p2["risk_triggers"] = ["y"]
        self.assertNotEqual(fi.framework_version(p1), fi.framework_version(p2))
        self.assertTrue(fi.framework_version(p1).startswith("fw-"))


class RunTest(unittest.TestCase):
    def _init_profile(self, us: userspace.UserSpace) -> None:
        us.ensure_dir()
        _, profile = perspective_lab.init_perspective(
            us, fi.FRAMEWORK_PERSPECTIVE_ID, ptype="user_framework"
        )
        # 让画像带一个必命中的风险信号词，验证判断→checkpoint 链路
        profile["risk_triggers"] = ["量能放大但涨家数收缩"]
        path = perspective_lab.profile_path(us, fi.FRAMEWORK_PERSPECTIVE_ID)
        path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")

    def test_skip_without_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            result = fi.run(us, date="2026-07-03", daily_review_md_path=Path(tmp) / "none.md")
            self.assertEqual(result["status"], "skipped")
            self.assertIn("profile", result["reason"])

    def test_skip_without_daily_review_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            self._init_profile(us)
            result = fi.run(us, date="2026-07-03", daily_review_md_path=Path(tmp) / "none.md")
            self.assertEqual(result["status"], "skipped")
            self.assertIn("不存在", result["reason"])

    def test_run_registers_checkpoints_with_framework_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            self._init_profile(us)
            md = Path(tmp) / "2026-07-03-daily-review.md"
            md.write_text(_DAILY_REVIEW_MD, encoding="utf-8")
            out = Path(tmp) / "out.md"
            result = fi.run(us, date="2026-07-03", daily_review_md_path=md, out_md=out)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["judgments"], 1)
            self.assertEqual(result["checkpoints_added"], 2)  # T+1 + T+3
            records = [
                json.loads(line)
                for line in us.checkpoints_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(records), 2)
            dues = sorted(r["due"] for r in records)
            self.assertEqual(dues, ["2026-07-04", "2026-07-06"])
            for r in records:
                self.assertEqual(r["framework_version"], result["framework_version"])
                self.assertEqual(r["category"], fi.CHECKPOINT_CATEGORY)
                self.assertIn("风险信号成立", r["claim"])
            report = out.read_text(encoding="utf-8")
            self.assertIn("框架解读", report)
            self.assertIn("最近纠偏回灌", report)
            self.assertIn("量能放大但涨家数收缩", report)

    def test_rerun_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            self._init_profile(us)
            md = Path(tmp) / "md.md"
            md.write_text(_DAILY_REVIEW_MD, encoding="utf-8")
            first = fi.run(us, date="2026-07-03", daily_review_md_path=md)
            second = fi.run(us, date="2026-07-03", daily_review_md_path=md)
            self.assertEqual(first["checkpoints_added"], 2)
            self.assertEqual(second["checkpoints_added"], 0)

    def test_corrections_injected_into_report(self) -> None:
        from intelligence.services import corrections as corrections_svc

        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            self._init_profile(us)
            corrections_svc.record_correction(
                us.corrections_path,
                correction="缩容行情说明资金进攻大成交抱团",
                original="量能扩张=普涨",
            )
            md = Path(tmp) / "md.md"
            md.write_text(_DAILY_REVIEW_MD, encoding="utf-8")
            result = fi.run(us, date="2026-07-03", daily_review_md_path=md)
            self.assertIn("缩容行情说明资金进攻大成交抱团", result["report"])
            self.assertIn("别再说「量能扩张=普涨」", result["report"])


if __name__ == "__main__":
    unittest.main()
