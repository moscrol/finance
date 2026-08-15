# dsh 吸收 P0 冲突矩阵

日期：2026-08-16
对应 spec：`docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md` §8、§9、§12
实施：已合 main #61。Arm A 校准脚手架本轮合入。第 8 步 live A/B 未开。
roadmap_ref: L1-DSH

本文件已在 main。

证据等级：**[实测]** = 跑过命令/读过代码。本文件是 L1-DSH 完成判据「冲突矩阵可画」的落点，**不是** spec §11 第 8 步对照收据。

## 0. 范围

第 1–7 步已合 main（#61）。第 8 步 live A/B **未开**。下面的矩阵回答「下一刀砍在哪、和谁冲突」，不回答「dsh 有没有净收益」。

默认立场（函数 `form_step8_decision`，已有测试）是 `retain_dsh_runtime=false` / `reason=live_ab_not_run`。这是 §12「样本量不足不得判定」的钉，不是对照结论。

## 1. 冲突矩阵

| # | 面 | 谁拥有 | 冲突时怎么走 | 状态 |
|---|---|---|---|---|
| 1 | Durable 事件账本 | Finance `AgentOutcome.events` | 禁止 dsh Session 第二账本 | 第 7 步上半已关 |
| 2 | 工具执行 | registry + `HeadlessToolGateway` | stub 不得绕过网关 | 第 7 步上半已关 |
| 3 | EpisodeScope | 网关可选 `scope` | `None` 保持旧行为 | 第 7 步上半已关 |
| 4 | 生产 backend 名 | `RUNTIME_BACKEND_NAMES` | 未证明净收益前禁止登记 `dsh_stub` | 已关 |
| 5 | 凭证 | `DSH_AB_RELAY_KEY` | 不复用 `OPENAI_API_KEY`；artifact 只记指纹 | 函数已关；注入留给 live 窗 |
| 6 | live A/B 命令 | 生产 env + terra | 禁止 `--keychain-user` / `localhost:57244` / `gpt-5.6-sol` | `forbidden_copy` 已钉 |
| 7 | dsh 源码 | pinned sparse checkout | 不复制；路径只经 `DSH_SOURCE_INDEX` | 第 7 步下半已关 |
| 8 | 观测台薄账 | `gitea/main` 的 `docs/roadmap.md` | 收口时另开观测台 PR | #66 已记 #61/#65 |
| 9 | 合 main / 删安全 ref | 用户 | #61 已合；删 ref 条件已满足，hook 挡住 agent，须用户手动 | 合 main 已做；ref 仍在 |
| 10 | 推翻默认立场 | 用户开 live 窗 | 先 45× Arm A，再 30×3，CI 上界；不许放宽 5pp | 脚手架已落；live 未开 |

## 2. 第 8 步仍欠什么

Step 1 收据 §3.2 / §6.1 原样有效：

1. 冻结九题 × 5 纯 Arm A 校准 σ_d；
2. 30 题 × 每臂 3 重复，九题作子集；
3. bootstrap 95% CI 上界，压不住 5pp 就加题/加重复；
4. 生产对齐 env（`credential_source=environment`，terra）。

stub 上的取消 / `tool_exception` / Scope 拒工具只证明协议，不代替 §9.2 失败注入集合上的 live 对照。
