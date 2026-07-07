import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_mod = _load_module(
    "validate_marketing_contracts", ROOT / "scripts" / "validate_marketing_contracts.py"
)
context_mod = _load_module(
    "marketing_generation_context", ROOT / "scripts" / "marketing_generation_context.py"
)


class MarketingContractsTests(unittest.TestCase):
    def test_contracts_validate(self):
        self.assertEqual(validate_mod.main(), 0)

    def test_generation_context_builds(self):
        text = context_mod.build_context("2026-07-05-launch-batch")
        self.assertIn("产品定位与表达边界", text)
        self.assertIn("claim-evidence-first-research", text)
        self.assertIn("不可以说：", text)
        self.assertIn("禁止改写为：", text)
        # 每个 required claim 都要带支撑功能与证据
        self.assertIn("支撑功能：", text)
        self.assertIn("docs/productization-roadmap.md", text)

    def test_generation_context_rejects_unknown_brief(self):
        with self.assertRaises(SystemExit):
            context_mod.build_context("no-such-brief")


if __name__ == "__main__":
    unittest.main()
