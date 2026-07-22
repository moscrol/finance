# Workbench Overview Data Root Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让隔离 Workbench runtime 的 Overview 始终从显式 `FINANCE_WS` 数据根读取 DuckDB 与 Daily Agent，而不是从代码 worktree 读取旧样例。

**Architecture:** 保持 `create_app()` 为 composition root，由 `default_paths()` 解析数据根并注入 Overview 服务。`build_workbench_overview()` 只消费显式 finance root；公共 API 测试用不同 code/data 目录锁定契约。

**Tech Stack:** FastAPI、DuckDB、pytest、TestClient

---

### Task 1: 公共 API 回归测试

**Files:**
- Modify: `intelligence/tests/test_workbench_api.py`

- [ ] **Step 1: 写隔离 code/data root 的失败测试**

测试创建 `code_root` 和 `finance_root`，前者仅放 `2026-07-01-daily-agent.json`，后者放可读取的市场 DB 与 `2026-07-20-daily-agent.json`；设置 `FINANCE_WS=finance_root` 后调用：

```python
with TestClient(app_module.create_app(repo_root=code_root)) as probe:
    overview = probe.get("/api/workbench/overview").json()

assert overview["as_of_date"] == "2026-07-21"
assert overview["signal_date"] == "2026-07-20"
assert overview["data_status"][0]["status"] != "missing"
assert "2026-07-01" not in str(overview["agent_artifact"])
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `python3 -m pytest -q intelligence/tests/test_workbench_api.py -k overview_uses_configured_finance_root`

Expected: FAIL；旧实现返回 `as_of_date=None`、`signal_date=2026-07-01`。

### Task 2: 显式注入 finance root

**Files:**
- Modify: `intelligence/api/app.py:1094-1128,1248-1257,1888-1890`
- Modify: `intelligence/services/workbench_overview.py:834-841,901,1004`

- [ ] **Step 1: 收紧 Overview 服务参数语义**

将服务的首参数从模糊的 `repo_root` 改为 `finance_root`，所有 DB、exports、forecast ledger 和 learning feedback 路径都从该 root 构造：

```python
def build_workbench_overview(finance_root: str | Path, knowledge_wiki: str | Path) -> dict[str, object]:
    root = Path(finance_root)
```

- [ ] **Step 2: 在 composition root 注入数据根**

```python
runtime_paths = default_paths()
app.state.finance_root = runtime_paths.finance_root

@app.get("/api/workbench/overview")
def workbench_overview() -> dict[str, object]:
    return build_workbench_overview(
        runtime_paths.finance_root,
        runtime_paths.knowledge_wiki,
    )
```

health 的 runtime payload 增加：

```python
"finance_root": str(runtime_paths.finance_root.resolve())
```

- [ ] **Step 3: 运行回归测试确认 GREEN**

Run: `python3 -m pytest -q intelligence/tests/test_workbench_api.py -k 'overview or health'`

Expected: 新回归和既有 Overview/health 测试全部 PASS。

- [ ] **Step 4: 提交最小修复**

```bash
git add intelligence/api/app.py intelligence/services/workbench_overview.py intelligence/tests/test_workbench_api.py
git commit -m "fix: read overview from configured finance root"
```

### Task 3: 隔离 runtime 与全量验证

**Files:**
- Modify: `docs/verification/task-fulfillment-seam-final-2026-07-22.md`

- [ ] **Step 1: 运行相关与全量测试**

Run: `python3 -m pytest -q tests/test_workbench_overview.py intelligence/tests/test_workbench_api.py intelligence/tests/test_runtime_provenance.py`

Expected: 全部 PASS。

Run: `python3 -m pytest -q intelligence/tests`

Expected: 本轮核心测试无新增失败；已有 subconscious/userspace 环境失败单独列明。

- [ ] **Step 2: 重启隔离 8795 并重跑原始 curl**

```bash
curl -sS http://127.0.0.1:8795/api/workbench/overview | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["as_of_date"] == "2026-07-21"; assert d["signal_date"] >= "2026-07-20"'
```

Expected: exit 0；数据库状态不为 missing，artifact 来自 `FINANCE_WS`。

- [ ] **Step 3: 更新验证记录并提交**

在验证文档记录根因、修复 commit、curl 结果和 health 的双根身份，然后：

```bash
git add docs/verification/task-fulfillment-seam-final-2026-07-22.md
git commit -m "docs: verify overview data root fix"
```

