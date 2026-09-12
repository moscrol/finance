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


def _make_decoy(tmp_path: Path, sentinel: str) -> Path:
    """造一棵能骗过 sentinel 判据、但不是 git 仓的假树。"""
    decoy = tmp_path / "decoy-tree"
    (decoy / "scripts").mkdir(parents=True)
    (decoy / sentinel).write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    return decoy


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
    for cwd, env_root in ((str(ROOT), ""), (str(tmp_path), str(ROOT))):
        env = {**os.environ, "CODEX_PROJECT_DIR": env_root}
        out = subprocess.run(
            ["bash", str(hook)], cwd=cwd, capture_output=True, text=True, env=env
        ).stdout
        assert "当前分支：" in out, f"cwd={cwd} env={env_root!r} 没注入 Git 现状段"
        assert "当前分支：?" not in out, (
            f"cwd={cwd} env={env_root!r} 分支解析失败——脚本没有在目标仓里执行"
        )
