# Unified Evidence Capability Registry 设计

日期：2026-07-21  
基线：`fix/agent-architecture-p13@3be221c5`  
目标分支：`fix/unified-evidence-capabilities`

## 1. 问题与证据

当前 P13 已经把 ownerless research 统一交给 `GenericResearchOwner`，并集成了
market-technical、P1-B agent loop、QueryLedger、EvidenceAtom、Grounded Presenter
和 fail-closed 出口。但真实问题“你觉得目前市场的主线是什么”仍失败，根因不是
缺数据：本地 DuckDB 已有 2026-07-20 的 `fact_market_daily`、
`fact_mainline_theme_daily`、`fact_mainline_sector_daily` 和 D4 主线块。

本次失败 run `run_20260721_101125_275027` 证明了三个接缝：

1. controller 识别为 `general_finance_qa`，Generic Owner 的能力面没有 D4/结构化
   主线 provider，只能选择 Web/News/KB；LLM 将查询改写为 2025 年历史热点。
2. Generic Owner 与 Ask 的 D-block 管线各自有一套注册/执行入口；已有
   `evidence_registry.REGISTRY` 没有穿透到 Generic Owner。
3. completion 允许 supporting evidence fulfilled 掩盖 direct assessment missing；
   `prepare_existing_answer()` 因 factual grounding fulfilled 继续启动自然语言合成，
   7 次 LLM 调用耗时 88.6 秒后仍以 completed + 降级短答结束。

## 2. 目标

- 同一个 Evidence Capability Registry 同时服务固定 Ask、Generic Owner 和 retrieval
  planner，不新增第三套数据源实现。
- 题目先声明“需要哪些证据能力”，代码从白名单 provider 中确定性执行；LLM 只能
  排序、改写查询和补充假设，不能删除必需能力或把过期来源当实时来源。
- “当前主线/市场结构”默认先取同日结构化市场总览 + D4，成功后不再做无关 Web
  搜索；正常路径在 20–30 秒内完成。
- required direct assessment 缺失时，业务状态必须为 `partial/gap`，不得进入自由合成，
  也不得显示为 completed。
- 结构化数据具备足够事实时，即使 LLM planner/合成失败，也由确定性业务 renderer
  生成直接判断、证据依据、反证和下一验证，而不是泛化“相关来源不足”。
- 保留所有已有硬边界：EvidenceAtom、过期证据、QueryLedger、ProviderTrace、预算、
  Grounded verifier、market-technical fail-closed 和专项 owner 兼容性。

## 3. 非目标

- 不新增“市场主线”专用答案路由，不扩张 route table 题型枚举来覆盖长尾。
- 不让 LLM 直接执行 SQL、任意文件访问或新增工具；所有 provider 仍由代码注册和
  capability whitelist 管控。
- 不切换 main 或 canonical 8792；先在从 P13 构建的隔离 runtime 验证。
- 不把 D4 的 L4 市场信号升级成公司基本面或公告事实。

## 4. 设计

### 4.1 单一能力注册与适配

保留 `intelligence/services/evidence_registry.py` 作为 provider 元数据 SSOT，扩展
provider 描述以表达 capability、freshness、cost 和可用的业务问题族。现有
`ask_planner.DataBlockProvider` 继续负责 D-block 的 `applies/collect`；新增一个
适配层，把同一 provider 包装为 `research_tool_registry.ToolSpec`，Generic Owner
和固定 Ask 调用同一个 `collect`，不复制 D4/市场数据查询逻辑。

适配器必须输出同一格式的 `AgentEvidence`、`Citation` 和 `ProviderTrace`：
`parent_id=run_id`、`step_id` 唯一、`source_trade_date` 和 freshness 明确。已由
固定管线预取的 provider 从 agent 可选工具中禁用，沿用现有 QueryLedger 去重。

### 4.2 证据需求而非题型路由

在 `ResearchTaskContract` 增加可审计的 evidence requirements 投影：

- `mainline_current`：`M`（同日市场总览）+ `D4`（主线结构）为 mandatory，
  `D0/D6/W7` 可按缺口补充；
- `market_forecast`：保留现有 `market_data` mandatory，并允许 D4 作为结构证据；
- general long-tail：由规则/LLM planner 选择 provider，但若问题含“当前/最新/主线/
  盘面/成交/涨停”等时效词，必须加入同日市场能力，不得只走 Web。

这不是新增意图路由：controller 仍只给粗粒度 question type，evidence planner
决定需要的证据产品；规则安全网负责强制 mandatory provider，LLM 不能删掉它们。

### 4.3 数据优先的 Generic Owner 循环

Generic Owner 执行顺序调整为：

1. 读取当前日期、数据库最新交易日和 registry capability 摘要；
2. 确定性预取 mandatory provider（主线问题先取 M+D4）；
3. 用同一 `ResearchState` 把预取事实、时效、假设和 gap 交给 agent；
4. Agent 只在 mandatory evidence 已成功后，按预算选择补充 provider；
5. 若 mandatory provider 已足以生成业务判断，直接结束检索，不再调用无关新闻；
6. completion 按 required outputs 和 evidence requirements 逐项判断；
7. 仅在业务完成且 grounding 通过时调用一次自然语言合成，否则走确定性业务化
   partial/gap renderer。

Agent system prompt 必须注入 `today`、`latest_data_date`、已取 provider 和未满足
的 evidence requirements，避免把当前问题改写成 2025 年历史问题。

### 4.4 完成状态与展示状态分离

新增 `business_status` 投影（`complete` / `partial` / `gap` / `blocked`），与 API
transport status 分开。只有以下条件全部满足才允许 `business_status=complete`：

- 所有 required outputs fulfilled；
- `direct_assessment` 有非空业务判断，且至少绑定一个与问题匹配的证据集合；
- mandatory evidence 的 freshness 与问题时间窗口一致；
- Grounded verifier 通过。

`factual_grounding=fulfilled` 不能单独放行合成。`partial/gap` 必须展示“已知事实、
当前判断（若有）、未知/缺口、下一验证”，不能显示“已完成”或启动无意义修订轮。

## 5. 以当前主线问题为例

正确输出应基于同日 D4，而不是全年 Web 回顾：当前数据支持“电力是当日增量启动
候选（涨幅、边际量、涨停扩散同步）”；医药属于分歧/存量修复；半导体与 AI 算力
是近 20 日持续方向但当日走弱，不能继续写成无条件主线。该结论仍标记为 L4
市场信号，不等同产业基本面兑现，并给出下一交易日验证条件。

## 6. 错误处理与预算

- M/D4 取数失败：保留明确 market-data gap；不得用旧 Web 文章替代同日盘面事实。
- D4 成功、LLM 失败：直接使用确定性 mainline renderer；不再启动第二次自由合成。
- planner 失败：规则 capability plan；不得退化为“只搜 Web”。
- QueryLedger 继续按 provider + normalized query + as-of 去重。
- mandatory prefetch 和 agent loop 共用同一 deadline；预取成功后禁用同名 agent tool，
  防止重复计费。标准题保留至少 20 秒 synthesis reserve，但合成最多一次。

## 7. 验收

### 单元/集成

- current-mainline fixture 必须断言：M+D4 被调用、同日日期传递、Web 不先行、D4
  provider trace 与 Citation 存在；D4 缺失时输出 typed gap。
- Generic Owner 的 completion fixture：supporting evidence 有但 direct assessment
  缺失时不能 `complete`，不能调用 synthesis。
- planner 输出 2025 等过期查询时，代码注入 current date 并拒绝越过 freshness gate。
- 数据成功后最多一次 synthesis；无关新闻查询为 0。

### 真实隔离 E2E

在新隔离端口运行：

`你觉得目前市场的主线是什么，给我你的判断依据`

必须出现同日主线、判断依据、反证/边界和下一验证；不得出现“全年回顾线索不足”、
不得把 2025 年文章当当前依据，且 `business_status=complete` 或在数据不足时明确
`partial/gap`，不能再出现“completed + degraded”伪完成组合。

## 8. 回滚

保留 `generic evidence capabilities` feature flag。关闭时回到 P13 的 Generic Owner
和现有 Ask 数据块路径；不删除旧 provider、QueryLedger 或 grounded verifier。新 runtime
验证失败只销毁候选 runtime，不切换 8792。
