"""向本机 workbench 发射一条 live 探针并等待公开答案。

防的失败形状（2026-08-21 两轮实测）：
1. ``POST /api/conversations`` 的用户字段是 ``user``；传 ``user_id`` 会被
   FastAPI 静默忽略、会话落到默认用户（探针污染主账号会话列表，且
   run 工件跑到 ``users/<默认用户>/runs`` 下去找不到）。本脚本钉死字段名。
2. ``/api/runs/{id}`` 不是等待完成的正确接口（会 404「run 不存在」）；
   正确做法是轮询会话 ``/messages`` 直到 assistant 消息非空。
3. 同一套「建会话→发消息→轮询」今天手写了两遍，第三遍必须走这里。
4. （2026-09-12）续问时「看到任意非空 assistant 消息就返回」会**立刻返回上一轮的
   旧答案**——多轮题（T2→T3 这种第三轮续第二轮的）会因此把上一轮答卷当成本轮结果，
   且时间上完全说得通，不看内容发现不了。改为发问前先数一遍已有 assistant 消息，
   只认新增的那条。

用法：
    .venv-workbench/bin/python scripts/workbench_probe.py \
        --user probe-xxx-0821 --question "……" [--port 8792] [--timeout 900]
    # 续问（第三轮接第二轮，同一会话）：
    .venv-workbench/bin/python scripts/workbench_probe.py \
        --user probe-xxx-0821 --question-file t3.txt --conversation conv_xxx

``--question`` 与 ``--question-file`` 二选一；长题面走文件，省掉 shell 引号那一层
（整段喂进 argv 时的引号/分词错误会伪造出一个读起来很合理的结果）。

输出：conversation_id、公开答案全文、run 工件目录提示（按 user 解析）。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path


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


def _assistant_messages(base: str, conversation_id: str, user: str) -> list[dict]:
    """会话里已有的、内容非空的 assistant 消息，按会话顺序。"""
    messages = _call(base, f"/api/conversations/{conversation_id}/messages?user={user}")
    items = messages.get("messages", messages) if isinstance(messages, dict) else messages
    return [
        message
        for message in items  # type: ignore[union-attr]
        if message.get("role") == "assistant" and (message.get("content") or "").strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--user", required=True, help="探针专用用户名（别用主账号）")
    parser.add_argument("--question", default=None)
    parser.add_argument(
        "--question-file",
        default=None,
        dest="question_file",
        help="题面文件（UTF-8）；与 --question 二选一，长题面用它避开 shell 引号",
    )
    parser.add_argument("--port", type=int, default=8792)
    parser.add_argument(
        "--conversation",
        default=None,
        help="续问已有会话的 conversation_id；不给则新建会话",
    )
    parser.add_argument("--title", default=None, help="会话标题，默认取问题前 24 字")
    parser.add_argument("--skill-mode", default="manual", dest="skill_mode")
    parser.add_argument("--timeout", type=int, default=900, help="等待答案的秒数上限")
    parser.add_argument("--poll-seconds", type=int, default=15)
    args = parser.parse_args()

    if bool(args.question) == bool(args.question_file):
        parser.error("--question 与 --question-file 必须且只能给一个")
    question = (
        args.question
        if args.question
        else Path(args.question_file).read_text(encoding="utf-8")
    )

    base = f"http://localhost:{args.port}"
    if args.conversation:
        conversation_id = args.conversation
    else:
        conversation = _call(
            base,
            "/api/conversations",
            {"user": args.user, "title": args.title or question[:24]},
        )
        conversation_id = conversation["conversation_id"]  # type: ignore[index]
    print(f"conversation_id={conversation_id}", flush=True)

    # 发问前先数：续问时会话里已经有上一轮的答案，不记基线就会把它当本轮结果返回。
    baseline = len(_assistant_messages(base, conversation_id, args.user))
    print(f"已有 assistant 消息 {baseline} 条，等第 {baseline + 1} 条", flush=True)

    _call(
        base,
        f"/api/conversations/{conversation_id}/messages",
        {"content": question, "skill_mode": args.skill_mode, "user": args.user},
    )

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        time.sleep(args.poll_seconds)
        answered = _assistant_messages(base, conversation_id, args.user)
        if len(answered) > baseline:
            print("---- 公开答案 ----")
            print(answered[-1]["content"])
            print("---- run 工件 ----")
            print(f"~/.local/share/finance-workbench/users/{args.user}/runs/")
            return 0
    print(f"TIMEOUT：{args.timeout}s 内未见新的 assistant 答案", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
