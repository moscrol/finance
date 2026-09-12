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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = ROOT / "scripts" / "build_registry.py"
_spec = importlib.util.spec_from_file_location("build_registry_under_test", _SCRIPT)
assert _spec is not None and _spec.loader is not None
build_registry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_registry)


def test_self_repo_name_comes_from_git_identity_not_directory_name() -> None:
    """仓名要按 git 身份取：附属 worktree 的目录名不是仓名。

    这条在主检出树/门禁检出里是恒真的（目录名本来就等于仓名），只有在
    ``fwp-wt-*`` 那种树里才有判别力——而那正是回归发生的地方。
    """
    assert build_registry._SELF_REPO_NAME == "finance-workspace-private", (
        f"本树被认成了 {build_registry._SELF_REPO_NAME!r}；"
        f"REPO_ROOT={build_registry.REPO_ROOT}"
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
