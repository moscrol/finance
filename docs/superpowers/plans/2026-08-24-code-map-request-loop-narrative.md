# Code Map Request-Loop Narrative Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one versioned Code Map steering page that lets a reader follow the repository's L0–L4 agent request loop through five stable code anchors, while keeping the generated graph, status, and wiki as reproducible ignored artifacts.

**Architecture:** Extend only `.code-review-graph/wiki-steering.json`; the existing `scripts/code_map.py` build pipeline turns that tracked narrative intent into `doors/agent-request-loop.md`. Add one exact configuration test and one build/query integration test. Do not change production runtime code or the Code Map generator.

**Tech Stack:** JSON, Python 3.12, pytest, `scripts/code_map.py`, Code Review Graph SQLite artifacts, `jq`, Git.

---

## 文件边界

Tracked implementation files:

- Modify: `.code-review-graph/wiki-steering.json`
- Modify: `tests/test_code_map.py`

Generated, ignored outputs rebuilt after the implementation commit:

- `.code-review-graph/graph.db`
- `.code-review-graph/status.json`
- `.code-review-graph/wiki/`

Explicit non-goals:

- No changes under `intelligence/`
- No changes to `scripts/code_map.py`
- No second source of truth for the L0–L4 model
- No hand-written generated wiki page

## Task 1: Add the steering contract test-first

**Files:**

- Modify: `tests/test_code_map.py:630-642`
- Add near: `tests/test_code_map.py:748-784`
- Modify: `.code-review-graph/wiki-steering.json:24-28`

- [ ] **Step 1: Tighten the tracked steering-file contract**

Replace the existing steering test with this exact test:

```python
def test_wiki_steering_is_narrative_only_and_tracked():
    path = ROOT / ".code-review-graph" / "wiki-steering.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["purpose"] == "steer narrative pages only; not a capability inventory"
    ids = [page["id"] for page in data["pages"]]
    assert "daily-review-door" in ids
    assert "run-scripts" in ids
    request_loop_pages = [
        page for page in data["pages"] if page["id"] == "agent-request-loop"
    ]
    assert request_loop_pages == [
        {
            "id": "agent-request-loop",
            "title": "Agent 请求 Loop",
            "queries": [
                "validate_runtime_selection",
                "conversation_orchestrator",
                "research_tool_registry",
                "episode_semantic_verifier",
                "experience_cards",
            ],
        }
    ]
    proc = subprocess.run(
        ["git", "check-ignore", "-q", ".code-review-graph/wiki-steering.json"],
        cwd=str(ROOT),
        check=False,
    )
    assert proc.returncode == 1
```

Why: this makes the five anchors, their order, the page identity, and the fact that the steering file is tracked into one executable contract.

- [ ] **Step 2: Add an end-to-end build/query regression test**

Add this test next to the existing Code Map post-processing tests:

```python
def test_request_loop_steering_generates_page_and_routes_all_anchors(
    tmp_path, monkeypatch
):
    cm = _cm()
    root = _init_repo(tmp_path)
    head = _git(root, "rev-parse", "HEAD")
    _make_graph(root, n_nodes=5, git_head_sha=head)
    (root / ".code-review-graphignore").write_text("*.duckdb\n", encoding="utf-8")

    source = json.loads(
        (ROOT / ".code-review-graph" / "wiki-steering.json").read_text(
            encoding="utf-8"
        )
    )
    request_loop_page = next(
        page for page in source["pages"] if page["id"] == "agent-request-loop"
    )
    anchors = request_loop_page["queries"]
    (root / "AGENTS.md").write_text("\n".join(anchors) + "\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("Agent 请求 Loop\n", encoding="utf-8")

    crg = root / ".code-review-graph"
    (crg / "wiki-steering.json").write_text(
        json.dumps(
            {
                "purpose": "steer narrative pages only; not a capability inventory",
                "pages": [request_loop_page],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cm, "_uvx_path", lambda: "/usr/bin/uvx")
    recorded: list[list[str]] = []
    monkeypatch.setattr(cm, "run_crg_cli", _fake_crg_ok(recorded))

    build_payload, build_code = cm.collect_build(root, full=True, postprocess="full")
    assert build_code == 0, build_payload
    page_path = crg / "wiki" / "doors" / "agent-request-loop.md"
    page_text = page_path.read_text(encoding="utf-8")
    assert "# Agent 请求 Loop" in page_text
    for query in anchors:
        assert f"## query: {query}" in page_text
        payload, code = cm.collect_query(root, query)
        assert code == 0
        assert payload["layers"]["narrative"]["state"] == "ok"
        assert any(
            hit["path"].endswith("doors/agent-request-loop.md")
            for hit in payload["layers"]["narrative"]["hits"]
        )

    index = (crg / "wiki" / "index.md").read_text(encoding="utf-8")
    assert "doors/agent-request-loop.md" in index
    title_payload, title_code = cm.collect_query(root, "Agent 请求 Loop")
    assert title_code == 0
    assert title_payload["layers"]["narrative"]["state"] == "ok"
```

Why: the first test protects declarative intent; this one protects the actual transformation from JSON steering entry to generated page and query routing.

- [ ] **Step 3: Run the two focused tests and confirm RED**

Run:

```bash
.venv-workbench/bin/python -m pytest \
  tests/test_code_map.py::test_wiki_steering_is_narrative_only_and_tracked \
  tests/test_code_map.py::test_request_loop_steering_generates_page_and_routes_all_anchors \
  -q
```

Expected: both tests fail because `agent-request-loop` is not yet present in the steering file. If they fail for imports, syntax, or fixture setup instead, fix the test harness before changing production configuration.

- [ ] **Step 4: Add the minimum steering entry**

Append this object to the existing `pages` array in `.code-review-graph/wiki-steering.json`:

```json
{
  "id": "agent-request-loop",
  "title": "Agent 请求 Loop",
  "queries": [
    "validate_runtime_selection",
    "conversation_orchestrator",
    "research_tool_registry",
    "episode_semantic_verifier",
    "experience_cards"
  ]
}
```

These anchors represent:

| Layer | Anchor | Responsibility |
|---|---|---|
| L0 | `validate_runtime_selection` | Validate the request's runtime/mode selection before orchestration |
| L1 | `conversation_orchestrator` | Own the request lifecycle and decide which path to take |
| L2 | `research_tool_registry` | Expose optional research tools when the chosen path needs external work |
| L3 | `episode_semantic_verifier` | Judge whether the produced answer satisfies semantic/evidence constraints |
| L4 | `experience_cards` | Turn accepted outcomes and corrections into reusable learning material |

- [ ] **Step 5: Re-run the focused tests and confirm GREEN**

Run the same focused command from Step 3.

Expected: `2 passed`.

- [ ] **Step 6: Run the full Code Map test file**

```bash
.venv-workbench/bin/python -m pytest tests/test_code_map.py -q
```

Expected: all tests pass. Do not accept skips or unrelated failures as proof of completion.

- [ ] **Step 7: Review the implementation diff**

```bash
git diff --check
git diff --name-only
```

Expected tracked implementation diff:

```text
.code-review-graph/wiki-steering.json
tests/test_code_map.py
```

Review for accidental generator/runtime edits and remove any such changes.

- [ ] **Step 8: Commit only the two implementation files**

```bash
git add .code-review-graph/wiki-steering.json tests/test_code_map.py
git commit -m "feat: add Code Map request-loop narrative" -- \
  .code-review-graph/wiki-steering.json tests/test_code_map.py
```

Expected: one implementation commit containing exactly those two paths.

## Task 2: Rebuild and verify the current Code Map

**Files:**

- Generate: `.code-review-graph/graph.db` (ignored)
- Generate: `.code-review-graph/status.json` (ignored)
- Generate: `.code-review-graph/wiki/doors/agent-request-loop.md` (ignored)
- Generate: `.code-review-graph/wiki/index.md` (ignored)

- [ ] **Step 1: Build from the committed implementation revision**

```bash
python3 scripts/code_map.py build --postprocess full
```

Expected: exit code `0`, post-processing reports success, the built SHA equals `git rev-parse HEAD`, node count is positive, and wiki generation is enabled.

- [ ] **Step 2: Prove freshness and repository cleanliness**

```bash
python3 scripts/code_map.py status --json | jq -e '
  .status == "ready"
  and .head_matches_build == true
  and .commits_behind == 0
  and .worktree_dirty_code == false
  and .node_count > 0
'
```

Expected: `jq` exits `0` and prints `true`.

- [ ] **Step 3: Verify all five anchors have both structural and narrative routes**

```bash
request_loop_queries=(
  validate_runtime_selection
  conversation_orchestrator
  research_tool_registry
  episode_semantic_verifier
  experience_cards
)

for request_loop_query in "${request_loop_queries[@]}"; do
  python3 scripts/code_map.py query "$request_loop_query" --json | jq -e '
    .status == "ready"
    and .layers.structure.state == "ok"
    and .layers.narrative.state == "ok"
    and (
      [.layers.narrative.hits[].path]
      | any(endswith("doors/agent-request-loop.md"))
    )
  '
done
```

Expected: five successful `true` results. A missing structure result means the chosen anchor is stale or misspelled; a missing narrative result means page generation/routing regressed.

- [ ] **Step 4: Verify the human-facing title route**

```bash
python3 scripts/code_map.py query "Agent 请求 Loop" --json | jq -e '
  .status == "ready"
  and .layers.narrative.state == "ok"
  and (
    [.layers.narrative.hits[].path]
    | any(endswith("doors/agent-request-loop.md"))
  )
'
```

Expected: `true`.

- [ ] **Step 5: Prove generated files stayed ignored**

```bash
git check-ignore \
  .code-review-graph/graph.db \
  .code-review-graph/status.json \
  .code-review-graph/wiki/doors/agent-request-loop.md
git diff --quiet
git diff --cached --quiet
git status --short
```

Expected: the first command lists all three generated paths; both diff commands exit `0`; `git status --short` shows only the pre-existing untracked `.venv-workbench` symlink.

## Task 3: Produce the teaching handoff and two-dimensional overview

**Files:** None. This is the final response, derived from verified repository evidence.

- [ ] **Step 1: Capture the verified two-axis matrix**

Use the five query results to record:

| Request axis | Primary implementation path | Code Map narrative path |
|---|---|---|
| L0 entry/selection | `intelligence/perspective_lab.py` | `doors/agent-request-loop.md` |
| L1 orchestration | `intelligence/runtime/conversation_orchestrator.py` | `doors/agent-request-loop.md` |
| L2 optional tool work | `intelligence/services/research_tool_registry.py` | `doors/agent-request-loop.md` |
| L3 verification/gate | `intelligence/services/episode_semantic_verifier.py` | `doors/agent-request-loop.md` |
| L4 learning/write-back | `intelligence/services/experience_cards.py` | `doors/agent-request-loop.md` |

If a query resolves a different primary path, use the verified query output rather than forcing this planned path.

- [ ] **Step 2: Draw the final two-dimensional diagram**

The diagram must show both dimensions at once:

1. Horizontal request flow: `L0 → L1 → optional L2 → L3 → L4`, plus the direct `L1 → L3` bypass when tools are unnecessary.
2. Vertical Code Map views for every layer: Door (where to enter), Structure (what code connects), Narrative (why the step exists).

Use solid arrows for runtime flow, dotted vertical lines for map views, and label the diagram with the verified build SHA and node count. Do not imply that Code Map executes the request; it describes and navigates the code that does.

- [ ] **Step 3: Teach the design from first principles**

Explain in plain Chinese:

- A request loop exists because a useful agent must repeatedly reduce uncertainty: understand → act if needed → verify → learn.
- L2 is optional because tool use is a cost-bearing side effect, not the goal of every request.
- L3 is separate from L1 because the actor should not be the sole judge of its own output.
- L4 is after verification because storing an unverified result amplifies mistakes.
- Code Map is not “just JSON”: the tracked JSON is steering intent; the generated SQLite/wiki/status artifacts are the navigable map; the underlying Python modules are the territory.
- This approach was chosen over hand-writing a large diagram or modifying the generator because it adds the smallest durable source-of-truth change and lets existing generation/tests prevent drift.

- [ ] **Step 4: State completion boundaries**

Report:

- implementation and test commit SHA;
- Code Map build SHA, node count, edge count, flow count, and community count;
- focused and full test results;
- branch name `codex/code-map-request-loop`;
- no merge into `main` and no push unless separately requested;
- the only remaining untracked item is the pre-existing `.venv-workbench` symlink.

## Final self-review gate

- [ ] Every approved design requirement maps to a task above.
- [ ] No unresolved placeholder language remains.
- [ ] Test code uses helpers and payload shapes that already exist in `tests/test_code_map.py`.
- [ ] The only tracked implementation paths are the steering JSON and its tests.
- [ ] Generated artifacts are rebuilt only after the implementation commit, so freshness can equal `HEAD`.
- [ ] No command stages or commits unrelated user files.
