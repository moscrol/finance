# Nightly Release Paths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 夜跑使用固定代码快照时，同步日志、质检 JSON 和增量备份仍落既有数据根。

**Architecture:** 已获总控授权，沿用 `FINANCE_DATA_ROOT → FINANCE_WS → ROOT`，不新增配置系统、不改 `local` 计划。代码路径继续来自脚本位置；运行产物来自数据根，备份保留 `DUCKDB_SNAPSHOT_OUT_ROOT` 和 `--out-root` 的显式覆盖。

**Tech Stack:** Python 3.12、pytest、临时目录中的小 DuckDB；验证不联网、不调用模型、不接触生产库。

---

### Task 1: 同步产物回归与最小修复

**Files:** `skills/daily-full-review/scripts/run_review_sync.py`、`tests/test_review_sync_data_paths.py`。

- [x] 复制同步入口到测试的临时代码树，以 `main()` 执行 `--only db-lock --skip-preflight --plan local`；只在 subprocess 边界用假子进程模拟质检文件写出，拒绝真实采集/写库。验收实际文件而非仅检查常量：

```python
assert module.main() == 0
assert (data / "skills/daily-full-review/state/runlog.md").is_file()
assert (data / "skills/daily-full-review/state/quality-2026-10-02.json").is_file()
assert tree_bytes(code) == before
```

- [x] 先运行新测试，确认旧版向临时代码树写日志/质检文件而失败。
- [x] 将现有 `_DATA_ROOT` 声明上移至路径初始化处，复用它构建 `STATE_DIR`/`RUNLOG`；质检使用同一 `STATE_DIR`。

```python
_DATA_ROOT = Path(os.environ.get("FINANCE_DATA_ROOT") or os.environ.get("FINANCE_WS") or ROOT).expanduser()
STATE_DIR = _DATA_ROOT / "skills/daily-full-review/state"
RUNLOG = STATE_DIR / "runlog.md"
```

- [x] 覆盖两个变量的优先级、只设置 FINANCE_WS、无变量的旧行为，以及质量门失败仍落失败日志。

### Task 2: 增量备份数据根

**Files:** `skills/daily-full-review/scripts/export_increment.py`、`tests/test_review_sync_data_paths.py`。

- [x] 用临时代码树中的真实导出 CLI 读取临时小 DuckDB，断言 tar.gz 落数据根且 manifest 指向显式 staging 库；先运行得到旧路径红证据。
- [x] 默认库和输出采用既有数据根，保留显式库/输出覆盖：

```python
DATA_ROOT = Path(os.environ.get("FINANCE_DATA_ROOT") or os.environ.get("FINANCE_WS") or REPO_ROOT).expanduser()
DEFAULT_DB = Path(os.environ.get("MARKET_FEATURE_STORE_DB") or DATA_ROOT / "db/market_feature_store.duckdb").expanduser()
DEFAULT_OUT = Path(os.environ.get("DUCKDB_SNAPSHOT_OUT_ROOT") or DATA_ROOT / "db/snapshots").expanduser()
```

- [x] 导出 CLI 回归覆盖数据根优先级、显式输出、无环境变量兼容路径。运行同步/生成段既有相关测试，保持备份失败只告警、质量门失败停止发布。

### Task 3: 验证、依赖说明与交接

- [x] 用 `/Users/a77/.codex/worktrees/9020/finance-workspace-private/.venv-workbench/bin/python -m pytest` 跑新测试与相关定向测试；ruff 验改动文件，记录红/绿仓外收据。
- [ ] 总控提供经过独立环境验证的可选 macOS 夜跑锁；保留 dev/consumer 锁，排除与锁定 httpx 冲突、且 local 计划未用的 mootdx。
- [ ] 记录发现的路径、已核对的路径和启动副作用；更新本分支交接，仅 pathspec 提交，交总控审查。UI 树保持 `1be7500c`，本子任务不推送、合并、部署。
