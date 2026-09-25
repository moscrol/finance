from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence.services import prime
from intelligence.userspace import user_space


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")


def _write_relations(wiki: Path) -> None:
    rel = wiki / "relations"
    rel.mkdir(parents=True, exist_ok=True)
    (rel / "concept_graph.json").write_text(
        json.dumps({"concepts": {"液冷服务器": {"summary": "AI 算力散热"}}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (rel / "entity_exposures.json").write_text(
        json.dumps(
            {
                "entities": {
                    "英维克": {
                        "codes": ["002837"],
                        "concepts": {
                            "液冷服务器": {"role": "温控核心", "strength": "core", "confidence": "high"}
                        },
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (rel / "evidence_index.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "target": "液冷服务器",
                        "evidence": "冷板式渗透率提升",
                        "source": "测试来源",
                        "source_date": "2026-06-01",
                        "confidence": "medium",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class PrimeTests(unittest.TestCase):
    def test_build_prime_combines_calibration_personal_and_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wiki = root / "wiki"
            _write_relations(wiki)
            with mock.patch.dict(
                "os.environ", {"FORESIGHT_USERS_DIR": str(root / "users"), "FORESIGHT_USER": "tester"}
            ):
                us = user_space("tester")
                us.ensure_dir()
                # 校准注入要求类别 >= DEFAULT_CALIBRATION_MIN_N 条终态判定；夹具跟着常量走
                n = prime.checkpoints_service.DEFAULT_CALIBRATION_MIN_N
                _write_jsonl(
                    us.checkpoints_path,
                    [
                        {
                            "id": f"ck{i}",
                            "claim": f"液冷渗透率超预期 {i}",
                            "due": "2026-01-01",
                            "category": "题材节奏",
                            "ts": "2025-12-01T10:00:00",
                        }
                        for i in range(n)
                    ],
                )
                _write_jsonl(
                    us.verdicts_path,
                    [
                        {
                            "id": f"ck{i}",
                            "verdict": "hit" if i % 2 == 0 else "miss",
                            "score": 1.0 if i % 2 == 0 else 0.0,
                            "checked_at": "2026-01-02T10:00:00",
                        }
                        for i in range(n)
                    ],
                )
                _write_jsonl(
                    us.interactions_path,
                    [
                        {
                            "kind": "click",
                            "weight": 1.0,
                            "themes": ["液冷"],
                            "stocks": [],
                            "ts": "2099-01-01T10:00:00",
                        }
                    ],
                )
                _write_jsonl(
                    us.corrections_path,
                    [{"correction": "先看渗透率数据", "principle": "拿数说话", "ts": "2026-01-01T10:00:00"}],
                )
                _write_jsonl(
                    us.judgments_path,
                    [{"memo": "液冷是长逻辑", "themes": ["液冷"], "ts": "2026-01-01T10:00:00"}],
                )

                result = prime.build_prime(
                    prime.PrimeOptions(query="液冷服务器", user="tester", kb_wiki=wiki)
                )

        self.assertEqual(result.user, "tester")
        self.assertIn("题材节奏", result.calibration_lines)
        self.assertTrue(any(a["label"] == "液冷" and a["relevant"] for a in result.affinity))
        self.assertIn("拿数说话", result.corrections_lines)
        self.assertIn("液冷是长逻辑", result.judgments_lines)
        self.assertTrue(any(i["concept"] == "液冷服务器" for i in result.graph_concepts))
        self.assertTrue(any(r["company"] == "英维克" for r in result.graph_companies))
        self.assertTrue(any(e.get("target") == "液冷服务器" for e in result.evidence))

        prefix = prime.render_prefix(result)
        for section in ("【校准｜历史判断胜率】", "【个人库｜画像与近期关注】", "【图谱｜知识库命中】"):
            self.assertIn(section, prefix)
        payload = prime.result_to_dict(result)
        self.assertEqual(payload["prefix"], prefix)

    def test_build_prime_degrades_without_any_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.dict(
                "os.environ", {"FORESIGHT_USERS_DIR": str(root / "users"), "FORESIGHT_USER": "nobody"}
            ):
                result = prime.build_prime(
                    prime.PrimeOptions(query="随便问问", user="nobody", kb_wiki=root / "no-wiki")
                )
        self.assertEqual(result.calibration_lines, "")
        self.assertEqual(result.affinity, [])
        prefix = prime.render_prefix(result)
        self.assertIn("检索前置", prefix)


if __name__ == "__main__":
    unittest.main()
