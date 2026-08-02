# Continuous Agent Runtime 生产候选验收

日期：2026-07-24  
状态：隔离自用 canary 验收通过；未合并 `main`、未切 canonical 8792、未 push

## 1. 结论

`fix/agent-harness-monotonicity@c327faf7a75fbdf99fda04541053a8e2e13d0bd7`
已经达到本阶段目标：长尾金融问题由同一个连续 Episode 在同一消息历史中完成
`plan → tool → observe → repair → finish`，确定性技术题继续走零 LLM 快车道，
最终回答统一经过结构化完成度校验和语义 grounding/repair。真实五问不再出现
Daily Agent/研究雷达越权终结、主题模板污染或“协议完成但没有回答问题”。

该结论只表示**可以在 8795 进行日常自用 canary 测试**，不等于已接入
Codex/Claude headless 或 OpenAI/Claude Agent SDK，也不等于已批准切换 8792。

## 2. 版本与运行身份

- 审查固定点：`7bc8dcff50747645b4b0c9bf27ba8b53118a3832`
- 候选分支：`fix/agent-harness-monotonicity`
- 最终候选：`c327faf7a75fbdf99fda04541053a8e2e13d0bd7`
- URL：`http://127.0.0.1:8795`
- PID：`50842`
- clean detached runtime：
  `/Users/a77/.finance-runtime/finance-workspace-c327faf7-continuous-canary`
- 私有数据根：`/Users/a77/finance-workspace-private`
- 隔离用户数据根：
  `/Users/a77/.finance-runtime/continuous-final-82d6d165`
- 模式：`ASK_CONTINUOUS_RUNTIME=canary`
- 模型：GLM 5.2；密钥仅在进程启动时从 macOS Keychain 注入
- health：`healthy`、`source_dirty=false`、revision/canary ID 与最终 SHA 一致
- 当前市场数据：2026-07-24；题材/板块/个股覆盖均为 4/4；L2 扫描仍在运行；
  晨汇/知识事件为 2026-07-23，UI 明确标为较旧

## 3. 本阶段完成的能力

1. `TaskFrame` 成为单轮问题语义的不可变事实源；controller、adapter、report 共用
   `task_frame_hash`，避免 `question_type`、route 和旧 TurnIntent 相互覆盖。
2. `ContinuousAgentEpisode` 保留原始模型动作和工具观察；模型不再每步“失忆重启”。
3. `ToolBatchExecutor` 并行执行同一模型回合的只读工具，结果按调用顺序回填；
   deadline、QueryLedger、ProviderTrace 和取消边界跨线程保持一致。
4. 终局压缩/格式损坏只恢复 finish envelope，不重建整个推理历史；终局所有权单调，
   超时、取消、语义修复不会反向覆盖已经验证的安全答案。
5. `EpisodeVerifier` 校验 required outputs 与 evidence hash；
   `EpisodeSemanticVerifier` 句级拒绝无据数字、因果和条件，并优先局部删除/修复。
6. 估值题新增 `financial_data` 硬锚与 `financial_business_anchor` 证据底线；亏损公司
   用 PB 敏感性而不是把盈利可比组倍数直接套用。
7. `market_technical` 保持结构化 OHLCV 的确定性 fast path，零 LLM、秒级完成。
8. Conversation API、SSE、Run/Report、Answer artifact 与真实 UI 共用同一候选 runtime；
   运行 provenance 可验证代码根、数据根、revision、dirty 状态和依赖指纹。

## 4. 同一 PID 五问 E2E

前五问均在父候选 `82d6d165` 的同一 PID 中顺序执行。其后只增加了技术区间
Markdown 安全符号、前端证据提示作用域和 Overview 覆盖率交集三个展示修复；
连续 Episode/GLM/工具内核没有改变。最终 SHA 又单独复跑了零 LLM 技术题。

| 问题 | Run / 延迟 | LLM / 工具 / 重复查询 | 结构 / 语义 | 人工正文结论 |
|---|---|---:|---|---|
| 瑞华泰合理估值 | `run_20260724_225425_670985` / 101.551s | 2 / 3 / 0 | completed / repaired | 当前市值 49.5 亿、PE 不适用；PB 保守 37.15–49.5 亿、中性 49.5–74.31 亿；财务硬锚覆盖 2024 年报至 2026Q1；无据的新品阶段与 20% 毛利率阈值被语义门删除 |
| 昨天反弹能持续多久 | `run_20260724_225715_936500` / 38.922s | 2 / 2 / 0 | completed / passed | 基准 1–3 个交易日，超过 5 日概率偏低；给出延续与失效条件，不把方向预测写成确定事实 |
| 本周下跌主要原因 | `run_20260724_225859_792359` / 61.179s | 3 / 5 / 0 | partial / repaired | 先纠正全周实际上涨 2.99%、仅 7 月 17 日跌 3.05%；同窗新闻三次为空，只保留盘面事实与明确原因缺口，不编造宏观归因 |
| 科创50反弹空间 | `run_20260724_230051_168925` / 0.541s | 0 / 1 / 0 | completed / passed | 压力 1811.76、1823.48、1854.94；支撑与失效条件完整；零 LLM |
| 当前市场主线 | `run_20260724_230324_149405` / 38.436s | 3 / 4 / 0 | completed / repaired | 截至当时最新 7 月 23 日：医药为韧性核心，有色与电力为轮动支线，科技短期退潮；用 20 日频次、同日涨跌/涨停、量能和情绪边际支撑；新闻为空不编催化 |

所有五问 `degrade_count=0`。第三题的 `partial` 是业务证据不足的诚实状态，
不是传输或模板降级。

### 产物 SHA256（Episode / Answer）

- 估值：`595666bf...eab7` / `36304910...5151`
- 反弹：`3dfe5fb0...f672` / `1b122e13...f692`
- 周内归因：`a0e7be60...4c31` / `b2398f41...a1ea`
- 技术位：`88de29a0...c9d1` / `5015ad36...376`
- 主线：`f93ab2f7...aced` / `b3607970...e025`

最终 SHA 技术位复跑：`run_20260724_233136_755594`，0.554s，零 LLM，
Episode / Answer SHA256 为 `7cadb62f...e6c` / `e0515e98...803`。

## 5. 浏览器验收发现并关闭的问题

1. 技术区间用两个 `~` 时被 Markdown 配成删除线。后端 fast path 和旧 ask 管线
   统一改为 `–`；真实 DOM 从 `del=1` 变为 `del=0`。
2. 前端把 `task_type=research` 粗暴等同“公司研究”，导致指数题显示“缺公司级来源”。
   `MessageBubble` 现在优先使用 `TaskFrame.subject_kind/evidence_policy`；只有公司研究
   才显示公司证据警告，旧无 TaskFrame 报告保留兼容逻辑。
3. 真实数据更新后子表存在额外孤儿 theme，Overview 曾显示 `5/4、missing=-1`。
   覆盖率现只统计父题材表与明细表的同日交集，最终为 4/4、missing=0。

浏览器最终验收：首页展示 2026-07-24；真实技术位回答区间完整、无删除线、无公司级
证据误提示，问答输入与运行详情可用。

## 6. 自动化验证

```text
Python focused                         404 passed
Python final full (.venv-workbench)   2483 passed
Frontend component/full               57 / 62 passed
Frontend lint/typecheck/build          passed
Focused Ruff                           passed
Final technical semantic smoke         completed, 0.554s, zero LLM
```

完整 Python 测试必须清除桌面会话注入的 `FORESIGHT_USERS_DIR`、`FORESIGHT_USER`、
`SUBCONSCIOUS_VAULT`、`AGENT_MEMORY_VAULT`，否则测试会读取真实共享记忆，产生
11 个环境污染失败。使用 `.venv-workbench` 后 FastAPI/Workbench 测试不会被跳过。

## 7. 保留边界与下一阶段

- 尚未接入 Codex/Claude headless；它适合作为质量上界和回归对照，不应作为最终
  产品反代架构。
- 尚未接入 OpenAI/Claude Agent SDK；当前 adapter 接口已 provider-neutral，下一阶段
  可增加官方 runtime backend，并与 GLM 自建 Episode 做三路 A/B。
- 当前 semantic judge 与 composer 仍可能使用同一 provider，存在相关性失败风险；
  生产切换前应配置独立 judge 或 GPT/Claude 交叉审查。
- 23:24 DuckDB 更新瞬间出现过一次“暂时不可读”，随后连续三次恢复。后续应采用
  last-known-good Overview 快照或有界读重试，避免同步窗口闪烁；本轮没有仓促引入
  进程缓存状态机。
- 8795 是临时 canary，不由 LaunchAgent 托管；Mac 重启后不会自动恢复。
- canonical 8792、`main` 与 `/Users/a77/finance-workspace-runtime` 均未改动。

## 8. 建议

本阶段可以结束并交给用户在 8795 做真实日常问答。下一阶段 P0 不是继续增加硬路由，
而是建立三路基准：`当前自建 Episode / OpenAI 或 Claude Agent SDK / headless 上界`，
使用同一问题、同一工具白名单、同一证据 verifier 对比任务完成度、回答偏好、延迟和
成本，再决定生产执行内核。
