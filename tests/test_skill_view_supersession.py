"""被取代的 skill 不许暴露，取代者必须暴露。

2026-09-30 质检发现的错位：`stock-technicals`（DuckDB 本地算 UP 线 / 均线 / 回踩，
SKILL.md 自述取代三个飞书旧件）**不在** `.claude/skills/`，被它取代的 `up-line` /
`watchlist-ma` / `top-gainers-feishu` 反而**在**，且飞书 2026-09-11 退役后都跑不通。
几个 skill 的触发词重叠（UP线 / 自选股 / 均线 / 回踩），用户说「查 UP 线」会先撞到坏的那个。

视图是人工策划的（`build_registry.py generate-views` 只规范已存在的软链，不增不删），
所以漂移不会被任何生成器自动纠正。这里用 frontmatter 的 ``metadata.superseded_by``
当事实源，锁住两条：

1. 声明了 ``superseded_by`` 的 skill 不出现在任何 agent 视图目录里；
2. 它指向的取代者真实存在，且已软链进 `.claude/skills/`（否则等于把入口整个拿掉）。

只做字面解析、不依赖 PyYAML：注册表扫描器在没装 PyYAML 的机器上也要跑得通。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
# 与 scripts/build_registry.py 的 AGENT_SKILL_DIRS 同一份名单。
AGENT_SKILL_DIRS = (".claude/skills", ".agents/skills", ".devin/skills", ".windsurf/skills")
PRIMARY_VIEW = REPO_ROOT / ".claude" / "skills"

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.S)
_SUPERSEDED_BY = re.compile(r"^\s+superseded_by:\s*([A-Za-z0-9_\-\u4e00-\u9fff]+)\s*$", re.M)


def _superseded_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        match = _FRONTMATTER.match(skill_md.read_text(encoding="utf-8"))
        if match is None:
            continue
        found = _SUPERSEDED_BY.search(match.group(1))
        if found is not None:
            pairs.append((skill_md.parent.name, found.group(1)))
    return pairs


def _exposed_in(view_dir: Path, name: str) -> bool:
    entry = view_dir / name
    return entry.is_symlink() or entry.exists()


def test_known_superseded_skills_are_declared() -> None:
    """回归锚：2026-09-30 撤下的三件必须带着声明，别被悄悄删掉 frontmatter 后又链回去。"""

    declared = dict(_superseded_pairs())
    for name in ("up-line", "watchlist-ma", "top-gainers-feishu"):
        assert declared.get(name) == "stock-technicals", name


@pytest.mark.parametrize("pair", _superseded_pairs(), ids=lambda pair: pair[0])
def test_superseded_skill_is_not_exposed_in_any_agent_view(pair: tuple[str, str]) -> None:
    name, successor = pair
    exposed = [
        rel for rel in AGENT_SKILL_DIRS if _exposed_in(REPO_ROOT / rel, name)
    ]
    assert not exposed, (
        f"{name} 已声明被 {successor} 取代，却仍出现在 {exposed}："
        "它会继续参与触发匹配、把请求带到跑不通的旧脚本上。"
    )


@pytest.mark.parametrize("pair", _superseded_pairs(), ids=lambda pair: pair[0])
def test_successor_exists_and_is_exposed(pair: tuple[str, str]) -> None:
    name, successor = pair
    assert (SKILLS_DIR / successor / "SKILL.md").is_file(), (
        f"{name} 的 superseded_by 指向不存在的 skill：{successor}"
    )
    link = PRIMARY_VIEW / successor
    assert link.is_symlink(), f"取代者 {successor} 没有软链进 .claude/skills/，入口等于被整个拿掉"
    assert (link / "SKILL.md").is_file(), f".claude/skills/{successor} 是断链"


def test_successor_is_not_itself_superseded() -> None:
    """链式取代（A→B→C 且 B 已撤）会让声明指向一个同样不暴露的件。"""

    pairs = dict(_superseded_pairs())
    for name, successor in pairs.items():
        assert successor not in pairs, f"{name} → {successor}，但 {successor} 自己也被取代了"
