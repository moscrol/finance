# Native Daily Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Daily Agent and Daily Review open as consistent, public-friendly native Workbench reports while retaining legacy HTML only as a safe secondary reference.

**Architecture:** Add a backend projection adapter that normalizes canonical Daily Agent JSON and Daily Review Markdown into one `DailyReportProjection`. Historical HTML is parsed only by a bounded compatibility adapter. React renders the projection with one shared report component; Artifact Registry remains the provenance and content boundary.

**Tech Stack:** Python 3.12, FastAPI, dataclasses, standard-library HTML parsing, React 19, TypeScript, Vitest, Playwright, GitHub Actions.

---

### Task 1: Daily report projection adapters

**Files:**
- Create: `intelligence/api/daily_reports.py`
- Create: `intelligence/tests/test_daily_report_projection.py`

- [ ] **Step 1: Write failing tests for Daily Agent JSON projection**

Create fixtures that assert reader-facing summaries, queue counts, translated lifecycle/evidence labels, glossary entries, and canonical provenance without exposing internal JSON keys.

```python
projection = project_daily_agent(payload, source_path="exports/2026-07-01-daily-agent.json")
assert projection["report_type"] == "daily_agent"
assert projection["metrics"][0]["label"] == "旧逻辑重新活跃"
assert "old_logic_wakeup" not in json.dumps(projection, ensure_ascii=False)
```

- [ ] **Step 2: Write failing tests for Markdown and historical HTML projection**

Assert extraction of the core dashboard, market assessment, source mode, and compatibility warning. Unknown headings and scripts must not enter the projection.

- [ ] **Step 3: Run projection tests and confirm failure**

Run: `python -m pytest -q intelligence/tests/test_daily_report_projection.py`

Expected: collection fails because `intelligence.api.daily_reports` does not exist.

- [ ] **Step 4: Implement the projection contract and bounded adapters**

Implement focused functions:

```python
def project_daily_agent(payload: dict[str, object], *, source_path: str) -> dict[str, object]: ...
def project_daily_review_markdown(source: str, *, source_path: str, date: str | None) -> dict[str, object]: ...
def project_daily_review_html(source: str, *, source_path: str, date: str | None) -> dict[str, object]: ...
```

Use deterministic field mappings and a standard-library `HTMLParser` subclass. Limit summaries to three and candidate/action lists to bounded counts.

- [ ] **Step 5: Run projection tests**

Expected: all projection tests pass.

### Task 2: Registry projection and companion asset API

**Files:**
- Modify: `intelligence/api/artifacts.py`
- Modify: `intelligence/api/app.py`
- Modify: `intelligence/tests/test_artifact_registry.py`
- Modify: `intelligence/tests/test_workbench_api.py`

- [ ] **Step 1: Add failing API tests**

Cover:

```python
projection = client.get(f"/api/artifacts/{artifact_id}/projection")
assert projection.json()["report_type"] == "daily_agent"

asset = client.get(f"/api/artifacts/{review_id}/chart.png")
assert asset.status_code == 200
assert client.get(f"/api/artifacts/{review_id}/..%2Fsecret.txt").status_code in (403, 404)
```

- [ ] **Step 2: Add safe canonical and sibling resolution**

Add registry methods that resolve only the descriptor's registered canonical path and sibling directory. Reject paths outside those roots after symlink resolution.

- [ ] **Step 3: Add projection and companion routes**

`GET /api/artifacts/{artifact_id}/projection` selects the daily adapter. `GET /api/artifacts/{artifact_id}/{asset_path:path}` serves only a safe sibling file for registered legacy content.

- [ ] **Step 4: Run backend API tests**

Run: `python -m pytest -q intelligence/tests/test_daily_report_projection.py intelligence/tests/test_artifact_registry.py intelligence/tests/test_workbench_api.py`

Expected: all tests pass.

### Task 3: Native Daily report UI

**Files:**
- Create: `intelligence/webapp/src/components/DailyReportView.tsx`
- Create: `intelligence/webapp/src/components/DailyReportView.test.tsx`
- Modify: `intelligence/webapp/src/types.ts`
- Modify: `intelligence/webapp/src/api.ts`
- Modify: `intelligence/webapp/src/App.tsx`
- Modify: `intelligence/webapp/src/components/ArtifactViewer.tsx`
- Modify: `intelligence/webapp/src/styles.css`

- [ ] **Step 1: Write failing component tests**

Assert the five report layers, reader-facing Chinese labels, glossary disclosure, compatibility warning, and secondary Original Report disclosure.

- [ ] **Step 2: Add TypeScript projection types and API client**

Define `DailyReportProjection`, `ReportMetric`, `ReportSection`, and `ReportItem`. Add `getArtifactProjection()`.

- [ ] **Step 3: Implement `DailyReportView`**

Render an unframed report layout with a compact summary band, stable metric grid, ordered action rows, evidence labels, and glossary disclosure. Do not render raw unknown JSON.

- [ ] **Step 4: Make native projection the default daily viewer**

For `daily_agent` and `daily_review`, `App` fetches the projection and `ArtifactViewer` renders it. The sandboxed iframe moves into an `Original report` disclosure.

- [ ] **Step 5: Add responsive Workbench styles**

Use existing tokens and breakpoints. Verify fixed grid constraints, wrapping, and no horizontal page overflow.

- [ ] **Step 6: Run component checks**

Run: `pnpm lint`, `pnpm typecheck`, and `pnpm test` from `intelligence/webapp`.

Expected: all pass.

### Task 4: Navigation and accessibility reliability

**Files:**
- Modify: `intelligence/webapp/src/App.tsx`
- Modify: `intelligence/webapp/src/components/Sidebar.tsx`
- Modify: `intelligence/webapp/src/components/components.test.tsx`
- Modify: `intelligence/webapp/e2e/workbench.spec.ts`

- [ ] **Step 1: Add tests for stale response isolation and trace deduplication**

Use deferred requests to prove a late Run or artifact response cannot replace the current selection. Replay the same `step_id` and assert one trace row.

- [ ] **Step 2: Implement request generation guards**

Track run and artifact request generations with refs, clear previous state before loading, and apply a response only when its generation is current.

- [ ] **Step 3: Reset scroll on surface identity changes**

Call `window.scrollTo({ top: 0, behavior: "auto" })` when the selected surface changes.

- [ ] **Step 4: Preserve mobile accessible names**

Add explicit `aria-label` values to New Research, Home, and Artifact Library buttons independent of visible spans and badges.

- [ ] **Step 5: Deduplicate SSE steps**

Upsert by `step_id` in App state so initial trace fetch, replay, and reconnect cannot duplicate inspector rows.

### Task 5: Reproducible E2E and CI

**Files:**
- Modify: `intelligence/webapp/playwright.config.ts`
- Modify: `intelligence/webapp/e2e/workbench.spec.ts`
- Create: `.github/workflows/workbench-check.yml`

- [ ] **Step 1: Discover the Python executable in Playwright config**

Prefer `WORKBENCH_PYTHON`, then repository `.venv-workbench`, then `.venv`, then `python3`. Build one quoted uvicorn command.

- [ ] **Step 2: Expand E2E mocks and assertions**

Mock projection responses and test both native report types, original-report disclosure, scroll reset, and no horizontal overflow at 1440, 1024, and 390 widths.

- [ ] **Step 3: Add GitHub Actions release gate**

Install Python 3.12, API requirements, pytest, PyYAML, Node 22, pnpm 10.12.1, and Playwright Chromium. Run the intelligence suite and all frontend checks.

- [ ] **Step 4: Run the complete local gate**

Run:

```bash
env -u FORESIGHT_USER -u FORESIGHT_USERS_DIR -u SUBCONSCIOUS_VAULT python -m pytest -q intelligence/tests
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
```

Expected: 817+ Python tests and every frontend check pass without a manual `.venv` symlink.

### Task 6: Real artifact and visual verification

**Files:**
- Modify generated build assets under `intelligence/api/static/` through `pnpm build`

- [ ] **Step 1: Start FastAPI from the isolated PR worktree**

Use the discovered Python executable on a free localhost port.

- [ ] **Step 2: Inspect real Daily Agent and Daily Review artifacts**

Verify reader-facing first viewport, source mode, original-report disclosure, and the historical chart's non-zero natural dimensions.

- [ ] **Step 3: Verify desktop, tablet, and mobile layouts**

Check 1440x900, 1024x768, and 390x844 for overflow, overlap, clipped labels, and unnamed controls.

- [ ] **Step 4: Commit and update PR #177**

Review staged files against repository red lines, commit the implementation, and push the fast-forward result to `codex/feat/workbench-ui-redesign`.
