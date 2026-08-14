# Workbench RAG Worker 启动预热设计

**日期：** 2026-07-16  
**状态：** 已批准（用户选择推荐方案 A）  
**范围：** 修复常驻 BGE-m3 worker 的导入上下文和冷启动生命周期，不改变 P0.5 的阶段超时、线程收束或缓存契约。

## 1. 问题与证据

线上 `main@05e4fd1d` 回放“中际旭创怎么看”已正确路由到
`stock-deep-dive`，但 `company_master` 在 20 秒阶段门限后降级。真实探针确认：

- worker 原先因未建立 knowledge-base 的 Python import context，在导入
  `scripts.rag_freshness` 时退出；
- 修复 import context 后，BGE-m3 首次加载约 43.9 秒，第二次查询约 4.0 秒；
- lazy worker 的首个查询仍受 20 秒门限约束，超时会终止子进程，因此永远无法进入
  warm 状态。

这说明问题不是阶段阈值偏小，而是模型生命周期与请求预算冲突。

## 2. 选型

采用 **Workbench 进程启动时同步预热**：FastAPI 完成 startup 前建立 worker，并执行
一次不暴露给用户的最小 hybrid query。预热成功后才开放 8792。

未采用的方案：

- 后台预热：API 可更早监听，但会出现“端口可访问、研究能力尚不可用”的半热状态，
  还要治理预热查询与用户查询争抢同一 worker 锁；
- 独立 LaunchAgent RAG daemon：API 重启更快且生命周期隔离更彻底，但需要额外 IPC、
  鉴权、健康检查和进程部署，超出当前单机产品的必要复杂度；
- 提高 owner 阶段阈值：首次用户请求仍需等待约 44 秒，并掩盖生命周期缺陷，拒绝采用。

同步预热把一次性模型加载成本从“用户请求路径”移到“服务部署路径”。这是模型服务、
连接池和大索引服务常用的 warm-up gate 模式。

## 3. 架构与职责

### `rag_worker.py`

- `PersistentRagWorker.prewarm(argv, timeout)` 复用现有 JSONL 协议完成一次查询；
- 管理 `cold -> warming -> ready | failed` 状态、耗时、错误类型和模型加载次数；
- 预热与普通查询使用同一把锁，确保同一个子进程只处理一个请求；
- import context 修复属于 worker 启动前置条件：子进程 cwd 为 knowledge-base 根目录，
  `sys.path` 同时包含根目录和 `scripts/`。

### `kb_rag.py`

- 提供 `prewarm()` 门面，复用生产检索路径解析出的 Python、knowledge-base 根目录、
  index 目录和兼容 CLI 参数；
- 预热 query 使用低返回量，不把结果写入会话或 RAG 业务缓存；
- 仅当 `RAG_WORKER_ENABLED=1` 时执行；未启用时返回 disabled 状态。

### `app.py`

- 在 FastAPI startup 生命周期中同步调用 `kb_rag.prewarm()`；
- `RAG_WORKER_PREWARM_TIMEOUT` 默认 90 秒，独立于用户请求的 20 秒阶段预算；
- 预热失败不伪装成功：应用可以启动以暴露诊断端点，但 `/api/health/ready` 返回非 ready，
  `workers.rag` 给出 `failed` 与安全错误类型；
- 预热成功后 readiness 要求 `workers.rag.state=ready` 且 worker 进程存活。

## 4. 数据流

1. launchd 启动 Workbench。
2. FastAPI startup 调用 `kb_rag.prewarm()`。
3. worker 加载 `rag_index.py`、索引和 BGE-m3，执行最小 hybrid query。
4. 成功后状态转为 `ready`，FastAPI startup 完成并开放 8792。
5. 首个用户研究请求复用同一 worker，模型加载次数保持 1。
6. 查询硬超时会终止 worker并把状态退回 `cold/failed`；readiness 不再把死 worker报成 ready。

## 5. 失败语义

- import、模型或索引加载失败：记录错误类型，不记录路径、query、token 或 stderr 原文；
- 预热超过 90 秒：终止 worker，状态 `failed`，readiness 不通过；
- 用户查询超时：继续遵守 P0.5 的结构化 join、超预算结果丢弃、不缓存；
- RAG worker 失败后仍允许现有 CLI fallback 生成明确降级回答，但产品 readiness 保持失败，
  防止运维把降级能力误认成成熟可用状态。

## 6. 验收标准

- fake knowledge-base 覆盖 `scripts.x` 与同目录 fallback import；
- prewarm 状态覆盖 disabled、warming、ready、failed、timeout；
- startup 测试证明启用 worker 时先预热再 ready，失败时 readiness 非 200；
- 全量 Python、前端和 Playwright CI 通过；
- 真实 BGE-m3 连续两次查询 `model_load_count=1`，第二次小于 20 秒；
- 部署后 readiness 显示 RAG `ready/active=1/model_load_count=1`；
- “中际旭创怎么看”不再因 `company_master` 冷启动超时而 degraded；
- 同会话“这个逻辑的边际变化呢”继承 `stock-deep-dive` owner；
- “光模块怎么看”路由到 `theme-research`，并生成有证据边界的成熟输出。

## 7. 非目标

- 不拆分 `answer_query` 为五个独立检索服务；
- 不改变 owner 的 20 秒阶段门限；
- 不把 RAG 改为独立网络 daemon；
- 不修改模型、embedding、BM25 或 rerank 算法；
- 不把预热结果写入用户会话、证据台账或业务缓存。
