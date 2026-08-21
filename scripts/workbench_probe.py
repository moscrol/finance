"""向本机 workbench 发射一条 live 探针并等待公开答案。

防的失败形状（2026-08-21 两轮实测）：
1. ``POST /api/conversations`` 的用户字段是 ``user``；传 ``user_id`` 会被
   FastAPI 静默忽略、会话落到默认用户（探针污染主账号会话列表，且
   run 工件跑到 ``users/<默认用户>/runs`` 下去找不到）。本脚本钉死字段名。
2. ``/api/runs/{id}`` 不是等待完成的正确接口（会 404「run 不存在」）；
   正确做法是轮询会话 ``/messages`` 直到 assistant 消息非空。
3. 同一套「建会话→发消息→轮询」今天手写了两遍，第三遍必须走这里。

用法：
    .venv-workbench/bin/python scripts/workbench_probe.py \
        --user probe-xxx-0821 --question "……" [--port 8792] [--timeout 900]

输出：conversation_id、公开答案全文、run 工件目录提示（按 user 解析）。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request


def _call(base: str, path: str, payload: dict[str, object] | None = None) -> object:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--user", required=True, help="探针专用用户名（别用主账号）")
    parser.add_argument("--question", required=True)
    parser.add_argument("--port", type=int, default=8792)
    parser.add_argument("--title", default=None, help="会话标题，默认取问题前 24 字")
    parser.add_argument("--skill-mode", default="manual", dest="skill_mode")
    parser.add_argument("--timeout", type=int, default=900, help="等待答案的秒数上限")
    parser.add_argument("--poll-seconds", type=int, default=15)
    args = parser.parse_args()

    base = f"http://localhost:{args.port}"
    conversation = _call(
        base,
        "/api/conversations",
        {"user": args.user, "title": args.title or args.question[:24]},
    )
    conversation_id = conversation["conversation_id"]  # type: ignore[index]
    print(f"conversation_id={conversation_id}", flush=True)

    _call(
        base,
        f"/api/conversations/{conversation_id}/messages",
        {"content": args.question, "skill_mode": args.skill_mode, "user": args.user},
    )

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        time.sleep(args.poll_seconds)
        messages = _call(
            base, f"/api/conversations/{conversation_id}/messages?user={args.user}"
        )
        items = messages.get("messages", messages) if isinstance(messages, dict) else messages
        for message in items:  # type: ignore[union-attr]
            if message.get("role") == "assistant" and (message.get("content") or "").strip():
                print("---- 公开答案 ----")
                print(message["content"])
                print("---- run 工件 ----")
                print(f"~/.local/share/finance-workbench/users/{args.user}/runs/")
                return 0
    print(f"TIMEOUT：{args.timeout}s 内未见 assistant 答案", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
