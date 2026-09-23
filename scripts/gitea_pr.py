#!/usr/bin/env python3
"""Gitea PR 的开 / 查 / 冲突探测 / 守卫 / 关闭 / 合并，一把 CLI 代替每天手敲八遍的 API 片段。

## 它防的失败形状（1–4 在 2026-09-03 的交接里有案，5–8 在 2026-09-21 两参表格家族收口里有案）

1. **同一个 head 重复开 PR**（#539 对 #538）：`open` 先列 open PR，head 分支相同就打印那张、
   不再开新的。分支名是天然幂等键，不需要人记「我刚才开过没」。
2. **信了 Gitea 的 `mergeable`**（2026-08-18 十张全报 true、两张真冲突）：`conflict-check`
   走 `git merge-tree --write-tree <base> <head>`，本机算、不问服务端。
3. **手敲 curl 时 token 进了 shell 历史 / 交接**：token 只从 Keychain
   （`security find-generic-password -s gitea-local -a a77-token -w`）或 `GITEA_TOKEN` 取，
   不接受命令行参数。
4. **合入 main 不经用户确认**（AGENTS.md）：`merge` 必须显式 `--yes`，默认只打印会做什么。
5. **「禁止合入」只写给人看**（#815 标题里的禁令挡不住合并按钮，06:35–10:50 平台层可合）：
   `guard` 给标题加 `WIP:` 前缀，Gitea 内建的 Work-In-Progress 机制会拒绝合并，`mergeable` 翻 false。
   组合 PR 罩住了不等于零件罩住了（#805/#806/#808 缺修复提交却各自可合），兄弟 PR 逐张 guard。
6. **关闭 PR 不留接替指针**（#789，2026-09-20 查出静默关闭）：`close` 没有 `--pointer-file`
   或文件为空就拒绝；先贴指针评论，再关，再（可选）删远端分支。
7. **合的不是验过的那棵树**：`merge --expect-head/--expect-base` 与 PR 当前身份不符即中止；
   合前本机 merge-tree 取预览树，合后核对 base 指向合并提交、head 是双亲、合并树 == 预览树。
8. **合并 POST 报错但其实已生效**（Gitea 返 500 之后 main 已前进）：POST 失败不退出，先回读
   再定结论。`--record` 把整个过程写成 JSON，且引用必须带来源：`--authorized-by`（用户原话）
   与 `--authorization-source`（出自哪条消息）缺一不可，脚本字面量冒充用户原话的记录比没有更误导。

仓地址从 `git remote get-url gitea` 解析，不写死；所有输出都是一行 JSON，方便写进交接。

用法：
    python3 scripts/gitea_pr.py open --head fix/x --title "…" [--body-file PR.md] [--base main]
    python3 scripts/gitea_pr.py show 551
    python3 scripts/gitea_pr.py list [--state open|closed|all]
    python3 scripts/gitea_pr.py conflict-check --head fix/x [--base gitea/main]
    python3 scripts/gitea_pr.py guard 551 [--suffix "（已并入 #815，勿单独合入）"] [--off]
    python3 scripts/gitea_pr.py close 551 --pointer-file pointer.md [--delete-branch]
    python3 scripts/gitea_pr.py merge 551 --yes [--do merge|squash|rebase] \\
        [--expect-head SHA --expect-base SHA] [--delete-branch] \\
        [--record out.json --authorized-by "合并" --authorization-source "会话 X 第 N 轮用户消息"]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_KEYCHAIN_SERVICE = "gitea-local"
_KEYCHAIN_ACCOUNT = "a77-token"
_WIP_PREFIXES = ("WIP:", "[WIP]")


def _git(*args: str, cwd: Path = REPO_ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _remote() -> tuple[str, str, str]:
    """把 gitea remote 解成 (api_base, owner, repo)。"""

    url = _git("remote", "get-url", "gitea")
    m = re.match(r"^(https?://[^/]+)/([^/]+)/([^/]+?)(?:\.git)?$", url)
    if not m:
        raise SystemExit(f"gitea remote 不是 http(s)://host/owner/repo 形状: {url}")
    return m.group(1), m.group(2), m.group(3)


def _token() -> str:
    env = os.environ.get("GITEA_TOKEN", "").strip()
    if env:
        return env
    try:
        out = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                _KEYCHAIN_SERVICE,
                "-a",
                _KEYCHAIN_ACCOUNT,
                "-w",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            f"取不到 Gitea token：Keychain {_KEYCHAIN_SERVICE}/{_KEYCHAIN_ACCOUNT} 或 GITEA_TOKEN ({exc})"
        ) from exc
    if not out:
        raise SystemExit("Keychain 里的 Gitea token 为空")
    return out


def _api(method: str, path: str, body: dict | None = None) -> object:
    base, owner, repo = _remote()
    url = f"{base}/api/v1/repos/{owner}/{repo}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"token {_token()}")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"Gitea {method} {path} → HTTP {exc.code}: {detail}") from exc
    return json.loads(raw) if raw else {}


def _summary(pr: dict) -> dict:
    return {
        "number": pr.get("number"),
        "state": pr.get("state"),
        "merged": bool(pr.get("merged")),
        "head": (pr.get("head") or {}).get("ref"),
        "head_sha": ((pr.get("head") or {}).get("sha") or "")[:12],
        "base": (pr.get("base") or {}).get("ref"),
        "mergeable_claimed_by_gitea": pr.get("mergeable"),
        "title": pr.get("title"),
        "url": pr.get("html_url"),
    }


def _emit(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def cmd_list(args: argparse.Namespace) -> int:
    prs = _api("GET", f"/pulls?state={args.state}&limit=50")
    _emit([_summary(pr) for pr in prs] if isinstance(prs, list) else prs)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    _emit(_summary(_api("GET", f"/pulls/{args.number}")))
    return 0


def _open_pr_for_head(head: str) -> dict | None:
    prs = _api("GET", "/pulls?state=open&limit=50")
    for pr in prs if isinstance(prs, list) else []:
        if (pr.get("head") or {}).get("ref") == head:
            return pr
    return None


def cmd_open(args: argparse.Namespace) -> int:
    existing = _open_pr_for_head(args.head)
    if existing is not None:
        _emit({"already_open": True, **_summary(existing)})
        return 0
    body = ""
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    elif args.body:
        body = args.body
    pr = _api(
        "POST",
        "/pulls",
        {"head": args.head, "base": args.base, "title": args.title, "body": body},
    )
    _emit({"already_open": False, **_summary(pr)})
    return 0


def _merge_tree(base: str, head: str) -> dict:
    """本机 merge-tree 预览：clean / conflicts / 预览树 SHA。不问服务端。"""

    proc = subprocess.run(
        ["git", "merge-tree", "--write-tree", base, head],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    lines = proc.stdout.splitlines()
    conflicted = [line for line in lines if line.startswith("CONFLICT")]
    clean = proc.returncode == 0 and not conflicted
    return {
        "base": base,
        "head": head,
        "clean": clean,
        "tree": lines[0].strip() if clean and lines else None,
        "conflicts": conflicted,
        "stderr": proc.stderr.strip()[:300],
    }


def cmd_conflict_check(args: argparse.Namespace) -> int:
    result = _merge_tree(args.base, args.head)
    _emit(result)
    return 0 if result["clean"] else 1


# ---------------------------------------------------------------- guard


def _is_guarded(title: str) -> bool:
    stripped = title.lstrip()
    return any(stripped.startswith(prefix) for prefix in _WIP_PREFIXES)


def _strip_guard(title: str) -> str:
    stripped = title.lstrip()
    for prefix in _WIP_PREFIXES:
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].lstrip()
    return title


def _readback_until(number: int, done, polls: int) -> dict:
    """回读 PR 直到 done(pr) 为真或轮询用尽；Gitea 改标题后 mergeable 要过一拍才重算。"""

    pr: dict = {}
    for i in range(max(1, polls)):
        pr = _api("GET", f"/pulls/{number}")
        if done(pr):
            break
        if i + 1 < polls:
            time.sleep(1)
    return pr


def _platform_refuses(pr: dict) -> bool:
    return pr.get("mergeable") is False


def _platform_allows(pr: dict) -> bool:
    return pr.get("mergeable") is True


def cmd_guard(args: argparse.Namespace) -> int:
    pr = _api("GET", f"/pulls/{args.number}")
    before = _summary(pr)
    title = pr.get("title") or ""
    if args.off:
        if not _is_guarded(title):
            _emit({"changed": False, "reason": "not_guarded", **before})
            return 0
        new_title = _strip_guard(title)
        if args.suffix and new_title.endswith(args.suffix):
            new_title = new_title[: -len(args.suffix)].rstrip()
        want = _platform_allows
    else:
        if _is_guarded(title):
            _emit({"changed": False, "reason": "already_guarded", **before})
            return 0
        new_title = f"WIP: {title}{args.suffix or ''}"
        want = _platform_refuses
    _api("PATCH", f"/pulls/{args.number}", {"title": new_title})
    after_pr = _readback_until(args.number, want, args.polls)
    after = _summary(after_pr)
    payload = {
        "changed": True,
        "guarded": not args.off,
        "title_before": title,
        "title_after": after.get("title"),
        "head_sha_before": before.get("head_sha"),
        "head_sha_after": after.get("head_sha"),
        "mergeable_before": before.get("mergeable_claimed_by_gitea"),
        "mergeable_after": after.get("mergeable_claimed_by_gitea"),
    }
    _emit(payload)
    head_untouched = before.get("head_sha") == after.get("head_sha")
    if args.off:
        return 0 if head_untouched else 1
    # 守卫的全部意义是平台层拒合：回读仍 true 就是没守住
    return 0 if head_untouched and after.get("mergeable_claimed_by_gitea") is False else 1


# ---------------------------------------------------------------- close


def cmd_close(args: argparse.Namespace) -> int:
    pointer_path = Path(args.pointer_file)
    if not pointer_path.is_file():
        raise SystemExit(f"接替指针文件不存在：{pointer_path}（AGENTS.md：关闭 PR 必留接替指针或废弃理由）")
    pointer = pointer_path.read_text(encoding="utf-8")
    if not pointer.strip():
        raise SystemExit(f"接替指针文件为空：{pointer_path}（关闭 PR 必留接替指针或废弃理由，不静默关闭）")
    pr = _api("GET", f"/pulls/{args.number}")
    before = _summary(pr)
    if before.get("state") == "closed":
        _emit({"changed": False, "reason": "already_closed", **before})
        return 0
    comment = _api("POST", f"/issues/{args.number}/comments", {"body": pointer})
    _api("PATCH", f"/pulls/{args.number}", {"state": "closed"})
    deleted_branch = None
    if args.delete_branch and before.get("head"):
        _api("DELETE", f"/branches/{urllib.parse.quote(before['head'], safe='')}")
        deleted_branch = before["head"]
    after = _summary(_api("GET", f"/pulls/{args.number}"))
    _emit(
        {
            "changed": True,
            "pointer_comment_id": (comment or {}).get("id") if isinstance(comment, dict) else None,
            "deleted_remote_branch": deleted_branch,
            **after,
        }
    )
    return 0 if after.get("state") == "closed" and not after.get("merged") else 1


# ---------------------------------------------------------------- merge


def _sha_matches(actual: str, expected: str | None) -> bool:
    if not expected:
        return True
    expected = expected.strip().lower()
    return len(expected) >= 7 and actual.lower().startswith(expected)


def _preview_merge(number: int, base_ref: str, head_sha: str) -> dict:
    """把 PR head 取到本地，再对 gitea/<base> 做 merge-tree 预览。"""

    _git("fetch", "-q", "gitea")
    _git("fetch", "-q", "gitea", f"refs/pull/{number}/head:refs/remotes/gitea-pr/{number}")
    return _merge_tree(f"gitea/{base_ref}", head_sha)


def _verify_merge(after_pr: dict, base_ref: str, head_sha: str, preview_tree: str | None, do: str) -> dict:
    """合后用 git 核：base 指向合并提交；Do=merge 时 head 是双亲、合并树 == 预览树。"""

    merge_sha = after_pr.get("merge_commit_sha") or ""
    _git("fetch", "-q", "gitea")
    base_now = _git("rev-parse", f"gitea/{base_ref}")
    result: dict = {
        "merge_commit_sha": merge_sha[:12],
        "base_ref_after": base_now[:12],
        "base_points_at_merge_commit": bool(merge_sha) and base_now == merge_sha,
    }
    if do == "merge" and merge_sha:
        parents = _git("log", "-1", "--format=%P", merge_sha).split()
        result["head_is_parent"] = head_sha in parents
        result["tree_matches_preview"] = (
            preview_tree is not None and _git("rev-parse", f"{merge_sha}^{{tree}}") == preview_tree
        )
    result["ok"] = all(value for value in result.values() if isinstance(value, bool))
    return result


def cmd_merge(args: argparse.Namespace) -> int:
    if args.record and not (args.authorized_by and args.authorization_source):
        raise SystemExit("--record 需要同时给 --authorized-by（用户原话）与 --authorization-source（出处）：授权记录的引用必须带来源")
    pr = _api("GET", f"/pulls/{args.number}")
    before = _summary(pr)
    head_sha = (pr.get("head") or {}).get("sha") or ""
    base_sha = (pr.get("base") or {}).get("sha") or ""
    base_ref = (pr.get("base") or {}).get("ref") or "main"
    problems = []
    if before.get("state") != "open" or before.get("merged"):
        problems.append(f"state={before.get('state')} merged={before.get('merged')}")
    if not _sha_matches(head_sha, args.expect_head):
        problems.append(f"head {head_sha[:12]} != expected {args.expect_head}")
    if not _sha_matches(base_sha, args.expect_base):
        problems.append(f"base {base_sha[:12]} != expected {args.expect_base}")
    if problems:
        _emit({"aborted": True, "problems": problems, **before})
        return 2
    preview = _preview_merge(args.number, base_ref, head_sha)
    if not preview["clean"]:
        _emit({"aborted": True, "reason": "merge_tree_conflict", "preview": preview, **before})
        return 1
    if not args.yes:
        _emit({"dry_run": True, "would_merge": before, "preview": preview, "hint": "加 --yes 才真合；合入 main 须用户确认"})
        return 0
    post_error = None
    try:
        _api(
            "POST",
            f"/pulls/{args.number}/merge",
            {"Do": args.do, "delete_branch_after_merge": bool(args.delete_branch)},
        )
    except SystemExit as exc:  # 基础设施报错可能掩盖已生效的动作：先回读再定结论
        post_error = str(exc)
    after_pr = _api("GET", f"/pulls/{args.number}")
    after = _summary(after_pr)
    verification = _verify_merge(after_pr, base_ref, head_sha, preview.get("tree"), args.do) if after.get("merged") else {"ok": False}
    ok = bool(after.get("merged")) and bool(verification.get("ok"))
    payload = {
        "dry_run": False,
        "ok": ok,
        "post_error": post_error,
        "preview_tree": preview.get("tree"),
        "verification": verification,
        **after,
    }
    if args.record:
        record = {
            "pr": args.number,
            "performed_at": _now(),
            "performed_by": f"{os.environ.get('USER', 'unknown')} via scripts/gitea_pr.py",
            "authorization": {
                "live_user_message_verbatim": args.authorized_by,
                "quote_source": args.authorization_source,
                "quote_verbatim_from_live_message": True,
            },
            "expect_head": args.expect_head,
            "expect_base": args.expect_base,
            "before": before,
            "preview": preview,
            "do": args.do,
            "delete_branch_after_merge": bool(args.delete_branch),
            "post_error": post_error,
            "after": after,
            "verification": verification,
        }
        out = Path(args.record)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["record"] = str(out)
    _emit(payload)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("--state", default="open", choices=("open", "closed", "all"))
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show")
    p_show.add_argument("number", type=int)
    p_show.set_defaults(func=cmd_show)

    p_open = sub.add_parser("open")
    p_open.add_argument("--head", required=True)
    p_open.add_argument("--base", default="main")
    p_open.add_argument("--title", required=True)
    p_open.add_argument("--body-file")
    p_open.add_argument("--body")
    p_open.set_defaults(func=cmd_open)

    p_cc = sub.add_parser("conflict-check")
    p_cc.add_argument("--head", required=True)
    p_cc.add_argument("--base", default="gitea/main")
    p_cc.set_defaults(func=cmd_conflict_check)

    p_guard = sub.add_parser("guard", help="加 / 去 WIP: 前缀，让「禁止合入」成为平台层拒合")
    p_guard.add_argument("number", type=int)
    p_guard.add_argument("--suffix", default="", help="加守卫时附在标题末尾的说明；--off 时若标题以它结尾也一并去掉")
    p_guard.add_argument("--off", action="store_true", help="去掉 WIP: 前缀（只在其声明的状态不再成立时用）")
    p_guard.add_argument("--polls", type=int, default=10, help="回读 mergeable 的最多轮询次数（每次 1s）")
    p_guard.set_defaults(func=cmd_guard)

    p_close = sub.add_parser("close", help="先贴接替指针评论再关闭；无指针拒绝")
    p_close.add_argument("number", type=int)
    p_close.add_argument("--pointer-file", required=True, help="接替指针正文（替代 PR / 提交 / 文档，以及替代物失效时怎么办）")
    p_close.add_argument("--delete-branch", action="store_true", help="关闭后删远端 head 分支（本地分支与工作树不动）")
    p_close.set_defaults(func=cmd_close)

    p_merge = sub.add_parser("merge")
    p_merge.add_argument("number", type=int)
    p_merge.add_argument("--yes", action="store_true")
    p_merge.add_argument("--do", default="merge", choices=("merge", "squash", "rebase", "rebase-merge"))
    p_merge.add_argument("--expect-head", help="PR head 必须以此 SHA（≥7 位）开头，否则中止")
    p_merge.add_argument("--expect-base", help="PR base 必须以此 SHA（≥7 位）开头，否则中止")
    p_merge.add_argument("--delete-branch", action="store_true", help="delete_branch_after_merge")
    p_merge.add_argument("--record", help="把身份 / 预览 / 授权 / 回读 / 核验写成 JSON 的路径")
    p_merge.add_argument("--authorized-by", help="用户原话（逐字），与 --record 配套")
    p_merge.add_argument("--authorization-source", help="原话出处（会话 / 轮次 / 消息 id），与 --record 配套")
    p_merge.set_defaults(func=cmd_merge)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
