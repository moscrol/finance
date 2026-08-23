from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence import userspace
from intelligence.services import activation_receipt, perspective_lab
from intelligence.services.activation_receipt import ActivationRecord


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


class PerspectiveActivationTests(unittest.TestCase):
    def test_f1_neutral_is_inactive_not_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            text, record = perspective_lab.activate_runtime_perspective(
                us,
                mode=perspective_lab.PERSPECTIVE_MODE_NEUTRAL,
                perspective_ids=(),
                query="行情怎么看",
            )
        self.assertEqual(text, "")
        self.assertEqual(record.status, "inactive")
        self.assertEqual(record.reason, "not_requested")
        self.assertFalse(record.injected)
        self.assertEqual(record.display_names, ())
        self.assertEqual(record.prompt_hash, "")
        self.assertEqual(perspective_lab.runtime_answer_header(record), "")
        self.assertEqual(perspective_lab.runtime_fallback_notice(record), "")
        self.assertIn("数据中立", perspective_lab.runtime_neutral_banner())

    def test_f2_single_success_freezes_display_names_from_same_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(
                us, "spt_molmansk", display_name="SPT-Molmansk", ptype="blogger"
            )
            text, record = perspective_lab.activate_runtime_perspective(
                us,
                mode=perspective_lab.PERSPECTIVE_MODE_SINGLE,
                perspective_ids=("spt_molmansk",),
                query="行情怎么看",
            )
        self.assertTrue(text)
        self.assertEqual(record.status, "injected")
        self.assertTrue(record.injected)
        self.assertEqual(record.display_names, ("SPT-Molmansk",))
        self.assertEqual(record.prompt_hash, "")
        header = perspective_lab.runtime_answer_header(record)
        self.assertIn("SPT-Molmansk", header)
        self.assertEqual(perspective_lab.runtime_fallback_notice(record), "")

    def test_f3_build_failure_does_not_print_shop_name(self) -> None:
        """Patch ``build_runtime_context`` only. Do not delete the profile.

        ``validate`` / ``load_profile`` share the same file. Deleting it collapses
        both paths and misses the real hole: header used to ``load_profile``
        after prompt build returned "".
        """

        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(
                us, "spt_molmansk", display_name="SPT-Molmansk", ptype="blogger"
            )
            still_on_disk = perspective_lab.load_profile(us, "spt_molmansk")
            self.assertEqual(still_on_disk["display_name"], "SPT-Molmansk")
            with mock.patch.object(
                perspective_lab,
                "build_runtime_context",
                side_effect=FileNotFoundError("articles gone"),
            ):
                text, record = perspective_lab.activate_runtime_perspective(
                    us,
                    mode=perspective_lab.PERSPECTIVE_MODE_SINGLE,
                    perspective_ids=("spt_molmansk",),
                    query="行情怎么看",
                )
            self.assertEqual(
                perspective_lab.load_profile(us, "spt_molmansk")["display_name"],
                "SPT-Molmansk",
            )

        self.assertEqual(text, "")
        self.assertEqual(record.status, "degraded")
        self.assertEqual(record.reason, "build_failed")
        self.assertFalse(record.injected)
        self.assertEqual(record.display_names, ())
        self.assertEqual(record.prompt_hash, "")
        header = perspective_lab.runtime_answer_header(record)
        notice = perspective_lab.runtime_fallback_notice(record)
        self.assertEqual(header, "")
        self.assertTrue(notice)
        visible = f"{header}\n{notice}"
        self.assertNotIn("SPT-Molmansk", visible)
        self.assertFalse(
            activation_receipt.visible_text_leaks_brand(visible, record)
        )

    def test_f4_empty_prompt_from_successful_build_is_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(
                us, "spt_molmansk", display_name="SPT-Molmansk", ptype="blogger"
            )
            empty = perspective_lab.RuntimePerspectiveContext(
                mode=perspective_lab.PERSPECTIVE_MODE_SINGLE,
                perspective_ids=("spt_molmansk",),
                display_names=("SPT-Molmansk",),
                prompt="",
            )
            with mock.patch.object(
                perspective_lab, "build_runtime_context", return_value=empty
            ):
                text, record = perspective_lab.activate_runtime_perspective(
                    us,
                    mode=perspective_lab.PERSPECTIVE_MODE_SINGLE,
                    perspective_ids=("spt_molmansk",),
                    query="行情怎么看",
                )
        self.assertEqual(text, "")
        self.assertEqual(record.status, "degraded")
        self.assertEqual(record.reason, "empty_prompt")
        self.assertEqual(record.display_names, ())
        self.assertEqual(perspective_lab.runtime_answer_header(record), "")

    def test_f5_compare_success_injects_frozen_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(
                us, "spt_a", display_name="SPT-A", ptype="blogger"
            )
            perspective_lab.init_perspective(
                us, "spt_b", display_name="SPT-B", ptype="blogger"
            )
            text, record = perspective_lab.activate_runtime_perspective(
                us,
                mode=perspective_lab.PERSPECTIVE_MODE_COMPARE,
                perspective_ids=("spt_a", "spt_b"),
                query="行情怎么看",
            )
        self.assertTrue(text)
        self.assertEqual(record.status, "injected")
        self.assertEqual(record.resolved, ("spt_a", "spt_b"))
        self.assertEqual(record.display_names, ("SPT-A", "SPT-B"))
        header = perspective_lab.runtime_answer_header(record)
        self.assertIn("SPT-A", header)
        self.assertIn("SPT-B", header)

    def test_f5_compare_missing_profile_is_degraded_not_partial(self) -> None:
        """validate/load fail closed. Partial resolve is not a current seam."""

        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(
                us, "spt_a", display_name="SPT-A", ptype="blogger"
            )
            text, record = perspective_lab.activate_runtime_perspective(
                us,
                mode=perspective_lab.PERSPECTIVE_MODE_COMPARE,
                perspective_ids=("spt_a", "ghost"),
                query="行情怎么看",
            )
        self.assertEqual(text, "")
        self.assertEqual(record.status, "degraded")
        self.assertIn(record.reason, {"build_failed", "profile_missing"})
        self.assertEqual(perspective_lab.runtime_answer_header(record), "")


class BaselineActivationTests(unittest.TestCase):
    def test_f6_enabled_nonempty_guidance_is_injected(self) -> None:
        record = activation_receipt.activate_reading_baseline(
            "- [SPT-A11] 双红要同时看量价",
            ("SPT-A11",),
            enabled=True,
        )
        self.assertEqual(record.status, "injected")
        self.assertEqual(record.resolved, ("SPT-A11",))
        self.assertTrue(record.injected)
        self.assertEqual(record.prompt_hash, "")

    def test_f7_disabled_is_inactive_switch_off(self) -> None:
        record = activation_receipt.activate_reading_baseline(
            "- [SPT-A11] x",
            ("SPT-A11",),
            enabled=False,
        )
        self.assertEqual(record.status, "inactive")
        self.assertEqual(record.reason, "switch_off")
        self.assertEqual(record.resolved, ())

    def test_f8_enabled_empty_guidance_is_degraded(self) -> None:
        record = activation_receipt.activate_reading_baseline(
            "",
            (),
            enabled=True,
        )
        self.assertEqual(record.status, "degraded")
        self.assertEqual(record.reason, "no_rules")

    def test_f9_pending_ids_do_not_enter_resolved(self) -> None:
        record = activation_receipt.activate_reading_baseline(
            "- [LIVE] keep",
            ("LIVE", "PENDING"),
            enabled=True,
            pending_ids=("PENDING",),
        )
        self.assertEqual(record.resolved, ("LIVE",))
        self.assertNotIn("PENDING", record.resolved)


class SealTests(unittest.TestCase):
    def test_f3b_hash_after_protocol_assignment_not_at_activate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(
                us, "spt_molmansk", display_name="SPT-Molmansk", ptype="blogger"
            )
            text, record = perspective_lab.activate_runtime_perspective(
                us,
                mode=perspective_lab.PERSPECTIVE_MODE_SINGLE,
                perspective_ids=("spt_molmansk",),
                query="行情怎么看",
            )
        self.assertEqual(record.prompt_hash, "")
        field_bytes = text
        sealed = activation_receipt.seal_prompt_hash(record, field_bytes)
        self.assertEqual(
            sealed.prompt_hash,
            activation_receipt.field_digest(field_bytes),
        )

    def test_seal_rejects_injected_empty_field(self) -> None:
        record = ActivationRecord(
            kind="perspective",
            requested="single:x",
            resolved=("x",),
            display_names=("X",),
            renderer="test",
            prompt_hash="",
            injected=True,
            status="injected",
            reason="",
        )
        with self.assertRaises(ValueError):
            activation_receipt.seal_prompt_hash(record, "")

    def test_active_runtime_prompt_delegates_without_second_logic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(
                us, "spt_molmansk", display_name="SPT-Molmansk", ptype="blogger"
            )
            text, record = perspective_lab.activate_runtime_perspective(
                us,
                mode=perspective_lab.PERSPECTIVE_MODE_SINGLE,
                perspective_ids=("spt_molmansk",),
                query="行情怎么看",
            )
            delegated = perspective_lab.active_runtime_prompt(
                us,
                mode=perspective_lab.PERSPECTIVE_MODE_SINGLE,
                perspective_ids=("spt_molmansk",),
                query="行情怎么看",
            )
        self.assertEqual(delegated, text)
        self.assertTrue(record.injected)


class ComposerReceiptTests(unittest.TestCase):
    def test_prepare_synthesis_uses_empty_override_and_does_not_rebuild(
        self,
    ) -> None:
        """F3-shaped compose path: override="" means already activated empty.

        Composer must not call ``build_runtime_context`` again. That second
        build is the hole: activate can be degraded (no title) while compose
        still injects a shop-named prompt, or the other way around.
        """

        from intelligence.services import ask_synthesis
        from intelligence.services.ask_types import AskOptions, AskResult

        class _Spec:
            def to_prompt_block(self) -> str:
                return "spec"

        result = AskResult(
            query="行情怎么看",
            trade_date=None,
            matched_theme=None,
            candidate_tier=None,
            priority_score=None,
        )
        result.answer_spec = _Spec()  # type: ignore[assignment]
        options = AskOptions(
            query="行情怎么看",
            user="tester",
            perspective_mode="single",
            perspective_ids=("spt_molmansk",),
            perspective_prompt_override="",
            enabled_providers=(),
            include_scenario_guidance=False,
            include_track_guidance=False,
        )
        plan = mock.Mock()
        plan.question_type = "general"

        with mock.patch.object(
            ask_synthesis.llm_refine,
            "build_synthesis_messages",
            return_value=[{"role": "system", "content": "base"}],
        ), mock.patch.object(
            perspective_lab,
            "build_runtime_context",
            side_effect=AssertionError("composer must not rebuild"),
        ):
            messages = ask_synthesis._prepare_answer_spec_synthesis(
                options=options,
                result=result,
                question_plan=plan,
                theme="x",
                citations=[],
                quality_context=None,  # type: ignore[arg-type]
                is_market_review=True,
            )

        self.assertEqual(messages[0]["content"], "base\n\n## 本轮视角约束\n")
        self.assertNotIn("SPT-Molmansk", messages[0]["content"])
        self.assertNotIn("sptfei", messages[0]["content"].lower())

    def test_active_perspective_prompt_empty_override_is_not_none(
        self,
    ) -> None:
        from intelligence.services import ask_synthesis
        from intelligence.services.ask_types import AskOptions

        with mock.patch.object(
            perspective_lab,
            "activate_runtime_perspective",
            side_effect=AssertionError("override must skip activate"),
        ):
            text = ask_synthesis._active_perspective_prompt(
                AskOptions(
                    query="行情怎么看",
                    perspective_prompt_override="",
                )
            )
        self.assertEqual(text, "")


if __name__ == "__main__":
    unittest.main()
