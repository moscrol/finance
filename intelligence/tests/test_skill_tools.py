from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from intelligence.services import skill_tools
from intelligence.services.skill_tools import (
    ALL_SKILLS,
    SKILL_REGISTRY,
    _parse_serenity,
    run_skill,
    skill_descriptions,
)


def _serenity_fixture() -> dict:
    return {
        "term": "液冷",
        "vault": "/tmp/wiki",
        "concepts": {
            "primary": "液冷",
            "matched": ["液冷", "液冷温控"],
            "related": ["AI算力基建", "数据中心", "光模块"],
        },
        "concept_cards": [{"name": "液冷", "updated": "2026-06-16", "one_liner": "", "core_logic": ""}],
        "candidate_companies": [
            {
                "company": "英维克",
                "ticker": "002837",
                "direct": True,
                "strength": "core",
                "evidence_count": 35,
                "has_logic_card": True,
                "role": "温控/液冷一次侧",
                "wiki_one_liner": "数据中心温控龙头",
                "wiki_updated": "2026-06-04",
                "concept": "液冷服务器",
            },
            {
                "company": "川润股份",
                "ticker": "002272",
                "direct": False,
                "strength": "",
                "evidence_count": 0,
                "has_logic_card": False,
                "role": "液压+液冷扩散",
                "wiki_one_liner": None,
                "wiki_updated": "2026-05-30",
                "concept": "液冷",
            },
        ],
        "fine_position_buckets": {"数据中心液冷": ["英维克", "高澜股份"], "微通道液冷": ["飞荣达"]},
        "role_buckets": {
            "anchor": ["英维克", "工业富联"],
            "bottleneck": ["飞荣达"],
            "old_label": [],
            "diffusion": ["川润股份"],
        },
        "synthesis_snapshots": [
            {"date": "2026-06-05", "title": "液冷-serenity-alpha-20260605", "is_serenity": True, "summary": "迁移条件需客户验证"},
        ],
        "benchmark_matches": [
            {"benchmark_company": "Vertiv", "benchmark_ticker": "VRT", "theme_routes": ["液冷", "数据中心温控"]},
        ],
        "tmp_reports": [],
        "usage_note": "context only",
    }


class ParseSerenityTests(unittest.TestCase):
    def test_parses_all_sections(self) -> None:
        title, highlights, follow_ups = _parse_serenity(_serenity_fixture())
        blob = "\n".join(highlights)
        self.assertIn("2 家", title)
        self.assertIn("概念定位", blob)
        self.assertIn("主匹配 液冷", blob)
        # both candidates surfaced with strength/evidence/logic-card flags
        self.assertIn("英维克", blob)
        self.assertIn("002837", blob)
        self.assertIn("逻辑卡✓", blob)
        self.assertIn("数据中心温控龙头", blob)
        # candidate with no one_liner falls back to role
        self.assertIn("液压+液冷扩散", blob)
        # role buckets (non-empty only)
        self.assertIn("锚候选", blob)
        self.assertIn("二阶瓶颈", blob)
        self.assertNotIn("旧标签重估", blob)  # empty bucket omitted
        # fine buckets + synthesis + benchmark
        self.assertIn("细分卡位", blob)
        self.assertIn("历史快照 1 篇", blob)
        self.assertIn("海外对标", blob)
        self.assertIn("Vertiv", blob)
        # follow-ups derived from top candidate
        self.assertTrue(any("英维克" in f for f in follow_ups))

    def test_empty_knowledge_yields_no_highlights(self) -> None:
        empty = {"term": "陌生词", "concepts": {}, "candidate_companies": []}
        title, highlights, _ = _parse_serenity(empty)
        self.assertEqual(highlights, [])
        self.assertIn("0 家", title)


class RunSkillDegradeTests(unittest.TestCase):
    VAULT = "/tmp/wiki"

    def test_unknown_skill(self) -> None:
        res = run_skill("does-not-exist", "液冷", self.VAULT)
        self.assertFalse(res.ok)
        self.assertIn("未知 skill", res.warning)

    def test_missing_vault(self) -> None:
        res = run_skill("serenity-alpha", "液冷", None)
        self.assertFalse(res.ok)
        self.assertIn("wiki", res.warning)

    def test_missing_script(self) -> None:
        spec = SKILL_REGISTRY["serenity-alpha"]
        with mock.patch.object(spec, "script", Path("/nonexistent/serenity_context.py")):
            res = run_skill("serenity-alpha", "液冷", self.VAULT)
        self.assertFalse(res.ok)
        self.assertIn("脚本不存在", res.warning)

    def _fake_proc(self, stdout: str = "", returncode: int = 0, stderr: str = ""):
        return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)

    def test_success_parses_and_cites(self) -> None:
        out = json.dumps(_serenity_fixture(), ensure_ascii=False)
        with mock.patch.object(skill_tools.subprocess, "run", return_value=self._fake_proc(stdout=out)):
            res = run_skill("serenity-alpha", "液冷", self.VAULT)
        self.assertTrue(res.ok)
        self.assertIn("2 家", res.title)
        self.assertTrue(res.highlights)
        self.assertIn("serenity", res.citation_source)
        self.assertEqual(res.citation_detail, "--term 液冷")
        self.assertIn("英维克", "\n".join(res.highlights))

    def test_nonzero_exit_degrades(self) -> None:
        with mock.patch.object(skill_tools.subprocess, "run", return_value=self._fake_proc(returncode=2, stderr="boom")):
            res = run_skill("serenity-alpha", "液冷", self.VAULT)
        self.assertFalse(res.ok)
        self.assertIn("退出码 2", res.warning)

    def test_timeout_degrades(self) -> None:
        with mock.patch.object(skill_tools.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1)):
            res = run_skill("serenity-alpha", "液冷", self.VAULT, timeout=1)
        self.assertFalse(res.ok)
        self.assertIn("超时", res.warning)

    def test_bad_json_degrades(self) -> None:
        with mock.patch.object(skill_tools.subprocess, "run", return_value=self._fake_proc(stdout="{not json")):
            res = run_skill("serenity-alpha", "液冷", self.VAULT)
        self.assertFalse(res.ok)
        self.assertIn("解析失败", res.warning)

    def test_non_dict_json_degrades(self) -> None:
        with mock.patch.object(skill_tools.subprocess, "run", return_value=self._fake_proc(stdout="[1, 2, 3]")):
            res = run_skill("serenity-alpha", "液冷", self.VAULT)
        self.assertFalse(res.ok)
        self.assertIn("格式异常", res.warning)

    def test_empty_result_degrades(self) -> None:
        empty = json.dumps({"term": "陌生词", "concepts": {}, "candidate_companies": []}, ensure_ascii=False)
        with mock.patch.object(skill_tools.subprocess, "run", return_value=self._fake_proc(stdout=empty)):
            res = run_skill("serenity-alpha", "陌生词", self.VAULT)
        self.assertFalse(res.ok)
        self.assertIn("无产出", res.warning)


class RegistryTests(unittest.TestCase):
    def test_safelist_only_known_skills(self) -> None:
        self.assertEqual(ALL_SKILLS, ("serenity-alpha",))
        self.assertIn("serenity-alpha", skill_descriptions())

    def test_spec_script_under_repo(self) -> None:
        spec = SKILL_REGISTRY["serenity-alpha"]
        self.assertTrue(str(spec.script).endswith("skills/serenity-alpha/scripts/serenity_context.py"))


if __name__ == "__main__":
    unittest.main()
