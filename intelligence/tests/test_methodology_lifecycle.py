"""候选经验生命周期（终局 spec §5.1、§7.10；V1「候选经验队列」）。

用合成收据：真库里 `methodology/receipts/` 是运行时产物、没进仓（实测 0 份），
拿真收据测就只能测到「没有收据」那一档。而这里要钉的恰恰是**晋升与掉档的规则**。

三条不肯让步的门，各自单独钉：
1. 窗口必须真的往后走——同一段数据跑三遍只算一步；
2. 共享层不能由 agent 批准——统计再漂亮也推不出 shared_*；
3. 过门之后仍会掉下来——新窗口证伪 → invalidated。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.methodology_backtest import lifecycle
from intelligence.services.methodology_backtest.receipts import RECEIPT_SCHEMA

RULE = {"rule_id": "r1", "sharing": "private", "owner": "alice"}


def _write(root: Path, rule_id: str, *, start: str, end: str, verdict: str, at: str) -> None:
    folder = root / f"{rule_id}@v1"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{at[:10]}-{verdict}.json").write_text(
        json.dumps(
            {
                "schema_version": RECEIPT_SCHEMA,
                "generated_at": at,
                "rule": {"rule_id": rule_id, "ref": f"{rule_id}@v1"},
                "window": {"start": start, "end": end},
                "stats": {"verdict": verdict},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _steps(root: Path, *specs) -> list[lifecycle.Step]:
    for i, (start, end, verdict) in enumerate(specs):
        _write(root, "r1", start=start, end=end, verdict=verdict, at=f"2026-0{i + 1}-01T00:00:00")
    return lifecycle.load_steps(root, "r1")


class Ladder(unittest.TestCase):
    def test_no_receipt_is_candidate(self) -> None:
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(RULE, lifecycle.load_steps(Path(t), "r1"))
            self.assertEqual(s.state, "candidate")
            self.assertFalse(s.in_method_library)
            self.assertIn("还没跑过", s.blocked_by or "")

    def test_one_supported_window_is_discovery(self) -> None:
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(RULE, _steps(Path(t), ("2026-01-01", "2026-02-01", "supported")))
            self.assertEqual(s.state, "discovery_passed")
            self.assertIn("时间外验证", s.blocked_by or "")

    def test_two_advancing_windows_is_validation(self) -> None:
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(
                RULE,
                _steps(
                    Path(t),
                    ("2026-01-01", "2026-02-01", "supported"),
                    ("2026-03-01", "2026-04-01", "supported"),
                ),
            )
            self.assertEqual(s.state, "validation_passed")
            self.assertIn("Holdout", s.blocked_by or "")

    def test_three_advancing_windows_reach_personal_method(self) -> None:
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(
                RULE,
                _steps(
                    Path(t),
                    ("2026-01-01", "2026-02-01", "supported"),
                    ("2026-03-01", "2026-04-01", "supported"),
                    ("2026-05-01", "2026-06-01", "supported"),
                ),
            )
            self.assertEqual(s.state, "personal_method")
            self.assertTrue(s.in_method_library)
            self.assertEqual(len(s.evidence), 3, "三段收据都要挂上，状态转移必须附带收据")


class WindowsMustActuallyAdvance(unittest.TestCase):
    """门 1：只看「跑了三次」不看窗口，等于把同一段数据数了三遍。"""

    def test_same_window_thrice_is_still_discovery(self) -> None:
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(
                RULE,
                _steps(
                    Path(t),
                    ("2026-01-01", "2026-02-01", "supported"),
                    ("2026-01-01", "2026-02-01", "supported"),
                    ("2026-01-01", "2026-02-01", "supported"),
                ),
            )
            self.assertEqual(s.state, "discovery_passed")

    def test_overlapping_window_does_not_count(self) -> None:
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(
                RULE,
                _steps(
                    Path(t),
                    ("2026-01-01", "2026-03-01", "supported"),
                    ("2026-02-01", "2026-04-01", "supported"),  # 与上一段重叠
                ),
            )
            self.assertEqual(s.state, "discovery_passed")

    def test_earlier_window_does_not_count(self) -> None:
        """倒着跑一段更早的数据不是验证，是又看了一遍历史。"""
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(
                RULE,
                _steps(
                    Path(t),
                    ("2026-05-01", "2026-06-01", "supported"),
                    ("2026-01-01", "2026-02-01", "supported"),
                ),
            )
            self.assertEqual(s.state, "discovery_passed")


class SharedLayerNeedsAHuman(unittest.TestCase):
    """门 2：spec §7.10——不得由 agent 自动批准。"""

    def _three_pass(self, t: str):
        return _steps(
            Path(t),
            ("2026-01-01", "2026-02-01", "supported"),
            ("2026-03-01", "2026-04-01", "supported"),
            ("2026-05-01", "2026-06-01", "supported"),
        )

    def test_without_approval_stops_at_personal(self) -> None:
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(RULE, self._three_pass(t))
            self.assertEqual(s.state, "personal_method")
            self.assertTrue(s.needs_human)
            self.assertNotIn(s.state, lifecycle.HUMAN_ONLY)

    def test_approval_without_signature_is_rejected(self) -> None:
        """没有署名的批准不算批准。"""
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(
                RULE, self._three_pass(t),
                human_approval={"state": "shared_method", "approved_by": "  "},
            )
            self.assertEqual(s.state, "personal_method")
            self.assertIn("approved_by", s.blocked_by or "")

    def test_approval_cannot_forge_a_non_human_state(self) -> None:
        """人工记录只能把它送进 shared_*；拿它跳到别的档一律忽略。"""
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(
                RULE, self._three_pass(t),
                human_approval={"state": "holdout_passed", "approved_by": "a77"},
            )
            self.assertEqual(s.state, "personal_method")

    def test_signed_approval_promotes(self) -> None:
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(
                RULE, self._three_pass(t),
                human_approval={"state": "shared_candidate", "approved_by": "a77"},
            )
            self.assertEqual(s.state, "shared_candidate")
            self.assertTrue(any(e.startswith("human:") for e in s.evidence), "批准人要留痕")
            self.assertIsNone(s.blocked_by)

    def test_approval_does_nothing_before_the_gates(self) -> None:
        """还没过三段门，签字也不该生效——人工审阅是加在统计之后，不是替代它。"""
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(
                RULE, _steps(Path(t), ("2026-01-01", "2026-02-01", "supported")),
                human_approval={"state": "shared_method", "approved_by": "a77"},
            )
            self.assertEqual(s.state, "discovery_passed")


class FallingOut(unittest.TestCase):
    """门 3：方法库不是一进永进（spec §6.3 失效监测）。"""

    def test_refuted_after_method_is_invalidated(self) -> None:
        with TemporaryDirectory() as t:
            root = Path(t)
            s = lifecycle.derive_state(
                RULE,
                _steps(
                    root,
                    ("2026-01-01", "2026-02-01", "supported"),
                    ("2026-03-01", "2026-04-01", "supported"),
                    ("2026-05-01", "2026-06-01", "supported"),
                    ("2026-07-01", "2026-08-01", "refuted"),
                ),
            )
            self.assertEqual(s.state, "invalidated")
            self.assertFalse(s.in_method_library)

    def test_refuted_before_method_is_contradicted(self) -> None:
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(
                RULE,
                _steps(
                    Path(t),
                    ("2026-01-01", "2026-02-01", "supported"),
                    ("2026-03-01", "2026-04-01", "refuted"),
                ),
            )
            self.assertEqual(s.state, "contradicted")

    def test_insufficient_is_its_own_state_not_pending(self) -> None:
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(RULE, _steps(Path(t), ("2026-01-01", "2026-02-01", "insufficient_n")))
            self.assertEqual(s.state, "insufficient")
            self.assertIn("不出比率", s.blocked_by or "")

    def test_never_supported_stays_candidate(self) -> None:
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(
                RULE, _steps(Path(t), ("2026-01-01", "2026-02-01", "not_distinguishable"))
            )
            self.assertEqual(s.state, "candidate")
            self.assertFalse(s.in_method_library)


class QueueRendering(unittest.TestCase):
    def test_render_puts_the_least_advanced_first(self) -> None:
        states = [
            lifecycle.MethodState("adv", "personal_method", "private", "a", (), None),
            lifecycle.MethodState("new", "candidate", "private", "a", (), "还没跑"),
        ]
        text = lifecycle.render_queue(states)
        self.assertLess(text.index("new"), text.index("adv"), "最该动手的排前面")
        self.assertIn("已进方法库 1 条", text)

    def test_empty_queue_says_how_to_add(self) -> None:
        self.assertIn("propose", lifecycle.render_queue([]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
