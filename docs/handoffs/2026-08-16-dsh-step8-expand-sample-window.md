# 2026-08-16 第 8 步「扩样再对照」下一窗交接（开不开由用户裁）

roadmap_ref: L1-DSH

一句话：45× Arm A 校准已定妆——pooled variance 0.1375，30×3 半宽 10.8pp 压不住 5pp，所需 n×r≈423/臂；裁定是加题/加重复、不许放宽门槛。本文件给开窗前置清单、成本推算、和草稿分支 4 个提交的处置。默认立场 `retain_dsh_runtime=false` 在对照跑完前不动。

证据等级：**[实测]** = 跑过命令/读过产物；**[推算]** = 由实测数字外推，未跑。

## 1. 现状（全部有主线收据）

- 校准收据 [实测]：`docs/superpowers/specs/2026-08-16-dsh-arm-a-calibration-receipt.md`（#68 已合）。pooled variance `0.1375`、投影 95% CI 半宽 `10.8pp`、`can_resolve_5pp=false`、所需 `n×r≈422.6`、`retain_dsh_runtime=false`、`live_ab_ran=false`。
- 裁定 [实测]：`increase_n_or_repeats_do_not_loosen_threshold`（step1 收据 §3.2/§6.1 + 设计 spec §9.4：样本量不足不得判定）。
- 薄账决策队列已有行：「扩样到 n×r≈423 再上 Arm B，还是先另开窗 | 卡在用户」。
- Arm 定义（设计 spec §9.1）：A = `continuous_glm` 生产基线；B = dsh Runtime Adapter，共用 Finance Domain Harness。§9.2 固定变量含同一失败注入集合（超时、空检索、参数错误、Provider 503、取消、重启）。主度量 `evidence_bound_rate`，门槛 5pp，bootstrap 95% CI 上界判。
- 注意：设计 spec 本体 `2026-08-15-agent-base-dsh-absorption-design.md` 目前只在本地未推分支 `docs/dsh-absorption-spec` 上；main 上的收据引用它是悬空指针。开窗前应把该 spec 经 PR 落 main（docs-only，一刀）。本 PR 不带 spec。

## 2. 草稿 4 提交：标 dropped（不开窗也必须处置）

`feat/dsh-absorption-p0-seams` 本地领先 `gitea/feat/dsh-absorption-p0-seams`（`9ab8c191`）4 个提交 [实测]。**整支不合。禁止 cherry-pick / 续做时当实测值捡起来。**

| 提交 | 内容 | 处置 |
|---|---|---|
| `ccdcfd00` / `a964607b` | Arm A 校准脚手架+轮小结 | **dropped**。主线已由 #67/#68 等价落地 |
| `de48d5c8` / `05072e78` | 冻结 30 题分层集 + 锁 30×13 | **dropped**。两处硬伤，本 PR 按真值重落 |

两处硬伤 [实测]：

1. `intelligence/eval/ab_sample_design.py` 写死 `MEASURED_POOLED_VARIANCE = 0.125`，注释自称「[实测] official Arm A 校准收据 pooled_variance」——主线收据实为 `0.1375`。数字错，出处标注也错。
2. 由 0.125 推出 required_nr≈384 → 锁 30×13=390/臂；按真值 0.1375 是 422.6 → **30×13 不够**（半宽 5.20pp）。修正后为 **30×15=450/臂**（半宽 4.85pp）。

可保留并已重落的资产：30 题分层法本身、`test_frozen_thirty.py` 的「前 9 题 = FROZEN_NINE_CASE_IDS」约束。常数与锁数按 0.1375 重算。

本地 worktree `fwp-wt-dsh-seams` 仍挂着这 4 个提交，**不要 reset / 不要推**；远程 `gitea/feat/dsh-absorption-p0-seams` 没有它们。幽灵常数的代码闸是 `DROPPED_DRAFT_VARIANCE = 0.125` 与「官方方差 ≠ 0.125」测试。

## 3. 开窗前置清单（本 PR 已做第 1 项；live 窗未开）

1. **已做**：从 `gitea/main` 拉新分支 `eval/frozen-thirty-450` 重落 frozen-30 + 修正版 ab_sample_design（v=0.1375，per-arm n×r=450≥423）。草稿 4 提交标 dropped。
2. 窗口对齐照抄校准收据 §1：`continuous_glm`、`credential_source=environment`、terra only、`x.ailzd.com`、`FORESIGHT_LLM_KEYCHAIN=0`；禁 sol/死网关/`--keychain-user`（`forbidden_copy` 已钉）。
3. Arm B 凭证（冲突矩阵 rows 4/5/6）：`DSH_AB_RELAY_KEY` 只在 live 窗注入，不复用 `OPENAI_API_KEY`，artifact 只记指纹；净收益未证明前不把 `dsh_stub` 登记进 `RUNTIME_BACKEND_NAMES`。
4. 8792 不动（对照跑仓库 tip，不跑生产快照）。
5. 判定按 §9.4：evidence_bound_rate 下降 >5pp 即 B 不过；桥接耗时单独拆，不算底座劣势；任一 Arm Trace/Projection 对账失败直接判不可发布。
6. 设计 spec 仍待 docs-only PR 落 main（悬空指针，本 PR 不带）。

## 4. 成本 [推算]

45 arm 官方窗墙钟 4030s → ~90s/arm。两臂 450×2=900 arm ≈ 81,000s ≈ **22.5 小时串行墙钟**，不含失败注入轮与重试。单窗吃不下，需要分批（如 3×~7.5h）或过夜多窗；每批都要满足 §9.2 同快照/同 cutoff 约束，跨天分批要先确认数据快照钉得住。

本 PR **不开** 这 22.5 小时的窗。

## 5. 若裁「不开 / 先放」

- 默认态自动站住：`retain_dsh_runtime=false` / `reason=live_ab_not_run`，L1-DSH 薄账行不动。
- 草稿 4 提交已标 dropped（§2），0.125 不得再当实测值。
- 观测台 PR 把「扩样还是另开窗」行保持卡在用户，直到你裁；不要把「锁了 450」误写成「对照已开」。

## 6. 5pp 门槛不放宽（两处钉死）

唯一不可谈判项。两处互相引用，改一处必须改另一处，且只许加题/加重复：

1. Step 1 收据 §6.1：`docs/superpowers/specs/2026-08-15-dsh-absorption-step1-baseline-receipt.md`——「不许放宽门槛」。
2. 冲突矩阵 row 10：`docs/superpowers/specs/2026-08-16-dsh-absorption-conflict-matrix.md`——「不许放宽 5pp」。

代码侧：`THRESHOLD_PP = 5.0` 不是 `recommend_design` 的参数；测试钉死 signature 里没有 `threshold`。

## 7. 决策归属

用户。本文件不预设开不开窗；本 PR 只做前置修数/重锁/丢草稿。`retain_dsh_runtime` 仍 false。
