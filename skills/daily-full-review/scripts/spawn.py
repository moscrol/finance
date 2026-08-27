#!/usr/bin/env python3
"""守护进程化启动器（daemonize launcher）。

背景：Mac 上的 exec 服务通过 `launchctl kickstart -k <label>` 重启时，`-k`
会向该 LaunchAgent 的**整个进程组**发 SIGKILL。用 `nohup ... &` 起的长任务
仍是 exec 服务的子进程、同属该进程组，nohup 只挡 SIGHUP，挡不住组 SIGKILL，
于是隧道一重启后台复盘/回填就被连带杀掉。

解法：把长任务 fork→setsid（脱离原会话/进程组，成为新会话首进程）→再 fork，
彻底与 exec 服务解耦；此后 kickstart -k exec 服务不会再波及它。

用法：
    python3 spawn.py <logfile> <cwd> <cmd> [args...]

示例（复盘编排器）：
    python3 skills/daily-full-review/scripts/spawn.py \\
        /tmp/bf/review_sync.log "$FINANCE_WS" \\
        /Library/Developer/CommandLineTools/usr/bin/python3 -u \\
        skills/daily-full-review/scripts/run_review_sync.py --date 2026-07-01

示例（cdp-proxy）：
    python3 skills/daily-full-review/scripts/spawn.py \\
        /tmp/bf/cdp_proxy.log "$HOME" \\
        /usr/local/bin/node ~/.claude/skills/web-access/scripts/cdp-proxy.mjs

启动后本进程立即返回（父进程退出），日志写入 <logfile>，用另开短 exec
轮询该日志即可。
"""
import os
import sys


def main() -> None:
    if len(sys.argv) < 4:
        sys.stderr.write(
            "usage: spawn.py <logfile> <cwd> <cmd> [args...]\n"
        )
        sys.exit(2)
    logpath = sys.argv[1]
    cwd = sys.argv[2]
    args = sys.argv[3:]

    # 第一次 fork：父进程立即退出，让调用方（exec 服务）拿回控制权。
    if os.fork() > 0:
        os._exit(0)
    # 脱离控制终端与原进程组，成为新会话首进程。
    os.setsid()
    # 第二次 fork：确保不是会话首进程，无法再获得控制终端。
    if os.fork() > 0:
        os._exit(0)

    os.chdir(cwd)
    logf = open(logpath, "ab", 0)
    os.dup2(logf.fileno(), 1)
    os.dup2(logf.fileno(), 2)
    devnull = open(os.devnull, "rb")
    os.dup2(devnull.fileno(), 0)
    os.execvp(args[0], args)


if __name__ == "__main__":
    main()
