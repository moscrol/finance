"""注册表生成器必须绑定**当前这棵树**，且不许静默抹掉整个仓的条目。

两件事都属于同一个失败形状：产物按「位置」而不是按「身份」生成，走错位置时
照样退出 0，diff 看起来像一次正常刷新。

- 仓根：``REPOS_DIR / "finance-workspace-private"`` 在附属 worktree 里指的是
  **主检出树**。2026-09-12 实测：在 ``fwp-wt-instruction-gate-clearance`` 里重扫，
  本分支刚恢复的三个技能（公司画像页 / 潜意识模式 / 行业概览）被删掉，61 → 58；
  ``backfill-tables`` 更会去改另一棵树的 ``AGENTS.md``。
- 缺仓：``scan`` 是全量重写，仓不在场就把那个仓的条目整段删掉。``check`` 早就对
  缺仓做了子集比对，写入侧不能比校验侧还松。
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = ROOT / "scripts" / "build_registry.py"


def _load_module(script: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_registry = _load_module(_SCRIPT, "build_registry_under_test")


def test_self_repo_name_is_the_repo_this_script_ships_with() -> None:
    """ws 那一项恒绑本脚本所在的仓：不猜目录名、不问 git。

    本脚本 checked in 在 finance-workspace-private 里，``__file__`` 的仓根就是它，
    没有第二个候选。git common-dir 的父目录名会随 clone 改名而变，不是仓的业务身份
    （2026-09-12 质检：改名独立 clone 里按 common-dir 推 self_name 得到新目录名，
    ws 于是解析到同级的标准名别树，scan/backfill 读写别树且 exit 0）。
    """
    assert build_registry._SELF_REPO_NAME == "finance-workspace-private"
    assert build_registry._repo_dir("finance-workspace-private") == build_registry.REPO_ROOT, (
        f"本仓没有绑到当前树；REPO_ROOT={build_registry.REPO_ROOT}"
    )


def test_resolve_repo_dir_binds_self_to_this_tree() -> None:
    tree = Path("/x/fwp-wt-some-task")
    repos_dir = Path("/x")
    kw = {"repo_root": tree, "repos_dir": repos_dir, "self_name": "finance-workspace-private"}

    assert build_registry.resolve_repo_dir("finance-workspace-private", **kw) == tree, (
        "本仓解析到了同级目录（= 主检出树），而不是当前这棵树"
    )
    # 同级仓照旧按名字找——修法只收紧「自己」这一项，不改跨仓行为。
    assert build_registry.resolve_repo_dir("knowledge-base-private", **kw) == (
        repos_dir / "knowledge-base-private"
    )


def test_repo_dir_is_the_only_resolver_used() -> None:
    """守住「单一解析入口」：源码里不该再出现 ``REPOS_DIR / <仓名>`` 的直写。

    五个消费点分散在 scan / lockfile 合并 / repos 元信息 / present 集合 /
    backfill-tables 里，漏改一个就只修好一半——而漏掉的那个往往是写文件那个
    （``backfill-tables`` 会去改另一棵树的 ``AGENTS.md``）。

    判据走 AST 而不是文本扫描：注释和 docstring 里提到这个写法是正当的，朴素
    grep 会把它们记成违规（本仓「数数别用固定行号、要数就用解析器」同一条纪律）。
    """
    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Div)
        and isinstance(node.left, ast.Name)
        and node.left.id == "REPOS_DIR"
    ]
    assert offenders == [], f"这些行绕过 _repo_dir() 直接解析仓根：{offenders}"


_FIXTURE_DOC = (
    "# demo\n\n## Skills 目录\n\n| Skill | 触发词 |\n|---|---|\n| stale | old |\n"
)


def _write_skill(root: Path, name: str) -> None:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name}\n---\n", encoding="utf-8"
    )


def test_renamed_clone_scan_and_backfill_stay_in_current_tree(tmp_path) -> None:
    """改名独立 clone + 同级标准名别树：读写都只对当前这棵树生效。

    布局：``tmp/renamed-clone/``（真 git 仓，放脚本拷贝与当前树内容），同级另放
    一棵有效的 ``tmp/finance-workspace-private/``（诱饵技能 + 文档）。缺陷在场时
    仓名取自 git common-dir 的父目录名，clone 一改名 self_name 就失配：scan 扫到
    别树技能，``backfill-tables`` 退出 0 并改写别树 AGENTS.md、本树文档原封不动
    （2026-09-12 质检探针在 ecc05e09 上实测复现的形状）。
    """
    active = tmp_path / "renamed-clone"
    other = tmp_path / "finance-workspace-private"
    (active / "scripts").mkdir(parents=True)
    other.mkdir()
    script = active / "scripts" / "build_registry.py"
    script.write_text(_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    _write_skill(active, "self-skill")
    _write_skill(other, "decoy-skill")
    (active / "AGENTS.md").write_text(_FIXTURE_DOC, encoding="utf-8")
    (other / "AGENTS.md").write_text(_FIXTURE_DOC, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(active)], check=True, capture_output=True)

    module = _load_module(script, "registry_renamed_clone")

    scanned = module.build_payload()["skills"]
    assert list(scanned) == ["ws/self-skill"], f"scan 扫到了别树内容：{sorted(scanned)}"
    before_other = (other / "AGENTS.md").read_bytes()
    before_active = (active / "AGENTS.md").read_bytes()
    assert module.cmd_backfill(check=False) == 0
    assert (other / "AGENTS.md").read_bytes() == before_other, "backfill 改写了别树的 AGENTS.md"
    assert (active / "AGENTS.md").read_bytes() != before_active, "backfill 没写当前树的 AGENTS.md"


def _payload(skills: dict) -> dict:
    return {"version": 2, "generator": "t", "repos": [], "declaredSplits": {},
            "crossRepoDuplicates": [], "skills": skills}


def test_scan_refuses_to_write_when_a_whole_repo_would_vanish(monkeypatch, tmp_path) -> None:
    existing = _payload({"ws/a": {}, "kb/b": {}})
    rebuilt = _payload({"ws/a": {}})  # kb 整段没了
    assert build_registry._repos_losing_all_skills(existing, rebuilt) == ["kb"]

    # 全程写到 tmp_path，绝不碰真的 skills.registry.json。
    target = tmp_path / "skills.registry.json"
    monkeypatch.setattr(build_registry, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(build_registry, "REGISTRY_PATH", target)
    monkeypatch.setattr(build_registry, "_load_existing", lambda: existing)
    monkeypatch.setattr(build_registry, "build_payload", lambda: _payload({"ws/a": {}}))

    assert build_registry.cmd_scan() == 2, "缺仓时 scan 必须拒绝写入并非 0 退出"
    assert not target.exists(), "已经拒绝写入了，却还是落了盘"

    # 逃生口存在，但必须显式声明。
    assert build_registry.cmd_scan(allow_missing_repos=True) == 0
    assert target.exists()
