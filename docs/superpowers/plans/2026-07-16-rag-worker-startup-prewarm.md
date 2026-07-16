# RAG Worker Startup Prewarm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Workbench 在开放 8792 前完成 BGE-m3 常驻 worker 预热，使首个真实研究请求复用已加载模型，同时保留 20 秒阶段门限。

**Architecture:** `rag_worker.py` 管理单个子进程及其预热状态，`kb_rag.py` 负责从生产知识库配置生成最小预热请求，`app.py` 在 FastAPI lifespan startup 中同步执行并把 worker readiness 纳入关键门禁。失败时应用保留诊断接口但 readiness 返回 503，不把 CLI fallback 误报成成熟可用。

**Tech Stack:** Python 3.12/3.14、FastAPI lifespan、JSONL 子进程协议、BGE-m3 Hybrid RAG、pytest、launchd。

---

## 文件职责

- `scripts/rag_query_worker.py`：建立与 knowledge-base CLI 相同的 cwd/import context。
- `intelligence/services/rag_worker.py`：子进程、互斥锁、预热状态机和安全 telemetry。
- `intelligence/services/kb_rag.py`：解析生产 Python/索引路径并生成最小预热请求。
- `intelligence/api/app.py`：启动门禁、关闭清理和 readiness 汇总。
- `intelligence/tests/test_rag_worker.py`：worker 协议、import context、复用和状态机测试。
- `intelligence/tests/test_workbench_api.py`：lifespan 与 readiness 集成测试。
- `docs/verification/workbench-rag-worker-prewarm-2026-07-16.md`：测试、真实模型和上线回放证据。

### Task 1: 修复动态 import context（已完成）

**Files:**
- Modify: `scripts/rag_query_worker.py:21-31`
- Test: `intelligence/tests/test_rag_worker.py:15-65`

- [x] **Step 1: 让 fake KB 同时依赖 package import 与同目录 fallback import**

```python
(script.parent / "rag_freshness.py").write_text(
    'IMPORT_CONTEXT = "knowledge-base-scripts"\n', encoding="utf-8"
)
```

- [x] **Step 2: 验证旧 worker 因缺少 `scripts` import context 失败**

Run: `pytest -q intelligence/tests/test_rag_worker.py`
Expected before fix: worker exits without response while importing `scripts.rag_freshness`.

- [x] **Step 3: 在 worker 子进程中设置 cwd 与两个 import roots**

```python
script_dir = root / "scripts"
for import_root in (root, script_dir):
    resolved = str(import_root)
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
os.chdir(root)
```

- [x] **Step 4: 运行定向与全量测试**

Run: `pytest -q intelligence/tests/test_rag_worker.py intelligence/tests/test_workbench_research_owner_skills.py`
Expected: `33 passed`.

Run: `env -u FORESIGHT_USERS_DIR -u FORESIGHT_USER -u SUBCONSCIOUS_VAULT -u AGENT_MEMORY_VAULT pytest -q`
Expected: `1831 passed, 1 skipped`.

- [x] **Step 5: 提交 import 修复**

Commit: `885b888 fix: initialize RAG worker import context`

### Task 2: 为 worker 增加预热状态机

**Files:**
- Modify: `intelligence/services/rag_worker.py:20-152`
- Test: `intelligence/tests/test_rag_worker.py`

- [ ] **Step 1: 写 ready/failed/timeout 的失败测试**

```python
def test_prewarm_marks_worker_ready_and_reuses_model(tmp_path: Path) -> None:
    worker = _fixture_worker(tmp_path)
    first = worker.prewarm(["query", "warmup", "--json"], timeout=2)
    second = worker.query(["query", "actual", "--json"], timeout=2)
    assert first.model_load_count == second.model_load_count == 1
    assert worker.status()["state"] == "ready"

def test_prewarm_timeout_is_failed_and_stops_process(tmp_path: Path) -> None:
    worker = _fixture_worker(tmp_path)
    with pytest.raises(TimeoutError):
        worker.prewarm(["query", "slow", "--json"], timeout=0.02)
    assert worker.status()["state"] == "failed"
    assert worker.status()["active"] is False
    assert worker.status()["last_error_type"] == "TimeoutError"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest -q intelligence/tests/test_rag_worker.py -k prewarm`
Expected: FAIL because `PersistentRagWorker.prewarm/status` do not exist.

- [ ] **Step 3: 抽取锁内查询并实现状态机**

```python
class PersistentRagWorker:
    def prewarm(self, argv: list[str], timeout: float) -> WorkerResponse:
        with self._lock:
            self._state = "warming"
            started = time.monotonic()
            try:
                response = self._query_locked(argv, timeout)
                if response.returncode != 0:
                    raise RuntimeError("rag worker prewarm failed")
            except Exception as exc:
                self._state = "failed"
                self._last_error_type = type(exc).__name__
                self._prewarm_latency_ms = int((time.monotonic() - started) * 1000)
                raise
            self._state = "ready"
            self._last_error_type = None
            self._prewarm_latency_ms = int((time.monotonic() - started) * 1000)
            return response
```

普通 `query()` 只包装同一个 `_query_locked()`，避免 `prewarm()` 二次获取非重入锁。错误 telemetry 只保留异常类型，不保存 stderr、query 或路径。

- [ ] **Step 4: 暴露全局 prewarm 与聚合状态**

```python
def prewarm(*, python: str, kb_root: Path, index_dir: Path,
            argv: list[str], timeout: float) -> WorkerResponse:
    return _worker_for(python, kb_root, index_dir).prewarm(argv, timeout)

def enabled() -> bool:
    return os.environ.get("RAG_WORKER_ENABLED", "0").strip().lower() not in {
        "0", "false", "off", "no",
    }
```

`status()` 必须返回：`enabled`、`state`、`active`、`configured_workers`、
`model_load_count`、`prewarm_latency_ms`、`last_error_type`、
`lifecycle="startup_prewarm"`。

- [ ] **Step 5: 运行 worker 测试并提交**

Run: `pytest -q intelligence/tests/test_rag_worker.py`
Expected: all tests PASS.

Commit: `feat: add RAG worker prewarm state machine`

### Task 3: 增加生产配置预热门面

**Files:**
- Modify: `intelligence/services/kb_rag.py:290-390`
- Test: `intelligence/tests/test_rag_worker.py`

- [ ] **Step 1: 写配置解析和 disabled 测试**

```python
def test_kb_rag_prewarm_uses_production_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    monkeypatch.setenv("KB_RAG_PYTHON", sys.executable)
    monkeypatch.setenv("RAG_INDEX_DIR", str(tmp_path / ".rag_index"))
    with mock.patch.object(kb_rag.rag_worker, "prewarm") as call:
        kb_rag.prewarm(tmp_path / "wiki", timeout=90)
    assert call.call_args.kwargs["kb_root"] == tmp_path
    assert call.call_args.kwargs["index_dir"] == tmp_path / ".rag_index"
    assert call.call_args.kwargs["argv"] == [
        "query", "Workbench RAG 预热", "--k", "1",
        "--mode", "hybrid", "--json",
    ]
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest -q intelligence/tests/test_rag_worker.py -k kb_rag_prewarm`
Expected: FAIL because `kb_rag.prewarm` does not exist.

- [ ] **Step 3: 实现最小门面**

```python
def prewarm(kb_wiki: str | Path | None, *, timeout: float = 90) -> dict[str, object]:
    if not rag_worker.enabled():
        return rag_worker.status()
    root = kb_root(kb_wiki)
    index_dir = _resolve_index_dir(root)
    rag_worker.prewarm(
        python=_resolve_rag_python(root),
        kb_root=root,
        index_dir=index_dir,
        argv=["query", "Workbench RAG 预热", "--k", "1", "--mode", "hybrid", "--json"],
        timeout=timeout,
    )
    return rag_worker.status()
```

在调用前验证 wiki、`rag_index.py` 和 index 存在；缺失时把 worker 状态置为 failed，并返回安全错误类型。

- [ ] **Step 4: 验证不写业务缓存**

测试前后断言 `_RESULT_CACHE` 数量不变；预热只走 worker 协议，不调用 `retrieve()`。

- [ ] **Step 5: 运行测试并提交**

Run: `pytest -q intelligence/tests/test_rag_worker.py`
Expected: all tests PASS.

Commit: `feat: prewarm RAG from production configuration`

### Task 4: 接入 FastAPI startup 与 readiness

**Files:**
- Modify: `intelligence/api/app.py:923-1140`
- Test: `intelligence/tests/test_workbench_api.py`

- [ ] **Step 1: 写 lifespan 先预热后 yield 的测试**

```python
def test_lifespan_prewarms_enabled_rag_before_ready(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    calls = []
    monkeypatch.setattr(app_module.kb_rag, "prewarm", lambda *a, **k: calls.append("warm"))
    monkeypatch.setattr(app_module.kb_rag.rag_worker, "status", _ready_worker_status)
    with TestClient(app_module.create_app(repo_root=tmp_path)) as probe:
        assert calls == ["warm"]
        assert probe.get("/api/health/ready").status_code == 200
```

- [ ] **Step 2: 写预热失败 readiness=503 测试**

```python
def test_rag_prewarm_failure_keeps_readiness_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    monkeypatch.setattr(app_module.kb_rag, "prewarm", lambda *a, **k: None)
    monkeypatch.setattr(app_module.kb_rag.rag_worker, "status", _failed_worker_status)
    with TestClient(app_module.create_app(repo_root=tmp_path)) as probe:
        payload = probe.get("/api/health/ready")
        assert payload.status_code == 503
        assert "rag_worker" in payload.json()["missing_critical"]
```

- [ ] **Step 3: 运行测试并确认失败**

Run: `pytest -q intelligence/tests/test_workbench_api.py -k 'prewarm or readiness'`
Expected: new tests FAIL because lifespan and critical checks do not use worker readiness.

- [ ] **Step 4: 在 lifespan 同步预热并关闭时清理**

```python
@asynccontextmanager
async def lifespan(_: FastAPI):
    if kb_rag.rag_worker.enabled():
        timeout = _positive_float_env("RAG_WORKER_PREWARM_TIMEOUT", 90.0)
        try:
            kb_rag.prewarm(runtime_paths.knowledge_wiki, timeout=timeout)
        except Exception:
            pass  # 状态机记录安全错误；readiness 负责 fail closed
    try:
        yield
    finally:
        kb_rag.rag_worker.close_all()
        llm_settings.clear_all()
        supervisor.shutdown()
```

- [ ] **Step 5: 把 worker ready 纳入 critical**

```python
worker_status = kb_rag.rag_worker.status()
worker_required = bool(worker_status["enabled"])
checks["rag_worker"] = (not worker_required) or (
    worker_status["state"] == "ready" and worker_status["active"] >= 1
)
critical["rag_worker"] = checks["rag_worker"]
```

payload 中复用同一个 `worker_status`，避免同一响应读取两次产生竞态快照。

- [ ] **Step 6: 运行 API 与全量测试并提交**

Run: `pytest -q intelligence/tests/test_workbench_api.py intelligence/tests/test_rag_worker.py`
Expected: all tests PASS.

Run: `env -u FORESIGHT_USERS_DIR -u FORESIGHT_USER -u SUBCONSCIOUS_VAULT -u AGENT_MEMORY_VAULT pytest -q`
Expected: all tests PASS.

Commit: `feat: gate Workbench startup on warm RAG worker`

### Task 5: 真实模型、CI 与部署验收

**Files:**
- Create: `docs/verification/workbench-rag-worker-prewarm-2026-07-16.md`
- Modify: `/Users/a77/.local/bin/start-finance-workbench` only if the existing environment lacks prewarm timeout configuration.

- [ ] **Step 1: 运行真实 BGE-m3 进程内复用探针**

Run a branch-code probe with two worker queries against
`/Users/a77/knowledge-base-private/.rag_index`.

Expected:

```text
returncode=0,0
model_load_count=1,1
second_query_seconds<20
state=ready
```

- [ ] **Step 2: 运行静态与产品验证**

Run: `ruff check scripts/rag_query_worker.py intelligence/services/rag_worker.py intelligence/services/kb_rag.py intelligence/api/app.py intelligence/tests/test_rag_worker.py intelligence/tests/test_workbench_api.py`
Expected: PASS.

Run frontend lint/typecheck/unit/build and Playwright from `intelligence/webapp`.
Expected: lint/typecheck/build PASS, 56 unit tests PASS, 15 Playwright tests PASS.

- [ ] **Step 3: 写验证报告并提交**

报告记录测试数量、首次/二次查询耗时、状态机、失败注入、PR/CI 和线上回放；不得记录 query 结果正文、密钥或路径外的用户数据。

Commit: `docs: verify RAG startup prewarm`

- [ ] **Step 4: 推送 ready PR 并等待两项 CI**

Run: `git push -u origin fix/rag-worker-import-context`

Create ready PR against `main`; wait for `registry-check` and `workbench-check` to pass before merge.

- [ ] **Step 5: 合并并创建版本化 runtime**

从 merged `origin/main` 创建新的 detached worktree；保留
`/Users/a77/.finance-runtime/finance-workspace-05e4fd1d356d` 作为回滚点。

- [ ] **Step 6: 原子切换并等待同步预热完成**

停止旧 LaunchAgent、切换 `/Users/a77/finance-workspace-runtime` 软链、重新 bootstrap；
readiness 等待上限至少 120 秒。失败时恢复旧软链并重启旧服务。

- [ ] **Step 7: 完成三类真实回放**

Expected:

1. `中际旭创怎么看`：owner=`stock-deep-dive`，不含 `company_master` 冷启动超时；
2. 同会话 `这个逻辑的边际变化呢`：继承 stock owner、subject 与证据上下文；
3. `光模块怎么看`：owner=`theme-research`，输出包含定义、产业链、公司证据、反证与验证条件；
4. 回放后 readiness：`rag.state=ready`、`active=1`、`model_load_count=1`。

- [ ] **Step 8: 完成目标审计与记忆回写**

逐项对照原 P0/P1/P2 清单、规格、CI、runtime 和三类回放；仅在所有证据成立后更新项目交接记录并把持久目标标记 complete。
