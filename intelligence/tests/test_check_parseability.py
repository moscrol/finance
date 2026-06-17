from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_registry.py"
_spec = importlib.util.spec_from_file_location("build_registry_under_test", _SCRIPT)
assert _spec and _spec.loader
build_registry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_registry)


def _write_skill(root: Path, name: str, *, frontmatter: bool = True,
                 fm_name: str | None = None, description: str | None = "desc 触发词：x") -> None:
    d = root / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    lines = []
    if frontmatter:
        lines.append("---")
        lines.append(f"name: {fm_name if fm_name is not None else name}")
        if description is not None:
            lines.append(f"description: {description}")
        lines.append("---")
    lines.append(f"\n# {name}\n正文")
    (d / "SKILL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run(root: Path) -> tuple[int, str, str]:
    orig = build_registry._present_repos
    build_registry._present_repos = lambda: [("finance-workspace-private", "ws", root)]  # type: ignore
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = build_registry.cmd_check_parseability()
    finally:
        build_registry._present_repos = orig  # type: ignore
    return rc, out.getvalue(), err.getvalue()


class CheckParseabilityTests(unittest.TestCase):
    def test_all_parseable_returns_0(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_skill(root, "alpha")
            _write_skill(root, "题材雷达", fm_name="题材雷达")
            rc, out, _ = _run(root)
            self.assertEqual(rc, 0)
            self.assertIn("2", out)

    def test_no_skills_dir_returns_0(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rc, _, _ = _run(Path(td))
            self.assertEqual(rc, 0)

    def test_missing_frontmatter_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_skill(root, "ok")
            _write_skill(root, "broken", frontmatter=False)
            rc, _, err = _run(root)
            self.assertEqual(rc, 1)
            self.assertIn("broken", err)
            self.assertIn("frontmatter", err)

    def test_name_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_skill(root, "good")
            _write_skill(root, "mydir", fm_name="other-name")
            rc, _, err = _run(root)
            self.assertEqual(rc, 1)
            self.assertIn("mydir", err)
            self.assertIn("other-name", err)

    def test_missing_description_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_skill(root, "nodesc", description=None)
            rc, _, err = _run(root)
            self.assertEqual(rc, 1)
            self.assertIn("description", err)

    def test_empty_name_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_skill(root, "blankname", fm_name="")
            rc, _, err = _run(root)
            self.assertEqual(rc, 1)
            self.assertIn("name", err)


if __name__ == "__main__":
    unittest.main()
