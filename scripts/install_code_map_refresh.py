#!/usr/bin/env python3
"""code map 夜间刷新：launchd 安装器 + 无人值守运行器。

为什么是 launchd 夜跑，而不是另外两个候选：
- commit 钩子：``code_map.py build`` 包装 ``uvx code-review-graph``，分钟级，
  挂进提交会把每次 commit 拖慢一个量级；
- SessionStart 懒重建：拖慢开工，且多会话并发可能同时写 ``.code-review-graph/graph.db``。
本机已有 com.a77.* 夜跑惯例（plist 用 Python 生成、过 plutil -lint，
见 skills/checkpoint-recheck-mac-setup）。

用法::

    python3 scripts/install_code_map_refresh.py install [--at HH:MM]  # 默认 04:25
    python3 scripts/install_code_map_refresh.py uninstall
    python3 scripts/install_code_map_refresh.py run   # launchd 每晚调的就是它

``run`` 沿用 code_map.py status 的退出码语义：0 新鲜→跳过；1 stale / 2 空图→build；
3 status 自身错误→不 build、退出 3（fail closed：宁可不刷，不要在错误状态上瞎刷）。

移植要改什么：LABEL 前缀（com.a77 是本机惯例）、默认触发时刻、日志路径形状。
安装动作在哪棵树跑，plist 就钉住哪棵树——请在主检出树上安装，不要在临时 worktree。
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import code_map

LABEL = "com.a77.finance-code-map-refresh"
DEFAULT_AT = "04:25"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def log_path() -> Path:
    return Path.home() / "Library" / "Logs" / f"{LABEL}.log"


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def cmd_run() -> int:
    root = repo_root()
    status, code = code_map.collect_status(root)
    print(f"[{_now()}] status exit={code}: {status.get('one_line', '')}")
    if code == 0:
        print(f"[{_now()}] 地图新鲜，跳过 build")
        return 0
    if code == 3:
        print(f"[{_now()}] status 自身错误，fail closed 不 build")
        return 3
    payload, build_code = code_map.collect_build(root)
    print(f"[{_now()}] build exit={build_code}: {payload}")
    return build_code


def _render_plist(at: str) -> bytes:
    hour, minute = (int(part) for part in at.split(":", 1))
    uvx = shutil.which("uvx")
    if not uvx:
        raise SystemExit("安装拒绝：PATH 上没有 uvx（code_map build 的硬依赖）")
    path_env = os.pathsep.join(
        dict.fromkeys(
            [str(Path(uvx).parent), "/usr/local/bin", "/opt/homebrew/bin", "/usr/bin", "/bin"]
        )
    )
    data = {
        "Label": LABEL,
        "ProgramArguments": [
            sys.executable,
            str(Path(__file__).resolve()),
            "run",
        ],
        "WorkingDirectory": str(repo_root()),
        "EnvironmentVariables": {"PATH": path_env},
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "RunAtLoad": False,
        "StandardOutPath": str(log_path()),
        "StandardErrorPath": str(log_path()),
    }
    return plistlib.dumps(data, fmt=plistlib.FMT_XML)


def _launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", *args], capture_output=True, text=True, check=False
    )


def cmd_install(at: str) -> int:
    target = plist_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_render_plist(at))
    lint = subprocess.run(
        ["plutil", "-lint", str(target)], capture_output=True, text=True, check=False
    )
    if lint.returncode != 0:
        print(lint.stderr or lint.stdout, file=sys.stderr)
        return 1
    gui = f"gui/{os.getuid()}"
    _launchctl("bootout", f"{gui}/{LABEL}")  # 幂等：不存在时报错可忽略
    boot = _launchctl("bootstrap", gui, str(target))
    if boot.returncode != 0:
        print(boot.stderr or boot.stdout, file=sys.stderr)
        return 1
    print(f"已挂载 {LABEL}（每日 {at}），plist={target}，日志={log_path()}")
    return 0


def cmd_uninstall() -> int:
    gui = f"gui/{os.getuid()}"
    _launchctl("bootout", f"{gui}/{LABEL}")
    target = plist_path()
    if target.exists():
        target.unlink()
    print(f"已卸载 {LABEL}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_install = sub.add_parser("install", help="生成 plist、plutil -lint、launchctl 挂载")
    p_install.add_argument("--at", default=DEFAULT_AT, help=f"每日触发时刻 HH:MM，默认 {DEFAULT_AT}")
    sub.add_parser("uninstall", help="bootout 并删除 plist")
    sub.add_parser("run", help="立即跑一次 stale→build（launchd 调用入口）")
    args = parser.parse_args(argv)
    if args.cmd == "run":
        return cmd_run()
    if args.cmd == "install":
        return cmd_install(args.at)
    return cmd_uninstall()


if __name__ == "__main__":
    sys.exit(main())
