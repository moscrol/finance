# dsh 吸收 P0 冲突矩阵

日期：2026-08-16
对应 spec：`docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md` §8、§9、§12
实施：已合 main #61。Arm A 45× 官方窗已跑。第 8 步对照未开。
roadmap_ref: L1-DSH

本文件已在 main。

证据等级：**[实测]** = 跑过命令/读过代码。本文件是 L1-DSH 完成判据「冲突矩阵可画」的落点，**不是** spec §11 第 8 步对照收据。

## 0. 范围

第 1–7 步已合 main（#61）。第 8 步先半段 45× Arm A 已跑；对照 **未开**。下面的矩阵回答「下一刀砍在哪、和谁冲突」，不回答「dsh 有没有净收益」。

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
| 8 | 观测台薄账 | `gitea/main` 的 `docs/roadmap.md` | 收口时另开观测台 PR | #66 已记 #61/#65；#69 锁样本待观测台记账 |
| 9 | 合 main / 删安全 ref | 用户 | #61 已合；安全 ref 已删（本地+gitea 均为空） | 已关 |
| 10 | 推翻默认立场 | 用户开对照窗 | 先校准，再扩到能压住 5pp 的 n×r，才上 Arm B；不许放宽 5pp（与 step1 收据 §6.1 互为钉死，门槛不是旋钮） | 45× 已跑；锁 30×15=450/臂（v=0.1375）；对照未开 |

## 2. 第 8 步仍欠什么

Step 1 收据 §3.2 / §6.1 原样有效（5pp 门槛不放宽，与本表 row 10 互为钉死）：

1. 冻结九题 × 5 纯 Arm A 校准 σ_d — **已做**（`2026-08-16-dsh-arm-a-calibration-receipt.md`）；
2. 30 题 × 每臂 3 重复不够：投影半宽 10.8pp，所需 n×r≈423；
3. 已按真值 v=0.1375 重锁 **30×15=450/臂**。草稿 `feat/dsh-absorption-p0-seams` 本地 4 提交（v=0.125 → 30×13=390）**标 dropped**，禁止回流；
4. bootstrap 95% CI 上界，压不住 5pp 就加题/加重复，**不许放宽门槛**；
5. 生产对齐 env 本窗已对齐（`credential_source=environment`，terra）。对照仍未开。

两臂 900 arm 串行墙钟约 22.5 小时（45 arm / 4030s 外推），单窗吃不下，开窗须分批。stub 上的取消 / `tool_exception` / Scope 拒工具只证明协议，不代替 §9.2 失败注入集合上的 live 对照。
