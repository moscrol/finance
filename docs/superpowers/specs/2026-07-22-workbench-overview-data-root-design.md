# Workbench Overview 数据根分离设计

## 背景与失败

隔离 runtime 在代码 worktree 启动，并通过 `FINANCE_WS` 读取私有金融数据。对话 Orchestrator 已支持代码根与数据根分离，但 `GET /api/workbench/overview` 仍把 `create_app()` 的代码 `root` 同时当作 DuckDB 和 exports 根目录。结果是 8795 找不到数据库，并从代码 worktree 中仅存的 `2026-07-01-daily-agent.json` 生成首页。

真实失败契约：当代码根和 `FINANCE_WS` 不同时，Overview 必须从 `FINANCE_WS` 返回最新市场日期和 Daily Agent 日期，不得返回代码 worktree 中的旧样例，也不得将数据库标成缺失。

## 方案选择

### 方案 A：在应用组装层显式注入 `finance_root`（采用）

`create_app()` 已通过 `default_paths()` 解析 `FINANCE_WS`。Overview endpoint 直接把 `runtime_paths.finance_root` 传给 `build_workbench_overview()`；服务参数改名为 `finance_root`，明确它只消费数据根。health runtime identity 同时公开 `finance_root`，便于现场核对。

优点：单一事实源、可测试、适合 clean worktree/detached runtime/容器；不会把部署布局泄漏进服务内部。代价：测试必须显式准备 `FINANCE_WS`。

### 方案 B：Overview 内部自行读取环境变量（不采用）

改动较少，但隐藏依赖使单元测试和调用方无法从接口判断数据来自哪里；服务也会同时承担路径解析和业务投影。

### 方案 C：给每个代码 worktree 建 DB/exports 软链（不采用）

无需改代码，但会让部署正确性依赖外部文件系统状态，容易读错私有数据或在切换 runtime 时产生漂移。

## 接口与数据流

```text
FINANCE_WS
  -> default_paths().finance_root
  -> create_app() /api/workbench/overview
  -> build_workbench_overview(finance_root, knowledge_wiki)
  -> finance_root/db/market_feature_store.duckdb
  -> finance_root/market_feature_store/exports/*-daily-agent.json
```

`repo_root` 继续只表示代码、静态资源和 runtime revision。`finance_root` 表示可写/私有数据与运营产物。二者相同时保持原行为；二者不同时不得回退到代码根。

## 错误处理

- `finance_root` 下数据库确实不存在时，继续返回现有 fail-closed `数据缺失`；不自动扫描其他目录。
- 数据库存在但部分表滞后时，继续使用现有逐数据域 freshness 状态。
- Daily Agent 缺失时只将知识事件标为 missing，不影响市场数据库的当前日期。

## 验收

公共 API 回归测试使用两个不同目录：代码根放置 7 月 1 日旧产物，数据根放置 7 月 21 日数据库和 7 月 20 日 Daily Agent。断言 Overview 返回 `as_of_date=2026-07-21`、`signal_date=2026-07-20`、数据库非 missing、artifact 不来自代码根。

隔离 8795 重启后，原 curl 复现必须由 RED 变 GREEN；`/api/health` 必须同时显示正确 `code_root` 与 `finance_root`。

