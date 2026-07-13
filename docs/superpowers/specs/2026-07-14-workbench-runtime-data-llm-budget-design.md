# Workbench 运行时数据根、内置模型与 60 秒预算接线设计

日期：2026-07-14
状态：待用户书面复核
分支：`fix/workbench-query-retrieval-latency`
前置设计：`2026-07-13-workbench-query-retrieval-latency-design.md`
用户选择：方案 A（DuckDB 主源 + 内置 GLM + 端到端预算分区）

## 1. 背景与真实运行证据

上一阶段已经修复通用市场问题被整句伪装成题材、公司锚点被题材别名覆盖、市场结构回答套用公司模板，以及无证据 UI 提示使用公司措辞等问题。自动化门禁和无模型临时运行均已通过。

使用正式 Workbench 的同一套安全启动链重新验收后，确认产品能力与临时运行配置之间仍有三处断点：

1. canonical `8792` 的 `/api/llm/config` 返回 `built_in_ready=true`，provider 为 `zhipu`，model 为 `glm-5.2`；但真实回答报告仍可能为 `llm.used=false`。模型“配置就绪”不等于回答链“实际调用”。
2. canonical DuckDB `db/market_feature_store.duckdb` 约 3.0GB，核心事实表截止 `2026-07-13`；隔离分支却从代码 worktree 读取到截止 `2026-07-01` 的题材候选快照。说明代码根、研究数据根和用户运行根仍被部分模块混用。
3. 个股深挖在 60 秒边界产生 `Skill theme-research 执行超时` 与 `executor_timeout`，最终 run 为 `failed`，报告停留在 `streaming`。父级 deadline、Skill timeout、检索 timeout 和模型预留时间没有形成一个可证明闭合的预算契约。

此外，readiness 只把独立 `market_snapshot/` 目录当作关键盘面输入。即使 DuckDB 健康且已更新到最新交易日，仍返回 `503 not_ready`。这会把“某项 CAR/快照能力不可用”错误扩大为“整个工作台未就绪”。

## 2. 目标

本轮要同时保证数据正确、模型真实参与和终态可靠：

- 所有 Workbench 研究消费者从同一个显式运行时上下文取得代码根、研究数据根、DuckDB、exports、market snapshot 和用户目录。
- DuckDB 成为结构化盘面的 canonical 主源；exports 是 DuckDB 派生产物，独立 market snapshot 只服务确实需要该契约的能力。
- 内置 GLM 就绪且预算足够时，Base Finance、题材研究和个股深挖都获得一次模型合成机会；报告能区分“配置就绪、已尝试、实际使用、回退原因”。
- 端到端仍以 60 秒为硬上限；个股深挖不得因专项 Skill 或模型超时留下 `failed + streaming report`。
- 数据截止日必须来自实际使用的数据源。旧 export 不得覆盖更新的 DuckDB 截止日，也不得被写成当前盘面事实。
- 不读取、不打印、不落盘内置模型密钥；继续由 Keychain/LaunchAgent 注入。

## 3. 非目标

- 不把 DuckDB 文件提交 Git，不修改数据生产流水线或 7 月 13 日已有事实表。
- 不在本轮生成一套新的 `market_snapshot/` 历史面板；只修正消费者与 readiness 的能力边界。
- 不提高 60 秒 SLA 来掩盖检索或模型耗时。
- 不引入常驻向量服务、消息队列或多 worker 部署。
- 不改变 GLM provider、模型版本、Keychain service 名称或 BYOK 安全策略。
- 不合并 `main`、不切换 canonical `8792` runtime，除非用户在验收后另行确认。

## 4. 方案比较

### 4.1 采用：统一运行时输入 + DuckDB 主源 + 模型预算预留

构建一个显式的运行时研究输入对象，由 API 根节点创建，并沿 conversation orchestrator、owner、Ask 和 readiness 传递。结构化盘面优先读 DuckDB；需要候选文档的模块读同一数据根下的 exports，并与 DuckDB cutoff 做一致性检查。检索阶段必须给内置 GLM 和终态提交预留时间。

优点是从根上消除模块级 `REPO_ROOT` 回落、数据时点漂移和“子模块各有一套 timeout”。代价是要修改多个边界接口，但这些接口可由类型与测试约束，长期维护成本最低。

### 4.2 未采用：只补环境变量或软链

给隔离进程增加更多环境变量、把旧 worktree 的 exports 软链到主仓，改动最少。但模块仍可绕过运行上下文读取源码旁路径；换 worktree、测试 fixture 或 canonical runtime 后问题会复发。

### 4.3 未采用：只把 deadline 提高到 90–120 秒

可以降低表面超时率，却不能保证模型真正参与，也不能解决旧 export 覆盖新 DuckDB 和失败 run 留下 streaming report。它把架构问题转成等待时间，因此不采用。

## 5. 运行时研究输入契约

新增或扩展一个不可变的 `RuntimeResearchInputs`（最终命名以现有代码风格为准）：

```python
@dataclass(frozen=True)
class RuntimeResearchInputs:
    code_root: Path
    data_root: Path
    market_db_path: Path
    exports_dir: Path
    market_snapshot_dir: Path
    users_root: Path
```

边界定义：

- `code_root`：当前运行版本，仅用于导入代码和读取随代码发布的静态配置。
- `data_root`：canonical 研究数据仓；由 `WORKBENCH_REPO_ROOT` / `FINANCE_WS` 解析。
- `market_db_path`：`data_root/db/market_feature_store.duckdb`。
- `exports_dir`：`data_root/market_feature_store/exports`。
- `market_snapshot_dir`：显式 `MARKET_SNAPSHOT_DIR`，否则为 `data_root/market_snapshot`。
- `users_root`：会话、run 和内存配置所属用户根，与研究数据根分离。

硬约束：业务服务不得在已经收到该对象后再次通过模块级 `REPO_ROOT`、`__file__` 或当前工作目录猜测研究数据位置。

这属于 dependency injection（依赖注入）：依赖由入口显式传入，而不是模块自己寻找。可复用到多环境部署、测试 fixture 和多租户数据隔离；系统设计面试也常用它解释“如何避免隐藏全局状态”。

## 6. 市场数据源与时点规则

### 6.1 数据源优先级

1. DuckDB：当前结构化市场事实、交易日历和 `duckdb_cutoff` 的主源。
2. exports：由 DuckDB 生成的题材候选、daily review、daily agent 等派生产物；只在对应业务模块需要文档结构时读取。
3. market snapshot：CAR、前向收益面板或明确依赖 snapshot contract 的能力；不再代表全部市场数据能力。

### 6.2 新鲜度与冲突处理

- 每轮先只读获取 DuckDB cutoff，再读取选中的 export `trade_date`。
- export 日期等于 DuckDB cutoff：可作为当前派生盘面使用。
- export 早于 DuckDB cutoff：标记 `stale_derivative`；可以作为历史背景，但不得覆盖当前数据日期或进入当前事实结论。
- export 晚于 DuckDB cutoff：标记时点冲突并 fail-closed，不把它当作已验证当前事实。
- 没有 export 但 DuckDB 健康：仍可回答通用市场结构和 DuckDB 可支持的问题；只降级题材候选文档能力。
- 没有 DuckDB 但存在通过 contract 校验的 snapshot/export：进入兼容降级，并明确实际数据源与截止日。

### 6.3 假设问法边界

市场方法论问题不因 DuckDB 可用就强行声称假设场景已发生。DuckDB 用于验证用户描述的条件或提供当前上下文；如果条件无法从表中对应，回答必须保持条件化表达。

## 7. Readiness 能力化

readiness 从“单目录总闸门”改成“核心服务 + 能力矩阵”：

- 核心服务：代码根、用户 run store 可写、知识库核心路径可读。
- `market_data`：DuckDB 健康且能读取 cutoff，或存在通过契约校验的兼容市场输入。
- `market_snapshot`：单独报告，用于 CAR/前向面板，不再在 DuckDB 健康时令整个服务 503。
- `market_exports`：报告最新 export 日期以及相对 DuckDB 的 fresh/stale/conflict 状态。
- `llm`：只报告配置 readiness；是否实际调用由每个 run 的 trace/report 记录。

当 DuckDB 健康、核心服务可用但 snapshot 缺失时，整体可为 `ready`，同时在 `capabilities.market_snapshot` 中标记 unavailable。只有请求明确需要 snapshot-only 能力时才对该次请求降级。

## 8. 内置 GLM 调用契约

所有路径仍先形成 `Evidence -> Claim -> AnswerSpec`，然后按预算决定是否调用内置 GLM：

```text
结构化数据/检索
  -> 证据门禁
  -> AnswerSpec
  -> 内置 GLM 合成（就绪且预算足够）
  -> 输出质检
  -> 通过则采用模型答案
  -> 失败/超时则确定性 Presenter 回退
```

Base Finance 的快速路径也必须经过同一合成决策，不能因为早返回而永久 `llm.used=false`。但模型不是事实源：它只组织已经通过门禁的证据和条件，不得补造 DuckDB 中不存在的数值。

每个 run 记录：

- `llm_configured`：服务端内置模型是否就绪；
- `llm_attempted`：本轮是否实际发起调用；
- `llm_used`：最终答案是否采用模型输出；
- `provider` / `model`：非敏感标识；
- `fallback_reason`：预算不足、provider timeout、质检拒绝或未配置。

这些字段进入 trace/report，不进入主正文；密钥、请求头和模型原始错误体禁止落盘。

## 9. 60 秒预算分区与终态

使用同一个 `ExecutionBudget` 做 deadline propagation（截止时间传递），建议软上限如下：

| 阶段 | 软上限 | 规则 |
|---|---:|---|
| 理解、路由、本地路径解析 | 5 秒 | 主要是确定性逻辑，正常应远低于上限 |
| DuckDB、BM25、图谱与证据门禁 | 25 秒 | 先便宜、确定的召回 |
| 可选一次 dense/Hybrid 补召回 | 10 秒 | 只有明确 subject 且预算允许 |
| 内置 GLM 合成与质检 | 15–20 秒 | 深挖路径必须预留，不允许被检索吃光 |
| 原子提交终态与报告 | 5 秒 | 任何路径都不得占用 |

软上限不是各自可叠加的独立 timeout，而是共享 60 秒 deadline 下的最大允许值。市场方法论没有 dense 召回时，可把未使用时间让给模型；个股深挖则必须在进入专项 Skill 前冻结至少 20 秒的“合成 + 提交”储备。

终态规则：

- 专项 Skill 在自己的 allowance 用尽时返回部分结构化结果和降级原因，不抛出覆盖全局结果的 timeout。
- 距 deadline 5 秒时禁止开始新检索或模型调用。
- 模型超时后立即使用已经构建的 AnswerSpec。
- run 必须原子地落为 `completed` 或 `completed + degrades`；只有无法构建任何安全回答的内部错误才为 `failed`。
- 报告状态必须与 run 终态一致，禁止 `run=failed` 而 report 永久 `streaming`。
- smoke 客户端在收到终态后必须仍有时间读取 report；服务端不能在客户端 60 秒窗口最后一刻才提交。

## 10. 代码边界

预计涉及：

- `intelligence/api/app.py`：创建统一运行时输入、能力化 readiness、向 orchestrator 注入依赖。
- `intelligence/paths.py` 或小型新模块：集中解析并校验代码根/数据根/用户根。
- `intelligence/services/conversation_orchestrator.py`：传递数据输入和共享预算，保证终态一致。
- `intelligence/workbench_skills/research_owner.py`：显式使用 market DB 与 exports，限制专项 Skill allowance。
- `intelligence/services/ask.py`：移除业务链的隐式数据根回落，统一 cutoff/exports 冲突处理，让 Base Finance 进入模型合成决策。
- `intelligence/services/llm_refine.py` / LLM settings：补充 attempted/used/fallback 遥测，不改密钥来源。
- run/report 结构和对应前端 Inspector：展示非敏感数据源、截止日与模型使用状态。
- 单元、集成、smoke 和真实 UI 回归。

最终文件列表以实施计划中的调用图和测试定位为准，不做无关重构。

## 11. 测试策略

### 11.1 路径与数据时点

- 代码 worktree 只有旧 export、data root 有新 export 和 DuckDB 时，必须使用 data root。
- DuckDB cutoff 为 `2026-07-13`、export 为 `2026-07-01` 时，整体数据日期仍为 `2026-07-13`，旧 export 标记 stale 且不进入当前事实。
- DuckDB 可用、market snapshot 缺失时，readiness 整体 ready，但 snapshot-only capability unavailable。
- 测试 fixture 显式传入 data root 后，不读取开发机真实仓库。

### 11.2 模型参与与回退

- 内置 GLM ready、预算足够：Base Finance 和个股深挖均记录 `attempted=true`；通过质检时 `used=true`。
- provider 超时或输出被质检拒绝：60 秒内使用 AnswerSpec 回退，记录明确 fallback reason。
- 未配置模型：保持确定性回答，不出现空白或失败 run。
- 日志、SSE、report、artifact 和 smoke 证据均通过 secret scan。

### 11.3 预算与终态

- 专项 Skill 超时后仍产生 degraded 完整回答与一致 report。
- 模拟检索耗尽 allowance，验证不会侵占 20 秒合成/提交储备。
- 模拟模型超过 allowance，验证不晚于 deadline 前 5 秒进入确定性提交。
- 并发两个请求时，executor 不因一个超时任务占满 worker。
- smoke 在 65 秒客户端窗口内完成 report 拉取；目标服务端终态不超过 60 秒。

### 11.4 回归

- 公司 + 题材别名仍保持公司 anchor。
- 市场结构问题不再出现题材/公司模板污染。
- 个股深挖、连续追问、新对话 owner 清空、无模型无证据回退继续通过。
- 前端五阶段状态和中立无证据提示继续正确。

## 12. 真实验收标准

隔离分支通过正式同源安全启动链启动，但使用独立临时用户目录；不修改 canonical `8792`。

至少验证：

1. `/api/llm/config` 显示 built-in GLM ready，不暴露 key。
2. readiness 显示 DuckDB cutoff `2026-07-13` 或运行时最新交易日，snapshot 缺失只影响对应 capability。
3. 市场背离问句在 60 秒内完成，route 为 `market_pattern`，模型实际参与或给出明确、可解释的模型回退原因。
4. `深挖英维克，它在液冷产业链的位置` 保持公司 anchor，在 60 秒内得到 completed/degraded 完整回答；不得出现 `executor_timeout` 或 streaming report 残留。
5. 输出数据日期不再退回 `2026-07-01`；没有无关题材引用，没有公司化无证据提示。
6. 自动测试、类型检查、生产构建、secret scan 和真实 UI 截图全部通过。

## 13. 风险与回滚

- DuckDB 只读连接可能受写入任务占锁影响：连接失败时快速降级到已校验 export/snapshot，不重试到耗尽 deadline。
- GLM 响应时间波动：模型始终是可回退的表达层，不阻塞确定性终态。
- readiness 语义变化可能影响监控：保留旧字段，并新增 capability 结构；先补兼容测试再调整关键性。
- 数据根显式化涉及多个调用边界：通过 fixture 泄漏测试和调用图逐层迁移，禁止一次性删除所有兼容参数。

回滚只需恢复旧的路径解析/readiness/预算接线；DuckDB、Keychain、用户数据和 canonical runtime 均不发生迁移。
