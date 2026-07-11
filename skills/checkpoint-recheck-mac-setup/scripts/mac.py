#!/usr/bin/env python3
"""在 Mac 上经 Cloudflare remote-exec 隧道跑一条 shell 命令。

用法：
    python3 mac.py 'echo ok; sw_vers -productVersion'   # 命令作为参数
    echo 'long script' | python3 mac.py -                # 或从 stdin 读

环境变量：
    CC_REMOTE_EXEC_TOKEN  必填，Bearer 鉴权 token。
    CC_REMOTE_EXEC_URL    可选，默认 https://exec-a77.industry7view.com/api/exec 。

要点：
- 必须带「curl 样式」User-Agent，否则 Cloudflare WAF 返回 error 1010 拦截。
- 隧道源站（Mac 上的 cloudflared + exec server）没起来时是 HTTP 530 / Cloudflare
  1033，需在 Mac 本地把 cloudflared 拉起来，远端无法修复。
- 隧道「回显」可能吞多字节字符（中文显示成残字），但**磁盘字节从不损坏**；核对中文
  数据请走 codepoint/base64 旁路，不要信肉眼回显（见 references/runbook.md）。
- 含多字节/空格的路径不要当字符串参数传，易被吞；用 cd 到目录后 $(pwd) 落盘再读。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get(
    "CC_REMOTE_EXEC_URL",
    "https://exec-a77.industry7view.com/api/exec",
)


def main() -> int:
    token = os.environ.get("CC_REMOTE_EXEC_TOKEN")
    if not token:
        print("缺少环境变量 CC_REMOTE_EXEC_TOKEN", file=sys.stderr)
        return 2
    if len(sys.argv) >= 2 and sys.argv[1] != "-":
        cmd = " ".join(sys.argv[1:])
    else:
        cmd = sys.stdin.read()
    payload = json.dumps({"cmd": cmd}).encode()
    req = urllib.request.Request(
        URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.5.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()[:500]}", file=sys.stderr)
        return 2
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print(body)
        return 0
    if data.get("stdout"):
        sys.stdout.write(data["stdout"])
        if not data["stdout"].endswith("\n"):
            sys.stdout.write("\n")
    if data.get("stderr"):
        sys.stderr.write("--- stderr ---\n" + data["stderr"])
        if not data["stderr"].endswith("\n"):
            sys.stderr.write("\n")
    meta = {k: data.get(k) for k in ("ok", "exitCode", "timedOut", "cwd", "error")}
    print(f"--- meta: {meta} ---", file=sys.stderr)
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
