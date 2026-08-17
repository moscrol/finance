# T-F 追加指令：改 pin + 判别力先算，**不开 900**

- 日期：2026-08-17 ｜ 正本：`2026-08-17-dispatch-f-arm-a-aprime-window.md`
- 触发：T-F 烟测报告（两臂 n=1 通、terra 通、8792 未碰）问「A′ pin 定哪个」
- 结论：**选方案 2（先定 pin），但不接着开窗。** 三条硬理由见 §3。

## 1. 烟测本身：接受

n=1 管道通、两臂 dry-run `task_frame_hash` 相同、生产 `model_load_count` 仍是 1、
readiness 仍 ready、产物不进 git。**这些都做对了，不必重做。**

⚠ **但 76.8s vs 63.4s 不得读成「A′ 更快」。** n=1，延迟是高方差量。
在 450/臂之前这个数不构成任何信息。（本仓已有教训：2–3 次采样的排序是噪声，
曾据此翻掉过一个模型轴决策，而那个结论是错的。）

## 2. pin 改了 —— 而且**你问的那个洞比你以为的大**

你报告说「A′ 用的是锁样本树，不是拍过的正式 pin」。查下来：**Arm A 的 pin 也是错的**，
是我在 spec §9.4 初版写错的，不是你的问题。

`23e2a07e` 是吸收**分支的分叉点**，不是「吸收合入前的 main」。
实测 `23e2a07e..2a2523f7^1` 夹着 **95 个无关提交**。

**新 pin（唯一能把吸收单独隔离出来的一对）：**

| Arm | pin | 是什么 |
|---|---|---|
| A | **`83e83b42`** | `2a2523f7^1`，#61 合入前一刻的 main |
| A′ | **`2a2523f7`** | #61 的 merge commit |

`2a2523f7^1..2a2523f7` = 32 文件 / +5867 / −67，**这就是吸收本身**。

已排除的三个候选（别再选）：

| 候选 | 差距 | 后果 |
|---|---|---|
| A=`23e2a07e` | 到 `83e83b42` 夹 95 个无关提交 | 测成「分叉点以来的一切」 |
| A′=`79582cd7`（你这次用的锁样本树） | 比 `2a2523f7` 多 10 个提交，含 `agent_episode.py` +35/−27 | 吸收收益混进后续 episode 改动 |
| A′=当前 `main` | 多 129 个提交 | 完全测不出吸收 |

⚠ 查 #61 别用 `git log --grep="#61"`——会捞到旧 GitHub 仓的同号 PR
（`73b738b4 theme-radar/winrate-html-viz`）。**认 commit 不认编号。**

**连带**：2026-08-16 那半段 45× Arm A（#68）跑的是旧 pin，**不能直接复用**。

## 3. 为什么不接着开窗

1. **配额撞车。** T-A 现在正在跑，吃同一份 5 小时滚动配额。900 次现在开，两边抢。
2. **判别力可能不够，而这个已经能免费算出来**——见 §4，我已经算了一半。
3. pin 刚改，`83e83b42` 那棵树能不能跑起来还没验过（它比 `23e2a07e` 晚 95 个提交，
   harness 未必一样）。

## 4. 判别力：我已离线算出基准，**你不用重跑**

原本想让你「统计冻结题集的诚实闸命中率」。后来发现 #68 的产物还在，
**能离线数，不烧配额**。数据源 `~/.finance-runtime/evals/arm-a-cal-20260816/`，
45 条臂级记录（9 题 × 5 次，Arm A，**旧 pin**）：

| `stop_reason` | 次数 | 占比 |
|---|---|---|
| `numeric_lineage_gap`（诚实闸） | **19** | **42%** |
| `model_finish` | 9 | 20% |
| `repair_model_unavailable` | 6 | 13% |
| `deterministic_fast_path` | 5 | 11% |
| `runner_exception` | 5 | 11% |
| `repair_model_finish` | 1 | 2% |

| 状态字段 | 分布 |
|---|---|
| `status` | degraded **30** / completed 10 / failed 5 |
| `structural_status` | completed 23 / partial 11 / failed 11 |
| `semantic_status` | **unavailable 33（73%）** / passed 10 / repaired 2 |

诚实闸命中是**双峰**的，不是均匀分布：

```
contextual-follow-up      5/5      counterfactual-mainline   0/5
current-mainline          4/5      index-rebound-space       0/5
ruihuatai-valuation       3/5      unfamiliar-methodology    0/5
weekly-market-cause       3/5
rebound-duration          2/5
theme-comparison          2/5
```

**这组数对 §9.4 的判定线是坏消息：**

- §9.4 的主门槛是「A′ 不得让 evidence-bound output rate 相对 A 下降超过 5pp」。
  而 `semantic_status=unavailable` 占 **73%**——**该指标的可用底数只有约四分之一**。
  450/臂 表面样本量，落到这个指标上有效 n 只剩约 110–120。
- `repair_model_unavailable`(6) + `runner_exception`(5) = **11/45（24%）是纯基础设施噪声**，
  与两臂的差异无关，却全额进方差。
- 42% 的运行两臂都会停在同一个诚实闸——**这部分对 A/A′ 零判别力**。

⚠ 口径：这是**九题集不是冻结 30**，且是**旧 pin 的 Arm A**。作基准率估计够用，
不能当冻结 30 的最终读数。

## 5. 你要做的三件（都不烧配额或只烧极少）

1. **按新 pin 重搭两臂，各跑 1 题复烟测**（同题 A1-market-overview，
   同 Provider `gpt-5.6-terra @ x.ailzd.com`，不挂 GLM 链）。
   **唯一目的**：确认 `83e83b42` 那棵树跑得起来、两臂 `task_frame_hash` 仍相同。
   仍不切 8792、产物不进 git。
2. **把 §4 的离线统计扩到冻结 30**：找 `~/.finance-runtime/evals/` 下冻结 30 的历史产物，
   同样数 `stop_reason` / `semantic_status`。**先找产物，找不到再说要不要跑。**
3. **产出一页「判别力评估」**：在当前基准率下，450/臂 能不能把 5pp 与噪声分开。
   若不能，给出选项（例如：把基础设施失败排除出分母并单独计数、
   或换判别力更高的指标、或先修 `repair_model_unavailable`）。
   **不要自行放宽 5pp 门槛**——§9.4 写死了不放宽。
   2026-08-17 已交：`2026-08-17-tf-power-assessment.md`。

## 6. 明确不做

- **不开 900 次窗**，等 T-A 收工 + 用户看过判别力评估。
- 不切 8792、不动 `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS` /
  `_REPAIR_SECONDS_CAP` / 档位 / `ASK_TOOL_BATCH_TIMEOUT`（R-20260816-07 绊线）。
- 不复用 #68 那半段 45× 当新 pin 的 Arm A 基线。
- 不再扩烟测题数（原方案 1）——n 从 1 加到 3 仍不是结论，且要花 T-A 正在用的配额。
