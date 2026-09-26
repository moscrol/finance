#!/usr/bin/env python3
"""棘轮门禁：``docs/handoffs/inflight/*.md`` 不得**新增**或**加重**超 3K 字节的交接。

## 它防的是哪种失败

``scripts/session_facts.sh`` 在 SessionStart 把在途交接注入给下一个 agent，预算约
2000 字符。超预算时它**从尾部截断**，而 ``skills/handoff`` 规定的小节顺序是：

    这个分支做什么 / 决策与被否方案 / 当前状态 / 已验证 / 未验证 / 下一步 / 踩过的坑

也就是说，被砍掉的恰好是「下一步」和「踩过的坑」——接手者拿到的是「我做完了什么」，
拿不到「什么还没验、哪里会咬人」。2026-08-11 的实测记录里，前 12 行只覆盖到「已做」。

读侧已经做了它能做的：超标时在指针行标注实际字节数，让截断从静默变成可见。
但**声明只是止损，不是止血**——它把成本转嫁给下一个 agent（多一次读文件，且要自己
意识到该读）。本门禁把同一件事挪到写侧：一开始就别超。

## 为什么是棘轮，而不是一刀切

落地当天全仓 104 份 inflight 里 **53 份超标**。一刀切会让超过一半的交接提交直接失败，
其中绝大多数与提交者本轮的活无关——那种门禁会在一周内被 ``--no-verify`` 绕过去，
然后永远绿着。本仓 ``layer_audit.py`` / ``check_path_literals.py`` 已经验证过的解法是
棘轮：**存量免检，只拦新增与恶化**。

判据因此是「有没有变得更糟」，不是「合不合规」：

    新文件      > 3000 字节            -> 拦
    存量文件    超标且比 HEAD 更大     -> 拦
    存量文件    超标但没变大（含变小） -> 放行
    任何文件    <= 3000 字节           -> 放行

存量基线不写进任何清单文件——直接跟 ``HEAD`` 里的同路径比。手抄的基线会与源码分叉，
且分叉时门禁照旧发绿（本仓在依赖清单上栽过一次）。

## 为什么比的是暂存区，不是工作区

门禁要回答的是「这次提交会不会让状态变糟」，所以两边都取版本控制里的事实：
新值取 ``:<path>``（暂存区 blob），旧值取 ``HEAD:<path>``。拿工作区文件大小去比，
会把「改了还没 add 的内容」算进这次提交，多 agent 共树时必然误判。

## 字节，不是字符

``skills/handoff`` 写的是「≤3K 字节」，``session_facts.sh`` 的指针行也按字节报，
这里跟着用字节。中文一字 3 字节，3000 字节 ≈ 1000 汉字——够写完六个小节的结论，
写不下的细节本来就该去日期快照（``docs/handoffs/YYYY-MM-DD-<主题>.md``，不限长）。

## 接受的漏报

**纯改名不拦**（``--diff-filter`` 不含 ``R``）：分支改名带着一份 10K 存量交接换个
文件名，会被当成存量放行。拦它没有收益——内容一个字没变，糟糕程度没有加重——而
误伤一次改名的代价是让人开始怀疑这道闸。宁可漏报，不可误报：一个喊过狼来了的门禁，
下次不会有人看。

``pre-commit run --all-files`` 时本脚本读的仍是索引（通常与 HEAD 相同），因而是空跑。
它是提交期门禁，不是全仓审计——全仓现状用 ``find docs/handoffs/inflight -size +3000c``
自己看，那是存量账，不是本门禁的职责。
"""

from __future__ import annotations

import subprocess
import sys

BUDGET_BYTES = 3000
INFLIGHT_PREFIX = "docs/handoffs/inflight/"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _staged_inflight_docs() -> list[str]:
    """本次提交新增/改动/复制的 inflight 交接（不含删除、不含纯改名）。"""

    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "-z"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted(
        path
        for path in out.split("\0")
        if path.startswith(INFLIGHT_PREFIX) and path.endswith(".md")
    )


def _blob_size(rev_path: str) -> int | None:
    """``git cat-file -s`` 取 blob 字节数；对象不存在（新文件）返回 None。"""

    done = subprocess.run(
        ["git", "cat-file", "-s", rev_path], capture_output=True, text=True
    )
    if done.returncode != 0:
        return None
    return int(done.stdout.strip())


def _has_head() -> bool:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "-q", "HEAD"], capture_output=True
    ).returncode == 0


def main() -> int:
    docs = _staged_inflight_docs()
    print("=" * 72)
    print("交接预算门禁 — inflight 不得新增 / 加重超 3K 字节（存量免检）")
    print("=" * 72)
    if not docs:
        print("  本次提交没有改动 inflight 交接，跳过。")
        return 0

    head_exists = _has_head()
    offenders: list[tuple[str, int, int | None]] = []
    for path in docs:
        new_size = _blob_size(f":{path}")
        if new_size is None:  # 理论上不会：路径来自暂存区清单
            continue
        old_size = _blob_size(f"HEAD:{path}") if head_exists else None
        verdict = "ok"
        if new_size > BUDGET_BYTES and (old_size is None or new_size > old_size):
            offenders.append((path, new_size, old_size))
            verdict = "拦"
        elif new_size > BUDGET_BYTES:
            verdict = f"存量免检（HEAD {old_size}）"
        was = "新文件 " if old_size is None else f"{old_size} -> "
        print(f"  {verdict:<22} {was}{new_size} 字节  {path.removeprefix(INFLIGHT_PREFIX)}")

    if not offenders:
        print(f"\n✅ 通过（{len(docs)} 份在途交接，无新增 / 加重超标）")
        return 0

    print(f"\n❌ {len(offenders)} 份交接超 {BUDGET_BYTES} 字节预算且比之前更大\n")
    for path, new_size, old_size in offenders:
        origin = "新文件" if old_size is None else f"原 {old_size} 字节"
        print(f"  {path}：{new_size} 字节（{origin}，超 {new_size - BUDGET_BYTES}）")
    print(
        "\nSessionStart 注入按小节从**尾部**截断，先被砍的正是「下一步」和「踩过的坑」——\n"
        "接手者会拿到「我做完了什么」，拿不到「什么还没验、哪里会咬人」。\n"
        "\n怎么改：结论留在 inflight，展开移到日期快照 docs/handoffs/YYYY-MM-DD-<主题>.md\n"
        "（不限长、写完不改），inflight 里留一行指针指过去。已合并 / 已归档的事直接删掉。\n"
        "\n确有理由超标时用 git commit --no-verify，并在交接里写明为什么——\n"
        "本门禁只拦「变得更糟」，不替你判断内容该不该长。"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
