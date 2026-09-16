#!/usr/bin/env python3
"""Gitea PR 的开 / 查 / 冲突探测 / 合并，一把 CLI 代替每天手敲八遍的 API 片段。

## 它防的失败形状（都在 2026-09-03 的交接里有案）

1. **同一个 head 重复开 PR**（#539 对 #538）：`open` 先列 open PR，head 分支相同就打印那张、
   不再开新的。分支名是天然幂等键，不需要人记「我刚才开过没」。
2. **信了 Gitea 的 `mergeable`**（2026-08-18 十张全报 true、两张真冲突）：`conflict-check`
   走 `git merge-tree --write-tree <base> <head>`，本机算、不问服务端。
3. **手敲 curl 时 token 进了 shell 历史 / 交接**：token 只从 Keychain
   （`security find-generic-password -s gitea-local -a a77-token -w`）或 `GITEA_TOKEN` 取，
   不接受命令行参数。
4. **合入 main 不经用户确认**（AGENTS.md）：`merge` 必须显式 `--yes`，默认只打印会做什么。

仓地址从 `git remote get-url gitea` 解析，不写死；所有输出都是一行 JSON，方便写进交接。

用法：
    python3 scripts/gitea_pr.py open --head fix/x --title "…" [--body-file PR.md] [--base main]
    python3 scripts/gitea_pr.py show 551
    python3 scripts/gitea_pr.py list [--state open|closed|all]
    python3 scripts/gitea_pr.py conflict-check --head fix/x [--base gitea/main]
    python3 scripts/gitea_pr.py merge 551 --yes [--do merge|squash|rebase]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_KEYCHAIN_SERVICE = "gitea-local"
_KEYCHAIN_ACCOUNT = "a77-token"


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


def cmd_conflict_check(args: argparse.Namespace) -> int:
    proc = subprocess.run(
        ["git", "merge-tree", "--write-tree", args.base, args.head],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    conflicted = [
        line for line in proc.stdout.splitlines() if line.startswith("CONFLICT")
    ]
    _emit(
        {
            "base": args.base,
            "head": args.head,
            "clean": proc.returncode == 0 and not conflicted,
            "conflicts": conflicted,
            "stderr": proc.stderr.strip()[:300],
        }
    )
    return 0 if proc.returncode == 0 and not conflicted else 1


def cmd_merge(args: argparse.Namespace) -> int:
    before = _summary(_api("GET", f"/pulls/{args.number}"))
    if not args.yes:
        _emit({"dry_run": True, "would_merge": before, "hint": "加 --yes 才真合；合入 main 须用户确认"})
        return 0
    _api("POST", f"/pulls/{args.number}/merge", {"Do": args.do})
    after = _summary(_api("GET", f"/pulls/{args.number}"))
    _emit({"dry_run": False, **after, "main_after": _git("ls-remote", "gitea", "refs/heads/main")[:12]})
    return 0 if after.get("merged") else 1


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

    p_merge = sub.add_parser("merge")
    p_merge.add_argument("number", type=int)
    p_merge.add_argument("--yes", action="store_true")
    p_merge.add_argument("--do", default="merge", choices=("merge", "squash", "rebase", "rebase-merge"))
    p_merge.set_defaults(func=cmd_merge)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
