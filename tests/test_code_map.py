"""代码地图门面契约。PR1 钉 status / 空图 fail-closed / gitignore。"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

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
    result = _run("build", "--full")
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "invalid" in combined or "unrecognized" in combined or "unknown" in combined


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
