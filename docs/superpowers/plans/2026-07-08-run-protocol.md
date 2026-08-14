# Run/Artifact/Trace 协议 v1（Agent Workbench 第 0 步）

状态：v1 已实现（`intelligence/services/run_store.py`），golden 样例见
`intelligence/tests/fixtures/golden_run/`，协议回归测试见
`intelligence/tests/test_run_store.py`。

## 核心概念

```
Session (会话)  1 ── n  Run (一次用户请求)  1 ── n  Artifact / TraceStep
```

- **Run**：一次用户请求 = 一个 run 目录，落点
  `intelligence/users/<id>/runs/<run_id>/`（用户态，不入 git；已登记台账地图）。
- **Session**：多轮追问共享上下文的会话（`ask_chat.py` 已是此模型），run 通过
  `session_id` 归组；追问派生用 `parent_run_id`，两者正交。
- **Artifact**：run 目录内的产物文件（answer.md / summary.json / html…），带
  sha256 + bytes 校验，UI 据 `renderer` 决定渲染方式。
- **Trace**：`trace.jsonl` append-only 步骤流水，边跑边写——刷新/崩溃后凭
  run_id 重放，这是 Agent 可观测性的最小形态。

## run.json（schema_version = 1）

| 字段 | 类型 | 说明 |
|---|---|---|
| run_id | str | `run_YYYYMMDD_HHMMSS_ffffff` |
| user | str | users/ 命名空间 id |
| question | str | 用户原话（写入前过 redact 脱敏） |
| task_type | str | ask / theme / daily / foresight / stock_research…（开放注册表） |
| status | enum | queued / running / completed / failed / cancelled |
| session_id | str? | 会话归组 |
| parent_run_id | str? | 追问派生（P0 即有，P1 追问卡片直接用） |
| created_at / finished_at | ISO8601 | 本地时区 |
| source_date / duckdb_cutoff | date? | 数据截止口径 |
| kb_commit | str? | 知识库 commit，可复现锚点 |
| manifest_ref | path? | daily 类任务**引用**现有 forecast-review-ledger manifest，不复制字段 |
| degrades | list[str] | 数据源降级一等字段（如 `ftshare_unavailable`） |
| error | str? | failed 时的结构化错误（脱敏） |
| artifacts | list | 见下 |

## Artifact 条目

`artifact_id / path（相对 run 目录）/ renderer（markdown|html|json|table|image）/
title / sha256 / bytes / previewable / downloadable`。

## Trace step（trace.jsonl 每行）

`step_id / name / status（running|completed|failed|skipped）/ started_at /
finished_at / input_summary / output_summary / warnings[]`，可选 `tokens`、
`retrieval`（检索类 step 的命中摘要——P2 检索 dashboard 从这里长出来）。

## 纪律

1. **单写入者**：run 目录只有 `run_store.py` 写（同台账地图其它台账）。
2. **摘要必脱敏**：所有 UI 可见字段写入前过 `redact()`；trace 是未来可分享产物。
3. **CLI 直跑也产 run**：落盘逻辑放 service 层而非 API 层，避免台账分叉（第 1 步接线时执行）。
4. **schema 演进**：改字段必须 bump `SCHEMA_VERSION` 并先让 golden fixture 测试通过。

## 设计取舍（教学）

- **文件分区 vs SQLite**：run 量级小、需 git 审计友好与 jq 直读，选 JSON/JSONL；
  全局检索属于「投影」，以后在其上建索引即可，canonical 落点不动。这与数仓
  「事实表 + 物化视图」同一思想。
- **trace 选 JSONL 而非最终 trace.json**：支持长任务边跑边写、断点重放；等价于
  结构化日志/tracing span，面试可讲 Agent observability。
- **manifest 引用而非复制**：同一事实只有一个写入位置（single source of truth），
  Run 协议是 manifest 的泛化，daily 任务通过 `manifest_ref` 指向既有冻结文件。
