"""代码地图门面契约。PR1 钉 status / 空图 fail-closed / gitignore。"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "code_map.py"
PY = sys.executable

INNER_GITIGNORE = """graph.db
graph.db-wal
graph.db-shm
wiki/
status.json
"""

CRG_IGNORE_MUST_CONTAIN = [
    "intelligence/users/",
    "intelligence/eval/runs/",
    "intelligence/dream/_local_store/",
    "intelligence/foresight_*.jsonl",
    "market_feature_store/exports/",
    "复盘/",
    "docs/handoffs/",
    "docs/learning/forecast-review-ledger/",
    "work/",
    "state/",
    "*.duckdb",
    ".env*",
    "secrets.py",
    "credentials.json",
    "cookie*",
    "feishu_config.json",
    "mcp_config.json",
    ".venv-*/",
    ".venv-workbench/",
]


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PY, str(SCRIPT), *args],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "code-map@test")
    _git(root, "config", "user.name", "code-map")
    (root / "README").write_text("x\n", encoding="utf-8")
    _git(root, "add", "README")
    _git(root, "commit", "-m", "init")
    return root


def _make_graph(root: Path, n_nodes: int, git_head_sha: str | None) -> None:
    db_dir = root / ".code-review-graph"
    db_dir.mkdir(exist_ok=True)
    db = db_dir / "graph.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE nodes (id INTEGER PRIMARY KEY, name TEXT)")
    con.execute(
        "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    con.execute("INSERT INTO metadata VALUES ('schema_version', '9')")
    for i in range(n_nodes):
        con.execute("INSERT INTO nodes (name) VALUES (?)", (f"n{i}",))
    if git_head_sha is not None:
        con.execute(
            "INSERT INTO metadata VALUES ('git_head_sha', ?)", (git_head_sha,)
        )
    con.commit()
    con.close()


def _collect(root: Path):
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import code_map as cm

    return cm.collect_status(root)


def test_cli_empty_tree_exits_2_and_one_line_forbids_overview():
    result = _run("status", "--one-line")
    assert result.returncode == 2
    line = result.stdout.strip()
    assert len(line) <= 80
    assert "禁止空图架构结论" in line
    assert "scripts/code_map.py build" not in line
    assert "scripts/code_map.py build" not in result.stderr


def test_cli_empty_json_status_empty():
    result = _run("status", "--json")
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "empty"
    assert payload["node_count"] == 0
    dumped = json.dumps(payload)
    assert "scripts/code_map.py build" not in dumped


def test_no_db_is_empty(tmp_path):
    root = _init_repo(tmp_path)
    payload, code = _collect(root)
    assert code == 2
    assert payload["status"] == "empty"
    assert payload["node_count"] == 0


def test_zero_nodes_is_empty(tmp_path):
    root = _init_repo(tmp_path)
    _make_graph(root, n_nodes=0, git_head_sha=None)
    payload, code = _collect(root)
    assert code == 2
    assert payload["status"] == "empty"


def test_missing_sha_is_stale(tmp_path):
    root = _init_repo(tmp_path)
    _make_graph(root, n_nodes=3, git_head_sha=None)
    payload, code = _collect(root)
    assert code == 1
    assert payload["status"] == "stale"
    assert "无 git_head_sha" in payload["one_line"]
    assert len(payload["one_line"]) <= 80
    assert "scripts/code_map.py build" not in payload["one_line"]


def test_sha_mismatch_light_stale(tmp_path):
    root = _init_repo(tmp_path)
    old = _git(root, "rev-parse", "HEAD")
    _make_graph(root, n_nodes=2, git_head_sha=old)
    (root / "README").write_text("y\n", encoding="utf-8")
    _git(root, "add", "README")
    _git(root, "commit", "-m", "docs only")
    payload, code = _collect(root)
    assert code == 1
    assert payload["status"] == "stale"
    assert payload["commits_behind"] == 1
    assert payload["stale_weight"] == "light"
    assert "仍可搜" in payload["one_line"]
    assert "勿当当前架构" not in payload["one_line"]
    assert len(payload["one_line"]) <= 80


def test_sha_mismatch_heavy_by_path(tmp_path):
    root = _init_repo(tmp_path)
    old = _git(root, "rev-parse", "HEAD")
    _make_graph(root, n_nodes=2, git_head_sha=old)
    intel = root / "intelligence"
    intel.mkdir()
    (intel / "x.py").write_text("x=1\n", encoding="utf-8")
    _git(root, "add", "intelligence/x.py")
    _git(root, "commit", "-m", "touch intelligence")
    payload, code = _collect(root)
    assert code == 1
    assert payload["stale_weight"] == "heavy"
    assert "勿当当前架构" in payload["one_line"]
    assert len(payload["one_line"]) <= 80


def test_ready_when_sha_matches(tmp_path):
    root = _init_repo(tmp_path)
    head = _git(root, "rev-parse", "HEAD")
    _make_graph(root, n_nodes=12, git_head_sha=head)
    payload, code = _collect(root)
    assert code == 0
    assert payload["status"] == "ready"
    assert payload["node_count"] == 12
    assert payload["one_line"].startswith("代码地图: ready n=12 @")
    assert len(payload["one_line"]) <= 80


def test_corrupt_db_is_error(tmp_path):
    root = _init_repo(tmp_path)
    db_dir = root / ".code-review-graph"
    db_dir.mkdir()
    (db_dir / "graph.db").write_bytes(b"not a sqlite database")
    payload, code = _collect(root)
    assert code == 3
    assert payload["status"] == "error"
    assert "禁止假装 ready" in payload["one_line"]


def test_nodes_without_git_is_error(tmp_path):
    root = tmp_path / "not-git"
    root.mkdir()
    _make_graph(root, n_nodes=1, git_head_sha="abc")
    payload, code = _collect(root)
    assert code == 3
    assert payload["status"] == "error"


def test_no_db_without_git_is_still_empty(tmp_path):
    root = tmp_path / "not-git"
    root.mkdir()
    payload, code = _collect(root)
    assert code == 2
    assert payload["status"] == "empty"


def test_worktree_dirty_code_true_for_scripts(tmp_path):
    root = _init_repo(tmp_path)
    head = _git(root, "rev-parse", "HEAD")
    _make_graph(root, n_nodes=1, git_head_sha=head)
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "x.py").write_text("print(1)\n", encoding="utf-8")
    payload, code = _collect(root)
    assert code == 0
    assert payload["worktree_dirty_code"] is True


def test_exports_do_not_count_as_code_dirty(tmp_path):
    root = _init_repo(tmp_path)
    head = _git(root, "rev-parse", "HEAD")
    _make_graph(root, n_nodes=1, git_head_sha=head)
    exp = root / "market_feature_store" / "exports"
    exp.mkdir(parents=True)
    (exp / "x.md").write_text("x\n", encoding="utf-8")
    payload, code = _collect(root)
    assert payload["worktree_dirty_code"] is False


def test_status_does_not_implement_build():
    result = _run("build", "--help")
    assert result.returncode == 0
    assert "--full" in result.stdout
    assert "--postprocess" in result.stdout


def test_inner_gitignore_is_explicit_list():
    text = (ROOT / ".code-review-graph" / ".gitignore").read_text(encoding="utf-8")
    assert text.strip() + "\n" == INNER_GITIGNORE
    assert "*" not in {ln.strip() for ln in text.splitlines() if ln.strip()}


def test_root_gitignore_does_not_ignore_whole_crg_dir():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    lines = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert ".code-review-graph/" not in lines
    assert ".code-review-graph" not in lines
    for needle in (
        ".code-review-graph/graph.db-wal",
        ".code-review-graph/graph.db-shm",
        ".code-review-graph/wiki/",
        ".code-review-graph/status.json",
    ):
        assert needle in text


def test_crg_ignore_blacklist_present():
    text = (ROOT / ".code-review-graphignore").read_text(encoding="utf-8")
    for item in CRG_IGNORE_MUST_CONTAIN:
        assert item in text


POINTER_NEEDLES = (
    "python3 scripts/code_map.py query",
    "get_architecture_overview",
    "code-review-graph init|install",
    "generate_wiki",
    "private index",
    "MCP 已连接",
)


def test_agents_and_claude_carry_code_map_pointer():
    for path in (ROOT / "AGENTS.md", ROOT / "CLAUDE.md"):
        text = path.read_text(encoding="utf-8")
        for needle in POINTER_NEEDLES:
            assert needle in text, f"{path.name} missing {needle!r}"


def test_session_facts_calls_status_one_line_after_interpreter():
    text = (ROOT / "scripts" / "session_facts.sh").read_text(encoding="utf-8")
    interp_at = text.index("解释器:")
    map_at = text.index("status --one-line")
    assert map_at > interp_at


def test_session_facts_hook_emits_code_map_line_and_exits_0():
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "session_facts.sh")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    lines = [ln for ln in ctx.splitlines() if ln.startswith("代码地图:")]
    assert lines, ctx
    assert len(lines[0]) <= 80
    assert "禁止空图架构结论" in lines[0]


def _query_json(*args: str) -> tuple[dict, subprocess.CompletedProcess[str]]:
    result = _run("query", *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout), result


def test_query_empty_graph_exits_0_and_refuses_structure():
    payload, result = _query_json("daily-full", "--json")
    assert payload["status"] == "empty"
    assert payload["layers"]["structure"]["state"] == "refused_empty"
    assert payload["layers"]["structure"]["hits"] == []
    assert payload["layers"]["narrative"]["state"] == "missing"
    assert payload["conflicts"] == []
    assert payload["completeness_claim"]["recall"] == "untested"
    assert payload["completeness_claim"]["structure"] == "unavailable"
    assert payload["completeness_claim"]["narrative"] == "unavailable"
    assert "python3 scripts/code_map.py build --full" in payload["next_action"]
    assert "禁止把空图写成架构结论" in payload["next_action"]


def test_query_daily_full_doors_probe():
    payload, _ = _query_json("daily-full")
    hits = payload["layers"]["doors"]["hits"]
    assert any(
        "CLAUDE.md" in h["path"]
        and "daily-full" in h["excerpt"]
        and "market_feature_store.cli" in h["excerpt"]
        for h in hits
    )
    cmd_hits = [
        h
        for h in hits
        if "market_feature_store.cli" in h["excerpt"] and "daily-full" in h["excerpt"]
    ]
    assert cmd_hits
    assert cmd_hits[0]["retired"] == []
    retired_lines = [r for h in hits for r in h["retired"]]
    assert any("已废弃" in r or "停用" in r for r in retired_lines)
    assert payload["completeness_claim"]["recall"] == "untested"
    assert payload["completeness_claim"]["doors"] in ("ok", "partial")


def test_query_skill_bridge_hits_are_a_set_not_merged_lines():
    payload, _ = _query_json("技能桥")
    hits = payload["layers"]["doors"]["hits"]
    excerpts = [h["excerpt"] for h in hits]
    assert any("intelligence/services/skill_tools.py" in e for e in excerpts)
    assert any("刻意" in e or "只开一个" in e for e in excerpts)
    assert any(
        "intelligence/services/skill_tools.py" in e and "刻意" not in e
        for e in excerpts
    ), "禁止把标题行与 skill_tools.py 合并成一条 excerpt"


def test_query_fact_sector_daily_is_view():
    payload, _ = _query_json("fact_sector_daily")
    hits = payload["layers"]["doors"]["hits"]
    assert any("CLAUDE.md" in h["path"] for h in hits)
    assert any(
        "VIEW" in h["excerpt"] or "_generation" in h["excerpt"] or "snapshot" in h["excerpt"]
        for h in hits
    )


def test_query_error_does_not_call_search(tmp_path, monkeypatch):
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import code_map as cm

    root = _init_repo(tmp_path)
    db_dir = root / ".code-review-graph"
    db_dir.mkdir()
    (db_dir / "graph.db").write_bytes(b"not a sqlite database")
    called = []

    def boom(question: str):
        called.append(question)
        raise AssertionError("empty/error must not call CRG search")

    monkeypatch.setattr(cm, "search_graph", boom)
    payload, code = cm.collect_query(root, "daily-full")
    assert code == 0
    assert payload["status"] == "error"
    assert payload["layers"]["structure"]["state"] == "refused_error"
    assert called == []


def test_query_empty_tmp_repo_does_not_call_search(tmp_path, monkeypatch):
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import code_map as cm

    root = _init_repo(tmp_path)
    (root / "AGENTS.md").write_text("daily-full gate\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("daily-full gate\n", encoding="utf-8")
    called = []
    monkeypatch.setattr(cm, "search_graph", lambda q: called.append(q) or [])
    payload, code = cm.collect_query(root, "daily-full")
    assert code == 0
    assert payload["layers"]["structure"]["state"] == "refused_empty"
    assert called == []


def test_code_map_has_no_home_path_literal():
    src = (ROOT / "scripts" / "code_map.py").read_text(encoding="utf-8")
    assert "/Users/" not in src
    assert "/home/" not in src


def _cm():
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import code_map as cm

    return cm


def _fake_crg_ok(recorded):
    def fake(args, cwd):
        recorded.append(list(args))
        return subprocess.CompletedProcess(["uvx"], 0, "ok", "")

    return fake


def test_build_update_uses_receipt_sha_and_skip_flows(tmp_path, monkeypatch):
    cm = _cm()
    root = _init_repo(tmp_path)
    (root / ".code-review-graphignore").write_text("*.duckdb\n", encoding="utf-8")
    crg = root / ".code-review-graph"
    crg.mkdir()
    (crg / "status.json").write_text(
        json.dumps(
            {
                "built_at_sha": "abc1234deadbeef",
                "node_count": 10,
                "postprocess": "full",
                "wiki_generated": False,
            }
        ),
        encoding="utf-8",
    )
    recorded: list[list[str]] = []
    monkeypatch.setattr(cm, "_uvx_path", lambda: "/usr/bin/uvx")
    monkeypatch.setattr(cm, "run_crg_cli", _fake_crg_ok(recorded))
    payload, code = cm.collect_build(root, full=False, postprocess="minimal")
    assert code == 0, payload
    assert recorded, payload
    cmd = recorded[0]
    assert cmd[0] == "update"
    assert "--base" in cmd
    assert "abc1234deadbeef" in cmd
    assert "--skip-flows" in cmd
    assert "--postprocess" not in cmd
    assert "init" not in cmd
    assert "install" not in cmd


def test_build_full_when_no_receipt(tmp_path, monkeypatch):
    cm = _cm()
    root = _init_repo(tmp_path)
    (root / ".code-review-graphignore").write_text("*.duckdb\n", encoding="utf-8")
    recorded: list[list[str]] = []
    monkeypatch.setattr(cm, "_uvx_path", lambda: "/usr/bin/uvx")
    monkeypatch.setattr(cm, "run_crg_cli", _fake_crg_ok(recorded))
    payload, code = cm.collect_build(root, full=False, postprocess="full")
    assert code == 0, payload
    cmd = recorded[0]
    assert cmd[0] == "build"
    assert "--base" not in cmd
    assert "--skip-flows" not in cmd
    assert "--postprocess" not in cmd
    assert "init" not in cmd


def test_build_none_uses_skip_postprocess(tmp_path, monkeypatch):
    cm = _cm()
    root = _init_repo(tmp_path)
    (root / ".code-review-graphignore").write_text("*.duckdb\n", encoding="utf-8")
    recorded: list[list[str]] = []
    monkeypatch.setattr(cm, "_uvx_path", lambda: "/usr/bin/uvx")
    monkeypatch.setattr(cm, "run_crg_cli", _fake_crg_ok(recorded))
    _, code = cm.collect_build(root, full=True, postprocess="none")
    assert code == 0
    assert "--skip-postprocess" in recorded[0]
    assert "--postprocess" not in recorded[0]


def test_build_without_uvx_fail_closed(tmp_path, monkeypatch, capsys):
    cm = _cm()
    root = _init_repo(tmp_path)
    (root / ".code-review-graphignore").write_text("*.duckdb\n", encoding="utf-8")
    monkeypatch.setattr(cm, "_uvx_path", lambda: None)
    payload, code = cm.collect_build(root, full=True, postprocess="full")
    assert code != 0
    err = capsys.readouterr().err
    assert "https://docs.astral.sh/uv/" in err
    assert "MCP" in err


def test_build_without_git_refuses(tmp_path, monkeypatch):
    cm = _cm()
    root = tmp_path / "not-git"
    root.mkdir()
    (root / ".code-review-graphignore").write_text("*.duckdb\n", encoding="utf-8")
    monkeypatch.setattr(cm, "_uvx_path", lambda: "/usr/bin/uvx")
    recorded: list[list[str]] = []
    monkeypatch.setattr(cm, "run_crg_cli", _fake_crg_ok(recorded))
    payload, code = cm.collect_build(root, full=True, postprocess="full")
    assert code != 0
    assert recorded == []


def _status_is_ready() -> bool:
    result = _run("status", "--json")
    if result.returncode != 0:
        return False
    try:
        return json.loads(result.stdout).get("status") == "ready"
    except json.JSONDecodeError:
        return False


@pytest.mark.skipif(not _status_is_ready(), reason="CI 不上传 graph.db；本机 status=ready 才跑结构探针")
def test_structure_probe_daily_full():
    payload, _ = _query_json("daily-full")
    blob = json.dumps(payload["layers"]["structure"]["hits"])
    assert "market_feature_store" in blob
    assert "cli" in blob.lower()

