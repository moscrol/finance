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


_DAILY_REVIEW_JSON = {
    "schema": "daily-review/v1",
    "trade_date": "2026-07-03",
    "core_board": [
        {"dimension": "情绪状态", "conclusion": "涨家数 1541，MA5 2903.2，涨停 52，跌停 8"},
    ],
    "facts": {
        "nature": "普通交易日",
        "price_day": False,
        "volume_day": True,
        "ma5_position": "震荡区间",
        "ma5_trend": "下降",
        "multi_period_themes": [["军贸概念", 4], ["旅游", 2]],
        "full_period_themes": ["军贸概念"],
        "max_boards": 4,
    },
    "sections": [
        {
            "id": "sentiment",
            "index": 2,
            "title": "市场情绪",
            "blocks": [
                {"kind": "table", "title": None, "columns": ["项目", "今日"], "rows": [["涨家数", 1541]]},
                {"kind": "note", "text": "**MA5位置**：当前处于 **震荡区间**，趋势为 **下降**。"},
                {"kind": "conclusion", "text": "涨家数收缩，MA5 走平。"},
            ],
        },
        {
            "id": "double_red_matrix",
            "index": 6,
            "title": "重点申万一级近15日子板块双红矩阵",
            "blocks": [
                {"kind": "note", "text": "单元格格式说明（不该进摘要）。"},
                {"kind": "conclusion", "text": "重点观察申万一级为 电子。"},
            ],
        },
    ],
    "assessment": "主线：人形机器人；双红题材扩散",
}


class ExtractFactsDigestTest(unittest.TestCase):
    def test_extracts_only_fact_sections(self) -> None:
        digest = fi.extract_facts_digest(_DAILY_REVIEW_MD)
        self.assertIn("核心看板", digest)
        self.assertIn("市场环境总评", digest)
        self.assertIn("量能放大但涨家数收缩", digest)
        self.assertNotIn("目录内容不应进入", digest)

    def test_empty_when_no_sections(self) -> None:
        self.assertEqual(fi.extract_facts_digest("# 空\n\n正文"), "")

    def test_json_digest_carries_lens_facts_and_section_conclusions(self) -> None:
        digest = fi.extract_facts_digest_from_json(_DAILY_REVIEW_JSON)
        # 核心看板与总评照旧
        self.assertIn("| 情绪状态 | 涨家数 1541", digest)
        self.assertIn("> 主线：人形机器人", digest)
        # 画像信号词真正会落的口径：MA5 位置/趋势、价日量日、共振题材、连板高度
        self.assertIn("涨家数MA5位置：震荡区间", digest)
        self.assertIn("涨家数MA5趋势：下降", digest)
        self.assertIn("价日：否", digest)
        self.assertIn("量日：是", digest)
        self.assertIn("多周期共振题材：军贸概念(4次)、旅游(2次)", digest)
        self.assertIn("最高连板：4", digest)
        # 分节结论逐字进来，格式说明类 note 不进
        self.assertIn("市场情绪：涨家数收缩，MA5 走平。", digest)
        self.assertIn("市场情绪：**MA5位置**", digest)
        self.assertIn("重点观察申万一级为 电子", digest)
        self.assertNotIn("单元格格式说明", digest)

    def test_load_prefers_json_sibling_and_falls_back_to_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "2026-07-03-daily-review.md"
            md.write_text(_DAILY_REVIEW_MD, encoding="utf-8")
            self.assertIn("量能放大但涨家数收缩", fi.load_facts_digest(md))
            md.with_suffix(".json").write_text(
                json.dumps(_DAILY_REVIEW_JSON, ensure_ascii=False), encoding="utf-8"
            )
            digest = fi.load_facts_digest(md)
            self.assertIn("涨家数MA5位置：震荡区间", digest)
            self.assertNotIn("量能放大但涨家数收缩", digest)


class FrameworkVersionTest(unittest.TestCase):
    def test_stable_and_content_sensitive(self) -> None:
        p1 = {"market_lenses": [{"name": "a"}], "risk_triggers": ["x"]}
        p2 = json.loads(json.dumps(p1))
        self.assertEqual(fi.framework_version(p1), fi.framework_version(p2))
        p2["risk_triggers"] = ["y"]
        self.assertNotEqual(fi.framework_version(p1), fi.framework_version(p2))
        self.assertTrue(fi.framework_version(p1).startswith("fw-"))


class HitTest(unittest.TestCase):
    def test_fragment_level_match(self) -> None:
        term = "缩容行情（涨家数收缩、量能扩张）= 资金进攻加强"
        facts = "今日量能放大，涨家数收缩至 1800 家"
        self.assertEqual(fi._hit(term, facts), "涨家数收缩")

    def test_no_match_returns_none(self) -> None:
        self.assertIsNone(fi._hit("北向资金大幅流出", "今日普涨"))

    def test_whole_sentence_match_preferred(self) -> None:
        term = "量能放大但涨家数收缩"
        self.assertEqual(fi._hit(term, "盘面：量能放大但涨家数收缩"), term)


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
