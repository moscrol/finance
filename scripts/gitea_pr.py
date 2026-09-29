#!/usr/bin/env python3
"""Gitea PR 的开 / 查 / 冲突探测 / 守卫 / 关闭 / 合并，一把 CLI 代替每天手敲八遍的 API 片段。

## 它防的失败形状（1–4 在 2026-09-03 的交接里有案，5–8 在 2026-09-21 两参表格家族收口里有案，9 在 2026-09-29）

1. **同一个 head 重复开 PR**（#539 对 #538）：`open` 先逐页列 open PR，head 分支相同就打印那张、
   不再开新的。分支名是天然幂等键，不需要人记「我刚才开过没」。POST 报错（含超时）也先按 head
   回读再定：#870 超时了其实开成了，#863 超时了什么都没开，只有回读分得清。
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
8. **合并 POST 报错但其实已生效**：报错描述的是客户端看到的那一段，不是服务端的结果。POST 失败
   ——HTTP 错误码，或超时 / 断连——都不退出，先在 `--readback-seconds` 预算内轮询 PR 的 `merged`
   与服务端 base ref（`git ls-remote`）再定结论（4xx 是明确拒绝，只读一次）。两者要分开看：#854 超时、#781 返 500 之后 main
   都已前进，PR 却仍是 open；#959 超时后什么都没发生。两种都有，所以只认回读，**从不自动重 POST**。
   `--record` 在每条路上都写，带 `post_error` 与 `outcome`，且引用必须带来源：`--authorized-by`
   （用户原话）与 `--authorization-source`（出自哪条消息）缺一不可，脚本字面量冒充用户原话的记录比没有更误导。
9. **客户端超时本身会造成半截状态**：客户端一断开，Gitea 就取消请求上下文，把正在跑的 `git push`
   杀在半路——#959 服务端在 30.3 s 处记 500、main 没动；#854 的 push 在断开后约 20 s 才过
   pre-receive，main 前进了、PR 再没被标成 merged。所以超时要比服务端最慢一次更长：默认 300 s，
   `GITEA_API_TIMEOUT` 可改，取值依据见 `_API_TIMEOUT_DEFAULT_S` 的注释。

仓地址从 `git remote get-url gitea` 解析，不写死；所有输出都是一行 JSON，方便写进交接。
退出码：0 成功；1 没做成 / 核验红 / 本机冲突；2 合并前身份漂移中止；3 结果未知（请求和回读都没拿到
答案）——3 时别重跑写操作，先 show / list 回读。

用法：
    python3 scripts/gitea_pr.py open --head fix/x --title "…" [--body-file PR.md] [--base main]
    python3 scripts/gitea_pr.py show 551
    python3 scripts/gitea_pr.py list [--state open|closed|all]
    python3 scripts/gitea_pr.py conflict-check --head fix/x [--base gitea/main]
    python3 scripts/gitea_pr.py guard 551 [--suffix "（已并入 #815，勿单独合入）"] [--off]
    python3 scripts/gitea_pr.py close 551 --pointer-file pointer.md [--delete-branch]
    python3 scripts/gitea_pr.py merge 551 --yes [--do merge|squash|rebase] \\
        [--expect-head SHA --expect-base SHA] [--delete-branch] \\
        [--record out.json --authorized-by "合并" --authorization-source "会话 X 第 N 轮用户消息"] \\
        [--readback-seconds 120 --readback-interval 10]
    GITEA_API_TIMEOUT=600 python3 scripts/gitea_pr.py …   # 单次请求的客户端超时（秒），默认 300
"""

from __future__ import annotations

import argparse
import datetime as _dt
import http.client
import json
import math
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
_PAGE_LIMIT = 50  # Gitea 单页上限（MAX_RESPONSE_ITEMS 默认值，本机 app.ini 未改）

# 单次请求的客户端超时。默认值是量出来的：/opt/homebrew/var/gitea/log 2026-09-21~29 全部保留日志里，
# 服务端耗时 POST /pulls（开 PR）n=168 p90 30.2 s、p99 173 s、最慢 211 s；POST …/merge n=137
# p99 51.7 s、最慢 72.3 s；GET 最慢 67.7 s。旧值 30 s 下 30/168 次开 PR、6/137 次合并超过它，而日志里
# 成簇的「201 in 30.0s」是客户端先挂断时记下的（同一秒一串 context canceled），真实尾部只会更长。
# 300 s ≈ 最慢一次的 1.4 倍；等得久的代价只在服务端真慢时才付，挂断的代价是半截状态（文首第 9 条）。
_API_TIMEOUT_ENV = "GITEA_API_TIMEOUT"
_API_TIMEOUT_DEFAULT_S = 300.0
# POST 报错后的回读预算：#854 的 ref 在客户端断开后约 20 s 才更新、#781 约 12 s，120 s 留 6 倍余量。
_READBACK_DEFAULT_S = 120.0
_READBACK_INTERVAL_DEFAULT_S = 10.0

# 请求发出后没拿到完整响应：超时、连接被拒 / 重置、响应被截断。TimeoutError、URLError、ConnectionError
# 都是 OSError 的子类（3.9 的 socket.timeout 也是）；IncompleteRead 之类只继承 HTTPException。
_TRANSPORT_ERRORS = (OSError, http.client.HTTPException)


class GiteaHTTPError(SystemExit):
    """服务端回了错误码。4xx 是明确拒绝；5xx 不代表没生效（#781 返 500 时 main 已前进）。

    仍是 SystemExit：没人接住时 CLI 照旧打印这行后退出。
    """

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class GiteaTransportError(Exception):
    """请求发出后没拿到可读的响应：服务端做没做成都有可能，写操作只能靠回读定结论。"""


def _git(*args: str, cwd: Path = REPO_ROOT, timeout: float | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=timeout
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


def _api_timeout() -> float:
    raw = os.environ.get(_API_TIMEOUT_ENV, "").strip()
    if not raw:
        return _API_TIMEOUT_DEFAULT_S
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not 0 < value < math.inf:
        raise SystemExit(f"{_API_TIMEOUT_ENV}={raw!r} 不是正的秒数")
    return value


def _api(method: str, path: str, body: dict | None = None, *, timeout: float | None = None) -> object:
    base, owner, repo = _remote()
    url = f"{base}/api/v1/repos/{owner}/{repo}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"token {_token()}")
    request.add_header("Content-Type", "application/json")
    limit = _api_timeout() if timeout is None else timeout
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=limit) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:  # 先于下一条：HTTPError 也是 OSError
        try:
            detail = exc.read().decode("utf-8", "replace")[:400]
        except _TRANSPORT_ERRORS:
            detail = "（错误正文没读到）"
        raise GiteaHTTPError(f"Gitea {method} {path} → HTTP {exc.code}: {detail}", exc.code) from exc
    except _TRANSPORT_ERRORS as exc:
        raise GiteaTransportError(
            f"Gitea {method} {path} → 没拿到响应（{type(exc).__name__}: {exc}；"
            f"等了 {time.monotonic() - started:.1f}s，超时 {limit:g}s）"
        ) from exc
    try:
        return json.loads(raw) if raw else {}
    except ValueError as exc:
        raise GiteaTransportError(f"Gitea {method} {path} → 响应不是 JSON：{raw[:120]!r}") from exc


def _rejected(exc: BaseException) -> bool:
    """4xx：服务端明确拒了这个请求，没有副作用可等；5xx 与传输错误都可能已部分生效。"""

    status = getattr(exc, "status", None)
    return isinstance(status, int) and 400 <= status < 500


def _poll(observe, done, *, budget_s: float, interval_s: float, once: bool = False) -> tuple[list, float]:
    """回读到 done(观测) 为真或预算用完；每次请求的超时压在剩余预算内，总等待约 budget_s。

    observe(timeout) 返回一个 dict，自己接住请求错误（记进 dict），这里不重发任何写请求。
    """

    started = time.monotonic()
    deadline = started + budget_s
    observations: list = []
    while True:
        remaining = deadline - time.monotonic()
        observation = observe(max(1.0, min(_api_timeout(), remaining)))
        observation["t_s"] = round(time.monotonic() - started, 1)
        observations.append(observation)
        if once or done(observation):
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval_s, remaining))
    return observations, round(time.monotonic() - started, 1)


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


def _open_pr_for_head(head: str, *, timeout: float | None = None) -> dict | None:
    """逐页找：只看第一页会把第 51 张 open PR 当成不存在，「没开成」的判定就不可信了。"""

    for page in range(1, 41):  # 上限 2000 张：服务端若不认 page 参数，别在同一页上转圈
        prs = _api("GET", f"/pulls?state=open&limit={_PAGE_LIMIT}&page={page}", timeout=timeout)
        if not isinstance(prs, list):
            return None
        for pr in prs:
            if (pr.get("head") or {}).get("ref") == head:
                return pr
        if len(prs) < _PAGE_LIMIT:
            return None
    return None


def cmd_open(args: argparse.Namespace) -> int:
    existing = _open_pr_for_head(args.head)
    if existing is not None:
        _emit({"outcome": "already_open", "already_open": True, **_summary(existing)})
        return 0
    body = ""
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    elif args.body:
        body = args.body
    try:
        pr = _api(
            "POST",
            "/pulls",
            {"head": args.head, "base": args.base, "title": args.title, "body": body},
        )
    except (GiteaTransportError, SystemExit) as exc:  # POST 报错不等于没开成：按 head 回读再定
        return _open_readback(args, exc)
    _emit({"outcome": "created", "already_open": False, **_summary(pr)})
    return 0


def _open_readback(args: argparse.Namespace, exc: BaseException) -> int:
    rejected = _rejected(exc)

    def observe(timeout: float) -> dict:
        try:
            return {"pr": _open_pr_for_head(args.head, timeout=timeout)}
        except (GiteaTransportError, SystemExit) as err:
            return {"error": str(err)}

    observations, waited = _poll(
        observe,
        lambda obs: obs.get("pr") is not None,
        budget_s=args.readback_seconds,
        interval_s=args.readback_interval,
        once=rejected,
    )
    last = observations[-1]
    report = {
        "post_error": str(exc),
        "readback": {"polls": len(observations), "waited_s": waited, "budget_s": args.readback_seconds},
    }
    if last.get("pr") is not None:
        # 服务端明确拒了（多半 409 已存在）还查得到，那张是早就开着的，不是这次开的
        outcome = "already_open" if rejected else "created_despite_post_error"
        _emit({"outcome": outcome, "already_open": rejected, **report, **_summary(last["pr"])})
        return 0
    if "error" in last:
        _emit(
            {
                "outcome": "unknown",
                **report,
                "hint": f"POST 与回读都没拿到响应，开没开成未知：稍后 list --state open 找 head={args.head}，别直接重跑",
            }
        )
        return 3
    _emit(
        {
            "outcome": "not_created",
            **report,
            "hint": f"回读 {waited}s 内没有 head={args.head} 的 open PR：服务端没开成（原因看 post_error）；重跑 open 是安全的（按 head 幂等）",
        }
    )
    return 1


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
    patch_error = None
    try:
        _api("PATCH", f"/pulls/{args.number}", {"title": new_title})
    except (GiteaTransportError, SystemExit) as exc:  # 改没改成交给下面的回读判定
        patch_error = str(exc)
    after_pr = _readback_until(args.number, want, args.polls)
    after = _summary(after_pr)
    payload = {
        "changed": True,
        "guarded": not args.off,
        "patch_error": patch_error,
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
        return 0 if head_untouched and not _is_guarded(after.get("title") or "") else 1
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
    """把 PR head 取到本地，再对 gitea/<base> 做 merge-tree 预览；记下预览对着的 base 提交，回读拿它比。"""

    _git("fetch", "-q", "gitea")
    _git("fetch", "-q", "gitea", f"refs/pull/{number}/head:refs/remotes/gitea-pr/{number}")
    preview = _merge_tree(f"gitea/{base_ref}", head_sha)
    preview["base_sha"] = _git("rev-parse", f"gitea/{base_ref}")
    return preview


def _verify_merge(merge_sha: str, base_ref: str, head_sha: str, preview_tree: str | None, do: str) -> dict:
    """合后用 git 核：base 指向合并提交；Do=merge 时 head 是双亲、合并树 == 预览树。"""

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


def _verify_safely(merge_sha: str, base_ref: str, head_sha: str, preview_tree: str | None, do: str) -> dict:
    try:
        return _verify_merge(merge_sha, base_ref, head_sha, preview_tree, do)
    except (subprocess.SubprocessError, OSError) as exc:  # 核验自己失败也不能挡住 --record
        return {"merge_commit_sha": merge_sha[:12], "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _observe_merge(number: int, base_ref: str, timeout: float) -> dict:
    """一次回读：PR 对象 + 服务端 base ref。分开记，因为两者会对不上（#854 / #781）。"""

    observation: dict = {}
    try:
        observation["pr"] = _api("GET", f"/pulls/{number}", timeout=timeout)
    except (GiteaTransportError, SystemExit) as exc:
        observation["pr_error"] = str(exc)
    if not (observation.get("pr") or {}).get("merged"):
        try:
            out = _git("ls-remote", "gitea", f"refs/heads/{base_ref}", timeout=timeout)
            observation["base_tip"] = out.split()[0] if out else ""
        except (subprocess.SubprocessError, OSError) as exc:
            observation["base_error"] = f"{type(exc).__name__}: {exc}"
    return observation


def _merge_outcome(
    observations: list, base_before: str, base_ref: str, head_sha: str, preview_tree: str | None, do: str
) -> tuple[str, dict, dict]:
    """按最后一次回读定 (outcome, 最近读到的 PR, verification)。"""

    last = observations[-1]
    pr = next((obs["pr"] for obs in reversed(observations) if isinstance(obs.get("pr"), dict)), {})
    if (last.get("pr") or {}).get("merged"):
        return "merged", pr, _verify_safely(pr.get("merge_commit_sha") or "", base_ref, head_sha, preview_tree, do)
    tip = last.get("base_tip")
    if tip and tip != base_before:
        # base 前进了、PR 没标 merged：tip 的双亲含 head 才认作这次合并落了地
        verification = _verify_safely(tip, base_ref, head_sha, preview_tree, do)
        return ("landed_pr_not_marked" if verification.get("head_is_parent") else "unknown"), pr, verification
    if tip:
        return "not_merged", pr, {"ok": False}
    return "unknown", pr, {"ok": False}


def _brief(observation: dict) -> dict:
    """写进 --record 的回读轨迹，只留判定用得上的字段。"""

    brief: dict = {"t_s": observation.get("t_s")}
    pr = observation.get("pr")
    if isinstance(pr, dict):
        brief.update(state=pr.get("state"), merged=bool(pr.get("merged")))
    if "base_tip" in observation:
        brief["base_tip"] = observation["base_tip"][:12]
    for key in ("pr_error", "base_error"):
        if key in observation:
            brief[key] = observation[key]
    return brief


def _merge_hint(outcome: str, number: int, base_ref: str, waited: float, verification: dict) -> str | None:
    if outcome == "landed_pr_not_marked":
        return (
            f"合并提交 {verification.get('merge_commit_sha')} 已在 {base_ref} 上（双亲含 head），Gitea 却没把 PR"
            f" 标成 merged：别再 POST；用 close --pointer-file 指向该提交收口"
        )
    if outcome == "not_merged":
        return (
            f"回读 {waited}s 内 PR 未合、{base_ref} 未动：这次没合成。要重试先 show {number} 确认，"
            f"再带 --expect-head / --expect-base 重跑（脚本不会自己重 POST）"
        )
    if outcome == "unknown":
        return f"回读窗口内没能确定结果：别重跑 merge；稍后 show {number} 与 git ls-remote gitea refs/heads/{base_ref} 再定"
    return None


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
    post_rejected = False
    post_started_at = _now()
    try:
        _api(
            "POST",
            f"/pulls/{args.number}/merge",
            {"Do": args.do, "delete_branch_after_merge": bool(args.delete_branch)},
        )
    except SystemExit as exc:  # HTTP 错误码：4xx 是明确拒绝，5xx 可能已部分生效
        post_error = str(exc)
        post_rejected = _rejected(exc)
    except GiteaTransportError as exc:  # 超时 / 断连：服务端可能做完了、做了一半、没做
        post_error = str(exc)
    base_before = preview.get("base_sha") or base_sha

    def settled(observation: dict) -> bool:
        tip = observation.get("base_tip")
        return bool((observation.get("pr") or {}).get("merged")) or bool(tip and tip != base_before)

    observations, waited = _poll(
        lambda timeout: _observe_merge(args.number, base_ref, timeout),
        settled,
        budget_s=args.readback_seconds,
        interval_s=args.readback_interval,
        once=post_rejected,
    )
    outcome, after_pr, verification = _merge_outcome(
        observations, base_before, base_ref, head_sha, preview.get("tree"), args.do
    )
    after = _summary(after_pr) if after_pr else {}
    ok = outcome == "merged" and bool(verification.get("ok"))
    readback = {"polls": len(observations), "waited_s": waited, "budget_s": args.readback_seconds}
    payload = {
        "dry_run": False,
        "number": args.number,
        "ok": ok,
        "outcome": outcome,
        "post_error": post_error,
        "readback": readback,
        "preview_tree": preview.get("tree"),
        "verification": verification,
        **after,
    }
    hint = _merge_hint(outcome, args.number, base_ref, waited, verification)
    if hint:
        payload["hint"] = hint
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
            "client_timeout_s": _api_timeout(),
            "post_started_at": post_started_at,
            "post_error": post_error,
            "outcome": outcome,
            "readback": {**readback, "observations": [_brief(obs) for obs in observations]},
            "after": after,
            "verification": verification,
        }
        out = Path(args.record)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["record"] = str(out)
    _emit(payload)
    if ok:
        return 0
    return 3 if outcome == "unknown" else 1


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

    for p in (p_open, p_merge):
        p.add_argument(
            "--readback-seconds",
            type=float,
            default=_READBACK_DEFAULT_S,
            help="POST 报错后回读的总预算（秒）；4xx 明确拒绝只读一次",
        )
        p.add_argument("--readback-interval", type=float, default=_READBACK_INTERVAL_DEFAULT_S, help="回读间隔（秒）")

    args = parser.parse_args(argv)
    _api_timeout()  # 坏的 GITEA_API_TIMEOUT 在任何请求之前就拒，免得写到一半才炸
    try:
        return int(args.func(args))
    except GiteaTransportError as exc:  # 没有专门回读的路径（show / list / close …）走这里
        print(f"{exc}\n没拿到响应不等于没做成：写操作先 show / list 回读，再决定是否重跑", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
