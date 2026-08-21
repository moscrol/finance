"""V4 索引卫生：工件页不进索引、同族多版本折叠。先红后绿。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence.services import kb_rag
from intelligence.services.kb_index_hygiene import (
    collapse_same_slug,
    family_key,
    indexable_paths,
    is_artifact_page,
    sanitize_hits,
)


def _hit(path: str, title: str = "", score: float = 0.5) -> kb_rag.WikiHit:
    title = title or Path(path).stem
    return kb_rag.WikiHit(
        page_id=title,
        file_path=path,
        title=title,
        score=score,
        excerpt=f"{title} excerpt",
    )


def _fresh_item(path: str, title: str, score: float) -> dict:
    return {
        "page_id": title,
        "file_path": path,
        "title": title,
        "score": score,
        "best_chunk_id": f"{path}::0",
        "content_hash": f"hash-{title}",
        "evidence_text": f"{title} matched chunk",
        "index_source_revision": "abc123",
        "index_freshness": "fresh",
    }


# 液冷案冻结夹具：与 run_20260820_032014_595378 第一跳 top-5 同形。
_LIQUID_COOLING_TOP5 = (
    (
        "wiki/sources/液冷服务器产业新变化与新格局全面分析报告.md",
        "液冷服务器产业新变化与新格局全面分析报告",
        0.91,
    ),
    (
        "wiki/synthesis/液冷服务器-theme-radar-验收.md",
        "液冷服务器-theme-radar-验收",
        0.88,
    ),
    (
        "wiki/synthesis/液冷服务器-theme-radar-验收-v5.md",
        "液冷服务器-theme-radar-验收-v5",
        0.87,
    ),
    (
        "wiki/synthesis/液冷服务器-theme-radar-验收-v6.md",
        "液冷服务器-theme-radar-验收-v6",
        0.86,
    ),
    (
        "wiki/synthesis/液冷服务器-theme-radar-验收-v7.md",
        "液冷服务器-theme-radar-验收-v7",
        0.85,
    ),
)


class ArtifactPathExclusionTests(unittest.TestCase):
    def test_index_build_entry_excludes_theme_radar_acceptance_pages(self) -> None:
        knowledge = "wiki/sources/液冷服务器产业新变化与新格局全面分析报告.md"
        artifacts = [
            "wiki/synthesis/液冷服务器-theme-radar-验收.md",
            "wiki/synthesis/液冷服务器-theme-radar-验收-v5.md",
            "wiki/synthesis/液冷服务器-theme-radar-验收-v8.md",
            "wiki/synthesis/图片题材批处理流程验收_20260605.md",
        ]
        served = indexable_paths([knowledge, *artifacts])
        self.assertEqual(served, [knowledge])
        self.assertTrue(all(is_artifact_page(path) for path in artifacts))
        self.assertFalse(is_artifact_page(knowledge))

    def test_frontmatter_kb_index_false_is_artifact(self) -> None:
        path = "wiki/synthesis/some-eval-dump.md"
        self.assertFalse(is_artifact_page(path))
        self.assertTrue(
            is_artifact_page(path, frontmatter={"kb_index": False})
        )
        self.assertTrue(
            is_artifact_page(
                path,
                page_text="---\ntype: artifact\n---\n# dump\n",
            )
        )

    def test_domain_pages_with_test_in_name_are_not_artifacts(self) -> None:
        keep = [
            "wiki/concepts/测试设备.md",
            "wiki/entities/谱尼测试.md",
            "wiki/synthesis/AI测试电源大功率化-serenity-alpha-20260605.md",
        ]
        self.assertEqual(indexable_paths(keep), keep)
        self.assertFalse(any(is_artifact_page(path) for path in keep))


class FamilyCollapseTests(unittest.TestCase):
    def test_same_slug_keeps_latest_version_only(self) -> None:
        hits = [
            _hit("wiki/synthesis/先进封装-v2.md", score=0.9),
            _hit("wiki/synthesis/先进封装-v4.md", score=0.8),
            _hit("wiki/synthesis/先进封装.md", score=0.7),
            _hit("wiki/concepts/先进封装.md", score=0.6),
        ]
        kept = collapse_same_slug(hits)
        self.assertEqual(
            [hit.file_path for hit in kept],
            [
                "wiki/synthesis/先进封装-v4.md",
                "wiki/concepts/先进封装.md",
            ],
        )

    def test_unrecognized_siblings_fail_open(self) -> None:
        # 日期戳、夹心 -v2、不同目录同名：认不出同族，照常收录。
        hits = [
            _hit("wiki/synthesis/图片题材批处理流程_20260605.md", score=0.9),
            _hit("wiki/synthesis/图片题材批处理流程_20260606.md", score=0.8),
            _hit("wiki/synthesis/报告-v2-draft.md", score=0.7),
            _hit("wiki/synthesis/报告.md", score=0.6),
        ]
        kept = collapse_same_slug(hits)
        self.assertEqual([hit.file_path for hit in kept], [h.file_path for h in hits])
        self.assertIsNone(family_key("wiki/synthesis/报告-v2-draft.md"))
        self.assertIsNone(family_key("wiki/synthesis/图片题材批处理流程_20260605.md"))


class LiquidCoolingReplayFixtureTests(unittest.TestCase):
    def test_sanitize_drops_artifacts_and_fills_top5_with_knowledge(self) -> None:
        hits = [_hit(path, title, score) for path, title, score in _LIQUID_COOLING_TOP5]
        extra = _hit(
            "wiki/concepts/液冷服务器.md",
            "液冷服务器",
            0.7,
        )
        kept = sanitize_hits([*hits, extra], k=5)
        self.assertEqual(len(kept), 2)
        self.assertEqual(
            [hit.file_path for hit in kept],
            [
                "wiki/sources/液冷服务器产业新变化与新格局全面分析报告.md",
                "wiki/concepts/液冷服务器.md",
            ],
        )
        self.assertFalse(any(is_artifact_page(hit.file_path) for hit in kept))


class RetrieveHygieneWiringTests(unittest.TestCase):
    def test_retrieve_excludes_artifact_paths_and_overfetches(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wiki = root / "wiki"
            script = root / kb_rag.RAG_SCRIPT_REL
            wiki.joinpath("concepts").mkdir(parents=True)
            script.parent.mkdir(parents=True)
            script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
            wiki.joinpath("concepts", "光刻机.md").write_text("# x\n", encoding="utf-8")
            (root / ".rag_index").mkdir()
            payload = [
                _fresh_item(path, title, score)
                for path, title, score in _LIQUID_COOLING_TOP5
            ]
            payload.append(
                _fresh_item("wiki/concepts/液冷服务器.md", "液冷服务器", 0.7)
            )
            proc = mock.Mock(
                returncode=0,
                stdout=json.dumps(payload, ensure_ascii=False),
                stderr="",
            )
            with mock.patch.dict(
                "os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=True
            ):
                with mock.patch("subprocess.run", return_value=proc) as run:
                    res = kb_rag.retrieve("液冷服务器", wiki, k=5)

            cmd = run.call_args.args[0]
            k_idx = cmd.index("--k")
            self.assertGreater(int(cmd[k_idx + 1]), 5)
            self.assertTrue(res.ok)
            self.assertEqual(res.telemetry.k, 5)
            titles = [hit.title for hit in res.hits]
            self.assertFalse(
                any("theme-radar-验收" in hit.file_path for hit in res.hits),
                titles,
            )
            self.assertIn(
                "液冷服务器产业新变化与新格局全面分析报告",
                titles,
            )
            self.assertLessEqual(len(res.hits), 5)
