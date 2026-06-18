from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.dream import kb_candidates as kc


class BuildCandidateTests(unittest.TestCase):
    def test_red_lines_hardcoded(self) -> None:
        cand = kc.build_candidate(
            kc.CandidateInput(
                company="某公司",
                judgment="边际订单改善",
                concepts=["液冷"],
                chain_layer="midstream",
                date="2026-06-17",
            )
        )
        self.assertIs(cand["graph_only"], True)
        self.assertIs(cand["exposure_only"], True)
        self.assertEqual(cand["update_type"], "review_candidate")
        self.assertEqual(cand["evidence_layer"], "L1_L3_candidate")
        self.assertEqual(cand["tier"], "peripheral")
        self.assertEqual(cand["chain_layer"], "midstream")

    def test_input_cannot_override_red_lines(self) -> None:
        # 即便输入字段试图翻转红线，build_candidate 也忽略（CandidateInput 无这些字段）
        cand = kc.build_candidate(kc.CandidateInput(company="X", judgment="y"))
        self.assertIs(cand["graph_only"], True)
        self.assertEqual(cand["update_type"], "review_candidate")

    def test_illegal_chain_layer_falls_back(self) -> None:
        cand = kc.build_candidate(kc.CandidateInput(company="X", judgment="y", chain_layer="bogus"))
        self.assertEqual(cand["chain_layer"], kc.DEFAULT_CHAIN_LAYER)

    def test_text_fields_are_redacted(self) -> None:
        secret = "ghp_" + "a" * 36
        cand = kc.build_candidate(kc.CandidateInput(company="X", judgment=f"token {secret} 注意"))
        self.assertNotIn(secret, cand["judgment"])
        self.assertIn("[REDACTED:github_token]", cand["judgment"])


class ScanLeaksTests(unittest.TestCase):
    def test_clean_text_no_leak(self) -> None:
        self.assertEqual(kc.scan_leaks("液冷服务器需求向上"), [])

    def test_secret_detected(self) -> None:
        self.assertIn("github_token", kc.scan_leaks("ghp_" + "b" * 36))

    def test_pii_detected(self) -> None:
        self.assertIn("email", kc.scan_leaks("联系 a@b.com"))


class ValidatePayloadTests(unittest.TestCase):
    def _good_payload(self):
        return kc.build_payload(
            [kc.CandidateInput(company="某公司", judgment="边际改善", concepts=["液冷"], chain_layer="midstream")],
            source_name="dream-2026-06-17",
            source_date="2026-06-17",
        )

    def test_good_payload_passes(self) -> None:
        self.assertEqual(kc.validate_payload(self._good_payload()), [])

    def test_reject_graph_only_false(self) -> None:
        p = self._good_payload()
        p["updates"][0]["graph_only"] = False
        errs = kc.validate_payload(p)
        self.assertTrue(any("graph_only" in e for e in errs))

    def test_reject_wrong_update_type(self) -> None:
        p = self._good_payload()
        p["updates"][0]["update_type"] = "curated_research"
        errs = kc.validate_payload(p)
        self.assertTrue(any("update_type" in e for e in errs))

    def test_reject_non_peripheral_tier(self) -> None:
        p = self._good_payload()
        p["updates"][0]["tier"] = "core"
        errs = kc.validate_payload(p)
        self.assertTrue(any("tier" in e for e in errs))

    def test_reject_hard_body_key(self) -> None:
        p = self._good_payload()
        p["updates"][0]["entity_markdown"] = "## 正文硬写"
        errs = kc.validate_payload(p)
        self.assertTrue(any("硬正文" in e for e in errs))

    def test_reject_create_missing_true(self) -> None:
        p = self._good_payload()
        p["create_missing"] = True
        errs = kc.validate_payload(p)
        self.assertTrue(any("create_missing" in e for e in errs))

    def test_reject_leak_in_payload(self) -> None:
        p = self._good_payload()
        p["updates"][0]["judgment"] = "ghp_" + "c" * 36  # 直接塞泄漏，绕过 builder 脱敏
        errs = kc.validate_payload(p)
        self.assertTrue(any("泄漏" in e for e in errs))


class WritePayloadTests(unittest.TestCase):
    def test_write_valid_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = kc.build_payload(
                [kc.CandidateInput(company="某公司", judgment="边际改善", chain_layer="midstream")],
                source_name="dream-2026-06-17",
                source_date="2026-06-17",
            )
            summary = kc.write_payload(payload, kb_dir=tmp)
            self.assertTrue(summary["written"])
            out = Path(summary["path"])
            self.assertTrue(out.is_file())
            self.assertTrue(out.name.endswith(kc.CANDIDATE_SUFFIX))
            loaded = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema_status"], "pending-kb-verify")
            self.assertIs(loaded["create_missing"], False)
            manifest = Path(tmp) / kc.MANIFEST_NAME
            self.assertTrue(manifest.is_file())

    def test_invalid_payload_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = kc.build_payload(
                [kc.CandidateInput(company="X", judgment="y")],
                source_name="dream",
                source_date="2026-06-17",
            )
            payload["updates"][0]["graph_only"] = False  # 触发红线拒绝
            summary = kc.write_payload(payload, kb_dir=tmp)
            self.assertFalse(summary["written"])
            self.assertTrue(summary["errors"])
            self.assertEqual(list(Path(tmp).glob("*" + kc.CANDIDATE_SUFFIX)), [])


class ResolveKbDirTests(unittest.TestCase):
    def test_explicit_wins(self) -> None:
        self.assertEqual(kc.resolve_kb_dir("/tmp/foo"), Path("/tmp/foo"))

    def test_default_is_in_repo_staging(self) -> None:
        d = kc.resolve_kb_dir(None)
        self.assertTrue(str(d).endswith("intelligence/dream/_kb_candidates"))


class LoadInputsTests(unittest.TestCase):
    def test_load_inputs(self) -> None:
        spec = {
            "source_name": "dream-2026-06-17",
            "source_date": "2026-06-17",
            "candidates": [
                {"company": "某公司", "judgment": "边际改善", "concepts": ["液冷"], "chain_layer": "downstream"}
            ],
        }
        inputs, meta = kc.load_inputs(spec)
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0].company, "某公司")
        self.assertEqual(inputs[0].chain_layer, "downstream")
        self.assertEqual(meta["source_name"], "dream-2026-06-17")

    def test_missing_candidates_raises(self) -> None:
        with self.assertRaises(ValueError):
            kc.load_inputs({"source_name": "x"})


class CliWiringTests(unittest.TestCase):
    def test_cli_registers_dream_kb_candidates(self) -> None:
        from intelligence import cli

        parser = cli.build_parser()
        args = parser.parse_args(["dream-kb-candidates", "--input", "x.json"])
        self.assertEqual(args.func, cli.cmd_dream_kb_candidates)


if __name__ == "__main__":
    unittest.main()
