"""scripts/gitea_pr.py 的 open / guard / close / merge 子命令：每个测试钉住一个失败形状。

不打真 Gitea：多数测试把 `_api` 换成内存里的假仓；客户端超时一节换的是更底下的
`urllib.request.urlopen`，真 `_api` 照跑——#854 / #959 的缺陷就出在两者之间（`_api` 只转 HTTPError、
`cmd_merge` 只接 SystemExit，TimeoutError 两头都漏），只换 `_api` 的测试看不见这条缝。
`_git` / `_merge_tree` / 时钟也换成假件；假仓地址是 `.invalid` 域名，万一漏换也打不到真 Gitea。
变异自检：去掉指针检查 → test_close_refuses_without_pointer 红；去掉 --expect-head 比对 →
test_merge_aborts_on_head_drift 红；去掉 POST 的 try/except → test_merge_post_error_but_readback_merged 红；
去掉合后树核对 → test_merge_happy_path 红；去掉幂等 → test_guard_is_idempotent 红。
超时一节的变异读数见该节开头。
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = REPO_ROOT / "scripts" / "gitea_pr.py"
_spec = importlib.util.spec_from_file_location("gitea_pr", _SCRIPT)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

HEAD_SHA = "06f74ef14dbe246cf8d9330b43711ffacb12284f"
BASE_SHA = "728f327160bbd2485cb635e7ef09d040d718d7b5"
MERGE_SHA = "8aff6ebc3f0ea681a80179fbca8e1f39a815f103"
PREVIEW_TREE = "0af605383f785a32c47d06fbf7d2b26c5775c378"
REMOTE_URL = "http://gitea.invalid:3300/a77/finance-workspace-private.git"
API_PREFIX = "/api/v1/repos/a77/finance-workspace-private"


def _pr(**overrides: object) -> dict:
    pr = {
        "number": 815,
        "state": "open",
        "merged": False,
        "mergeable": True,
        "title": "fix(fincalc): 行值快照",
        "html_url": "http://gitea.local/a77/repo/pulls/815",
        "head": {"ref": "fix/row-snapshot", "sha": HEAD_SHA},
        "base": {"ref": "main", "sha": BASE_SHA},
        "merge_commit_sha": "",
    }
    pr.update(overrides)
    return pr


class FakeClock:
    """假时钟：sleep 推进 monotonic；FakeUrlopen 模拟超时时推进整段超时，等于客户端干等满。"""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeGitea:
    """内存假仓：记录每次调用，模拟 Gitea 把 WIP 前缀折进 mergeable、合并后改 state、按页列 open PR。

    mark_merged=False 是 #854 的形状：合并落到了 main（git_main 前进），PR 对象却没被标成 merged。
    """

    def __init__(
        self,
        pr: dict | None,
        *,
        honor_wip: bool = True,
        fail_post_merge: bool = False,
        mark_merged: bool = True,
        others: list[dict] | None = None,
    ):
        self.pr = pr
        self.others = others or []
        self.calls: list[tuple[str, str, dict | None]] = []
        self.honor_wip = honor_wip
        self.fail_post_merge = fail_post_merge
        self.mark_merged = mark_merged
        self.deleted_branches: list[str] = []
        self.git_main = BASE_SHA
        self.ls_remote_fails = False

    def __call__(self, method: str, path: str, body: dict | None = None, *, timeout: float | None = None) -> object:
        self.calls.append((method, path, body))
        route, _, query = path.partition("?")
        if method == "GET" and route == "/pulls":
            params = dict(urllib.parse.parse_qsl(query))
            listed = [p for p in [*self.others, *([self.pr] if self.pr else [])] if p["state"] == params["state"]]
            limit, page = int(params["limit"]), int(params.get("page", "1"))
            return json.loads(json.dumps(listed[(page - 1) * limit : page * limit]))
        if method == "POST" and route == "/pulls":
            assert body is not None
            head = {"ref": body["head"], "sha": HEAD_SHA}
            self.pr = _pr(number=960, title=body["title"], head=head, base={"ref": body["base"], "sha": BASE_SHA})
            return json.loads(json.dumps(self.pr))
        assert self.pr is not None, f"no PR for {method} {path}"
        n = self.pr["number"]
        if method == "GET" and path == f"/pulls/{n}":
            return json.loads(json.dumps(self.pr))
        if method == "PATCH" and path == f"/pulls/{n}":
            assert body is not None
            if "title" in body:
                self.pr["title"] = body["title"]
                if self.honor_wip:
                    self.pr["mergeable"] = not mod._is_guarded(body["title"])
            if body.get("state") == "closed":
                self.pr["state"] = "closed"
            return json.loads(json.dumps(self.pr))
        if method == "POST" and path == f"/issues/{n}/comments":
            assert body is not None and body["body"].strip()
            return {"id": 4242, "body": body["body"]}
        if method == "POST" and path == f"/pulls/{n}/merge":
            self.merge_body = body
            self.git_main = MERGE_SHA
            if self.mark_merged:
                self.pr.update({"state": "closed", "merged": True, "merge_commit_sha": MERGE_SHA})
            if self.fail_post_merge:
                raise SystemExit("Gitea POST /pulls/815/merge → HTTP 500: boom")
            return {}
        if method == "DELETE" and path.startswith("/branches/"):
            self.deleted_branches.append(urllib.parse.unquote(path[len("/branches/") :]))
            return {}
        raise AssertionError(f"unexpected call {method} {path}")

    def methods(self) -> list[str]:
        return [f"{m} {p.split('?')[0]}" for m, p, _ in self.calls]


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class FakeUrlopen:
    """urlopen 层的假 Gitea：请求交给 FakeGitea 处理，再按剧本决定客户端收不收得到响应。

    剧本按 (method, 路由) 给一串模式，逐次取用、最后一个一直沿用：
    "ok" 正常；"lost" 服务端做了、响应没回来（#854 / #870）；"dropped" 服务端没做、客户端照样
    等满超时（#959 / #863）；"lost500" 服务端做了却回 500（#781）；"http405" 服务端明确拒绝。
    """

    def __init__(self, fake: FakeGitea, clock: FakeClock, script: dict | None = None) -> None:
        self.fake = fake
        self.clock = clock
        self.script = {key: [modes] if isinstance(modes, str) else list(modes) for key, modes in (script or {}).items()}
        self.seen: list[tuple[str, str, float]] = []

    def _mode(self, method: str, route: str) -> str:
        modes = self.script.get((method, route)) or ["ok"]
        return modes.pop(0) if len(modes) > 1 else modes[0]

    def __call__(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
        url = urllib.parse.urlsplit(request.full_url)
        assert url.path.startswith(API_PREFIX), url.path
        assert request.get_header("Authorization") == "token test-token"
        route = url.path[len(API_PREFIX) :]
        path = f"{route}?{url.query}" if url.query else route
        method = request.get_method()
        self.seen.append((method, path, timeout))
        mode = self._mode(method, route)
        if mode == "http405":
            raise urllib.error.HTTPError(request.full_url, 405, "Method Not Allowed", {}, io.BytesIO(b'{"message":"no"}'))
        if mode == "dropped":
            self.clock.now += timeout
            raise TimeoutError("timed out")
        result = self.fake(method, path, json.loads(request.data) if request.data else None)
        if mode == "lost":
            self.clock.now += timeout
            raise TimeoutError("timed out")
        if mode == "lost500":
            raise urllib.error.HTTPError(request.full_url, 500, "Internal Server Error", {}, io.BytesIO(b"git push:"))
        return FakeResponse(result)

    def count(self, method: str, route: str) -> int:
        return sum(1 for m, p, _ in self.seen if m == method and p.split("?")[0] == route)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake_clock = FakeClock()
    monkeypatch.setattr(mod.time, "monotonic", fake_clock.monotonic)
    monkeypatch.setattr(mod.time, "sleep", fake_clock.sleep)
    return fake_clock


@pytest.fixture
def emitted(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> list:
    out: list = []
    monkeypatch.setattr(mod, "_emit", out.append)
    monkeypatch.delenv("GITEA_API_TIMEOUT", raising=False)
    return out


def _install(
    monkeypatch: pytest.MonkeyPatch, fake: FakeGitea, *, tree_after: str = PREVIEW_TREE, fake_api: bool = True
) -> None:
    if fake_api:
        monkeypatch.setattr(mod, "_api", fake)

    def fake_git(*args: str, cwd: Path = REPO_ROOT, timeout: float | None = None) -> str:
        if args[0] == "fetch":
            return ""
        if args == ("remote", "get-url", "gitea"):
            return REMOTE_URL
        if args == ("ls-remote", "gitea", "refs/heads/main"):
            if fake.ls_remote_fails:
                raise subprocess.CalledProcessError(128, ["git", *args])
            return f"{fake.git_main}\trefs/heads/main"
        if args == ("rev-parse", "gitea/main"):
            return fake.git_main
        if args == ("log", "-1", "--format=%P", MERGE_SHA):
            return f"{BASE_SHA} {HEAD_SHA}"
        if args == ("rev-parse", f"{MERGE_SHA}^{{tree}}"):
            return tree_after
        raise AssertionError(f"unexpected git {args}")

    monkeypatch.setattr(mod, "_git", fake_git)
    monkeypatch.setattr(
        mod,
        "_merge_tree",
        lambda base, head: {"base": base, "head": head, "clean": True, "tree": PREVIEW_TREE, "conflicts": [], "stderr": ""},
    )


def _install_http(
    monkeypatch: pytest.MonkeyPatch, fake: FakeGitea, clock: FakeClock, script: dict | None = None
) -> FakeUrlopen:
    """真 `_api` 照跑，只把 urlopen 换成按剧本出错的假服务端。"""

    _install(monkeypatch, fake, fake_api=False)
    monkeypatch.setenv("GITEA_TOKEN", "test-token")
    opener = FakeUrlopen(fake, clock, script)
    monkeypatch.setattr(mod.urllib.request, "urlopen", opener)
    return opener


# ---------------------------------------------------------------- guard


def test_guard_adds_prefix_and_reads_back_platform_refusal(monkeypatch, emitted):
    fake = FakeGitea(_pr())
    _install(monkeypatch, fake)
    rc = mod.main(["guard", "815", "--suffix", "（已并入 #816，勿单独合入）"])
    assert rc == 0
    patch = [b for m, p, b in fake.calls if m == "PATCH"]
    assert patch == [{"title": "WIP: fix(fincalc): 行值快照（已并入 #816，勿单独合入）"}]
    assert emitted[-1]["mergeable_before"] is True
    assert emitted[-1]["mergeable_after"] is False
    assert emitted[-1]["head_sha_after"] == HEAD_SHA[:12]


def test_guard_is_idempotent(monkeypatch, emitted):
    fake = FakeGitea(_pr(title="WIP: 已经守住了", mergeable=False))
    _install(monkeypatch, fake)
    assert mod.main(["guard", "815"]) == 0
    assert "PATCH /pulls/815" not in fake.methods()
    assert emitted[-1]["reason"] == "already_guarded"


def test_guard_reports_red_when_platform_does_not_honor_prefix(monkeypatch, emitted):
    fake = FakeGitea(_pr(), honor_wip=False)
    _install(monkeypatch, fake)
    rc = mod.main(["guard", "815", "--polls", "2"])
    assert rc == 1
    assert emitted[-1]["mergeable_after"] is True


def test_guard_off_strips_prefix_and_suffix(monkeypatch, emitted):
    fake = FakeGitea(_pr(title="WIP: fix(fincalc): 行值快照（已并入 #816，勿单独合入）", mergeable=False))
    _install(monkeypatch, fake)
    rc = mod.main(["guard", "815", "--off", "--suffix", "（已并入 #816，勿单独合入）"])
    assert rc == 0
    patch = [b for m, p, b in fake.calls if m == "PATCH"]
    assert patch == [{"title": "fix(fincalc): 行值快照"}]
    assert emitted[-1]["mergeable_after"] is True


# ---------------------------------------------------------------- close


def test_close_refuses_without_pointer(monkeypatch, emitted, tmp_path):
    fake = FakeGitea(_pr())
    _install(monkeypatch, fake)
    with pytest.raises(SystemExit):
        mod.main(["close", "815", "--pointer-file", str(tmp_path / "missing.md")])
    empty = tmp_path / "empty.md"
    empty.write_text("   \n", encoding="utf-8")
    with pytest.raises(SystemExit):
        mod.main(["close", "815", "--pointer-file", str(empty)])
    assert fake.calls == []


def test_close_posts_pointer_then_closes_then_deletes_branch(monkeypatch, emitted, tmp_path):
    fake = FakeGitea(_pr())
    _install(monkeypatch, fake)
    pointer = tmp_path / "pointer.md"
    pointer.write_text("接替：#816 / 8aff6ebc；若回退可从 06f74ef1 重放。", encoding="utf-8")
    rc = mod.main(["close", "815", "--pointer-file", str(pointer), "--delete-branch"])
    assert rc == 0
    assert fake.methods() == [
        "GET /pulls/815",
        "POST /issues/815/comments",
        "PATCH /pulls/815",
        "DELETE /branches/fix%2Frow-snapshot",
        "GET /pulls/815",
    ]
    assert fake.deleted_branches == ["fix/row-snapshot"]
    assert emitted[-1]["pointer_comment_id"] == 4242
    assert emitted[-1]["state"] == "closed" and emitted[-1]["merged"] is False


def test_close_already_closed_is_noop(monkeypatch, emitted, tmp_path):
    fake = FakeGitea(_pr(state="closed"))
    _install(monkeypatch, fake)
    pointer = tmp_path / "pointer.md"
    pointer.write_text("接替：#816", encoding="utf-8")
    assert mod.main(["close", "815", "--pointer-file", str(pointer)]) == 0
    assert fake.methods() == ["GET /pulls/815"]
    assert emitted[-1]["reason"] == "already_closed"


# ---------------------------------------------------------------- merge


def test_merge_aborts_on_head_drift_before_any_fetch_or_post(monkeypatch, emitted):
    fake = FakeGitea(_pr())
    _install(monkeypatch, fake)
    previews: list = []
    monkeypatch.setattr(mod, "_preview_merge", lambda *a: previews.append(a))
    rc = mod.main(["merge", "815", "--yes", "--expect-head", "deadbeef0"])
    assert rc == 2
    assert previews == []
    assert "POST /pulls/815/merge" not in fake.methods()
    assert emitted[-1]["aborted"] is True and "head" in emitted[-1]["problems"][0]


def test_merge_record_requires_verbatim_quote_and_its_source(monkeypatch, emitted, tmp_path):
    fake = FakeGitea(_pr())
    _install(monkeypatch, fake)
    with pytest.raises(SystemExit):
        mod.main(["merge", "815", "--yes", "--record", str(tmp_path / "r.json"), "--authorized-by", "合并"])
    assert fake.calls == []


def test_merge_aborts_on_local_conflict(monkeypatch, emitted):
    fake = FakeGitea(_pr())
    _install(monkeypatch, fake)
    monkeypatch.setattr(
        mod,
        "_merge_tree",
        lambda base, head: {"base": base, "head": head, "clean": False, "tree": None, "conflicts": ["CONFLICT (content): x"], "stderr": ""},
    )
    rc = mod.main(["merge", "815", "--yes"])
    assert rc == 1
    assert "POST /pulls/815/merge" not in fake.methods()
    assert emitted[-1]["reason"] == "merge_tree_conflict"


def test_merge_dry_run_never_posts(monkeypatch, emitted):
    fake = FakeGitea(_pr())
    _install(monkeypatch, fake)
    assert mod.main(["merge", "815", "--expect-head", HEAD_SHA[:8]]) == 0
    assert "POST /pulls/815/merge" not in fake.methods()
    assert emitted[-1]["dry_run"] is True and emitted[-1]["preview"]["tree"] == PREVIEW_TREE


def test_merge_happy_path_verifies_tree_and_writes_record(monkeypatch, emitted, tmp_path):
    fake = FakeGitea(_pr())
    _install(monkeypatch, fake)
    record = tmp_path / "records" / "merge-815.json"
    rc = mod.main(
        [
            "merge", "815", "--yes", "--delete-branch",
            "--expect-head", HEAD_SHA, "--expect-base", BASE_SHA[:10],
            "--record", str(record), "--authorized-by", "合并", "--authorization-source", "本会话 user turn 2",
        ]
    )
    assert rc == 0
    assert fake.merge_body == {"Do": "merge", "delete_branch_after_merge": True}
    payload = emitted[-1]
    assert payload["ok"] is True and payload["post_error"] is None
    assert payload["verification"]["tree_matches_preview"] is True
    assert payload["verification"]["head_is_parent"] is True
    assert payload["verification"]["base_points_at_merge_commit"] is True
    data = json.loads(record.read_text(encoding="utf-8"))
    assert data["authorization"] == {
        "live_user_message_verbatim": "合并",
        "quote_source": "本会话 user turn 2",
        "quote_verbatim_from_live_message": True,
    }
    assert data["preview"]["tree"] == PREVIEW_TREE and data["preview"]["base_sha"] == BASE_SHA
    assert data["after"]["merged"] is True and data["verification"]["ok"] is True
    assert data["outcome"] == "merged" and data["post_error"] is None and data["readback"]["polls"] == 1


def test_merge_flags_tree_mismatch_as_red(monkeypatch, emitted):
    """合并成功但合并树 != 预览树：merged 仍 true，ok 必须 false、退 1——「合的不是验过的那棵树」。"""

    fake = FakeGitea(_pr())
    _install(monkeypatch, fake, tree_after="1111111111111111111111111111111111111111")
    rc = mod.main(["merge", "815", "--yes"])
    assert rc == 1
    assert emitted[-1]["merged"] is True
    assert emitted[-1]["verification"]["tree_matches_preview"] is False
    assert emitted[-1]["ok"] is False


def test_merge_post_error_but_readback_merged_is_success(monkeypatch, emitted):
    fake = FakeGitea(_pr(), fail_post_merge=True)
    _install(monkeypatch, fake)
    rc = mod.main(["merge", "815", "--yes"])
    assert rc == 0
    assert "HTTP 500" in emitted[-1]["post_error"]
    assert emitted[-1]["ok"] is True and emitted[-1]["merged"] is True


def test_merge_tree_reports_conflicts_from_git(monkeypatch):
    class Proc:
        returncode = 1
        stdout = "CONFLICT (content): Merge conflict in a.py\n"
        stderr = ""

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: Proc())
    result = mod._merge_tree("gitea/main", "fix/x")
    assert result["clean"] is False and result["tree"] is None
    assert result["conflicts"] == ["CONFLICT (content): Merge conflict in a.py"]


# ---------------------------------------------------------------- 客户端超时（打在 urlopen 层，真 _api 照跑）

MERGE_ARGV = ["merge", "815", "--yes", "--expect-head", HEAD_SHA, "--expect-base", BASE_SHA[:10]]


def _record_argv(path: Path) -> list[str]:
    return ["--record", str(path), "--authorized-by", "合并", "--authorization-source", "测试会话 user turn 1"]


def test_api_timeout_default_env_override_and_rejects_bad_values(monkeypatch, emitted, clock):
    fake = FakeGitea(_pr())
    opener = _install_http(monkeypatch, fake, clock)
    assert mod.main(["show", "815"]) == 0
    assert opener.seen[-1][2] == 300.0  # 旧值 30 s；取值依据见 _API_TIMEOUT_DEFAULT_S 的注释
    monkeypatch.setenv("GITEA_API_TIMEOUT", "45")
    assert mod.main(["show", "815"]) == 0
    assert opener.seen[-1][2] == 45.0
    for bad in ("abc", "0", "-5", "nan", "inf"):
        monkeypatch.setenv("GITEA_API_TIMEOUT", bad)
        sent = len(opener.seen)
        with pytest.raises(SystemExit, match="GITEA_API_TIMEOUT"):
            mod.main(["show", "815"])
        assert len(opener.seen) == sent  # 坏值在任何请求之前就拒


def test_merge_post_timeout_after_server_applied_reads_back_merged(monkeypatch, emitted, clock, tmp_path):
    """服务端合完了、响应没回来（客户端等满 300 s）：回读认出 merged，核验照做，记录照写。"""

    fake = FakeGitea(_pr())
    opener = _install_http(monkeypatch, fake, clock, {("POST", "/pulls/815/merge"): "lost"})
    record = tmp_path / "merge-815.json"
    assert mod.main([*MERGE_ARGV, *_record_argv(record)]) == 0
    assert opener.count("POST", "/pulls/815/merge") == 1  # 从不自动重 POST
    assert emitted[-1]["outcome"] == "merged" and emitted[-1]["ok"] is True
    data = json.loads(record.read_text(encoding="utf-8"))
    assert "TimeoutError" in data["post_error"] and "超时 300s" in data["post_error"]
    assert data["outcome"] == "merged" and data["after"]["merged"] is True
    assert data["verification"]["ok"] is True and data["verification"]["tree_matches_preview"] is True
    assert data["client_timeout_s"] == 300.0 and data["readback"]["polls"] == 1


def test_merge_post_timeout_without_apply_reports_not_merged(monkeypatch, emitted, clock, tmp_path):
    """#959：服务端没合成，客户端同样只看到超时。整个回读预算里 PR 未合、base 未动 → not_merged。"""

    fake = FakeGitea(_pr())
    opener = _install_http(monkeypatch, fake, clock, {("POST", "/pulls/815/merge"): "dropped"})
    record = tmp_path / "merge-815.json"
    argv = [*MERGE_ARGV, *_record_argv(record), "--readback-seconds", "60", "--readback-interval", "15"]
    assert mod.main(argv) == 1
    assert opener.count("POST", "/pulls/815/merge") == 1
    data = json.loads(record.read_text(encoding="utf-8"))
    assert "TimeoutError" in data["post_error"]
    assert data["outcome"] == "not_merged" and data["after"]["merged"] is False
    assert data["readback"]["polls"] == 5 and data["readback"]["waited_s"] == 60.0  # t = 0/15/30/45/60
    assert {obs["base_tip"] for obs in data["readback"]["observations"]} == {BASE_SHA[:12]}
    assert emitted[-1]["ok"] is False and "不会自己重 POST" in emitted[-1]["hint"]


@pytest.mark.parametrize("mode", ["lost", "lost500"], ids=["timeout-854", "http500-781"])
def test_merge_landed_on_base_but_pr_not_marked(monkeypatch, emitted, clock, tmp_path, mode):
    """#854 / #781：main 前进到合并提交，PR 却仍 open。只看 PR 的 merged 会把它判成「没合」。"""

    fake = FakeGitea(_pr(), mark_merged=False)
    opener = _install_http(monkeypatch, fake, clock, {("POST", "/pulls/815/merge"): mode})
    record = tmp_path / "merge-815.json"
    assert mod.main([*MERGE_ARGV, *_record_argv(record)]) == 1
    assert opener.count("POST", "/pulls/815/merge") == 1
    data = json.loads(record.read_text(encoding="utf-8"))
    assert data["post_error"]
    assert data["outcome"] == "landed_pr_not_marked"
    assert data["after"]["state"] == "open" and data["after"]["merged"] is False
    assert data["verification"]["head_is_parent"] is True and data["verification"]["tree_matches_preview"] is True
    assert data["readback"]["observations"][-1]["base_tip"] == MERGE_SHA[:12]
    assert "close --pointer-file" in emitted[-1]["hint"]


def test_merge_post_timeout_and_readback_unreachable_is_unknown(monkeypatch, emitted, clock, tmp_path):
    """POST 与回读都没拿到答案：退 3（结果未知），记录照写，也不重 POST。"""

    fake = FakeGitea(_pr())
    fake.ls_remote_fails = True
    script = {("POST", "/pulls/815/merge"): "dropped", ("GET", "/pulls/815"): ["ok", "dropped"]}
    opener = _install_http(monkeypatch, fake, clock, script)
    record = tmp_path / "merge-815.json"
    assert mod.main([*MERGE_ARGV, *_record_argv(record), "--readback-seconds", "30"]) == 3
    assert opener.count("POST", "/pulls/815/merge") == 1
    data = json.loads(record.read_text(encoding="utf-8"))
    assert "TimeoutError" in data["post_error"]
    assert data["outcome"] == "unknown" and data["after"] == {}
    last = data["readback"]["observations"][-1]
    assert "TimeoutError" in last["pr_error"] and "CalledProcessError" in last["base_error"]
    assert "别重跑" in emitted[-1]["hint"]


def test_merge_post_rejected_4xx_reads_back_once(monkeypatch, emitted, clock, tmp_path):
    """405（比如标题还挂着 WIP:）是服务端明确拒绝，没有副作用可等：回读一次就定，不干等预算。"""

    fake = FakeGitea(_pr())
    _install_http(monkeypatch, fake, clock, {("POST", "/pulls/815/merge"): "http405"})
    record = tmp_path / "merge-815.json"
    assert mod.main([*MERGE_ARGV, *_record_argv(record)]) == 1
    data = json.loads(record.read_text(encoding="utf-8"))
    assert "HTTP 405" in data["post_error"]
    assert data["outcome"] == "not_merged" and data["readback"]["polls"] == 1
    assert clock.sleeps == []


def test_open_post_timeout_but_created_reports_it(monkeypatch, emitted, clock):
    """#870：开 PR 的 POST 超时了，服务端其实开成了。按 head 回读找到它、退 0，不开第二张。"""

    fake = FakeGitea(None)
    opener = _install_http(monkeypatch, fake, clock, {("POST", "/pulls"): "lost"})
    assert mod.main(["open", "--head", "fix/row-snapshot", "--title", "fix: x", "--body", "b"]) == 0
    assert opener.count("POST", "/pulls") == 1
    assert emitted[-1]["outcome"] == "created_despite_post_error" and emitted[-1]["already_open"] is False
    assert emitted[-1]["number"] == 960 and "TimeoutError" in emitted[-1]["post_error"]


def test_open_post_timeout_not_created_reports_it(monkeypatch, emitted, clock):
    """#863 / #959 第一次：POST 超时、什么都没开。回读整个预算都找不到 → not_created、退 1。"""

    fake = FakeGitea(None)
    opener = _install_http(monkeypatch, fake, clock, {("POST", "/pulls"): "dropped"})
    argv = ["open", "--head", "fix/row-snapshot", "--title", "fix: x", "--readback-seconds", "20", "--readback-interval", "10"]
    assert mod.main(argv) == 1
    assert opener.count("POST", "/pulls") == 1
    assert emitted[-1]["outcome"] == "not_created" and emitted[-1]["readback"]["polls"] == 3
    assert "TimeoutError" in emitted[-1]["post_error"]
    assert fake.pr is None


def test_open_finds_existing_pr_on_second_page(monkeypatch, emitted):
    """open PR 超过一页（50）时第 51 张也得找得到，否则幂等和「没开成」的判定都是假的。"""

    others = [_pr(number=700 + i, head={"ref": f"feat/other-{i}", "sha": HEAD_SHA}) for i in range(50)]
    fake = FakeGitea(_pr(), others=others)
    _install(monkeypatch, fake)
    assert mod.main(["open", "--head", "fix/row-snapshot", "--title", "dup"]) == 0
    assert emitted[-1]["outcome"] == "already_open" and emitted[-1]["number"] == 815
    assert fake.methods() == ["GET /pulls", "GET /pulls"]


@pytest.mark.parametrize(("mode", "rc", "mergeable_after"), [("lost", 0, False), ("dropped", 1, True)])
def test_guard_patch_timeout_is_settled_by_readback(monkeypatch, emitted, clock, mode, rc, mergeable_after):
    """同族：guard 的 PATCH 超时也不该在回读前退出；守没守住看回读的 mergeable。"""

    fake = FakeGitea(_pr())
    opener = _install_http(monkeypatch, fake, clock, {("PATCH", "/pulls/815"): mode})
    assert mod.main(["guard", "815", "--polls", "3"]) == rc
    assert opener.count("PATCH", "/pulls/815") == 1
    assert "TimeoutError" in emitted[-1]["patch_error"]
    assert emitted[-1]["mergeable_after"] is mergeable_after


def test_transport_error_elsewhere_exits_3_with_readback_hint(monkeypatch, emitted, clock, capsys):
    """没有专门回读的路径（show / list / close）超时：退 3 并提示先回读，不甩 traceback。"""

    fake = FakeGitea(_pr())
    _install_http(monkeypatch, fake, clock, {("GET", "/pulls/815"): "dropped"})
    assert mod.main(["show", "815"]) == 3
    err = capsys.readouterr().err
    assert "TimeoutError" in err and "回读" in err
