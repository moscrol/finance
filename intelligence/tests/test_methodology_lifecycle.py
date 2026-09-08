"""候选经验生命周期（终局 spec §5.1、§7.10；V1「候选经验队列」；工单 #42 晋升认证）。

用合成收据：真库里 `methodology/receipts/` 是运行时产物、没进仓（实测 0 份），
拿真收据测就只能测到「没有收据」那一档。而这里要钉的恰恰是**晋升与掉档的规则**。

三条不肯让步的门，各自单独钉：
1. 窗口必须真的往后走——同一段数据跑三遍只算一步；
2. 共享层不能由 agent 批准——统计再漂亮也推不出 shared_*；
3. 过门之后仍会掉下来——新窗口证伪 → invalidated。

工单 #42 加的认证门（补强 spec OPT-04 五种「不得误晋升」夹具）：
4. 同身份——不同 rule 版本 / 内容 hash / label_version 的收据不拼一条链；
5. 预声明阶段——没写 `declared_stage` 的收据是历史观察，不是晋升证据；
6. 顶层最终结论——BH 校正后的 `verdict` 说了算，`stats.verdict` 只解释；
7. 失效开新轮次——refuted 之后一份 supported 不能复活方法；
8. 同级不许换窗——同一阶段两个窗口 = 事后挑窗；同窗重跑取最新一份。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.methodology_backtest import lifecycle
from intelligence.services.methodology_backtest.receipts import RECEIPT_SCHEMA

RULE = {"rule_id": "r1", "version": 1, "sharing": "private", "owner": "alice"}
SHA_V1 = "sha-v1"
STAGES = ("discovery", "validation", "holdout")


def _write(
    root: Path,
    rule_id: str,
    *,
    start: str,
    end: str,
    verdict: str,
    at: str,
    stage: str | None,
    version: int = 1,
    sha256: str | None = SHA_V1,
    label_version: str | None = "v3",
    internal_verdict: str | None = None,
    filename: str | None = None,
) -> Path:
    """写一份**认证过**的合成收据：顶层最终结论 + 规则身份 + 声明阶段。

    ``internal_verdict`` 是 ``stats.verdict``（原始读数），默认与最终结论相同；
    scan 模式下 BH 校正会让两者分叉，这正是门 6 要钉的形状。
    """
    folder = root / f"{rule_id}@v{version}"
    folder.mkdir(parents=True, exist_ok=True)
    name = filename or f"{at[:10]}-{stage or 'nostage'}-{verdict}.json"
    path = folder / name
    rule_block = {"rule_id": rule_id, "version": version, "ref": f"{rule_id}@v{version}"}
    if sha256 is not None:
        rule_block["sha256"] = sha256
    path.write_text(
        json.dumps(
            {
                "schema_version": RECEIPT_SCHEMA,
                "generated_at": at,
                "rule": rule_block,
                "window": {"start": start, "end": end},
                "verdict": verdict,
                "declared_stage": stage,
                "stats": {"verdict": internal_verdict or verdict},
                "conditions": {"label_version": label_version},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _steps(root: Path, *specs) -> list[lifecycle.Step]:
    """按位置声明阶段：第 1 份 discovery、第 2 份 validation、第 3 份 holdout，之后是失效监测（不声明）。"""
    for i, (start, end, verdict) in enumerate(specs):
        stage = STAGES[i] if i < len(STAGES) else None
        _write(root, "r1", start=start, end=end, verdict=verdict, at=f"2026-0{i + 1}-01T00:00:00", stage=stage)
    return lifecycle.load_steps(root, "r1")


THREE_PASS = (
    ("2026-01-01", "2026-02-01", "supported"),
    ("2026-03-01", "2026-04-01", "supported"),
    ("2026-05-01", "2026-06-01", "supported"),
)


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
            self.assertIn("validation", s.blocked_by or "")

    def test_two_advancing_windows_is_validation(self) -> None:
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(RULE, _steps(Path(t), *THREE_PASS[:2]))
            self.assertEqual(s.state, "validation_passed")
            self.assertIn("holdout", s.blocked_by or "")

    def test_three_advancing_windows_reach_personal_method(self) -> None:
        """合法晋升必须仍然成立——门不能修成「所有方法都过不了」。"""
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(RULE, _steps(Path(t), *THREE_PASS))
            self.assertEqual(s.state, "personal_method")
            self.assertTrue(s.in_method_library)
            self.assertEqual(len(s.evidence), 3, "三段收据都要挂上，状态转移必须附带收据")
            self.assertEqual(s.validation_cycle, 1)
            self.assertEqual(s.history_receipts, 0)


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
        return _steps(Path(t), *THREE_PASS)

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
        """失效监测那份收据**没有**声明阶段——证伪不需要预注册，同身份的 refuted 就生效。"""
        with TemporaryDirectory() as t:
            s = lifecycle.derive_state(
                RULE,
                _steps(Path(t), *THREE_PASS, ("2026-07-01", "2026-08-01", "refuted")),
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


class SameIdentityOnly(unittest.TestCase):
    """门 4（OPT-04）：三个版本各一次成功，不是一条方法过了三段门，是三条候选各过了一段。"""

    def _three_versions(self, root: Path) -> None:
        for i, ((start, end, verdict), version) in enumerate(zip(THREE_PASS, (1, 2, 3))):
            _write(
                root, "r1", start=start, end=end, verdict=verdict, at=f"2026-0{i + 1}-01T00:00:00",
                stage=STAGES[i], version=version, sha256=f"sha-v{version}",
            )

    def test_three_versions_each_supported_do_not_chain(self) -> None:
        with TemporaryDirectory() as t:
            root = Path(t)
            self._three_versions(root)
            steps = lifecycle.load_steps(root, "r1")
            self.assertEqual(len(steps), 3, "load_steps 仍读全部版本——过滤发生在推导层，历史不丢")
            for version in (1, 2, 3):
                s = lifecycle.derive_state({**RULE, "version": version}, steps)
                self.assertNotEqual(s.state, "personal_method", f"v{version} 不得靠别的版本的收据晋升")
                self.assertFalse(s.in_method_library)
                self.assertEqual(s.history_receipts, 2, "另两个版本的收据保留为历史，不计入本轮")

    def test_without_rule_version_identity_change_still_splits(self) -> None:
        """规则文档没写 version 时不能退化成旧行为：身份变化仍切轮次。"""
        with TemporaryDirectory() as t:
            root = Path(t)
            self._three_versions(root)
            s = lifecycle.derive_state({"rule_id": "r1"}, lifecycle.load_steps(root, "r1"))
            self.assertNotEqual(s.state, "personal_method")
            self.assertFalse(s.in_method_library)

    def test_content_change_without_version_bump_is_a_new_cycle(self) -> None:
        """改了规则文件没升 version：sha256 变了，旧收据属旧内容。"""
        with TemporaryDirectory() as t:
            root = Path(t)
            for i, (start, end, verdict) in enumerate(THREE_PASS):
                sha = "sha-edited" if i == 2 else SHA_V1
                _write(root, "r1", start=start, end=end, verdict=verdict, at=f"2026-0{i + 1}-01T00:00:00", stage=STAGES[i], sha256=sha)
            steps = lifecycle.load_steps(root, "r1")
            by_sha = lifecycle.derive_state(RULE, steps, rule_sha256="sha-edited")
            self.assertNotEqual(by_sha.state, "personal_method")
            self.assertEqual(by_sha.history_receipts, 2)
            self.assertIn("discovery", by_sha.blocked_by or "")
            by_split = lifecycle.derive_state(RULE, steps)
            self.assertNotEqual(by_split.state, "personal_method")

    def test_label_version_change_splits_cycle(self) -> None:
        """标签口径变了没有兼容声明 → 新轮次（OPT-04「标签或来源口径变动须有兼容声明，否则开启新轮次」）。"""
        with TemporaryDirectory() as t:
            root = Path(t)
            for i, (start, end, verdict) in enumerate(THREE_PASS):
                _write(
                    root, "r1", start=start, end=end, verdict=verdict, at=f"2026-0{i + 1}-01T00:00:00",
                    stage=STAGES[i], label_version="v4" if i == 2 else "v3",
                )
            s = lifecycle.derive_state(RULE, lifecycle.load_steps(root, "r1"))
            self.assertNotEqual(s.state, "personal_method")
            self.assertIn("label_version", s.blocked_by or "")


class FinalVerdictWins(unittest.TestCase):
    """门 6（OPT-04）：读顶层最终结论；内部原始读数只用来解释。"""

    def test_bh_downgraded_holdout_does_not_promote(self) -> None:
        with TemporaryDirectory() as t:
            root = Path(t)
            for i, (start, end, verdict) in enumerate(THREE_PASS[:2]):
                _write(root, "r1", start=start, end=end, verdict=verdict, at=f"2026-0{i + 1}-01T00:00:00", stage=STAGES[i])
            _write(
                root, "r1", start="2026-05-01", end="2026-06-01", at="2026-03-01T00:00:00", stage="holdout",
                verdict="not_distinguishable", internal_verdict="supported",
            )
            s = lifecycle.derive_state(RULE, lifecycle.load_steps(root, "r1"))
            self.assertEqual(s.state, "validation_passed")
            self.assertFalse(s.in_method_library)
            self.assertIn("内部", s.blocked_by or "", "要告诉用户：原始读数 supported 但最终结论没过")

    def test_receipt_without_final_verdict_is_not_evidence(self) -> None:
        """旧收据只有 stats.verdict、没有顶层 verdict：保留为历史观察，不自动补一个「通过」身份。"""
        with TemporaryDirectory() as t:
            root = Path(t)
            for i, (start, end, verdict) in enumerate(THREE_PASS):
                p = _write(root, "r1", start=start, end=end, verdict=verdict, at=f"2026-0{i + 1}-01T00:00:00", stage=STAGES[i])
                doc = json.loads(p.read_text(encoding="utf-8"))
                del doc["verdict"]
                p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            s = lifecycle.derive_state(RULE, lifecycle.load_steps(root, "r1"))
            self.assertEqual(s.state, "candidate")
            self.assertEqual(s.history_receipts, 3)


class DeclaredStagesOnly(unittest.TestCase):
    """门 5 / 门 8（OPT-04）：不能从任意历史收据里事后挑三段成功窗口。"""

    def test_undeclared_receipts_are_history_not_evidence(self) -> None:
        with TemporaryDirectory() as t:
            root = Path(t)
            for i, (start, end, verdict) in enumerate(THREE_PASS):
                _write(root, "r1", start=start, end=end, verdict=verdict, at=f"2026-0{i + 1}-01T00:00:00", stage=None)
            s = lifecycle.derive_state(RULE, lifecycle.load_steps(root, "r1"))
            self.assertEqual(s.state, "candidate")
            self.assertFalse(s.in_method_library)
            self.assertEqual(s.history_receipts, 3)
            self.assertIn("--stage", s.blocked_by or "", "要给出重跑指引")

    def test_window_shopping_within_a_stage_is_blocked(self) -> None:
        """validation 跑了两个窗口，一个没过一个过了——挑过的那个 = 事后挑窗。"""
        with TemporaryDirectory() as t:
            root = Path(t)
            _write(root, "r1", start="2026-01-01", end="2026-02-01", verdict="supported", at="2026-01-01T00:00:00", stage="discovery")
            _write(root, "r1", start="2026-03-01", end="2026-04-01", verdict="not_distinguishable", at="2026-02-01T00:00:00", stage="validation")
            _write(root, "r1", start="2026-04-02", end="2026-05-01", verdict="supported", at="2026-03-01T00:00:00", stage="validation")
            s = lifecycle.derive_state(RULE, lifecycle.load_steps(root, "r1"))
            self.assertEqual(s.state, "discovery_passed")
            self.assertIn("挑窗", s.blocked_by or "")

    def test_same_window_rerun_takes_the_latest_verdict(self) -> None:
        """同窗重跑不是挑窗（数据修订后重算是正当的），但以**最新**一份为准，不能挑好的那次。"""
        with TemporaryDirectory() as t:
            root = Path(t)
            for i, (start, end, verdict) in enumerate(THREE_PASS[:2]):
                _write(root, "r1", start=start, end=end, verdict=verdict, at=f"2026-0{i + 1}-01T00:00:00", stage=STAGES[i])
            _write(root, "r1", start="2026-05-01", end="2026-06-01", verdict="supported", at="2026-03-01T00:00:00", stage="holdout")
            _write(root, "r1", start="2026-05-01", end="2026-06-01", verdict="not_distinguishable", at="2026-03-02T00:00:00", stage="holdout")
            s = lifecycle.derive_state(RULE, lifecycle.load_steps(root, "r1"))
            self.assertEqual(s.state, "validation_passed", "修订后最新一份没过，就是没过")

    def test_stage_order_is_enforced_even_if_declared(self) -> None:
        """声明了 holdout 但没有 discovery / validation：阶梯从第一级开始缺，不是跳级。"""
        with TemporaryDirectory() as t:
            root = Path(t)
            _write(root, "r1", start="2026-05-01", end="2026-06-01", verdict="supported", at="2026-03-01T00:00:00", stage="holdout")
            s = lifecycle.derive_state(RULE, lifecycle.load_steps(root, "r1"))
            self.assertEqual(s.state, "candidate")
            self.assertIn("discovery", s.blocked_by or "")


class InvalidationOpensANewCycle(unittest.TestCase):
    """门 7（OPT-04）：失效后一个新成功不能复活；旧轮次的成功不带进新轮次。"""

    def test_one_success_after_invalidation_does_not_revive(self) -> None:
        with TemporaryDirectory() as t:
            root = Path(t)
            _steps(root, *THREE_PASS, ("2026-07-01", "2026-08-01", "refuted"))
            _write(root, "r1", start="2026-09-01", end="2026-10-01", verdict="supported", at="2026-05-01T00:00:00", stage="holdout")
            s = lifecycle.derive_state(RULE, lifecycle.load_steps(root, "r1"))
            self.assertNotEqual(s.state, "personal_method")
            self.assertFalse(s.in_method_library)
            self.assertEqual(s.validation_cycle, 2)
            self.assertIn("轮次", s.blocked_by or "")

    def test_new_cycle_can_pass_all_three_gates_again(self) -> None:
        """复活的正路：新轮次自己再走三段门。"""
        with TemporaryDirectory() as t:
            root = Path(t)
            _steps(root, *THREE_PASS, ("2026-07-01", "2026-08-01", "refuted"))
            for i, (start, end) in enumerate((("2026-09-01", "2026-10-01"), ("2026-11-01", "2026-12-01"), ("2027-01-01", "2027-02-01"))):
                _write(root, "r1", start=start, end=end, verdict="supported", at=f"2026-0{i + 5}-01T00:00:00", stage=STAGES[i])
            s = lifecycle.derive_state(RULE, lifecycle.load_steps(root, "r1"))
            self.assertEqual(s.state, "personal_method")
            self.assertEqual(s.validation_cycle, 2)
            self.assertEqual(len(s.evidence), 3, "只挂新轮次的三份，旧轮次的成功不算")


class Idempotence(unittest.TestCase):
    """OPT-04「晋升写入幂等」在推导式实现里的形状：同一份收据重复投递只发生一次状态转移。"""

    def test_duplicate_receipt_delivery_changes_nothing(self) -> None:
        with TemporaryDirectory() as t:
            root = Path(t)
            _steps(root, *THREE_PASS)
            _write(
                root, "r1", start="2026-05-01", end="2026-06-01", verdict="supported", at="2026-03-01T00:00:00",
                stage="holdout", filename="2026-03-01-holdout-supported-dup.json",
            )
            steps = lifecycle.load_steps(root, "r1")
            self.assertEqual(len(steps), 4)
            first = lifecycle.derive_state(RULE, steps)
            second = lifecycle.derive_state(RULE, steps)
            self.assertEqual(first, second, "纯函数：同输入同输出")
            self.assertEqual(first.state, "personal_method")
            self.assertEqual(len(first.evidence), 3, "重复投递的那份不额外挂证据")

    def test_duplicate_discovery_does_not_count_as_validation(self) -> None:
        with TemporaryDirectory() as t:
            root = Path(t)
            _write(root, "r1", start="2026-01-01", end="2026-02-01", verdict="supported", at="2026-01-01T00:00:00", stage="discovery")
            _write(root, "r1", start="2026-01-01", end="2026-02-01", verdict="supported", at="2026-01-01T00:00:00", stage="discovery", filename="dup.json")
            s = lifecycle.derive_state(RULE, lifecycle.load_steps(root, "r1"))
            self.assertEqual(s.state, "discovery_passed")


class QueueRendering(unittest.TestCase):
    def test_render_puts_the_least_advanced_first(self) -> None:
        states = [
            lifecycle.MethodState("adv", "personal_method", "private", "a", (), None),
            lifecycle.MethodState("new", "candidate", "private", "a", (), "还没跑"),
        ]
        text = lifecycle.render_queue(states)
        self.assertLess(text.index("new"), text.index("adv"), "最该动手的排前面")
        self.assertIn("已进方法库 1 条", text)

    def test_render_shows_cycle_and_history(self) -> None:
        states = [
            lifecycle.MethodState("r", "candidate", "private", "a", (), "上一轮次已失效", validation_cycle=2, history_receipts=4),
        ]
        text = lifecycle.render_queue(states)
        self.assertIn("轮次 2", text)
        self.assertIn("历史收据 4", text)

    def test_to_dict_carries_certification_fields(self) -> None:
        s = lifecycle.MethodState("r", "candidate", "private", "a", (), None, validation_cycle=1, history_receipts=0)
        d = s.to_dict()
        self.assertEqual((d["validation_cycle"], d["history_receipts"]), (1, 0))

    def test_empty_queue_says_how_to_add(self) -> None:
        self.assertIn("propose", lifecycle.render_queue([]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
