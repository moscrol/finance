#!/usr/bin/env python3
"""通过 exec 隧道在 Mac 上执行一条命令（云端 agent 用）。

用法：
    CC_REMOTE_EXEC_TOKEN=<token> python3 scripts/rexec.py '<command>' [timeout_s]

防的失败形状（2026-08-12 实测）：

1. **Cloudflare 隧道对同步响应有 ~100s 上限**（超时回 HTTP 524）。
   长命令不要同步等：`nohup <cmd> > /tmp/xx.log 2>&1 < /dev/null &` 起后台，
   再用本脚本轮询日志。注意 exec-server 会等整个进程组，
   所以 nohup 那一发本身也会把客户端拖到超时——属预期，起没起来看 pgrep。
2. **token 不落盘**：只从环境变量读。把 token 写进脚本/交接是红线。
3. 非交互 shell 的 PATH 没有 homebrew：远端 `python3` 是系统 3.9，
   跑本仓代码要用显式解释器（/opt/homebrew/bin/python3 或 .venv-workbench）。

退出码透传远端命令的 exitCode。
"""
import json
import os
import sys
import urllib.request

ENDPOINT = os.environ.get(
    "CC_REMOTE_EXEC_URL",
    "https://exec-a77.industry7view.com/api/exec",
)


def main() -> int:
    cmd = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps({"cmd": cmd, "timeout": timeout * 1000}).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['CC_REMOTE_EXEC_TOKEN']}",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.4.0",
        },
        method="POST",
    )
    body = json.loads(
        urllib.request.urlopen(request, timeout=timeout + 30).read()
    )
    sys.stdout.write(body.get("stdout") or "")
    if body.get("stderr"):
        sys.stderr.write(body["stderr"])
    if body.get("timedOut"):
        print("[rexec] TIMED OUT", file=sys.stderr)
    return int(body.get("exitCode") or 0)


if __name__ == "__main__":
    raise SystemExit(main())
