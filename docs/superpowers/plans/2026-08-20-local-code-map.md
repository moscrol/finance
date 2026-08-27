# 本地代码地图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给本仓编码 agent 一条 CLI 查询门面 `scripts/code_map.py`：空图 fail-closed 的 `status`、正门优先的 `query`、正确 `--base` 的 `build` 包装、跨 harness AGENTS 指针与 skill 软链、第二期本地 wiki/`ask`。不上传代码、不加用户级 hook。

**Architecture:** 门面只编排，不把能力图谱抄进 SQLite，也不把 CRG 节点抄进 markdown。`status` 读 `.code-review-graph/graph.db`（只读 URI、50ms 超时）；`query` 先 rg 仓内正门，空图/error 不调 CRG；`build` 只包装 `uvx --from code-review-graph`，禁止 `init|install`。实现在干净分支 `feat/code-map-facade`（worktree `.worktrees/feat-code-map-facade`），基线 `gitea/main`。

**Tech Stack:** Python 3.12 stdlib（argparse / sqlite3 / json / subprocess）、pytest、仓内 `.venv-workbench/bin/python`。不进 `intelligence.cli`，不改金融业务代码。

**Seams（测试只打这些）：**
1. CLI：`python3 scripts/code_map.py status [--json|--one-line]` 的 stdout / exit code
2. 可导入函数 `collect_status(root: Path)`（tmp 仓夹具，不碰本树 graph.db）
3. 提交文件：内层 gitignore、根 gitignore、`.code-review-graphignore`
4. 后续 PR：`query` JSON 契约、`build` 的 argv（mock subprocess）、AGENTS/CLAUDE 指针、SessionStart 一行、skill 软链

**解释器：** `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`

---

## File map

| Path | Responsibility |
|---|---|
| `scripts/code_map.py` | 唯一门面。PR1=`status`；PR3+=`query`；PR4+=`build` |
| `tests/test_code_map.py` | 契约测试 |
| `.code-review-graph/.gitignore` | 显式忽略 db/wal/shm/wiki/status.json，放行 steering |
| `.code-review-graphignore` | CRG 解析黑名单 |
| 仓根 `.gitignore` | 只列生成物，不忽略整目录 |
| `AGENTS.md` / `CLAUDE.md` | PR2 一行禁令指针 |
| `scripts/session_facts.sh` | PR2：解释器之后一行 `status --one-line` |
| `skills/code-map/SKILL.md` | PR5 |
| `.claude/skills/code-map` | PR5 软链 |

禁止：`code-review-graph init\|install`、家目录字面量、`research_tool_registry`、`intelligence.cli` 子命令、用户级 hook、wiki/`ask`。

---

### Task 1: 空图 status fail-closed（PR1）

**Files:**
- Create: `tests/test_code_map.py`
- Create: `scripts/code_map.py`
- Create: `.code-review-graph/.gitignore`
- Create: `.code-review-graphignore`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing tests**

`tests/test_code_map.py` 必须覆盖 spec §8.1 / §13.1：

```python
"""代码地图门面契约。PR1 只钉 status / 空图 fail-closed / gitignore。"""
from __future__ import annotations

import json
import os
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
    sys.path.insert(0, str(ROOT / "scripts"))
    import code_map as cm  # type: ignore

    return cm.collect_status(root)


def test_cli_empty_tree_exits_2_and_one_line_forbids_overview():
    result = _run("status", "--one-line")
    assert result.returncode == 2
    line = result.stdout.strip()
    assert len(line) <= 80
    assert "禁止空图架构结论" in line
    assert "scripts/code_map.py build" not in line
    assert "build" not in line.lower() or "禁止" in line


def test_cli_empty_json_status_empty():
    result = _run("status", "--json")
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "empty"
    assert payload["node_count"] == 0
    assert "scripts/code_map.py build" not in json.dumps(payload)


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
    combined = result.stdout + result.stderr
    assert "invalid" in combined.lower() or "unknown" in combined.lower() or "invalid choice" in combined.lower()


def test_inner_gitignore_is_explicit_list():
    text = (ROOT / ".code-review-graph" / ".gitignore").read_text(encoding="utf-8")
    assert text.strip() + "\n" == INNER_GITIGNORE
    assert "*" not in text.splitlines()


def test_root_gitignore_does_not_ignore_whole_crg_dir():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_code_map.py`

Expected: FAIL collecting or `ModuleNotFoundError` / missing files.

- [ ] **Step 3: Write minimal implementation**

`scripts/code_map.py` — 只实现 `status`。`collect_status(root)` 可测。默认与 `--one-line` 都打一行；`--json` 打契约 JSON。无库或 `COUNT(nodes)=0` → empty/2；有节点缺 sha 或 sha≠HEAD → stale/1；匹配 → ready/0；sqlite/git 失败（且已有节点或 sqlite 坏了）→ error/3。无库时 git 失败仍 empty。`--one-line` 不得出现 `scripts/code_map.py build`。

SQLite：`file:<abs>?mode=ro`，`timeout=0.05`。

`.code-review-graph/.gitignore` 按 spec §12 显式名单。`.code-review-graphignore` 按 spec §12 黑名单。根 `.gitignore` 追加生成物四行，**不要**忽略整目录。

完整实现见本 task 落地文件（本计划与代码同提交，实现以测试为准）。

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_code_map.py`

Expected: PASS

- [ ] **Step 5: Commit PR1**

```bash
git add -- scripts/code_map.py tests/test_code_map.py \
  .code-review-graph/.gitignore .code-review-graphignore .gitignore
git commit -- scripts/code_map.py tests/test_code_map.py \
  .code-review-graph/.gitignore .code-review-graphignore .gitignore \
  -m "$(cat <<'EOF'
feat: 代码地图 status 对空图 fail-closed

MCP 已连接不等于有地图。status 在无库/零节点时 exit 2，
one-line 打脸空图总览，且不指向尚未存在的 build 子命令。
EOF
)"
```

---

### Task 2: AGENTS 指针与 SessionStart（PR2）

**Files:**
- Modify: `AGENTS.md`（用户偏好之后插入一节，一行禁令，不抄查询契约）
- Modify: `CLAUDE.md`（能力现状之前，同一行）
- Modify: `scripts/session_facts.sh`（解释器段落后调用 `status --one-line`；忽略其 exit code；空输出则写 error 句；截到 80 字；hook 仍恒 0）
- Modify: `tests/test_code_map.py`（断言指针与 hook 行）

指针正文（两份文件同一句，可换行排版但语义一行）：

```
编码任务先 `python3 scripts/code_map.py query "<问题>"`。禁止把空图 `get_architecture_overview` 写成架构结论；禁止 `code-review-graph init|install`；禁止 DeepWiki `generate_wiki` / 对本仓 private index。MCP 已连接 ≠ 地图可用。
```

SessionStart：紧跟解释器之后。`python3 "$REPO/scripts/code_map.py" status --one-line`（stdlib，不依赖 venv）。stdout 照收（empty 的 exit 2 不当失败）。超时/空 → `代码地图: error ← 状态未知，禁止假装 ready`。

测试：AGENTS/CLAUDE 含上述禁令子串；`session_facts.sh` 含 `status --one-line` 且在解释器段之后；跑 hook 的 additionalContext 含 `代码地图:`。

Commit: `feat: AGENTS 指针与 SessionStart 注入代码地图状态`

---

### Task 3: query 正门层（PR3）

**Files:**
- Modify: `scripts/code_map.py`（加 `query`）
- Modify: `tests/test_code_map.py`（§13.2 三条探针 + 契约枚举）

`query` 契约合法 **exit 0**（含 empty/error）。顺序：doors → structure（empty=`refused_empty` 且不调 CRG；error=`refused_error` 且不调 CRG；ready/stale 才包 search，PR3 可先把 structure 停在 refused_* / missing，因 PR4 才有 search 包装——**空图必须 refused_empty**）→ narrative 恒 missing → conflicts 恒 []。

正门匹配机械规则见 spec §6.2.1。禁止家目录字面量。vault 缺失 → `"vault":"unavailable"`。`next_action` 在 PR4 前**不要**点 `build`。

探针（对 hits **集合**）：
- `daily-full`：某 hit path 含 CLAUDE.md，excerpt 含 `daily-full` 与 `market_feature_store.cli`；至少一条 retired 含 `已废弃` 或 `停用`
- `技能桥`：某 excerpt 含 `intelligence/services/skill_tools.py`，另一条（或同集合）含「刻意」或「只开一个」——禁止合并相邻行
- `fact_sector_daily`：path 含 CLAUDE.md、不含当唯一来源的 AGENTS；excerpt 含 VIEW 或 `*_generation` 或 snapshot

`completeness_claim.recall` 恒 `untested`。`completeness_claim.narrative` 恒 `unavailable`。

结构层 PR3：顶层 empty → `structure.state=refused_empty`、hits=[]，用 mock/spy 断言未调 subprocess `code-review-graph search`。损坏 db → `refused_error`。

Commit: `feat: 代码地图 query 先返回设计正门`

---

### Task 4: build 包装（PR4）

**Files:**
- Modify: `scripts/code_map.py`（`build`）
- Modify: `tests/test_code_map.py`（mock subprocess）

翻译：
- `full`（默认）→ `uvx --from code-review-graph code-review-graph build` 或 `update --base <built_at_sha>`，无 skip
- `minimal` → 加 `--skip-flows`
- `none` → 加 `--skip-postprocess`

有 `status.json.built_at_sha` → `update --base <that sha>`；否则 `build`。永不 `--postprocess`、永不 `init`。无 uvx → 非 0，stderr 含 `https://docs.astral.sh/uv/`。非 git 仓拒绝。只写当前树 `.code-review-graph/`。

落地后 empty 的 `query` `next_action` 可追加 `python3 scripts/code_map.py build --full`。

结构探针 `query daily-full` 的 structure hits 标 `@pytest.mark.skipif` 直到本机 `status=ready`。

Commit: `feat: 代码地图 build 包装 CRG 并按 built_at_sha 增量`

---

### Task 5: skill 与发现根软链（PR5a）

**Files:**
- Create: `skills/code-map/SKILL.md`
- Create: `.claude/skills/code-map` → `../../skills/code-map`
- Run: `scripts/build_registry.py scan` + `backfill-tables`（worktree 下 `REPOS_DIR` 会指到 `.worktrees/`，必须用临时兄弟仓布局：`finance-workspace-private`→本 worktree，`knowledge-base-private`/`finance-research-site`→`/Users/a77/` 下真仓，再 monkeypatch `REPOS_DIR`。禁止手改生成段。）

触发词（frontmatter description 含「触发词:」以便 registry 抽取）：`代码地图`、`code-map`、`code-review-graph`、`deepwiki`、`造轮子`、`现有实现`。不要用 `架构`/`正门`/`我们有没有`。不要复制能力清单。dispatcher 不是 Grok 默认第一步。

**PR5b（vault，非本仓）：** 本计划不改 `agent-memory`。交给用户另开 vault 仓 commit。

Commit: `feat: code-map skill 与 .claude/skills 软链`

---

## Spec coverage

| Spec | Task |
|---|---|
| §8.1 status / 空图 exit 2 / one-line ≤80 / 禁 build 字样 | T1 |
| §7 / §12 gitignore + crgignore | T1 |
| §10 / §11 AGENTS 禁令含 DeepWiki generate_wiki | T2 |
| §8.1 SessionStart 一行 | T2 |
| §6.2 / §8.2 / §13.2 query 正门探针 | T3 |
| §8.3 / §13.4 build argv | T4 |
| §7 skill 软链 | T5 |
| PR6 wiki / 用户级 hook / intelligence.cli | T6 wiki+ask（用户 2026-08-20 执行）；用户级 hook / intelligence.cli 仍不做 |

## Placeholder scan

无 TBD。PR5b 显式排除。`query` 在 PR3 的 structure 对 empty/error fail-closed；ready 图的 search 包装可与 PR4 一并完成（PR3 测试不要求真 search）。
