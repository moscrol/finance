from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from intelligence.eval.retrieval_recall import (
    evaluate_cases,
    experience_cards_retriever,
    kb_rag_retriever,
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


class ExperienceCardsRetrieverTests(unittest.TestCase):
    def _make_cards(self, root: Path) -> None:
        _write_jsonl(
            root / "experience_cards.jsonl",
            [
                {"ts": "e1", "question": "深挖飞凯材料", "applies_to": ["个股深挖"]},
                {"ts": "e2", "question": "液冷温控怎么看", "applies_to": ["题材方向判断"]},
                {"ts": "e3", "question": "深挖飞凯材料（旧版）", "applies_to": ["个股深挖"],
                 "invalidated": "坏指标"},
                {"ts": "e4", "question": "深挖飞凯材料（已固化）", "applies_to": ["个股深挖"],
                 "promotion": "promoted_to_code"},
            ],
        )

    def test_relevant_card_ts_and_invalidated_skipped(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_cards(root)
            ids = experience_cards_retriever("帮我深挖飞凯材料", None, None, 3, users_root=root)
        self.assertIn("e1", ids)
        # invalidated 卡不参与召回（load_cards 已过滤，尺子必须继承该语义）
        self.assertNotIn("e3", ids)
        # 已固化进管线的卡同样不注入（promoted_to_code ≠ invalidated：对的，只是重复供给）
        self.assertNotIn("e4", ids)

    def test_k_limits_returned_cards(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_cards(root)
            ids = experience_cards_retriever("帮我深挖飞凯材料", None, None, 1, users_root=root)
        self.assertLessEqual(len(ids), 1)


class KbRagRetrieverTests(unittest.TestCase):
    def _hit(self, rel: str) -> SimpleNamespace:
        return SimpleNamespace(file_path=rel)

    def test_dedup_order_and_trim_to_k(self) -> None:
        res = SimpleNamespace(
            ok=True,
            warning="",
            hits=[self._hit("wiki/a.md"), self._hit("wiki/a.md"),
                  self._hit("wiki/b.md"), self._hit("wiki/c.md")],
        )
        with patch("intelligence.services.kb_rag.retrieve", return_value=res) as mocked:
            ids = kb_rag_retriever("q", None, None, 2, kb_wiki="/tmp/wiki")
        self.assertEqual(ids, ["wiki/a.md", "wiki/b.md"])
        self.assertEqual(mocked.call_args.kwargs["k"], 2)

    def test_unavailable_channel_degrades_to_empty(self) -> None:
        res = SimpleNamespace(ok=False, warning="索引不可用", hits=[])
        with patch("intelligence.services.kb_rag.retrieve", return_value=res):
            ids = kb_rag_retriever("q", None, None, 3, kb_wiki="/tmp/wiki")
        self.assertEqual(ids, [])


class ChannelFilterTests(unittest.TestCase):
    def test_channel_filter_and_default_channel(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "cases.jsonl"
            p.write_text(
                '{"case_id": "m1", "query": "液冷", "relevant": ["j1"]}\n'
                '{"case_id": "k1", "channel": "kb_rag", "query": "液冷", "relevant": ["wiki/a.md"]}\n',
                encoding="utf-8",
            )
            um = load_cases(p, channel="user_memory")
            kb = load_cases(p, channel="kb_rag")
            all_cases = load_cases(p)
        # 未写 channel 的 case 按 user_memory 算（兼容既有夹具）
        self.assertEqual([c["case_id"] for c in um], ["m1"])
        self.assertEqual([c["case_id"] for c in kb], ["k1"])
        self.assertEqual(len(all_cases), 2)


class CasesV1Tests(unittest.TestCase):
    """钉住 S4 标注集本体：20 条、通道配比、每条带标注理由与出处。"""

    CASES = Path(__file__).resolve().parents[1] / "eval" / "cases" / "retrieval_recall_v1.jsonl"

    def test_v1_shape_and_provenance(self) -> None:
        cases = load_cases(self.CASES)
        self.assertEqual(len(cases), 20)
        by_channel: dict[str, int] = {}
        for c in cases:
            by_channel[str(c.get("channel"))] = by_channel.get(str(c.get("channel")), 0) + 1
            self.assertTrue(str(c.get("note") or "").strip(), c["case_id"])
            self.assertTrue(str(c.get("source_ref") or "").strip(), c["case_id"])
        self.assertEqual(
            by_channel,
            {"user_memory": 15, "experience_cards": 3, "kb_rag": 2},
        )


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
    def test_bundled_fixture_is_runnable_and_labels_are_truthful(self) -> None:
        # 夹具标注必须全部真实（该召回的才标 relevant）：错误标注会永久拉低宏平均，
        # 后来者会把 66% 当成检索坏了。「尺子能测出 miss」由下面的合成 case 证明。
        from intelligence.eval.retrieval_recall import FIXTURE_CASES, FIXTURE_LEDGERS

        cases = load_cases(FIXTURE_CASES)
        self.assertGreaterEqual(len(cases), 2)
        report = evaluate_cases(
            cases, user_memory_retriever, ks=(5,), users_root=FIXTURE_LEDGERS
        )
        for row in report["per_case"]:
            self.assertEqual(row["recall_at"][5], 1.0, row["case_id"])
        self.assertEqual(report["recall_at"][5], 1.0)

    def test_ruler_detects_miss_with_synthetic_wrong_label(self) -> None:
        # 故意错标（无关题材标成 relevant）→ 尺子必须读出 0 召回。
        from intelligence.eval.retrieval_recall import FIXTURE_LEDGERS

        report = evaluate_cases(
            [{"case_id": "syn-miss", "query": "光模块份额", "theme": "光模块",
              "relevant": ["j-liquid-1"]}],
            user_memory_retriever,
            ks=(5,),
            users_root=FIXTURE_LEDGERS,
        )
        self.assertEqual(report["per_case"][0]["recall_at"][5], 0.0)
        self.assertIn("j-liquid-1", report["per_case"][0]["missed"][5])


if __name__ == "__main__":
    unittest.main()
