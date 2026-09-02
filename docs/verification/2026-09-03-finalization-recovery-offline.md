# 离线量：合成失败后「抢救一次」（`_recover_finalization`）在生产触发了几次（2026-09-03）

零 LLM，零生产改动。脚本：`scripts/offline_finalization_recovery.py`。数字：
`docs/verification/2026-09-03-finalization-recovery-offline.json`。

**结论：0 次。** 生产用户 381 份 episode、全部来源 823 份，`finalization_recovery_started` /
`finalization_recovery_outcome` 一次都没出现；`stop_reason` 里也没有 `finalization_recovered` /
`finalization_recovery_failed`。这台状态机在生产的现行时钟下**从未走过**。

## 为什么要量

`2026-09-02-repair-policy-state-machine.md` §2.2 把它画成 repair cycle 之外的第二台机器（恰好一次、
不计 cycle、不经 `root_budget.grant()`，只 `_consume_root_seconds` 事后扣账），§6 红线写「本单不动，
并进 repair cycle 是另一个决定」。要拍这个决定，先得知道它多常发生——没有频次，「并不并」只是口味。

## 怎么量 [代码路径]

两个事件都在 durable 集合（`episode_event_lanes.py`），落盘就能数到。扫 `~/.local/share/finance-workbench/users`
+ `finance-base-ab/out/users` 的全部 `continuous-episode.json`，数 `finalization_recovery_started`（触发）与
`finalization_recovery_outcome.status`（recovered / failed），并看同一 episode 有没有 `repair_goal`。

## 读数 [实测]

| 队列 | n episode | 触发 | recovered | failed |
|---|---:|---:|---:|---:|
| 生产 `linxiaoqi5111` | 381 | **0** | 0 | 0 |
| 生产 · 近 14 天 | 83 | 0 | 0 | 0 |
| 全部（含探针 / finance-base-ab） | 823 | 0 | 0 | 0 |

生产失败形状与抢救前置（`bool(evidence)` ∧ `synthesis_timeout ≥ 1.0s`）逐一对照：

| stop_reason | n | 有证据 | 抢救为何没起 |
|---|---:|---:|---|
| `deadline_exhausted` | 28 | 22 | 时钟已死 → 第二条前置（剩余合成窗 ≥ 1s）结构性不成立 |
| `model_unavailable` | 10 | 0 | 零证据 → 第一条前置不成立 |
| `invalid_model_finish` | 1 | 1 | 该驳回类未开 `allow_recovery` |
| `repair_*`（adapter 修复线） | 252 | — | 走的是 A–D 四条入口那台机器，与本台无关 |

也就是说：生产上会出现的合成失败，恰好都落在这台机器的前置之外。它不是「偶尔触发」，是「前置在
90/60/30 的钟下几乎不可能同时成立」。

## 对拍板的含义

- **并进 repair cycle**：零 live 样本，收益无从量起；改控制流却要冒零行为改动之外的风险。**不建议现在做。**
- **删掉**：也不建议——单测覆盖着，且 deep 档（240s / reserve 48s）或预算 P1 拍成「工具有地板」之后，
  前置可能开始成立。
- **建议处置**：维持 §6 红线（不动），把「首次在生产触发」登记成观察点；等它真走过一次，再拿那份 episode 决定并不并。
  预算 P1 若改动 reserve，重跑本脚本一次即知有没有变化。

## 没做

没烧配额。没改 Episode / 8792 / 档位。没改 `MIN_FINALIZATION_RECOVERY_SECONDS`（1.0s）。
