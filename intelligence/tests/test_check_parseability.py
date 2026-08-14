from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

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


class FrontmatterDeterminismTests(unittest.TestCase):
    """装了 PyYAML 与没装时必须解析出同一份 frontmatter。

    ``_parse_frontmatter`` 有 PyYAML 优先、极简解析兜底两条路径。两条脱引号行为
    一旦不一致，同一份 SKILL.md 就会因「本机装没装 PyYAML」解析出不同
    description，注册表产物与 computedHash 随之不同——本仓 2026-08-13 的
    registry-check 长红就是这么来的：本地 scan 出无引号版，CI（不装 PyYAML）
    check 算出带引号版，重跑多少次都判漂移。注册表不能是环境的函数。
    """

    _QUOTED = (
        "---\n"
        "name: alpha\n"
        'description: "做 A 股题材研究：先定义边界，再谈公司。see: docs, 触发词：题材"\n'
        "---\n\n# alpha\n正文\n"
    )

    @staticmethod
    def _parse_without_pyyaml(text: str) -> dict[str, str]:
        # sys.modules 里放 None 会让 `import yaml` 抛 ImportError，等价于没装。
        with mock.patch.dict(sys.modules, {"yaml": None}):
            return build_registry._parse_frontmatter(text)

    def _require_pyyaml(self) -> None:
        try:
            import yaml  # noqa: F401
        except ImportError:  # pragma: no cover - 只在没装 PyYAML 的环境走到
            self.skipTest("本环境没有 PyYAML，两条路径无从比对")

    def test_quoted_scalar_parses_the_same_with_and_without_pyyaml(self) -> None:
        self._require_pyyaml()
        fallback = self._parse_without_pyyaml(self._QUOTED)

        self.assertEqual(build_registry._parse_frontmatter(self._QUOTED), fallback)
        # 引号进了 description 就意味着两条路径已经分叉。
        self.assertNotIn('"', fallback["description"])
        self.assertTrue(fallback["description"].startswith("做 A 股题材研究"))

    def test_registry_fields_of_every_skill_md_are_pyyaml_independent(self) -> None:
        """只比 ``_make_entry`` 真正消费的字段，不比整份 frontmatter。

        两条路径在**嵌套**块上本来就不同：极简解析会把 ``metadata:`` 下的
        ``pattern`` / ``also`` 拍平成顶层键，PyYAML 则嵌成字典（本仓
        advancers-chart 就是这个形状）。这种分叉不进注册表，因此无害；
        真正不能分叉的是喂给注册表条目的那两个字段。
        """
        self._require_pyyaml()
        repo = Path(__file__).resolve().parents[2]
        skill_files = sorted((repo / "skills").glob("*/SKILL.md"))
        self.assertTrue(skill_files, "本仓 skills/ 下没扫到 SKILL.md，断言会变成空跑")

        consumed = ("name", "description")
        for path in skill_files:
            text = path.read_text(encoding="utf-8", errors="replace")
            with_yaml = build_registry._parse_frontmatter(text)
            fallback = self._parse_without_pyyaml(text)
            with self.subTest(skill=path.parent.name):
                self.assertEqual(
                    {key: with_yaml.get(key) for key in consumed},
                    {key: fallback.get(key) for key in consumed},
                    f"{path.relative_to(repo)} 的 name/description 依赖 PyYAML 是否"
                    "安装，注册表会随环境漂移",
                )


if __name__ == "__main__":
    unittest.main()
