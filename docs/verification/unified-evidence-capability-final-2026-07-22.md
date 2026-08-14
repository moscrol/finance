# Unified Evidence Capability Registry：候选分支验收记录（2026-07-22）

## 验收对象

- 分支：`fix/unified-evidence-capabilities`
- 基线：`9edcf926`
- 运行方式：候选 worktree 代码，隔离用户目录，8794/8795/8796 临时端口；没有切换 canonical 8792。
- 模型：真实 `glm-5.2`；行情与知识库使用本机配置。

## 本轮完成的行为修复

1. `agent_research.block_lines_to_evidence` 支持结构化证据保真长度，并把日期区间取末日，避免窗口和报告时效倒退。
2. `finish(sufficient=false)` 在相关白名单能力尚未尝试时最多退回一次；空结果或错误结果仍可如实报 gap，不形成隐藏固定管线。
3. 当前主线、市场原因、预测和“双红+当前事实”分别使用声明的证据能力；结构化真值成功后不因模型措辞失败而伪报“没有答案”。
4. 预测 fallback 的反弹/下跌/失效三条条件情景回写 `ResearchState` hypothesis 支持边，completion 不再把已经绑定真值的条件情景判成 gap。
5. 结构化报告公共投影去重来源、去除内部证据 marker/层级 token/空括号；审计编号仍保留在内部 citation drawer。
6. Grounded 合成若漏掉预测题的一整个情景分支，只追加 AnswerSpec 中已绑定证据的确定性情景，不重写已有 LLM 表达。

## 自动化回归

针对性回归：`124 passed`。

全量 intelligence 非环境基线：`1874 passed, 51 deselected`。原先被排除的 51 项属于本机 userspace/subconscious 环境路径集合，不是本次改动覆盖范围。

## 真实隔离 E2E

### 四题首轮（8794）

验证了四类入口都能完成 transport，且公共扫描 `0 hits`：

- 主线：`run_20260722_000843_824574`
- 周跌原因：`run_20260722_000919_814118`
- 明日预测：`run_20260722_001011_453461`
- 双红混合题：`run_20260722_001131_859598`

首轮发现并修复：主线 completion 误报 partial、预测正文漏掉继续下跌/失效条件、报告来源重复和内部层级 token 泄漏。

### 四题复验（8795）

- 主线：`run_20260722_003918_588103`，`business_status=complete`；正文明确半导体+AI算力双主线、医药次主线；公共扫描 0 hits。
- 周跌原因：`run_20260722_004020_862409`，答案给出“风险偏好收缩/卖压集中释放”机制；宏观/外盘/资金的周内对齐证据仍缺，因此保持 `partial` 并明确 gap，不编造外因。
- 明日预测：`run_20260722_004102_904975`，正文同时给出低置信度基准、反弹情景、继续下跌情景和失效条件；此前的 `gap` 已由 hypothesis 绑定修复为 `business_status=complete`。
- 双红混合题：`run_20260722_004130_779029`，定义与 2026-07-20 电力事实均在正文；模型一次 chat 调用失败但确定性答案完整，故 transport 为 degraded、业务报告为 complete。

### 关键两题复验（8796）

- 主线：`run_20260722_004809_027116`，`report.status=completed`、`business_status=complete`；报告不再出现 `L4_market_signal` 或 `L4_structured`。
- 明日预测：`run_20260722_004853_091364`，`report.status=completed`、`business_status=complete`；真实模型波动导致 decision-brief fallback，但正文仍完整保留四个必需判断块。

## 仍需明确的边界

- 周跌原因的外部触发证据确实没有取得，系统因此只给“盘面机制判断 + 明确缺口”，不能把 `partial` 改成虚假的 complete。
- LLM provider 的单次超时/失败仍会出现在 transport degrade 计数中；这是可观测的服务状态，不能用模板伪装成模型成功。确定性证据答案和业务 completion 不受其影响。
- 本记录只证明候选分支可验收，不代表 canonical 8792 已切换；切换需用户明确批准。
