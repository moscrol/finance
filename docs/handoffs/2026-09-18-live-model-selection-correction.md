# 真实验收模型纠偏：GLM 已获授权，不应等待 GPT 钥匙串

## 结论与范围

用户本轮问“你找下这个 session，不是可用 glm 去跑实际的吗”。已定位原会话，并确认 **`8a00a7c6` 把过期的 GPT 模型决定误当成当前唯一许可**。可以沿用已授权的智谱 `glm-5.3-flash` 路线准备新版验收，无需先恢复 `gpt-5.6-sol` 钥匙串。

原凭据前置的“当前搜索范围未找到条目、0题/0模型调用”仍是历史事实，不覆盖该收据；撤销的是“因此所有新版真实验收都必须等待”的解释。新版真模型验收仍 `not_run`，原 live 仍 `not_passed`。

## 原会话定位

- Session ID：`01a0af55-1bfb-738d-8a3a-90805a51b1b2`。
- 会话文件：`~/.pi/agent/sessions/--Users-a77-finance-workspace-private--/2026-09-17T12-26-25-660Z_01a0af55-1bfb-738d-8a3a-90805a51b1b2.jsonl`。
- 用户于 2026-09-17 20:28（+08）提出 8792 与组件研究的对照题：“这里的行情哪个板块更有机会，历史上有相似的阶段吗”。
- 用户于 09-18 19:28 说“执行”；agent 于 20:11 回复本轮所引用的凭据阻塞报告。原会话的用户消息没有要求这次改用 `gpt-5.6-sol`。
- 工作树：`/Users/a77/fwp-wt-research-answer-preservation`，分支 `feat/research-answer-preservation`。接手时 clean、HEAD=`8a00a7c6`；主检出树他人未提交文件未动。

## 按核对顺序的证据

1. [原前置快照](2026-09-18-finish-candidate-live-preflight.md) 明写：目标 GPT 来自项目记忆的模型决策，而不是本次会话新增要求。
2. 项目记忆 `20_projects/finance-workspace-private.md` 的“2026-08-05 用户决策”仍写“GLM 模型退役”。但 [09-16 切流记录](2026-09-16-8792-switch-a26cec4d.md) 已载明用户要求“用 glm-5.3-flash 跑”，主写手直连 `open.bigmodel.cn/api/coding/paas/v4`，兜底为 `glm-5.3`。不能把 fomo 网关当时的 GLM 故障外推到智谱直连。
3. 原会话先前的真实研究 `run_20260918_113122_450933`，其 `~/.finance-runtime/reviews/research-answer-preservation-20260918/live-inspection.json` 明确记录 `model_metadata={used:true, provider:zhipu, model:glm-5.3-flash}`。即同一工作流已经实际使用该模型；这不改变该答卷未通过的结果。
4. 本轮只读查询生产 `GET http://127.0.0.1:8792/api/health`：`runtime.source_revision=bf662e9310ff751a4c31763815ee78fb7d6d5122`、`runtime.code_matches_repo=true`、`runtime.agent_runtime={backend:continuous_glm, ready:true, model:glm-5.3-flash}`。初次投影误取顶层字段得到 null，按实际嵌套路径复核后如上。**health 就绪不是新的端点/额度探测，也不保证下一请求成功。**
5. 已通过 `intelligence.cli record-correction` 记录用户纠偏；落点由 userspace 解析，为当前用户的 `corrections.jsonl`。同步更正活交接与项目记忆的当前模型前提，旧日期快照不改写。

## 决策及被否方案

| 方案 | 决定 | 原因 |
|---|---|---|
| 沿用已授权 GLM 路线，首题前固定实际配置 | 采用 | 与较新用户决定、既有真实 run 和现役配置一致 |
| 继续强制等待 GPT Keychain | 否决 | 把旧模型选择误作当前验收的必要条件 |
| 把 health ready 当成新 live 通过 | 否决 | 没有真实请求，更没有候选版本交付证据 |
| 删掉原阻塞或改写原失败 | 否决 | 历史检查事实与当前授权解释分账 |
| 直接在生产发题或切流 | 本轮不做 | 本轮定位与纠偏；不额外消耗研究样本，不改8792 |

## 后续

执行者先核候选代码仍为已验的 `35ee8a5c`，再在隔离实例准备一次新版 Workbench conversations/messages 验收：固定主模型及兜底规则、数据副本、预算、判官配置、首题零重发规则；使用现有授权凭据传递方式，不输出密钥。保留原失败，记录新 run 实际使用的模型，不能把另一模型的结果移绑 GPT 或把接口就绪写成模型成功。

本轮新增研究提交0、模型调用0、服务启动0；仅只读 health 与文档/纠偏台账写入。未读取密钥、未修改运行配置、未合并或部署。没有新增脚本或业务门禁；根因是时序与适用范围的语义误判，本次复用现有纠偏入口并修正会被接手者读取的前提，不造第二套凭据工具。
