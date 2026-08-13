from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.eval.retrieval_recall import (
    evaluate_cases,
    load_cases,
    render_report,
    user_memory_retriever,
)
from intelligence.services import memory_status


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8",
    )


def _make_ledgers(root: Path) -> None:
    _write_jsonl(
        root / "judgments.jsonl",
        [
            {"ts": "j1", "memo": "液冷渗透率是核心变量", "themes": ["液冷"]},
            {"ts": "j2", "memo": "固态电池看设备端先行", "themes": ["固态电池"]},
        ],
    )
    _write_jsonl(
        root / "corrections.jsonl",
        [
            {"ts": "c1", "correction": "液冷题材双红要看边际量不是涨幅", "themes": ["液冷"]},
        ],
    )
    # checkpoints/verdicts 缺失是允许的（memory_block 会跳过校准），这里不建


class LoadCasesTests(unittest.TestCase):
    def test_loads_valid_and_skips_invalid(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "cases.jsonl"
            p.write_text(
                "# 注释\n"
                '{"case_id": "a", "query": "液冷怎么看", "theme": "液冷", "relevant": ["j1"]}\n'
                '{"query": "", "relevant": ["x"]}\n'
                '{"query": "没有标注"}\n'
                "not-json\n",
                encoding="utf-8",
            )
            cases = load_cases(p)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["case_id"], "a")


class UserMemoryRetrieverTests(unittest.TestCase):
    def test_retrieves_relevant_ids_from_both_ledgers(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_ledgers(root)
            ids = user_memory_retriever("液冷渗透率怎么看", "液冷", None, 5, users_root=root)
        self.assertIn("j1", ids)
        self.assertIn("c1", ids)
        self.assertNotIn("j2", ids)  # 不相关题材不该被召回

    def test_archived_records_not_retrieved(self) -> None:
        # 与 slice 5 联动：归档后的记忆不应再被召回 → 尺子能测出退出机制生效
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_ledgers(root)
            memory_status.record_status(
                root / "judgments.jsonl", target_ts="j1", status="archived"
            )
            ids = user_memory_retriever("液冷渗透率怎么看", "液冷", None, 5, users_root=root)
        self.assertNotIn("j1", ids)


class EvaluateCasesTests(unittest.TestCase):
    def _cases(self) -> list[dict]:
        return [
            {"case_id": "hit", "query": "液冷渗透率怎么看", "theme": "液冷", "relevant": ["j1", "c1"]},
            {"case_id": "miss", "query": "液冷渗透率怎么看", "theme": "液冷", "relevant": ["j2"]},
        ]

    def test_recall_and_hit_metrics(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_ledgers(root)
            report = evaluate_cases(
                self._cases(), user_memory_retriever, ks=(5,), users_root=root
            )
        self.assertEqual(report["cases"], 2)
        by_id = {r["case_id"]: r for r in report["per_case"]}
        self.assertEqual(by_id["hit"]["recall_at"][5], 1.0)
        self.assertEqual(by_id["miss"]["recall_at"][5], 0.0)
        self.assertEqual(by_id["miss"]["missed"][5], ["j2"])
        self.assertAlmostEqual(report["recall_at"][5], 0.5)
        self.assertAlmostEqual(report["hit_rate_at"][5], 0.5)

    def test_report_renders_worst_cases_and_discipline(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_ledgers(root)
            report = evaluate_cases(
                self._cases(), user_memory_retriever, ks=(1, 5), users_root=root
            )
        text = render_report(report)
        self.assertIn("recall@k", text)
        self.assertIn("未完全召回的 case", text)
        self.assertIn("miss", text)
        self.assertIn("读数纪律", text)

    def test_empty_cases(self) -> None:
        report = evaluate_cases([], user_memory_retriever, ks=(3,))
        self.assertEqual(report["cases"], 0)
        self.assertIsNone(report["recall_at"][3])


class FixtureSetTests(unittest.TestCase):
    def test_bundled_fixture_is_runnable(self) -> None:
        from intelligence.eval.retrieval_recall import FIXTURE_CASES, FIXTURE_LEDGERS

        cases = load_cases(FIXTURE_CASES)
        self.assertGreaterEqual(len(cases), 3)
        report = evaluate_cases(
            cases, user_memory_retriever, ks=(5,), users_root=FIXTURE_LEDGERS
        )
        by_id = {r["case_id"]: r for r in report["per_case"]}
        self.assertEqual(by_id["m-001"]["recall_at"][5], 1.0)
        self.assertEqual(by_id["m-002"]["recall_at"][5], 1.0)
        self.assertEqual(by_id["m-003"]["recall_at"][5], 0.0)


if __name__ == "__main__":
    unittest.main()
