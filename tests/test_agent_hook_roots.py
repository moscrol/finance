"""SessionStart / SessionEnd 钩子必须把「选定的仓根」绑定到下游。

背景：外层钩子命令按 `cwd 的 git 仓根 → 环境变量 → 主检出树` 的顺序挑 ``$R``，
而下游 ``scripts/session_facts.sh`` / ``scripts/check_inflight_stale.sh`` 各有一套
自己的根解析，且顺序**相反**（环境变量排第一）。外层选完不绑定，环境变量指向
另一棵**有效**树时就会推翻外层的选择——注入别人的分支、未提交改动与测试收据，
而且 exit 0，静默失真。

「变量指向不存在的目录」能通过，不代表「变量指向另一棵有效树」也正确：
前者靠 sentinel 判空回退，后者 sentinel 是满足的。本文件锁的是后者。
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVIN_CONFIG = ROOT / ".devin" / "config.json"


def _devin_command(event: str) -> str:
    cfg = json.loads(DEVIN_CONFIG.read_text(encoding="utf-8"))
    return cfg["hooks"][event][0]["hooks"][0]["command"]


def _short_head() -> str:
    return subprocess.run(
        ["git", "--no-optional-locks", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _vault_home(tmp_path: Path) -> str:
    """给被委托的记忆钩子一个可达的空 vault，返回用作 ``HOME`` 的目录。

    钩子先找仓根 ``.agent-memory``、再找 ``$HOME/agent-memory``，都不在就静默 exit 0、注入为空。
    开发机上仓根软链在，这里不起作用；CI / 云端容器两者都没有，不给就测不到选根逻辑。
    """
    home = tmp_path / "vault-home"
    (home / "agent-memory").mkdir(parents=True)
    return str(home)


def _make_decoy(tmp_path: Path, sentinel: str) -> Path:
    """造一棵能骗过 sentinel 判据、但不是 git 仓的假树。"""
    decoy = tmp_path / "decoy-tree"
    (decoy / "scripts").mkdir(parents=True)
    (decoy / sentinel).write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    return decoy


def _make_valid_sibling_tree(tmp_path: Path) -> Path:
    """造第二棵**有效**项目树：真 git 仓 + 满足 sentinel 的被委托脚本。

    与 ``_make_decoy`` 的差别正是本文件要锁的那一半：诱饵树靠「脚本不在」被判空
    回退，任何选根顺序都挡得住它；另一棵有效树 sentinel 完全满足，只有选根**顺序**
    能挡。被委托脚本打印一行形状与真货相同的「当前分支：」，于是选错根时产出的是
    一份看起来完全正常、只是属于另一棵树的注入——生产里那种静默失真的样子。
    """
    other = tmp_path / "other-valid-tree"
    (other / ".claude" / "hooks").mkdir(parents=True)
    (other / ".claude" / "hooks" / "load-memory.sh").write_text(
        "#!/usr/bin/env bash\necho '当前分支：other-valid-tree-branch'\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=other, capture_output=True, check=False)
    return other


def test_devin_hooks_bind_chosen_root_before_delegating() -> None:
    for event, script in (
        ("SessionStart", "scripts/session_facts.sh"),
        ("SessionEnd", "scripts/check_inflight_stale.sh"),
    ):
        cmd = _devin_command(event)
        assert f'DEVIN_PROJECT_DIR="$R" bash "$R/{script}"' in cmd, (
            f"{event} 钩子必须用 DEVIN_PROJECT_DIR=\"$R\" 绑定后再调下游，"
            f"否则下游的根解析会推翻外层选择。实得：{cmd}"
        )


def test_devin_session_start_ignores_env_pointing_at_another_tree(
    tmp_path: Path,
) -> None:
    decoy = _make_decoy(tmp_path, "scripts/session_facts.sh")
    env = {**os.environ, "DEVIN_PROJECT_DIR": str(decoy)}
    out = subprocess.run(
        ["bash", "-c", _devin_command("SessionStart")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    ).stdout

    assert out.strip(), "钩子不该静默无输出"
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert _short_head() in context, f"注入的应是本树的事实，实得：{context[:200]}"
    assert decoy.name not in context, f"注入了诱饵树的事实：{context[:200]}"


def test_codex_hook_injects_repo_facts_regardless_of_cwd(tmp_path: Path) -> None:
    """Codex 钩子：脚本路径拼对还不够，必须在目标仓里执行。

    下游用 cwd 找 git；只拼路径不切目录，会注入「当前分支：?」且没有项目笔记。
    """
    hook = ROOT / ".codex" / "hooks" / "load-memory.sh"
    home = _vault_home(tmp_path)
    for cwd, env_root in ((str(ROOT), ""), (str(tmp_path), str(ROOT))):
        env = {**os.environ, "CODEX_PROJECT_DIR": env_root, "HOME": home}
        out = subprocess.run(
            ["bash", str(hook)], cwd=cwd, capture_output=True, text=True, env=env
        ).stdout
        assert "当前分支：" in out, f"cwd={cwd} env={env_root!r} 没注入 Git 现状段"
        assert "当前分支：?" not in out, (
            f"cwd={cwd} env={env_root!r} 分支解析失败——脚本没有在目标仓里执行"
        )


def test_memory_hook_binds_finance_project_in_renamed_clone(tmp_path: Path) -> None:
    """记忆钩子的项目身份必须绑 checked-in 仓，不猜目录名 / common-dir / origin。

    布局：独立 clone 改名 ``finhot``（origin 仍指 finance-workspace-private.git），
    假 vault 的 ``20_projects/`` 下两份项目笔记都在。缺陷在场时 common-dir 父目录名
    = finhot → 注入 finhot 笔记、尾部回写约定指向 ``20_projects/finhot.md``，两个入口
    都 exit 0（2026-09-13 质检：基线选对、候选选错的新增回归；真机 vault 确有
    finhot 项目笔记，这不是纯假想布局）。
    """
    clone = tmp_path / "finhot"
    subprocess.run(["git", "init", "-q", str(clone)], check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin",
         "https://example.invalid/a77/finance-workspace-private.git"],
        cwd=clone, check=True, capture_output=True,
    )
    vault = clone / ".agent-memory" / "20_projects"
    vault.mkdir(parents=True)
    for name, marker in (("finance-workspace-private", "EXPECTED_WS_NOTE"),
                         ("finhot", "WRONG_FINHOT_NOTE")):
        (vault / f"{name}.md").write_text(
            f"# {name}\n\n{marker}\n\n## 交接记录\nold history\n", encoding="utf-8"
        )
    # Codex wrapper 会 cd 进选中的根并跑该处的 .claude/hooks/load-memory.sh，
    # 所以 clone 里放一份当前工作区钩子的逐字节拷贝——测的就是现在的代码。
    claude_hook = clone / ".claude" / "hooks" / "load-memory.sh"
    claude_hook.parent.mkdir(parents=True)
    claude_hook.write_text(
        (ROOT / ".claude" / "hooks" / "load-memory.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    for entry, argv in (
        ("claude", ["bash", str(claude_hook)]),
        ("codex", ["bash", str(ROOT / ".codex" / "hooks" / "load-memory.sh")]),
    ):
        proc = subprocess.run(argv, cwd=clone, capture_output=True, text=True)
        out = proc.stdout
        assert proc.returncode == 0, f"{entry} 入口退出码 {proc.returncode}"
        assert "EXPECTED_WS_NOTE" in out, f"{entry} 入口没注入金融项目笔记：{out[:200]}"
        assert "WRONG_FINHOT_NOTE" not in out, f"{entry} 入口注入了改名目录的项目笔记"
        assert "20_projects/finance-workspace-private.md" in out, (
            f"{entry} 入口的回写约定没有指向金融项目笔记"
        )
        assert "20_projects/finhot.md" not in out, f"{entry} 入口的回写约定指向错误项目"


def test_codex_hook_ignores_env_pointing_at_another_valid_tree(tmp_path: Path) -> None:
    """Codex 钩子的选根顺序必须与 ``.devin/config.json`` 一致：cwd 的仓根优先。

    上一条只覆盖「变量为空」与「cwd 不在仓里」两种情形，两种下环境变量赢都是对的，
    所以它对本缺陷沉默：断言只问「有分支且不是 ?」，注入的是**哪棵树**的分支不问。
    """
    other = _make_valid_sibling_tree(tmp_path)
    hook = ROOT / ".codex" / "hooks" / "load-memory.sh"
    out = subprocess.run(
        ["bash", str(hook)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "CODEX_PROJECT_DIR": str(other), "HOME": _vault_home(tmp_path)},
    ).stdout

    assert "other-valid-tree-branch" not in out, (
        "CODEX_PROJECT_DIR 指向另一棵有效树时压过了 cwd 的仓根，"
        f"注入的是那棵树的事实：{out[:200]}"
    )
    assert "## 回写约定" in out, (
        f"没有落到本树的被委托脚本（只有它会输出尾部固定段）：{out[:200]}"
    )
