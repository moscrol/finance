# Market Snapshot Provider Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 DuckDB 完整事实层和隔离 AkShare worker 组成可审计 provider chain，确保公开端点失败时 partial 永不污染 canonical snapshot，Workbench 仍可使用最近完整交易日。

**Architecture:** 新建只读 DuckDB candidate builder 和 provider orchestrator。编排顺序固定为 exact-date DuckDB、临时 AkShare、latest-prior DuckDB；所有候选通过 contract 后才原子发布。LaunchAgent 调用 chain runner，两个 provider 继续使用隔离 Python 环境。

**Tech Stack:** Python 3.11+、DuckDB、AkShare 1.18.64、JSON snapshot contract、macOS LaunchAgent、pytest。

---

## 文件边界

- Create `intelligence/services/duckdb_market_snapshot.py`：只读查询、完整度门禁、contract document 映射。
- Create `intelligence/services/market_snapshot_sync.py`：provider 顺序、AkShare subprocess、临时目录、原子发布、attempt telemetry。
- Create `scripts/sync_market_snapshot.py`：provider-chain CLI。
- Create `scripts/run_market_snapshot.sh`：选择 Workbench Python，传入 code/data/db/venv 路径。
- Modify `intelligence/data/com.a77.finance-akshare-snapshot.plist`：调度 chain runner 并增加 DuckDB/Python 配置。
- Modify `intelligence/services/market_snapshot_contract.py`：返回 provider/provenance 摘要，不改变 complete 门槛。
- Modify `intelligence/api/app.py`：readiness 投影 provider 与 served date。
- Test `intelligence/tests/test_duckdb_market_snapshot.py`：candidate mapping 和质量门。
- Test `intelligence/tests/test_market_snapshot_sync.py`：三层选择、partial 隔离、旧 complete 保全。
- Modify `intelligence/tests/test_akshare_runtime_assets.py`：双环境 runner/plist 契约。
- Modify `tests/test_market_snapshot_contract.py`、`intelligence/tests/test_workbench_api.py`：provenance/readiness 投影。
- Modify `docs/workbench/akshare-snapshot-runtime.md`、`docs/workbench/canonical-8792-cutover.md`：部署与真实验收命令。

### Task 1: DuckDB candidate builder

**Files:**
- Create: `intelligence/services/duckdb_market_snapshot.py`
- Create: `intelligence/tests/test_duckdb_market_snapshot.py`

- [ ] **Step 1: 写 exact-date 成功测试**

测试用临时 DuckDB 建四张最小表，插入 4000 条完整个股、市场行、板块和主线行：

```python
candidate = build_duckdb_snapshot_candidate(
    db_path,
    target_date="2026-07-16",
    allow_latest_before=False,
    now=datetime(2026, 7, 16, 17, tzinfo=BEIJING),
)
assert candidate.trade_date == "2026-07-16"
assert candidate.document["quality"] == "complete"
assert candidate.document["freshness"] == "fresh"
assert candidate.document["market"]["advancers"] == 2500
assert candidate.document["market"]["decliners"] == 1500
assert candidate.document["source"] == "duckdb:market_feature_store"
```

- [ ] **Step 2: 写 previous-date 与完整度失败测试**

```python
candidate = build_duckdb_snapshot_candidate(
    db_path,
    target_date="2026-07-16",
    allow_latest_before=True,
)
assert candidate.trade_date == "2026-07-15"
assert candidate.document["freshness"] == "historical"

with pytest.raises(DuckDbSnapshotUnavailable, match="stock rows"):
    build_duckdb_snapshot_candidate(sparse_db, target_date="2026-07-16")
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest -q intelligence/tests/test_duckdb_market_snapshot.py`

Expected: FAIL，模块尚不存在。

- [ ] **Step 4: 实现 candidate 类型与只读查询**

实现公开类型：

```python
@dataclass(frozen=True)
class DuckDbSnapshotCandidate:
    trade_date: str
    document: dict[str, object]
    source_tables: tuple[str, ...]
    source_updated_at: str | None

class DuckDbSnapshotUnavailable(RuntimeError):
    pass
```

公开函数签名为
`build_duckdb_snapshot_candidate(db_path, *, target_date, allow_latest_before=False, now=None) -> DuckDbSnapshotCandidate`。

连接必须使用 `duckdb.connect(str(path), read_only=True)`。日期选择只允许 `=` 或
`<= target_date`，四类查询全部绑定同一个 `served_date`。门槛固定为 4000 行和三个关键
字段 98% 非空率。strong stocks 取 `pct_chg >= 7` 后按涨幅、成交额降序，最多 80 条；
若不足一条则判 unavailable。

- [ ] **Step 5: 实现 theme 映射与 sector fallback**

主线行按 `theme_name` 聚合：

```python
{
    "concept": theme_name,
    "priority_score": max(strength_values),
    "trigger_types": ["duckdb_mainline"],
    "limit_up_count": sum(limit_up_count),
    "strong_stock_count": None,
}
```

无主线行时从 `fact_sector_daily` 按 `coalesce(strength, pct_chg)` 降序取 20 条，使用
`duckdb_sector_strength`，不得写成 mainline。

- [ ] **Step 6: 运行并提交**

Run: `pytest -q intelligence/tests/test_duckdb_market_snapshot.py`

Expected: PASS。

```bash
git add intelligence/services/duckdb_market_snapshot.py intelligence/tests/test_duckdb_market_snapshot.py
git commit -m "feat: build governed DuckDB market snapshots"
```

### Task 2: Provider orchestrator 与 partial 隔离

**Files:**
- Create: `intelligence/services/market_snapshot_sync.py`
- Create: `intelligence/tests/test_market_snapshot_sync.py`

- [ ] **Step 1: 写 provider 顺序测试**

用 callable 注入避免单测访问网络：

```python
result = sync_market_snapshot(
    root,
    db_path=db_path,
    target_date="2026-07-16",
    akshare_runner=runner_that_must_not_be_called,
)
assert result.quality == "complete"
assert result.served_trade_date == "2026-07-16"
assert [attempt.provider for attempt in result.attempts] == ["duckdb_exact"]
```

- [ ] **Step 2: 写 AkShare complete 和 partial 隔离测试**

```python
complete = sync_market_snapshot(
    root,
    db_path=db_without_target,
    target_date="2026-07-16",
    akshare_runner=write_complete_temp_snapshot,
)
assert complete.provider == "akshare_exact"

fallback = sync_market_snapshot(
    root,
    db_path=db_with_only_2026_07_15,
    target_date="2026-07-16",
    akshare_runner=write_partial_temp_snapshot,
)
assert fallback.provider == "duckdb_latest"
assert fallback.served_trade_date == "2026-07-15"
assert not (root / "2026-07-16.json").exists()
assert json.loads((root / "latest.json").read_text())["trade_date"] == "2026-07-15"
```

- [ ] **Step 3: 写全失败与旧 complete 保全测试**

```python
before = (root / "latest.json").read_bytes()
result = sync_market_snapshot(
    root,
    db_path=db_without_market_rows,
    target_date="2026-07-16",
    akshare_runner=failed_runner,
)
assert result.ok is False
assert result.preserved_existing_snapshot is True
assert (root / "latest.json").read_bytes() == before
```

- [ ] **Step 4: 运行测试确认失败**

Run: `pytest -q intelligence/tests/test_market_snapshot_sync.py`

Expected: FAIL，模块尚不存在。

- [ ] **Step 5: 实现 result/attempt 与三层编排**

```python
@dataclass(frozen=True)
class ProviderAttempt:
    provider: str
    requested_trade_date: str
    served_trade_date: str | None
    quality: str
    freshness: str | None
    duration_ms: int
    published: bool
    error: str | None = None

@dataclass(frozen=True)
class MarketSnapshotSyncResult:
    ok: bool
    quality: str
    requested_trade_date: str
    served_trade_date: str | None
    provider: str | None
    attempts: tuple[ProviderAttempt, ...]
    written_files: tuple[str, ...]
    preserved_existing_snapshot: bool
```

AkShare 默认 runner 使用 `subprocess.run` 调用：

```text
<AKSHARE_VENV>/bin/python -m scripts.sync_akshare_market_snapshot
  --date <target> --output-dir <temporary-directory>
```

设置 `cwd=code_root`、`PYTHONPATH=code_root`、timeout 240 秒；退出 0 后仍必须读取
contract 并验证 `PASS + ready=true`，不能只相信进程码。

- [ ] **Step 6: 实现原子发布与状态台账**

候选 document 写 `daily/latest/meta` 前再次验证；用 `mkstemp + fsync + os.replace`。
状态写 `market_snapshot_sync_status.json`。AkShare temporary partial 只进入 attempts，绝不复制。

- [ ] **Step 7: 运行并提交**

Run: `pytest -q intelligence/tests/test_market_snapshot_sync.py intelligence/tests/test_duckdb_market_snapshot.py`

Expected: PASS。

```bash
git add intelligence/services/market_snapshot_sync.py intelligence/tests/test_market_snapshot_sync.py
git commit -m "feat: orchestrate resilient market snapshot providers"
```

### Task 3: CLI、runner 与 LaunchAgent

**Files:**
- Create: `scripts/sync_market_snapshot.py`
- Create: `scripts/run_market_snapshot.sh`
- Modify: `intelligence/data/com.a77.finance-akshare-snapshot.plist`
- Modify: `intelligence/tests/test_akshare_runtime_assets.py`

- [ ] **Step 1: 先改资产测试**

```python
assert "run_market_snapshot.sh" in payload["ProgramArguments"][0]
assert payload["EnvironmentVariables"]["WORKBENCH_PYTHON"].endswith(
    "/.venv-workbench/bin/python"
)
assert payload["EnvironmentVariables"]["AKSHARE_VENV"].endswith("/akshare-venv")
assert "MARKET_DB_PATH" in payload["EnvironmentVariables"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest -q intelligence/tests/test_akshare_runtime_assets.py`

Expected: FAIL，plist 仍指向旧 runner。

- [ ] **Step 3: 实现 CLI**

参数固定为 `--date`、`--output-dir`、`--db-path`、`--akshare-python`、
`--code-root`、`--akshare-timeout`。输出 `MarketSnapshotSyncResult.to_dict()` JSON；complete
返回 0，保留旧 complete 但本轮失败返回 1，配置错误返回 2。

- [ ] **Step 4: 实现 shell runner**

runner 使用 `WORKBENCH_PYTHON` 执行 chain CLI；AkShare Python 只作为参数传入。默认路径：

```text
WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
AKSHARE_PYTHON=/Users/a77/.local/share/finance-workbench/akshare-venv/bin/python
MARKET_DB_PATH=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb
```

保留现有 direct proxy 清理逻辑，确保 AkShare subprocess 不读取 macOS 系统代理。

- [ ] **Step 5: 修改 plist 并验证**

Run: `pytest -q intelligence/tests/test_akshare_runtime_assets.py`

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add scripts/sync_market_snapshot.py scripts/run_market_snapshot.sh intelligence/data/com.a77.finance-akshare-snapshot.plist intelligence/tests/test_akshare_runtime_assets.py
git commit -m "feat: schedule governed market snapshot chain"
```

### Task 4: Contract 与 readiness 可观测性

**Files:**
- Modify: `intelligence/services/market_snapshot_contract.py`
- Modify: `intelligence/api/app.py`
- Modify: `tests/test_market_snapshot_contract.py`
- Modify: `intelligence/tests/test_workbench_api.py`

- [ ] **Step 1: 写 contract provenance 测试**

```python
result = validate_market_snapshot_root(root)
assert result["summary"]["provider"] == "duckdb_exact"
assert result["summary"]["source"] == "duckdb:market_feature_store"
assert result["summary"]["requested_trade_date"] == "2026-07-16"
assert result["summary"]["served_trade_date"] == "2026-07-15"
```

- [ ] **Step 2: 写 API readiness 测试**

```python
payload = client.get("/api/health/ready").json()
assert payload["market_snapshot"]["provider"] == "duckdb_latest"
assert payload["market_snapshot"]["date"] == "2026-07-15"
assert payload["market_snapshot"]["requested_date"] == "2026-07-16"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest -q tests/test_market_snapshot_contract.py intelligence/tests/test_workbench_api.py -k 'snapshot or readiness'`

Expected: FAIL，新字段尚未投影。

- [ ] **Step 4: 实现摘要投影**

只增加 provider/source/requested/served/source_updated_at，绝不放宽 ready 公式：

```python
ready = status == "PASS" and quality == "complete" and freshness in {
    "fresh", "historical"
}
```

- [ ] **Step 5: 运行并提交**

Run: `pytest -q tests/test_market_snapshot_contract.py intelligence/tests/test_workbench_api.py -k 'snapshot or readiness'`

Expected: PASS。

```bash
git add intelligence/services/market_snapshot_contract.py intelligence/api/app.py tests/test_market_snapshot_contract.py intelligence/tests/test_workbench_api.py
git commit -m "feat: expose snapshot provider readiness"
```

### Task 5: canonical DuckDB 隔离真实验收

**Files:**
- Modify: `docs/workbench/akshare-snapshot-runtime.md`
- Modify: `docs/workbench/canonical-8792-cutover.md`
- Modify: `docs/verification/workbench-retrieval-data-followups-p1-2026-07-16.md`

- [ ] **Step 1: 对临时目录运行真实 provider chain**

```bash
tmp_snapshot="$(mktemp -d /tmp/market-snapshot-chain.XXXXXX)"
WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
AKSHARE_PYTHON=/tmp/workbench-akshare-acceptance.amiGZ0/venv/bin/python \
MARKET_DB_PATH=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb \
MARKET_SNAPSHOT_DIR="$tmp_snapshot" \
./scripts/run_market_snapshot.sh --date 2026-07-16
```

Expected: AkShare 允许失败；最终 provider=`duckdb_latest`、served date=`2026-07-15`、
quality=`complete`、freshness=`historical`、exit 0。

- [ ] **Step 2: 验证 contract 与事实对账**

```bash
PYTHONPATH=. python3 -m scripts.check_market_snapshot_contract \
  --root "$tmp_snapshot" --pretty
jq '.status, .ready, .summary' "$tmp_snapshot/market_snapshot_sync_status.json"
```

Expected: contract `PASS`、`ready=true`；market breadth 与 DuckDB 同日统计一致。

- [ ] **Step 3: 更新 runbook 与验证报告**

文档必须记录此前 AkShare-only 真实失败，不删除负面证据；部署命令改用 chain runner，
并说明 historical 是实际日期降级，不是当天数据。

- [ ] **Step 4: 提交**

```bash
git add docs/workbench/akshare-snapshot-runtime.md docs/workbench/canonical-8792-cutover.md docs/verification/workbench-retrieval-data-followups-p1-2026-07-16.md
git commit -m "docs: verify resilient snapshot provider chain"
```

### Task 6: 完整回归与发布门

**Files:**
- Modify only generated frontend assets if production build changes them.

- [ ] **Step 1: 聚焦 Python**

Run:

```bash
pytest -q intelligence/tests/test_duckdb_market_snapshot.py \
  intelligence/tests/test_market_snapshot_sync.py \
  intelligence/tests/test_akshare_market_snapshot.py \
  intelligence/tests/test_akshare_runtime_assets.py \
  tests/test_market_snapshot_contract.py \
  intelligence/tests/test_workbench_api.py
```

Expected: PASS。

- [ ] **Step 2: 全量 Python 与 registry**

Run:

```bash
pytest -q
python3 scripts/check_skill_registry_parseability.py
python3 scripts/check_skill_registry.py
python3 scripts/backfill_skill_registry_tables.py --check
python3 scripts/generate_skill_registry_views.py --check
```

Expected: 全部 PASS，只有已知 `datetime.utcnow()` deprecation warning 可保留。

- [ ] **Step 3: 前端全套**

Run:

```bash
cd intelligence/webapp
pnpm lint
pnpm exec tsc --noEmit
pnpm test -- --run
pnpm build
pnpm exec playwright test
```

Expected: lint/typecheck/unit/build/E2E 全部 PASS。

- [ ] **Step 4: 安全与工作树审计**

Run:

```bash
git diff --check origin/main...HEAD
git status --short
git diff --name-only origin/main...HEAD | rg '\.(env|pdf|zip|duckdb|db|sqlite|pptx)$' && exit 1 || true
```

Expected: 无红线文件；只有计划内改动。

- [ ] **Step 5: 等待用户发布授权**

不得自行合并 main。用户明确确认后才 push/PR/merge，并按 canonical runbook 原子切换
8792；上线后再次运行 readiness、路由黄金回放和真实 self-use smoke。
