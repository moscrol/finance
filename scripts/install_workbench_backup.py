#!/usr/bin/env python3
"""Workbench 用户数据异地备份：launchd 安装器 + 无人值守运行器。

备份对象是 ``FORESIGHT_USERS_DIR``（默认 ``~/.local/share/finance-workbench/users``）——
内测用户的全部对话、run、纠偏、配额都在这一个目录里，此前是单副本。

形状：每日一个快照目录 ``<target>/<YYYY-MM-DD>/``，用 ``rsync --link-dest`` 对上一份
快照做硬链接，没变的文件不占新空间、变了的文件保留旧版本；``latest`` 软链指向最新
一份；超过保留天数的快照删除。为什么不是单目录 ``rsync --delete`` 镜像：镜像会把
「今天写坏的数据」原样覆盖到唯一的副本上，快照才有回退点。

目标可以是远端 ``user@host:/abs/path``（走 ssh，launchd 下无法输密码，必须免密钥
登录）或本地目录（挂载盘 / 测试）。

用法::

    python3 scripts/install_workbench_backup.py install --target vps:/srv/backup/finance-workbench [--at HH:MM] [--keep-days 14]
    python3 scripts/install_workbench_backup.py run --target ...        # launchd 每晚调的就是它
    python3 scripts/install_workbench_backup.py uninstall

退出码：0 成功；1 rsync 失败；2 预检失败（源目录空 / ssh 不通 / 目标不可写）。
移植要改什么：LABEL 前缀（com.a77 是本机惯例）、默认触发时刻。
安装动作在哪棵树跑，plist 就钉住哪棵树——请在主检出树上安装，不要在临时 worktree。
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import plistlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

LABEL = "com.a77.finance-workbench-backup"
DEFAULT_AT = "03:40"
DEFAULT_KEEP_DAYS = 14
ENV_TARGET = "WORKBENCH_BACKUP_TARGET"
ENV_KEEP_DAYS = "WORKBENCH_BACKUP_KEEP_DAYS"
ENV_USERS_DIR = "FORESIGHT_USERS_DIR"
_SNAPSHOT_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def log_path() -> Path:
    return Path.home() / "Library" / "Logs" / f"{LABEL}.log"


def default_users_dir() -> Path:
    raw = os.environ.get(ENV_USERS_DIR)
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".local" / "share" / "finance-workbench" / "users"


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _log(message: str) -> None:
    print(f"[{_now()}] {message}", flush=True)


@dataclass(frozen=True)
class Target:
    """``user@host:/abs/path`` → 远端；否则本地目录。"""

    host: str | None
    root: str

    @classmethod
    def parse(cls, spec: str) -> "Target":
        spec = spec.strip()
        if not spec:
            raise ValueError("备份目标不能为空")
        # 只有形如 host:/path 才算远端；本地 Windows 盘符不在考虑范围（macOS 专用）。
        if ":" in spec and not spec.startswith("/"):
            host, _, root = spec.partition(":")
            if not host or not root.startswith("/"):
                raise ValueError(f"远端目标须为 user@host:/abs/path，得到 {spec!r}")
            return cls(host=host, root=root.rstrip("/") or "/")
        return cls(host=None, root=str(Path(spec).expanduser()))

    @property
    def is_remote(self) -> bool:
        return self.host is not None

    def rsync_dest(self, name: str) -> str:
        path = f"{self.root}/{name}/"
        return f"{self.host}:{path}" if self.is_remote else path

    def sh(self, script: str) -> subprocess.CompletedProcess[str]:
        """在目标端跑一段 sh；远端走 ssh BatchMode（无交互，拿不到密钥立刻失败）。"""
        if self.is_remote:
            cmd = [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=15",
                str(self.host),
                script,
            ]
        else:
            cmd = ["sh", "-c", script]
        return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _preflight(source: Path, target: Target) -> str | None:
    """返回错误信息；None 表示通过。"""
    if not source.is_dir():
        return f"源目录不存在：{source}"
    if not any(source.iterdir()):
        return f"源目录为空，拒绝备份（否则会把空目录轮成 latest）：{source}"
    if shutil.which("rsync") is None:
        return "PATH 上没有 rsync"
    probe = target.sh(f"mkdir -p '{target.root}' && test -w '{target.root}'")
    if probe.returncode != 0:
        where = f"ssh {target.host}" if target.is_remote else "本地"
        return (
            f"目标不可达或不可写（{where}）：{(probe.stderr or probe.stdout).strip()}"
        )
    return None


def _list_snapshots(target: Target) -> list[str]:
    listed = target.sh(f"ls -1 '{target.root}'")
    if listed.returncode != 0:
        return []
    return sorted(name for name in listed.stdout.split() if _SNAPSHOT_NAME.match(name))


def run_backup(
    *,
    source: Path,
    target: Target,
    keep_days: int,
    today: dt.date | None = None,
) -> int:
    error = _preflight(source, target)
    if error:
        _log(f"预检失败：{error}")
        return 2
    snapshot = (today or dt.date.today()).isoformat()
    previous = [name for name in _list_snapshots(target) if name != snapshot]
    cmd = ["rsync", "-az", "--delete"]
    if previous:
        cmd.append(f"--link-dest={target.root}/{previous[-1]}")
    cmd += [f"{source}/", target.rsync_dest(snapshot)]
    _log("rsync " + " ".join(cmd[1:]))
    sync = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if sync.returncode != 0:
        _log(
            f"rsync 失败 exit={sync.returncode}：{(sync.stderr or sync.stdout).strip()}"
        )
        return 1

    stale = [name for name in previous if name < _cutoff(snapshot, keep_days)]
    rotate = [
        f"cd '{target.root}'",
        # -n：latest 已是指向目录的软链时不要钻进去（BSD/GNU ln 都认）；
        # 不能用 mv 覆盖——mv 会把新链移进旧目录里。
        f"ln -sfn '{snapshot}' latest",
        f"printf '%s\\n' '{_now()} {snapshot}' > last-success.txt",
    ] + [f"rm -rf '{target.root}/{name}'" for name in stale]
    done = target.sh(" && ".join(rotate))
    if done.returncode != 0:
        _log(f"快照写成但轮转失败：{(done.stderr or done.stdout).strip()}")
        return 1
    _log(
        f"完成：{target.host or 'local'}:{target.root}/{snapshot}（保留 {keep_days} 天，清理 {len(stale)} 份）"
    )
    return 0


def _cutoff(snapshot: str, keep_days: int) -> str:
    return (dt.date.fromisoformat(snapshot) - dt.timedelta(days=keep_days)).isoformat()


def _render_plist(*, at: str, target: str, keep_days: int) -> bytes:
    hour, minute = (int(part) for part in at.split(":", 1))
    rsync = shutil.which("rsync")
    if not rsync:
        raise SystemExit("安装拒绝：PATH 上没有 rsync")
    path_env = os.pathsep.join(
        dict.fromkeys(
            [
                str(Path(rsync).parent),
                "/usr/local/bin",
                "/opt/homebrew/bin",
                "/usr/bin",
                "/bin",
            ]
        )
    )
    env = {
        "PATH": path_env,
        ENV_TARGET: target,
        ENV_KEEP_DAYS: str(keep_days),
        ENV_USERS_DIR: str(default_users_dir()),
    }
    data = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, str(Path(__file__).resolve()), "run"],
        "WorkingDirectory": str(Path(__file__).resolve().parents[1]),
        "EnvironmentVariables": env,
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


def cmd_install(*, at: str, target: str, keep_days: int) -> int:
    parsed = Target.parse(target)
    error = _preflight(default_users_dir(), parsed)
    if error:
        print(
            f"安装拒绝（先修再装，别把一个跑不通的任务挂进 launchd）：{error}",
            file=sys.stderr,
        )
        return 2
    plist = plist_path()
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_bytes(_render_plist(at=at, target=target, keep_days=keep_days))
    lint = subprocess.run(
        ["plutil", "-lint", str(plist)], capture_output=True, text=True, check=False
    )
    if lint.returncode != 0:
        print(lint.stderr or lint.stdout, file=sys.stderr)
        return 1
    gui = f"gui/{os.getuid()}"
    _launchctl("bootout", f"{gui}/{LABEL}")  # 幂等：不存在时报错可忽略
    boot = _launchctl("bootstrap", gui, str(plist))
    if boot.returncode != 0:
        print(boot.stderr or boot.stdout, file=sys.stderr)
        return 1
    print(
        f"已挂载 {LABEL}（每日 {at} → {target}，保留 {keep_days} 天），plist={plist}，日志={log_path()}"
    )
    print("建议立刻手动跑一次验证：python3 scripts/install_workbench_backup.py run")
    return 0


def cmd_uninstall() -> int:
    gui = f"gui/{os.getuid()}"
    _launchctl("bootout", f"{gui}/{LABEL}")
    plist = plist_path()
    if plist.exists():
        plist.unlink()
    print(f"已卸载 {LABEL}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_install = sub.add_parser(
        "install", help="生成 plist、plutil -lint、launchctl 挂载"
    )
    p_install.add_argument(
        "--target", required=True, help="user@host:/abs/path 或本地目录"
    )
    p_install.add_argument(
        "--at", default=DEFAULT_AT, help=f"每日触发时刻 HH:MM，默认 {DEFAULT_AT}"
    )
    p_install.add_argument("--keep-days", type=int, default=DEFAULT_KEEP_DAYS)
    sub.add_parser("uninstall", help="bootout 并删除 plist")
    p_run = sub.add_parser(
        "run", help="立即备份一次（launchd 调用入口；参数缺省读环境变量）"
    )
    p_run.add_argument("--target", default=os.environ.get(ENV_TARGET, ""))
    p_run.add_argument(
        "--keep-days",
        type=int,
        default=int(os.environ.get(ENV_KEEP_DAYS) or DEFAULT_KEEP_DAYS),
    )
    p_run.add_argument(
        "--source",
        default=None,
        help=f"默认 ${ENV_USERS_DIR} 或 ~/.local/share/finance-workbench/users",
    )
    args = parser.parse_args(argv)
    if args.cmd == "uninstall":
        return cmd_uninstall()
    if args.keep_days < 1:
        parser.error("--keep-days 必须 >= 1")
    if args.cmd == "install":
        return cmd_install(at=args.at, target=args.target, keep_days=args.keep_days)
    if not args.target:
        parser.error(f"run 需要 --target 或环境变量 {ENV_TARGET}")
    source = Path(args.source).expanduser() if args.source else default_users_dir()
    return run_backup(
        source=source, target=Target.parse(args.target), keep_days=args.keep_days
    )


if __name__ == "__main__":
    sys.exit(main())
