# Self-use Baseline and Maturity Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 PR #190 收口为稳定的本人自用基线，并建立可审计的 10 交易日 Self-use Maturity Gate，后续产品 Skill、数据运营和今日情报均在该基线上迭代。

**Architecture:** 保留 PR #190 的 React/FastAPI/Conversation/Run/SSE 架构；新增一个独立的 `self_use_maturity` 服务作为自用验收台账唯一写入者，事件以用户私有 JSONL 保存，确定性聚合为状态快照。CLI 负责人工记录与查状态，Workbench bootstrap 只读聚合结果并展示，不把自用评分混入市场证据或用户 correction。

**Tech Stack:** Python 3.12、FastAPI、pytest、React 19、TypeScript、Vitest、Playwright、JSONL 用户私有台账、现有 RunStore/ConversationStore。

---

## Scope and execution order

本计划只覆盖第一批可独立验收的软件：

1. PR #190 合并前最终基线审计；
2. Self-use 事件契约与用户私有台账；
3. 10 交易日成熟度计算；
4. CLI 记录/查询入口；
5. Workbench 只读状态展示；
6. 真实运行 smoke 与自用 runbook。

后续按依赖顺序另建四份计划：

1. `self-use-data-freshness-and-publishing`：DuckDB 原子快照、公告新闻刷新、新鲜度契约、健康状态；
2. `self-use-product-skills`：今日市场、题材、个股、消息、自选五个正式产品 Skill；
3. `self-use-research-home-and-watchlist`：今日情报状态、本地自选、卡片到对话；
4. `self-use-quality-evaluation`：Knevo 对照集、真实数据评测、10 日使用裁决。

外部认证、PostgreSQL、多租户和邀请制不在 Self-use 阶段实现。

## Preconditions

- 不在当前脏工作区直接执行实现。
- PR #190 必须先完成 review；是否转 ready、是否合并 `main` 均由用户明确确认。
- PR #190 合并后，从最新 `main` 创建 `feat/self-use-maturity-gate`。
- 不提交 `.env*`、密钥、数据库、PDF、缓存、虚拟环境或真实用户台账。

### Task 1: Freeze the PR #190 baseline

**Files:**
- Verify: `.github/workflows/workbench-check.yml`
- Verify: `intelligence/api/app.py`
- Verify: `intelligence/services/conversation_orchestrator.py`
- Verify: `intelligence/services/conversation_store.py`
- Verify: `intelligence/services/llm_settings.py`
- Verify: `intelligence/workbench_skills/registry.py`
- Verify: `intelligence/webapp/e2e/workbench.spec.ts`
- Modify only if audit finds a defect: the matching file above and its existing test file

- [ ] **Step 1: Compare PR #190 with current main**

Run:

```bash
git fetch origin main feat/chat-first-skill-workbench
git diff --stat origin/main...origin/feat/chat-first-skill-workbench
gh pr view 190 --json isDraft,mergeStateStatus,statusCheckRollup,reviewDecision,headRefOid
```

Expected: PR is open, mergeable, and both `registry-check` and `workbench-check` are successful. Record the exact head SHA; do not use a moving branch name as runtime evidence.

- [ ] **Step 2: Run the branch test suite in an isolated worktree**

Run:

```bash
git worktree add ../finance-workspace-pr190 origin/feat/chat-first-skill-workbench
cd ../finance-workspace-pr190
python -m pytest -q intelligence/tests
cd intelligence/webapp
corepack enable
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
```

Expected: all Python, lint, typecheck, Vitest, build, and non-skipped Playwright checks pass. Any failure becomes a focused PR #190 fix before this plan continues.

- [ ] **Step 3: Run a real managed-model conversation smoke**

Run from the isolated worktree with the server-injected managed credential:

```bash
python -m intelligence.cli serve --host 127.0.0.1 --port 8765
```

In a second terminal, create one conversation, send “今天市场怎么样”, wait for terminal state, then inspect the run report and events. Save only redacted diagnostics under `/tmp`; do not commit runtime output.

Expected:

- one user message and one terminal assistant message;
- at least one `text.delta` event when LLM is available;
- exactly one terminal completed or observably degraded event;
- `report.llm.provider/model` are present only when `llm.used=true`;
- no API key or `Authorization: Bearer` string in persisted files, SSE capture, or logs;
- data-quality warnings are visible rather than silently omitted.

- [ ] **Step 4: Present merge readiness to the user**

Do not run `gh pr ready` or merge without explicit user confirmation. Report:

- exact tested SHA;
- test totals;
- real model result;
- remaining data-quality warnings;
- whether PR #197/#198 affect the same contracts.

- [ ] **Step 5: After user approval, merge and branch from latest main**

The user performs or explicitly authorizes the merge. Then run:

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feat/self-use-maturity-gate
```

Expected: clean task branch based on the merge commit containing PR #190.

### Task 2: Define the self-use event ledger

**Files:**
- Create: `intelligence/services/self_use_maturity.py`
- Create: `intelligence/tests/test_self_use_maturity.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing tests for the event contract**

Create `intelligence/tests/test_self_use_maturity.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services.self_use_maturity import (
    SelfUseEvent,
    SelfUseLedger,
)


def test_record_event_appends_private_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "self-use-events.jsonl"
    ledger = SelfUseLedger(path)
    event = SelfUseEvent(
        trade_date="2026-07-13",
        workflow="stock_research",
        outcome="success",
        manual_rescue=False,
        severe_fact_error=False,
        useful=True,
        note="完成个股深挖",
        run_id="run_123",
    )

    ledger.record(event)

    payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["schema_version"] == 1
    assert payload["workflow"] == "stock_research"
    assert payload["run_id"] == "run_123"


@pytest.mark.parametrize("workflow", ["daily_market", "theme_research", "stock_research", "news_impact", "watchlist"])
def test_supported_workflows_are_accepted(tmp_path: Path, workflow: str) -> None:
    ledger = SelfUseLedger(tmp_path / "events.jsonl")
    ledger.record(SelfUseEvent("2026-07-13", workflow, "success", False, False, True))
    assert ledger.load()[0].workflow == workflow


def test_invalid_event_is_rejected_without_partial_write(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    ledger = SelfUseLedger(path)
    with pytest.raises(ValueError, match="workflow"):
        ledger.record(SelfUseEvent("2026-07-13", "unknown", "success", False, False, True))
    assert not path.exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest -q intelligence/tests/test_self_use_maturity.py
```

Expected: FAIL because `intelligence.services.self_use_maturity` does not exist.

- [ ] **Step 3: Implement the event and single-writer ledger**

Create `intelligence/services/self_use_maturity.py` with these public types and validation rules:

```python
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from intelligence.services.run_store import redact

Workflow = Literal["daily_market", "theme_research", "stock_research", "news_impact", "watchlist"]
Outcome = Literal["success", "degraded", "failed"]

WORKFLOWS = {"daily_market", "theme_research", "stock_research", "news_impact", "watchlist"}
OUTCOMES = {"success", "degraded", "failed"}


@dataclass(frozen=True)
class SelfUseEvent:
    trade_date: str
    workflow: str
    outcome: str
    manual_rescue: bool
    severe_fact_error: bool
    useful: bool
    note: str = ""
    run_id: str | None = None
    recorded_at: str | None = None
    schema_version: int = 1

    def validated(self) -> "SelfUseEvent":
        date.fromisoformat(self.trade_date)
        if self.workflow not in WORKFLOWS:
            raise ValueError("unsupported workflow")
        if self.outcome not in OUTCOMES:
            raise ValueError("unsupported outcome")
        if self.schema_version != 1:
            raise ValueError("unsupported schema_version")
        return SelfUseEvent(
            **{
                **asdict(self),
                "note": redact(self.note.strip()[:1000]),
                "run_id": redact(self.run_id.strip()) if self.run_id else None,
                "recorded_at": self.recorded_at or datetime.now().astimezone().isoformat(),
            }
        )


class SelfUseLedger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def record(self, event: SelfUseEvent) -> SelfUseEvent:
        value = event.validated()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(value), ensure_ascii=False, sort_keys=True) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(prefix=".self-use-", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                if self.path.exists():
                    handle.write(self.path.read_text(encoding="utf-8"))
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        return value

    def load(self) -> list[SelfUseEvent]:
        if not self.path.exists():
            return []
        events: list[SelfUseEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(SelfUseEvent(**json.loads(line)).validated())
        return events
```

Use this implementation as written so `note` and `run_id` pass through the repository's existing redaction helper before persistence.

- [ ] **Step 4: Add the private ledger path to gitignore**

Append:

```gitignore
intelligence/users/*/self-use/
```

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest -q intelligence/tests/test_self_use_maturity.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .gitignore intelligence/services/self_use_maturity.py intelligence/tests/test_self_use_maturity.py
git commit -m "feat: add private self-use maturity ledger"
```

### Task 3: Implement deterministic maturity evaluation

**Files:**
- Modify: `intelligence/services/self_use_maturity.py`
- Modify: `intelligence/tests/test_self_use_maturity.py`

- [ ] **Step 1: Write failing gate tests**

Add:

```python
from intelligence.services.self_use_maturity import evaluate_maturity


def test_gate_requires_ten_distinct_trade_dates_and_all_workflows() -> None:
    events = [
        SelfUseEvent(f"2026-07-{day:02d}", workflow, "success", False, False, True)
        for day in range(1, 11)
        for workflow in ("daily_market", "theme_research", "stock_research", "news_impact", "watchlist")
    ]
    result = evaluate_maturity(events)
    assert result.metrics["distinct_trade_dates"] == 10
    assert result.metrics["core_success_rate"] == 1.0
    assert result.eligible_for_user_decision is True
    assert result.user_approved is False
    assert result.passed is False


def test_severe_fact_error_blocks_gate() -> None:
    events = [
        SelfUseEvent(f"2026-07-{day:02d}", "daily_market", "success", False, day == 5, True)
        for day in range(1, 11)
    ]
    result = evaluate_maturity(events)
    assert "severe_fact_error" in result.blockers
    assert result.eligible_for_user_decision is False


def test_user_approval_cannot_override_mechanical_blockers() -> None:
    event = SelfUseEvent("2026-07-01", "daily_market", "success", False, False, True)
    result = evaluate_maturity([event], user_approved=True)
    assert result.passed is False
    assert "minimum_trade_dates" in result.blockers
```

- [ ] **Step 2: Run the tests to verify failure**

```bash
python -m pytest -q intelligence/tests/test_self_use_maturity.py
```

Expected: FAIL because `evaluate_maturity` is missing.

- [ ] **Step 3: Implement the evaluator**

Add the following code after `SelfUseLedger`:

```python
@dataclass(frozen=True)
class MaturityResult:
    metrics: dict[str, float | int | list[str]]
    blockers: tuple[str, ...]
    eligible_for_user_decision: bool
    user_approved: bool
    passed: bool


def evaluate_maturity(
    events: list[SelfUseEvent], *, user_approved: bool = False
) -> MaturityResult:
    total = len(events)
    trade_dates = sorted({event.trade_date for event in events})
    covered = sorted({event.workflow for event in events})
    success_rate = (
        sum(event.outcome == "success" for event in events) / total if total else 0.0
    )
    useful_rate = sum(event.useful for event in events) / total if total else 0.0
    manual_rescue_rate = (
        sum(event.manual_rescue for event in events) / total if total else 0.0
    )
    severe_fact_errors = sum(event.severe_fact_error for event in events)

    blockers: list[str] = []
    if len(trade_dates) < 10:
        blockers.append("minimum_trade_dates")
    if set(covered) != WORKFLOWS:
        blockers.append("missing_workflows")
    if success_rate < 0.95:
        blockers.append("success_rate")
    if severe_fact_errors:
        blockers.append("severe_fact_error")
    if manual_rescue_rate > 0.05:
        blockers.append("manual_rescue_rate")
    if useful_rate < 0.80:
        blockers.append("useful_rate")

    eligible = not blockers
    return MaturityResult(
        metrics={
            "distinct_trade_dates": len(trade_dates),
            "covered_workflows": covered,
            "core_success_rate": round(success_rate, 6),
            "useful_rate": round(useful_rate, 6),
            "manual_rescue_rate": round(manual_rescue_rate, 6),
            "severe_fact_errors": severe_fact_errors,
            "event_count": total,
        },
        blockers=tuple(blockers),
        eligible_for_user_decision=eligible,
        user_approved=bool(user_approved),
        passed=eligible and bool(user_approved),
    )
```

The stable blocker codes are `minimum_trade_dates`, `missing_workflows`, `success_rate`, `severe_fact_error`, `manual_rescue_rate`, and `useful_rate`. Explicit user approval never overrides a mechanical blocker.

- [ ] **Step 4: Run tests**

```bash
python -m pytest -q intelligence/tests/test_self_use_maturity.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add intelligence/services/self_use_maturity.py intelligence/tests/test_self_use_maturity.py
git commit -m "feat: evaluate self-use maturity gate"
```

### Task 4: Add CLI record and status commands

**Files:**
- Modify: `intelligence/cli.py`
- Create: `intelligence/tests/test_self_use_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `intelligence/tests/test_self_use_cli.py` using `build_parser()` and a temporary explicit `--ledger` path. Cover:

```python
def test_self_use_record_and_status_json(tmp_path, capsys):
    ledger = tmp_path / "events.jsonl"
    parser = build_parser()
    args = parser.parse_args([
        "self-use", "record", "--ledger", str(ledger),
        "--date", "2026-07-13", "--workflow", "daily_market",
        "--outcome", "success", "--useful", "--run-id", "run_123",
    ])
    assert args.func(args) == 0
    args = parser.parse_args(["self-use", "status", "--ledger", str(ledger), "--json"])
    assert args.func(args) == 1
    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert payload["metrics"]["distinct_trade_dates"] == 1
    assert "minimum_trade_dates" in payload["blockers"]
```

Also test `--manual-rescue`, `--severe-fact-error`, `--not-useful`, invalid workflow, and `status --user-approved` not bypassing blockers.

- [ ] **Step 2: Run the tests to verify failure**

```bash
python -m pytest -q intelligence/tests/test_self_use_cli.py
```

Expected: FAIL because the `self-use` parser is missing.

- [ ] **Step 3: Add CLI handlers and parser**

Add these handlers near the other user-learning commands:

```python
def _self_use_ledger(args: argparse.Namespace):
    from intelligence import userspace
    from intelligence.services.self_use_maturity import SelfUseLedger

    if args.ledger:
        path = Path(args.ledger).expanduser()
    else:
        path = userspace.user_space(args.user).root / "self-use" / "events.jsonl"
    return SelfUseLedger(path)


def cmd_self_use_record(args: argparse.Namespace) -> int:
    from intelligence.services.self_use_maturity import SelfUseEvent

    event = SelfUseEvent(
        trade_date=args.date,
        workflow=args.workflow,
        outcome=args.outcome,
        manual_rescue=args.manual_rescue,
        severe_fact_error=args.severe_fact_error,
        useful=args.useful,
        note=args.note,
        run_id=args.run_id,
    )
    recorded = _self_use_ledger(args).record(event)
    print(json.dumps(asdict(recorded), ensure_ascii=False, sort_keys=True))
    return 0


def cmd_self_use_status(args: argparse.Namespace) -> int:
    from intelligence.services.self_use_maturity import evaluate_maturity

    try:
        result = evaluate_maturity(
            _self_use_ledger(args).load(), user_approved=args.user_approved
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"self-use ledger error: {exc}", file=sys.stderr)
        return 2
    payload = asdict(result)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"Self-use: {result.metrics['distinct_trade_dates']}/10 交易日；"
            f"workflow={len(result.metrics['covered_workflows'])}/5；"
            f"blockers={','.join(result.blockers) or '-'}；passed={result.passed}"
        )
    return 0 if result.passed else 1


def add_self_use_parser(subparsers: argparse._SubParsersAction) -> None:
    from intelligence.services.self_use_maturity import OUTCOMES, WORKFLOWS

    parser = subparsers.add_parser("self-use", help="记录和检查本人自用成熟度")
    sub = parser.add_subparsers(dest="action", required=True)

    record = sub.add_parser("record", help="记录一次真实自用结果")
    record.add_argument("--user", default=None)
    record.add_argument("--ledger", default=None)
    record.add_argument("--date", required=True)
    record.add_argument("--workflow", choices=sorted(WORKFLOWS), required=True)
    record.add_argument("--outcome", choices=sorted(OUTCOMES), required=True)
    usefulness = record.add_mutually_exclusive_group(required=True)
    usefulness.add_argument("--useful", action="store_true", dest="useful")
    usefulness.add_argument("--not-useful", action="store_false", dest="useful")
    record.add_argument("--manual-rescue", action="store_true")
    record.add_argument("--severe-fact-error", action="store_true")
    record.add_argument("--run-id", default=None)
    record.add_argument("--note", default="")
    record.set_defaults(func=cmd_self_use_record)

    status = sub.add_parser("status", help="聚合自用成熟度")
    status.add_argument("--user", default=None)
    status.add_argument("--ledger", default=None)
    status.add_argument("--json", action="store_true")
    status.add_argument("--user-approved", action="store_true")
    status.set_defaults(func=cmd_self_use_status)
```

Add `from dataclasses import asdict` if `cli.py` does not already import it. Add one `add_self_use_parser(subparsers)` call in `build_parser()`.

Command contract:

```text
python -m intelligence.cli self-use record \
  --date YYYY-MM-DD \
  --workflow daily_market|theme_research|stock_research|news_impact|watchlist \
  --outcome success|degraded|failed \
  --useful|--not-useful \
  [--manual-rescue] [--severe-fact-error] [--run-id ID] [--note TEXT]

python -m intelligence.cli self-use status [--json] [--user-approved]
```

Default ledger path must resolve through `userspace.user_space(args.user).root / "self-use/events.jsonl"`. `--ledger` exists only for tests and explicit local diagnostics.

Exit codes:

- `record`: 0 on successful append;
- `status`: 0 only when final gate passed, 1 when not passed, 2 when the ledger cannot be parsed.

- [ ] **Step 4: Run focused and parser regression tests**

```bash
python -m pytest -q intelligence/tests/test_self_use_cli.py intelligence/tests/test_cli.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add intelligence/cli.py intelligence/tests/test_self_use_cli.py
git commit -m "feat: expose self-use maturity CLI"
```

### Task 5: Expose read-only maturity status in Workbench

**Files:**
- Modify: `intelligence/api/app.py`
- Modify: `intelligence/tests/test_workbench_api.py`
- Modify: `intelligence/webapp/src/types.ts`
- Modify: `intelligence/webapp/src/components/ResearchInspector.tsx`
- Modify: `intelligence/webapp/src/components/components.test.tsx`

- [ ] **Step 1: Write the failing API test**

Add a test that writes one event beneath the fixture user's private `self-use/events.jsonl`, calls `/api/workbench/bootstrap?user=demo`, and asserts:

```python
assert response.status_code == 200
assert response.json()["self_use_maturity"] == {
    "distinct_trade_dates": 1,
    "success_rate": 1.0,
    "useful_rate": 1.0,
    "manual_rescue_rate": 0.0,
    "covered_workflows": ["daily_market"],
    "blockers": ["minimum_trade_dates", "missing_workflows"],
    "eligible_for_user_decision": False,
    "passed": False,
}
```

The endpoint is read-only: bootstrap must never create or mutate the ledger.

- [ ] **Step 2: Run the API test to verify failure**

```bash
python -m pytest -q intelligence/tests/test_workbench_api.py -k self_use_maturity
```

Expected: FAIL because bootstrap has no `self_use_maturity` field.

- [ ] **Step 3: Add the bootstrap projection**

Import `SelfUseLedger` and `evaluate_maturity`, then add this local helper beside the other `create_app` store helpers:

```python
def self_use_projection(user: str | None) -> dict[str, object]:
    conversation_store = conversation_store_for(user)
    ledger = SelfUseLedger(
        conversation_store.root.parent / "self-use" / "events.jsonl"
    )
    result = evaluate_maturity(ledger.load())
    return {
        "distinct_trade_dates": result.metrics["distinct_trade_dates"],
        "success_rate": result.metrics["core_success_rate"],
        "useful_rate": result.metrics["useful_rate"],
        "manual_rescue_rate": result.metrics["manual_rescue_rate"],
        "covered_workflows": result.metrics["covered_workflows"],
        "blockers": list(result.blockers),
        "eligible_for_user_decision": result.eligible_for_user_decision,
        "passed": result.passed,
    }
```

Add `"self_use_maturity": self_use_projection(user)` to the bootstrap response. Do not catch malformed-ledger errors as an empty ledger: return an observable API error so corruption cannot look like zero usage. Do not return event notes or individual run IDs through bootstrap.

- [ ] **Step 4: Add the TypeScript contract**

Add:

```typescript
export interface SelfUseMaturity {
  distinct_trade_dates: number;
  success_rate: number;
  useful_rate: number;
  manual_rescue_rate: number;
  covered_workflows: string[];
  blockers: string[];
  eligible_for_user_decision: boolean;
  passed: boolean;
}
```

and `self_use_maturity: SelfUseMaturity` to `Bootstrap`.

- [ ] **Step 5: Write the failing component test**

Render `ResearchInspector` with a bootstrap fixture containing one trade date and assert that it displays “自用成熟度 1/10 交易日” and does not display notes or run IDs.

- [ ] **Step 6: Implement a compact inspector status**

Add this rendering block in the existing inspector metadata/status section, using the actual `bootstrap.self_use_maturity` prop path established by the component:

```tsx
<section aria-label="自用成熟度" className="inspector-section">
  <h3>自用成熟度 {maturity.distinct_trade_dates}/10 交易日</h3>
  <p>核心工作流 {maturity.covered_workflows.length}/5</p>
  <p>
    成功 {(maturity.success_rate * 100).toFixed(0)}% ·
    有用 {(maturity.useful_rate * 100).toFixed(0)}% ·
    人工救场 {(maturity.manual_rescue_rate * 100).toFixed(0)}%
  </p>
  <p>阻塞项 {maturity.blockers.length}</p>
  {maturity.eligible_for_user_decision ? <p>可由用户最终裁决</p> : null}
</section>
```

Display semantics:

- `自用成熟度 N/10 交易日`;
- workflow coverage `N/5`;
- success/useful/manual-rescue percentages;
- blocker count;
- “可由用户最终裁决” only when `eligible_for_user_decision=true`.

Do not add a second dashboard or progress gamification. This is an operational gate, not a user achievement system.

- [ ] **Step 7: Run backend and frontend tests**

```bash
python -m pytest -q intelligence/tests/test_workbench_api.py -k self_use_maturity
cd intelligence/webapp
pnpm test
pnpm typecheck
pnpm lint
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add intelligence/api/app.py intelligence/tests/test_workbench_api.py intelligence/webapp/src/types.ts intelligence/webapp/src/components/ResearchInspector.tsx intelligence/webapp/src/components/components.test.tsx
git commit -m "feat: show self-use maturity status"
```

### Task 6: Add real-runtime smoke automation

**Files:**
- Create: `scripts/smoke_workbench_self_use.py`
- Create: `tests/test_smoke_workbench_self_use.py`
- Modify: `docs/workbench/local-site.md`

- [ ] **Step 1: Write failing parser tests for redacted smoke results**

The script must accept `--base-url`, `--user`, `--question`, `--timeout`, and `--output`. The test starts a fixture FastAPI app or mocks HTTP responses and verifies the output JSON contains:

```json
{
  "conversation_created": true,
  "terminal_status": "completed",
  "text_delta_count": 3,
  "terminal_event_count": 1,
  "llm_used": true,
  "provider": "zhipu",
  "model": "glm-5.2",
  "degrades": [],
  "secret_scan_matches": 0
}
```

The output must not contain message content, API keys, Authorization headers, full citations, or private paths.

- [ ] **Step 2: Run the test to verify failure**

```bash
python -m pytest -q tests/test_smoke_workbench_self_use.py
```

Expected: FAIL because the script does not exist.

- [ ] **Step 3: Implement the smoke client**

Use the Python standard library or existing `requests` dependency to:

1. call readiness;
2. create a conversation;
3. create a message in hybrid mode;
4. poll/replay SSE until one terminal event;
5. fetch the run report;
6. count non-empty `text.delta` events;
7. scan only collected redacted strings for common secret markers;
8. write a JSON summary atomically.

Return exit code 0 for completed or explicitly degraded terminal results, 1 for failed/cancelled, and 2 for protocol/secret-scan violations.

- [ ] **Step 4: Run tests**

```bash
python -m pytest -q tests/test_smoke_workbench_self_use.py
```

Expected: PASS.

- [ ] **Step 5: Document the smoke command**

Add to `docs/workbench/local-site.md`:

```bash
python scripts/smoke_workbench_self_use.py \
  --base-url http://127.0.0.1:8765 \
  --user linxiaoqi5111 \
  --question "今天市场怎么样" \
  --output /tmp/workbench-self-use-smoke.json
```

Explain every output field and state that `/tmp` artifacts are diagnostics, not ledgers and not commit candidates.

- [ ] **Step 6: Commit**

```bash
git add scripts/smoke_workbench_self_use.py tests/test_smoke_workbench_self_use.py docs/workbench/local-site.md
git commit -m "test: automate self-use workbench smoke"
```

### Task 7: Run the complete baseline gate and start the campaign

**Files:**
- Modify: `docs/workbench/local-site.md`
- Verify only: `intelligence/users/<user>/self-use/events.jsonl` (gitignored)
- Verify only: `/tmp/workbench-self-use-smoke.json`

- [ ] **Step 1: Run the complete automated suite**

```bash
python -m pytest -q intelligence/tests
python -m pytest -q tests/test_smoke_workbench_self_use.py
cd intelligence/webapp
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
```

Expected: all required checks pass; existing explicitly documented skips remain skips.

- [ ] **Step 2: Run the real smoke**

Start the local product and run the smoke command from Task 6. Inspect the JSON summary and the UI inspector maturity status.

Expected:

- one terminal assistant response;
- no secret matches;
- model metadata internally consistent;
- data-quality warnings visible;
- maturity status initially below the gate.

- [ ] **Step 3: Record the first real event**

After actually reviewing the answer, run:

```bash
python -m intelligence.cli self-use record \
  --user linxiaoqi5111 \
  --date YYYY-MM-DD \
  --workflow daily_market \
  --outcome success \
  --useful \
  --run-id RUN_ID \
  --note "盘后市场结论可直接使用，数据时点清楚"
```

Use `degraded`, `failed`, `--manual-rescue`, `--severe-fact-error`, or `--not-useful` truthfully. The ledger is not a vanity score.

- [ ] **Step 4: Verify the gate remains closed**

```bash
python -m intelligence.cli self-use status --user linxiaoqi5111 --json
```

Expected after the first day: exit code 1 with `minimum_trade_dates` and missing workflow blockers.

- [ ] **Step 5: Add the 10-day operating instructions**

Document:

- one event per genuinely reviewed workflow result;
- how to link a Run;
- how to mark manual rescue and severe fact error;
- how to inspect status;
- that `--user-approved` is used only after mechanical blockers are clear and the user explicitly approves;
- that the campaign does not start Hosted Beta work.

- [ ] **Step 6: Commit documentation only**

```bash
git add docs/workbench/local-site.md
git commit -m "docs: start self-use maturity campaign"
```

Do not stage the real JSONL ledger or `/tmp` diagnostics.

## Final verification

Run:

```bash
git status --short
python -m pytest -q intelligence/tests
cd intelligence/webapp && pnpm lint && pnpm typecheck && pnpm test && pnpm build && pnpm test:e2e
python -m intelligence.cli self-use status --user linxiaoqi5111 --json
```

Expected handoff:

- PR #190 baseline is merged only with user approval;
- self-use events are private and gitignored;
- Workbench shows aggregate maturity without exposing notes;
- real smoke is repeatable and secret-safe;
- gate is observably closed until 10 real trading days, all workflows, quality thresholds, and explicit user approval are satisfied;
- no Hosted Beta infrastructure has started prematurely.
