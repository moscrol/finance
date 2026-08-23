# Code Map Agent Runtime Paths Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the misleading L0–L4 request-loop narrative with a Code Map entry for real product doors and parallel runtime paths, then rebuild and verify the map without touching production runtime code or another worktree's in-flight Door document.

**Architecture:** Keep `scripts/code_map.py` unchanged. Change only the tracked steering intent and its public-seam tests: human entry queries must project non-empty Door hits into one narrative page, while internal implementation symbols remain Structure concerns. The corrected Mermaid flow and responsibility table live in the approved design document; generated graph/wiki/status files remain ignored.

**Tech Stack:** JSON, Python 3.12, pytest, `scripts/code_map.py`, Code Review Graph SQLite artifacts, `jq`, Git.

---

## File boundaries

Tracked implementation files:

- Modify: `.code-review-graph/wiki-steering.json`
- Modify: `scripts/code_map.py`
- Modify: `tests/test_code_map.py`

Tracked documentation already approved for this correction:

- Modify: `docs/superpowers/specs/2026-08-24-code-map-request-loop-narrative-design.md`
- Modify: `docs/superpowers/plans/2026-08-24-code-map-request-loop-narrative.md`

Generated, ignored outputs rebuilt after all tracked commits:

- `.code-review-graph/graph.db`
- `.code-review-graph/status.json`
- `.code-review-graph/wiki/`

Explicit non-goals:

- No changes under `intelligence/`
- No Code Map schema, query ranking, Door scanning, or conflict-priority changes
- No edits to `docs/agent-product-door.md`, `AGENTS.md`, or `CLAUDE.md`
- No L0–L4 request-lifecycle model
- No 5×3 Door / Structure / Narrative matrix

## Task 1: Replace the tracked steering contract test-first

**Files:**

- Modify: `tests/test_code_map.py:630-660`
- Modify: `.code-review-graph/wiki-steering.json:29-41`

- [ ] **Step 1: Write the failing tracked-config contract**

Replace the request-loop assertions inside `test_wiki_steering_is_narrative_only_and_tracked` with:

```python
    ids = [page["id"] for page in data["pages"]]
    assert "daily-review-door" in ids
    assert "run-scripts" in ids
    assert "agent-request-loop" not in ids
    runtime_path_pages = [
        page for page in data["pages"] if page["id"] == "agent-runtime-paths"
    ]
    assert runtime_path_pages == [
        {
            "id": "agent-runtime-paths",
            "title": "Agent 产品入口与运行路径",
            "queries": [
                "产品入口",
                "CLI ask",
                "Workbench UI",
                "CLI agent",
                "TurnOrchestrator",
            ],
        }
    ]
```

Keep the existing `git check-ignore` assertion after this block. This seam protects the tracked public intent rather than generator internals.

- [ ] **Step 2: Leave the steering JSON unchanged and add the integration test**

Continue directly to Task 2 Step 1. Both tests must exist before the first RED run; do not change `.code-review-graph/wiki-steering.json` yet.

## Task 2: Protect generated navigation and view separation

**Files:**

- Modify: `tests/test_code_map.py:803-850`

- [ ] **Step 1: Replace the old anchor-routing integration test**

Replace `test_request_loop_steering_generates_page_and_routes_all_anchors` with:

```python
def test_agent_runtime_paths_steering_routes_doors_without_claiming_structure(
    tmp_path, monkeypatch
):
    cm = _cm()
    root = _init_repo(tmp_path)
    head = _git(root, "rev-parse", "HEAD")
    _make_graph(root, n_nodes=5, git_head_sha=head)
    (root / ".code-review-graphignore").write_text(
        "*.duckdb\n", encoding="utf-8"
    )

    source = json.loads(
        (ROOT / ".code-review-graph" / "wiki-steering.json").read_text(
            encoding="utf-8"
        )
    )
    runtime_page = next(
        page for page in source["pages"] if page["id"] == "agent-runtime-paths"
    )
    human_queries = runtime_page["queries"]
    (root / "AGENTS.md").write_text(
        "评接口与产品入口读 docs/agent-product-door.md。\n"
        "默认产品门是 CLI ask。\n"
        "Workbench UI 走 TurnOrchestrator。\n"
        "显式工具循环走 CLI agent。\n",
        encoding="utf-8",
    )
    (root / "CLAUDE.md").write_text("正门约束见 AGENTS。\n", encoding="utf-8")

    crg = root / ".code-review-graph"
    (crg / "wiki-steering.json").write_text(
        json.dumps(
            {
                "purpose": "steer narrative pages only; not a capability inventory",
                "pages": [runtime_page],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cm, "_uvx_path", lambda: "/usr/bin/uvx")
    recorded: list[list[str]] = []
    monkeypatch.setattr(cm, "run_crg_cli", _fake_crg_ok(recorded))

    build_payload, build_code = cm.collect_build(root, full=True, postprocess="full")
    assert build_code == 0, build_payload
    page_path = crg / "wiki" / "doors" / "agent-runtime-paths.md"
    page_text = page_path.read_text(encoding="utf-8")
    assert "# Agent 产品入口与运行路径" in page_text
    assert "（正门无命中）" not in page_text

    for query in human_queries:
        assert f"## query: {query}" in page_text
        payload, code = cm.collect_query(root, query)
        assert code == 0
        assert payload["layers"]["doors"]["state"] == "ok"
        assert payload["layers"]["narrative"]["state"] == "ok"
        assert any(
            hit["path"].endswith("doors/agent-runtime-paths.md")
            for hit in payload["layers"]["narrative"]["hits"]
        )

    index = (crg / "wiki" / "index.md").read_text(encoding="utf-8")
    assert "doors/agent-runtime-paths.md" in index
    title_payload, title_code = cm.collect_query(root, "Agent 产品入口与运行路径")
    assert title_code == 0
    assert title_payload["layers"]["narrative"]["state"] == "ok"

    symbol_payload, symbol_code = cm.collect_query(root, "ResearchToolRegistry")
    assert symbol_code == 0
    assert not any(
        hit["path"].endswith("doors/agent-runtime-paths.md")
        for hit in symbol_payload["layers"]["narrative"]["hits"]
    )
```

Why: this tests the public transformation `wiki-steering.json → build → query`. It also proves that a tool implementation symbol is not mislabeled as the product-door narrative.

- [ ] **Step 2: Run both focused tests and confirm RED**

Run:

```bash
.venv-workbench/bin/python -m pytest \
  tests/test_code_map.py::test_wiki_steering_is_narrative_only_and_tracked \
  tests/test_code_map.py::test_agent_runtime_paths_steering_routes_doors_without_claiming_structure \
  -q
```

Expected: both FAIL because the old `agent-request-loop` page still exists and `agent-runtime-paths` is missing. A `StopIteration` from the integration test and an exact config mismatch from the contract test are the intended failures.

- [ ] **Step 3: Apply the minimum steering change**

Replace the old page object with:

```json
{
  "id": "agent-runtime-paths",
  "title": "Agent 产品入口与运行路径",
  "queries": [
    "产品入口",
    "CLI ask",
    "Workbench UI",
    "CLI agent",
    "TurnOrchestrator"
  ]
}
```

- [ ] **Step 4: Run both focused tests and confirm GREEN**

```bash
.venv-workbench/bin/python -m pytest \
  tests/test_code_map.py::test_wiki_steering_is_narrative_only_and_tracked \
  tests/test_code_map.py::test_agent_runtime_paths_steering_routes_doors_without_claiming_structure \
  -q
```

Expected: `2 passed`.

- [ ] **Step 5: Run the full Code Map test file**

```bash
.venv-workbench/bin/python -m pytest tests/test_code_map.py -q
```

Expected: all runnable tests pass. Existing environment-gated skips must be named in the final receipt; no new skip is acceptable.

- [ ] **Step 6: Run lint and JSON validation**

```bash
.venv-workbench/bin/python -m ruff check tests/test_code_map.py
.venv-workbench/bin/python -m json.tool .code-review-graph/wiki-steering.json >/dev/null
git diff --check
```

Expected: all commands exit `0`.

- [ ] **Step 7: Review and commit only the implementation paths**

```bash
git diff --name-only
git diff --cached --name-only
git commit -m "fix: correct Code Map runtime path narrative" -- \
  .code-review-graph/wiki-steering.json tests/test_code_map.py
```

Expected implementation commit paths:

```text
.code-review-graph/wiki-steering.json
tests/test_code_map.py
```

## Task 3: Reconcile removed steering pages discovered during full build

**Files:**

- Modify: `tests/test_code_map.py:825-875`
- Modify: `scripts/code_map.py:821-848`

- [ ] **Step 1: Seed a stale generated page and assert full-build cleanup**

In `test_agent_runtime_paths_steering_routes_doors_without_claiming_structure`, create the removed page before `collect_build`:

```python
    stale_page = crg / "wiki" / "doors" / "agent-request-loop.md"
    stale_page.parent.mkdir(parents=True)
    stale_page.write_text("# 已撤销的旧请求 Loop\n", encoding="utf-8")
```

After the build, assert both the file and its index entry are gone:

```python
    assert not stale_page.exists()
    assert "doors/agent-request-loop.md" not in index
```

- [ ] **Step 2: Run the integration test and confirm RED**

```bash
.venv-workbench/bin/python -m pytest \
  tests/test_code_map.py::test_agent_runtime_paths_steering_routes_doors_without_claiming_structure \
  -q
```

Expected: FAIL at `assert not stale_page.exists()`. This proves current full build only adds/overwrites pages and does not reconcile removals.

- [ ] **Step 3: Reconcile the generator-owned directory**

In `_write_steering_pages`, collect valid page IDs first, remove Markdown files whose names are not in that set, then render current pages:

```python
    valid_pages: list[tuple[dict[str, Any], str]] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        pid = str(page.get("id") or "").strip()
        if PAGE_ID_RE.match(pid):
            valid_pages.append((page, pid))

    expected_names = {f"{pid}.md" for _page, pid in valid_pages}
    for path in out.glob("*.md"):
        if path.name not in expected_names:
            path.unlink()
```

Iterate `for page, pid in valid_pages` in the existing render loop. This is safe because `wiki/doors/` is created and exclusively populated by `_write_steering_pages()`.

- [ ] **Step 4: Re-run the integration test and confirm GREEN**

Run the command from Step 2.

Expected: `1 passed`.

- [ ] **Step 5: Run full tests, lint, and diff checks**

```bash
.venv-workbench/bin/python -m pytest tests/test_code_map.py -q -rs
.venv-workbench/bin/python -m ruff check scripts/code_map.py tests/test_code_map.py
git diff --check
```

Expected: all runnable tests pass, only the three pre-existing empty-map environment skips remain, and lint/diff checks pass.

- [ ] **Step 6: Commit the durable stale-page fix**

```bash
git commit -m "fix: reconcile Code Map steering pages" -- \
  scripts/code_map.py tests/test_code_map.py
```

Expected: the commit contains only the generator reconciliation and its regression assertions.

## Task 4: Rebuild and verify the current Code Map

**Files:**

- Generate: `.code-review-graph/graph.db` (ignored)
- Generate: `.code-review-graph/status.json` (ignored)
- Generate: `.code-review-graph/wiki/doors/agent-runtime-paths.md` (ignored)
- Generate: `.code-review-graph/wiki/index.md` (ignored)

- [ ] **Step 1: Build from the final tracked revision**

```bash
python3 scripts/code_map.py build --full --postprocess full
```

Expected: exit `0`, positive node count, and wiki generation enabled. `--full` is required because a docs-only commit can otherwise advance `status.json` without advancing graph metadata SHA.

- [ ] **Step 2: Prove freshness**

```bash
python3 scripts/code_map.py status --json | jq -e '
  .status == "ready"
  and .head_matches_build == true
  and .commits_behind == 0
  and .worktree_dirty_code == false
  and .node_count > 0
'
```

Expected: `true` and exit `0`.

- [ ] **Step 3: Verify the human-facing Door/Narrative routes**

```bash
runtime_path_queries=(
  "产品入口"
  "CLI ask"
  "Workbench UI"
  "CLI agent"
  "TurnOrchestrator"
)

for runtime_path_query in "${runtime_path_queries[@]}"; do
  python3 scripts/code_map.py query "$runtime_path_query" --json | jq -e '
    .status == "ready"
    and .layers.doors.state == "ok"
    and .layers.narrative.state == "ok"
    and (
      [.layers.narrative.hits[].path]
      | any(endswith("doors/agent-runtime-paths.md"))
    )
  '
done
```

Expected: five successful `true` results.

- [ ] **Step 4: Verify internal symbols remain Structure concerns**

```bash
runtime_symbols=(
  ContinuousAgentEpisode
  ResearchToolRegistry
  SemanticEpisodeVerifier
  AgentSession
)

for runtime_symbol in "${runtime_symbols[@]}"; do
  python3 scripts/code_map.py query "$runtime_symbol" --json | jq -e '
    .status == "ready"
    and .layers.structure.state == "ok"
    and (
      [.layers.narrative.hits[].path]
      | all(endswith("doors/agent-runtime-paths.md") | not)
    )
  '
done
```

Expected: four successful `true` results. Other narrative pages may legitimately match; the corrected product-path page must not.

- [ ] **Step 5: Verify generated page content and title route**

```bash
test -f .code-review-graph/wiki/doors/agent-runtime-paths.md
test ! -e .code-review-graph/wiki/doors/agent-request-loop.md
! rg -n "正门无命中" .code-review-graph/wiki/doors/agent-runtime-paths.md
python3 scripts/code_map.py query "Agent 产品入口与运行路径" --json | jq -e '
  .layers.narrative.state == "ok"
  and (
    [.layers.narrative.hits[].path]
    | any(endswith("doors/agent-runtime-paths.md"))
  )
'
```

Expected: the new file exists, the removed page is absent, every query section has a Door hit, and the title query returns `true`. Do not grep for bare `L0`–`L4`: generated Door excerpts may legitimately mention Harness or evidence-layer coordinates such as `L1_L3_candidate`.

- [ ] **Step 6: Prove generated files stayed ignored and tracked files are clean**

```bash
git check-ignore \
  .code-review-graph/graph.db \
  .code-review-graph/status.json \
  .code-review-graph/wiki/doors/agent-runtime-paths.md
git diff --quiet
git diff --cached --quiet
git status --short
```

Expected: generated paths are listed; both diff checks exit `0`; status shows only the pre-existing untracked `.venv-workbench` symlink.

## Task 5: Deliver the corrected teaching handoff

**Files:** None. The final response is derived from the approved design and verified map.

- [ ] **Step 1: Present the runtime flow only as a flow**

Use the Mermaid diagram from the design document. Explicitly label tools optional, verifier Engine-A-specific, and learning cross-turn.

- [ ] **Step 2: Present responsibilities as a table**

Use the five-row responsibility mapping from the design document. Do not call the rows L0–L4 and do not align them with Door / Structure / Narrative.

- [ ] **Step 3: Explain Code Map from first principles**

State:

- Door is the normative entry contract;
- Structure is the current code graph;
- Narrative groups relevant Door results for reading;
- the tracked JSON is steering intent, not the whole map;
- the diagram is the online question-path slice, not an all-repository layer model.

- [ ] **Step 4: Report receipts and boundaries**

Report:

- design, plan, and implementation commit SHAs;
- Code Map build SHA and graph metrics;
- focused and full test results, including named existing skips;
- branch `codex/code-map-request-loop`;
- no push and no merge into `main`;
- no edits to the dirty `docs/request-loop-three-paths` worktree;
- only remaining untracked item is `.venv-workbench`.

## Final self-review gate

- [ ] Every approved requirement maps to a task above.
- [ ] The plan contains no unresolved placeholders.
- [ ] Tests exercise the tracked config and public build/query seam, not Mermaid layout.
- [ ] No production runtime changes; the only generator change is steering-page set reconciliation.
- [ ] No edit overlaps the other worktree's in-flight Door document.
- [ ] Generated artifacts are rebuilt only after all tracked commits.
