"""``superseded_by``：被取代的 skill 不许留在 agent 视图里（2026-10-01 质检 P0①）。

现场：stock-technicals 取代了 up-line / watchlist-ma / top-gainers-feishu，却没软链进
``.claude/skills/``，三个旧件反而还在视图里、且飞书退役后全都跑不通——「查 UP 线」
会被带到坏掉的那个。这里钉住 check-parseability 的两条硬约束，并对真仓做一次回归。
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_check_parseability import build_registry  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def _skill(root: Path, name: str, extra: str = "") -> None:
    d = root / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: d 触发词：x\n{extra}---\n\n# {name}\n", encoding="utf-8"
    )


def _view(root: Path, name: str) -> None:
    vdir = root / ".claude" / "skills"
    vdir.mkdir(parents=True, exist_ok=True)
    os.symlink(f"../../skills/{name}", vdir / name)


def _run(root: Path) -> tuple[int, str]:
    orig = build_registry._present_repos
    build_registry._present_repos = lambda: [("finance-workspace-private", "ws", root)]  # type: ignore
    err = io.StringIO()
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            rc = build_registry.cmd_check_parseability()
    finally:
        build_registry._present_repos = orig  # type: ignore
    return rc, err.getvalue()


class SupersededViewTests(unittest.TestCase):
    def test_superseded_skill_off_view_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _skill(root, "new")
            _skill(root, "old", "superseded_by: new\n")
            _view(root, "new")
            self.assertEqual(_run(root)[0], 0)

    def test_superseded_skill_still_exposed_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _skill(root, "new")
            _skill(root, "old", "superseded_by: new\n")
            _view(root, "old")
            rc, err = _run(root)
            self.assertEqual(rc, 1)
            self.assertIn(".claude/skills/old", err)

    def test_dangling_or_chained_target_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _skill(root, "a", "superseded_by: missing\n")
            _skill(root, "b", "superseded_by: c\n")
            _skill(root, "c", "superseded_by: d\n")
            _skill(root, "d")
            rc, err = _run(root)
            self.assertEqual(rc, 1)
            self.assertIn("'missing' 不存在", err)
            self.assertIn("'c' 自己也已被取代", err)


class RealRepoTests(unittest.TestCase):
    def test_stock_technicals_exposed_and_predecessors_hidden(self) -> None:
        view = REPO / ".claude" / "skills"
        self.assertTrue((view / "stock-technicals" / "SKILL.md").is_file())
        for old in ("up-line", "watchlist-ma", "top-gainers-feishu"):
            self.assertFalse((view / old).is_symlink() or (view / old).exists(), old)
            fm = build_registry._parse_frontmatter((REPO / "skills" / old / "SKILL.md").read_text())
            self.assertEqual(fm.get("superseded_by"), "stock-technicals", old)


if __name__ == "__main__":
    unittest.main()
