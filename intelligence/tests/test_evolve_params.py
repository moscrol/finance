from __future__ import annotations

import json
import os
import tempfile
import unittest

from evolution import params as evparams


_BASE = {
    "version": 2,
    "note": "baseline",
    "strategy1": {"t1core_size": 6, "quintile": 5, "double_red": {"amount_min": 500}},
    "strategy3": {"pool_topN": 20},
    "validation": {"horizons": [1, 3, 5], "win_gt": 0},
    "suggest": {"min_samples": 30},
}


def _write(d: str, name: str, obj) -> str:
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    return path


class DeepMergeTests(unittest.TestCase):
    def test_scalar_and_list_override_dict_recurse(self) -> None:
        base = {"a": 1, "b": {"x": 1, "y": 2}, "c": [1, 2]}
        overlay = {"a": 9, "b": {"y": 99, "z": 3}, "c": [7]}
        out = evparams.deep_merge(base, overlay)
        self.assertEqual(out["a"], 9)
        self.assertEqual(out["b"], {"x": 1, "y": 99, "z": 3})  # recurse, x preserved
        self.assertEqual(out["c"], [7])  # list overrides wholesale

    def test_does_not_mutate_inputs(self) -> None:
        base = {"b": {"x": 1}}
        overlay = {"b": {"x": 2}}
        out = evparams.deep_merge(base, overlay)
        self.assertEqual(base["b"]["x"], 1)
        self.assertEqual(out["b"]["x"], 2)


class SanitizeTests(unittest.TestCase):
    def test_keeps_allowed_sections_and_meta(self) -> None:
        raw = {
            "_overlay_version": 3,
            "strategy1": {"quintile": 6},
            "version": 99,  # disallowed: baseline meta
            "bogus": {"k": 1},  # disallowed section
            "validation": "not-a-dict",  # wrong type
        }
        overlay, meta, warnings = evparams._sanitize_overlay(raw)
        self.assertEqual(overlay, {"strategy1": {"quintile": 6}})
        self.assertEqual(meta, {"_overlay_version": 3})
        self.assertEqual(len(warnings), 3)

    def test_non_dict_overlay_warns(self) -> None:
        overlay, meta, warnings = evparams._sanitize_overlay([1, 2, 3])
        self.assertEqual(overlay, {})
        self.assertEqual(meta, {})
        self.assertEqual(len(warnings), 1)


class LoadEffectiveTests(unittest.TestCase):
    def test_no_overlay_returns_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base_path = _write(d, "params.json", _BASE)
            params, meta = evparams.load_effective_params(base_path=base_path)
            self.assertEqual(params, _BASE)
            self.assertFalse(meta["overlay_applied"])
            self.assertEqual(meta["base_version"], 2)
            self.assertIsNone(meta["overlay_version"])
            self.assertEqual(meta["overlay_sections"], [])

    def test_missing_overlay_file_returns_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base_path = _write(d, "params.json", _BASE)
            params, meta = evparams.load_effective_params(
                base_path=base_path, overlay_path=os.path.join(d, "nope.json")
            )
            self.assertEqual(params, _BASE)
            self.assertFalse(meta["overlay_applied"])

    def test_overlay_merges_and_records_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base_path = _write(d, "params.json", _BASE)
            overlay_path = _write(d, "strategy_params.json", {
                "_overlay_version": 7,
                "strategy1": {"quintile": 6},
                "validation": {"horizons": [1, 3, 5, 10]},
            })
            params, meta = evparams.load_effective_params(
                base_path=base_path, overlay_path=overlay_path
            )
            # merged: quintile overridden, t1core_size + nested double_red preserved
            self.assertEqual(params["strategy1"]["quintile"], 6)
            self.assertEqual(params["strategy1"]["t1core_size"], 6)
            self.assertEqual(params["strategy1"]["double_red"], {"amount_min": 500})
            self.assertEqual(params["validation"]["horizons"], [1, 3, 5, 10])
            self.assertEqual(params["validation"]["win_gt"], 0)  # preserved
            self.assertEqual(params["version"], 2)  # baseline version untouched
            self.assertTrue(meta["overlay_applied"])
            self.assertEqual(meta["overlay_version"], 7)
            self.assertEqual(meta["overlay_sections"], ["strategy1", "validation"])
            self.assertEqual(meta["warnings"], [])

    def test_empty_overlay_not_applied(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base_path = _write(d, "params.json", _BASE)
            overlay_path = _write(d, "ov.json", {"_overlay_version": 1, "bogus": {"a": 1}})
            params, meta = evparams.load_effective_params(
                base_path=base_path, overlay_path=overlay_path
            )
            self.assertEqual(params, _BASE)
            self.assertFalse(meta["overlay_applied"])
            self.assertTrue(meta["warnings"])  # bogus section warned


if __name__ == "__main__":
    unittest.main()
