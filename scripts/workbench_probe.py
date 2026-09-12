"""向本机 workbench 发射一条 live 探针：按 run_id 等终态、按 message_id 取公开答案。

防的失败形状（2026-08-21 / 2026-09-12 三轮实测）：
1. ``POST /api/conversations`` 的用户字段是 ``user``；传 ``user_id`` 会被
   FastAPI 静默忽略、会话落到默认用户（探针污染主账号会话列表，且 run 工件
   跑到 ``users/<默认用户>/runs`` 下去找不到）。本脚本钉死字段名。
2. ``GET /api/runs/{id}`` 不带 ``?user=`` 会在**默认用户**的 run store 里找，
   探针用户的 run 一律 404「run 不存在」——不是接口错了，是 scope 错了。带上
   user 后它就是权威的等待接口：``run.status`` 才是成败判据
   （queued/running → completed/failed/cancelled）。
3. 同一套「建会话→发消息→等终态」手写过两遍，第三遍必须走这里。
4. （2026-09-12）按「新增非空 assistant 消息」认答案有两种假阳性，都实测踩过：
   - 续问时把上一轮的旧答案当本轮结果返回（时间上说得很通，不看内容发现不了）；
   - 失败存根也是一条非空的新 assistant 消息（orchestrator 在 ``not answer_text``
     时把 run 判 failed 并写入「本轮连续研究未取得可公开答案。」），不查
     run.status 会把它当答卷带回来。
   所以本脚本只认 POST 202 响应发回的一对 ID：``run_id`` 决定成败与何时取货，
   ``assistant_message_id`` 决定取哪条；会话里其它消息一概不看。

时序事实（读 conversation_orchestrator 完成分支钉过）：先 claim run 终态、后
revise 消息终稿，所以 run=completed 而消息内容还是空是**合法瞬时状态**——遇到
它继续短轮询消息，直到拿到内容或超时。

退出码（调用方 agent 按它判读，不要只看 stdout 有没有字）：
    0  run=completed 且我们的 assistant 消息有非空内容（全文已打印到 stdout）
    1  超时，run 未到终态
    2  请求失败（提交 / 轮询 / 取消息的 HTTP 错误或传输中断，无 traceback）
       或 run=failed/cancelled
    3  run=completed 但直到超时我们的消息仍是空（退化形态，需人工查）

用法：
    .venv-workbench/bin/python scripts/workbench_probe.py \
        --user probe-xxx-0821 --question "……" [--port 8792] [--timeout 900]
    # 续问（第三轮接第二轮，同一会话）：
    .venv-workbench/bin/python scripts/workbench_probe.py \
        --user probe-xxx-0821 --question-file t3.txt --conversation conv_xxx

``--question`` 与 ``--question-file`` 二选一；长题面走文件，省掉 shell 引号那一层
（整段喂进 argv 时的引号/分词错误会伪造出一个读起来很合理的结果）。

输出：conversation_id、run_id、run 状态迁移、公开答案全文、run 工件目录提示。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RUN_SUCCESS = "completed"
RUN_FAILURE = ("failed", "cancelled")
# run 记录在 POST 返回前就建好，之后还 404 只可能是可见性竞态；给几次机会再判死。
RUN_MISSING_TOLERANCE = 3


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


def _get_run(base: str, run_id: str, user: str) -> dict:
    return _call(base, f"/api/runs/{run_id}?user={user}")  # type: ignore[return-value]


def _transport_summary(exc: OSError) -> str:
    """URLError 的错误在 .reason 里，裸超时/断连没有；统一成一行可读摘要。"""
    reason = getattr(exc, "reason", None)
    return str(reason if reason is not None else exc)


def _find_message(
    base: str, conversation_id: str, user: str, message_id: str
) -> dict | None:
    messages = _call(base, f"/api/conversations/{conversation_id}/messages?user={user}")
    items = (
        messages.get("messages", messages) if isinstance(messages, dict) else messages
    )
    for message in items:  # type: ignore[union-attr]
        if message.get("message_id") == message_id:
            return message
    return None


def _artifacts_hint(user: str, run_id: str) -> str:
    return f"~/.local/share/finance-workbench/users/{user}/runs/{run_id}/"


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
    parser.add_argument(
        "--timeout", type=int, default=900, help="等 run 到终态的秒数上限"
    )
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
    try:
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
        posted = _call(
            base,
            f"/api/conversations/{conversation_id}/messages",
            {"content": question, "skill_mode": args.skill_mode, "user": args.user},
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        print(f"提交失败：HTTP {exc.code} {body}", file=sys.stderr)
        return 2
    except OSError as exc:  # URLError（连不上/断连）与 socket 超时同属 OSError
        print(
            f"提交阶段传输失败：{_transport_summary(exc)}（base={base}，workbench 在吗）",
            file=sys.stderr,
        )
        return 2

    run_id = posted["run_id"]  # type: ignore[index]
    assistant_message_id = posted["assistant_message_id"]  # type: ignore[index]
    print(f"run_id={run_id} assistant_message_id={assistant_message_id}", flush=True)

    deadline = time.time() + args.timeout
    last_status: str | None = None
    completed_seen = False
    run_missing = 0
    while time.time() < deadline:
        time.sleep(args.poll_seconds)
        try:
            run = _get_run(base, run_id, args.user)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                run_missing += 1
                if run_missing >= RUN_MISSING_TOLERANCE:
                    print(
                        f"run {run_id} 连续 {run_missing} 次 404"
                        f"（user={args.user} 的 run store 里不存在），放弃",
                        file=sys.stderr,
                    )
                    return 2
                continue
            print(f"查询 run 失败：HTTP {exc.code}", file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"查询 run 传输失败：{_transport_summary(exc)}", file=sys.stderr)
            return 2
        status = str(run.get("status", "?"))
        if status != last_status:
            print(f"run status: {status}", flush=True)
            last_status = status
        if status in RUN_FAILURE:
            print(
                f"run 终态={status} run_id={run_id} error={run.get('error')}",
                file=sys.stderr,
            )
            print(f"run 工件：{_artifacts_hint(args.user, run_id)}", file=sys.stderr)
            return 2
        if status == RUN_SUCCESS:
            completed_seen = True
            try:
                message = _find_message(
                    base, conversation_id, args.user, assistant_message_id
                )
            except urllib.error.HTTPError as exc:
                print(f"取消息失败：HTTP {exc.code}", file=sys.stderr)
                return 2
            except OSError as exc:
                print(f"取消息传输失败：{_transport_summary(exc)}", file=sys.stderr)
                return 2
            content = (message or {}).get("content") or ""
            if content.strip():
                print("---- 公开答案 ----")
                print(content)
                print("---- run 工件 ----")
                print(_artifacts_hint(args.user, run_id))
                return 0
            # run 已 completed 但消息终稿未落盘（claim 先于 revise，见模块 docstring），
            # 继续短轮询消息。
    if completed_seen:
        print(
            f"run {run_id} 已 completed，但 assistant 消息 {assistant_message_id} "
            f"到 {args.timeout}s 超时仍无内容（退化形态，需人工查）",
            file=sys.stderr,
        )
        return 3
    print(
        f"TIMEOUT：{args.timeout}s 内 run 未到终态"
        f"（run_id={run_id}，最后状态={last_status or '未轮询'}）",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
