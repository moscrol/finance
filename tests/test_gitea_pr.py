"""scripts/gitea_pr.py 的 guard / close / merge 子命令：每个测试钉住一个失败形状。

不打真 Gitea：`_api` 换成内存里的假仓，`_git` / `_merge_tree` / `time.sleep` 换成假件。
变异自检：去掉指针检查 → test_close_refuses_without_pointer 红；去掉 --expect-head 比对 →
test_merge_aborts_on_head_drift 红；去掉 POST 的 try/except → test_merge_post_error_but_readback_merged 红；
去掉合后树核对 → test_merge_happy_path 红；去掉幂等 → test_guard_is_idempotent 红。
"""

from __future__ import annotations

import importlib.util
import json
import urllib.parse
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


class FakeGitea:
    """内存假仓：记录每次调用，模拟 Gitea 把 WIP 前缀折进 mergeable、合并后改 state。"""

    def __init__(self, pr: dict, *, honor_wip: bool = True, fail_post_merge: bool = False):
        self.pr = pr
        self.calls: list[tuple[str, str, dict | None]] = []
        self.honor_wip = honor_wip
        self.fail_post_merge = fail_post_merge
        self.deleted_branches: list[str] = []
        self.git_main = BASE_SHA

    def __call__(self, method: str, path: str, body: dict | None = None) -> object:
        self.calls.append((method, path, body))
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
            self.pr.update({"state": "closed", "merged": True, "merge_commit_sha": MERGE_SHA})
            self.git_main = MERGE_SHA
            if self.fail_post_merge:
                raise SystemExit("Gitea POST /pulls/815/merge → HTTP 500: boom")
            return {}
        if method == "DELETE" and path.startswith("/branches/"):
            self.deleted_branches.append(urllib.parse.unquote(path[len("/branches/") :]))
            return {}
        raise AssertionError(f"unexpected call {method} {path}")

    def methods(self) -> list[str]:
        return [f"{m} {p.split('?')[0]}" for m, p, _ in self.calls]


@pytest.fixture
def emitted(monkeypatch: pytest.MonkeyPatch) -> list:
    out: list = []
    monkeypatch.setattr(mod, "_emit", out.append)
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    return out


def _install(monkeypatch: pytest.MonkeyPatch, fake: FakeGitea) -> None:
    monkeypatch.setattr(mod, "_api", fake)

    def fake_git(*args: str, cwd: Path = REPO_ROOT) -> str:
        if args[0] == "fetch":
            return ""
        if args == ("rev-parse", "gitea/main"):
            return fake.git_main
        if args == ("log", "-1", "--format=%P", MERGE_SHA):
            return f"{BASE_SHA} {HEAD_SHA}"
        if args == ("rev-parse", f"{MERGE_SHA}^{{tree}}"):
            return PREVIEW_TREE
        raise AssertionError(f"unexpected git {args}")

    monkeypatch.setattr(mod, "_git", fake_git)
    monkeypatch.setattr(
        mod,
        "_merge_tree",
        lambda base, head: {"base": base, "head": head, "clean": True, "tree": PREVIEW_TREE, "conflicts": [], "stderr": ""},
    )


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
    assert data["preview"]["tree"] == PREVIEW_TREE
    assert data["after"]["merged"] is True and data["verification"]["ok"] is True


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
