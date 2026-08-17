# T-F 派单：Arm A / A′ 对照窗（**通用底座**·配额重）

- 日期：2026-08-17 ｜ 索引：`2026-08-17-dispatch-00-index.md`
- **层：通用底座**（测的是吸收的接缝有没有净收益，不测领域正确性）
- 依据：`docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md`
  §9.1（2026-08-17 改口径）、§9.4、§11 第 8 步
- **状态：需用户批准才可开跑**（配额重，见 §5）

## 0. 一句话

跑分对照已从「我们 vs dsh」改为「**我们吸收前 vs 吸收后**」。
Arm A 基线现在只有半段，先把它跑满，再跑 A′。

## 1. 现状（自包含）

spec §11 第 8 步自述：

> 2026-08-16：先半段 45× Arm A 已跑（#68，v=0.1375，30×3 压不住 5pp）；
> 已按裁定加重复锁 30×15=450/臂（#69）。5pp 门槛不放宽。对照仍未开。
> 2026-08-17：Arm A 基线仍只有半段（45×），距锁定的 450/臂还差一大截；A′ 未跑。

即：**吸收的接缝（第 1–7 步）已合入 #61，但「吸收到底有没有用」一次都没量过。**

## 2. 两臂定义（2026-08-17 口径，别用旧的）

| Arm | 是什么 |
|---|---|
| A | **吸收前基线**，pin 到实施分叉点 `gitea/main@23e2a07e` |
| A′ | **吸收后**，同一 Runtime、同 Provider，P0/P1 接缝（spec §7.1–7.6）已落 |

⚠ **Arm A 必须 pin 到 `23e2a07e`，不得拿「当前生产」冒充吸收前基线**——
生产已经含了部分吸收成果，拿它当 A 会把收益吃掉一半还看不出来。这条是 §9.4 新加的。

⚠ 原 Arm B（dsh Runtime Adapter）**已降级，不要跑**。它被 §9.5 的静态形状对照替代，
那是另一轨（T-E），不烧配额，不由本轨负责。

## 3. 固定变量（spec §9.2，一条都不能松）

同模型与 Provider、同题与对话上下文、同 Task Frame 与 `task_frame_hash`、
同数据快照与 `information_cutoff` 与知识库 revision、同 Tool Registry 与 Schema 与
Evidence Ledger 与 Verifier、同总 deadline 与 call budget 与 repair budget 与输出契约、
同失败注入集合（超时 / 空检索 / 参数错误 / Provider 503 / 取消 / 重启）。

## 4. 判定线（spec §9.4，2026-08-17 已改成以 A′ 为主语）

- 判定前必须固定题集规模与每臂重复次数，并说明 5pp 差异在该样本量下可与噪声区分；
  样本量不足**先扩样本，不得直接判定**。
- A′ 不得让 evidence-bound output rate 相对 A 下降超过 5pp。
- A′ 不得增加未经绑定的数字/日期断言。
- A′ 须在 P95 延迟、修复成功率、恢复能力、维护成本中**至少一项明确改善**，吸收才算兑现；
  无改善则该接缝保留形状、**不宣称收益**（不是判它失败）。
- 任一 Arm 的 Trace/Projection 对账失败 → 该 Arm 不可发布。

## 5. ⚠ 配额（开跑前先算）

**LLM 是 5 小时滚动上限，约 15 次 canary 跑光。** 锁定的样本量是 **30×15=450/臂**，
两臂 900 次。**这不可能一口气跑完**，必须分批并在账本里写明批次与每批的环境快照。

先做的事：**算出需要多少个滚动窗口、写成排期给用户看**，再开跑。
不要开跑到一半发现配额不够——半截样本比没有更糟（会诱导按不足样本判定，正是 §9.4 禁的）。

## 6. 完成定义

- Arm A 跑满 450，环境快照与 revision 逐批入账本。
- Arm A′ 同样本量跑满。
- 按 §9.3 三组指标（领域质量 / Runtime 质量 / 工程成本）出决策收据。
- 收据须自述**对哪个 revision、哪个 Provider、哪份数据快照成立**。

## 7. 边界

- 不动 `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS` / `_REPAIR_SECONDS_CAP` / 生产档位 /
  `ASK_TOOL_BATCH_TIMEOUT`（R-20260816-07 绊线）。
- 不切 8792。
- 不碰 `ASK_DEGRADED_FALLBACK`（T-A 的活）、不改降级文案（T-B）、不改结转判据（T-C）。
  **本轨跑的题集若与 T-A 的对照窗撞车，先跟主 agent 对时段**——两轨都吃同一份配额。
- 合 main 必须等用户确认。

## 8. 环境

- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`
- ⚠ 在生产实例上做旁路测量会污染它自己的探针（直调 `kb_rag.retrieve` 加载 BGE-m3 的
  39 秒里 `/api/readiness` 会翻 `not_ready`）。判据：`workers.rag.model_load_count` 没变
  就说明常驻 worker 没重载，红的是探针不是 worker。
- Gitea PR：`git credential fill` + `http://127.0.0.1:3300/api/v1/repos/a77/finance-workspace-private/pulls`
- ⚠ 不要从 `/Users/a77/finance-workspace-private` 工作树提交——该工作树 2026-08-17 已复位，
  但其本地 `main` 仍落后 `gitea/main` 293 个提交，除非已 ff 过。开工先
  `git status --short && git branch --show-current` 并核对是否与 `gitea/main` 同步。
