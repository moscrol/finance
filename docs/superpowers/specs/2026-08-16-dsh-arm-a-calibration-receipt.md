# dsh 吸收 Step 8 先半段：Arm A 校准收据

日期：2026-08-16
对应 spec：`docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md` §9.4、§11 第 8 步
对应裁定：`docs/superpowers/specs/2026-08-15-dsh-absorption-step1-baseline-receipt.md` §3.2 / §6.1
roadmap_ref: L1-DSH

证据等级：**[实测]** = 跑过命令/读过产物。本文件是冻结九题 × 5 纯 Arm A 的校准收据，**不是** §11 第 8 步对照收据，也不是 `retain_dsh_runtime` 的翻转依据。

## 0. 结论

- **官方窗成立** [实测]：`official_window=true`，`mode=live`，`repeat_count=5`，九题 ID 与冻结集一致，env 无 issues，resolved model 只有 `gpt-5.6-terra`。
- **30×3 压不住 5pp** [实测]：pooled variance `0.1375`，投影 95% CI 半宽 `10.8pp`，`can_resolve_5pp=false`，所需 `n×r ≈ 423`（设计 30×3=90）。
- **对照未开** [实测]：`retain_dsh_runtime=false`，`live_ab_ran=false`，`reason=calibration_only_live_ab_not_run`。没有上 Arm B，没有登记 `dsh_stub`。
- **下一步按裁定走**：`increase_n_or_repeats_do_not_loosen_threshold`。不许把门槛从 5pp 拧松。

## 1. 窗口对齐

| 项 | 值 |
|---|---|
| 题集 | `frozen-nine-2026-07-25.questions.json`（九题 ID 顺序与 `FROZEN_NINE_CASE_IDS` 一致） |
| 后端 | `continuous_glm` only，`credential_source=environment` |
| 模型 | `gpt-5.6-terra`（禁止 sol / 死网关 / `--keychain-user`；本窗未出现） |
| 中转 host | `x.ailzd.com` |
| keychain 开关 | `FORESIGHT_LLM_KEYCHAIN=0` |
| key 指纹 | `854d167caac988c8`（只记指纹） |
| 代码 tip | `gitea/main@eecdff8e`（#67 脚手架已在） |
| 墙钟 | 4030s / 退出码 0 |
| 主度量 | `evidence_bound_rate`，门槛 5pp |

## 2. 重复产物（不入库）

完整 arm JSON 留在本机 evals 目录，不进 git。收据文件名 `arm-a-calibration-receipt.json`。

| 重复 | 文件 | sha256 |
|---|---|---|
| 1 | `arm-a-cal-r1.json` | `2b42034f161ee3761bca31d32c08661ddd49c5d68a161f0278a41102c23085d9` |
| 2 | `arm-a-cal-r2.json` | `8e656ba8a99080c349ba43d3847d4b430673db8440837708a57d2550546bc182` |
| 3 | `arm-a-cal-r3.json` | `9e541b939af5162d6e25b13e57a8c60fc51cc6eedace650ace4cae43d6b3e135` |
| 4 | `arm-a-cal-r4.json` | `7dc948edcbeee828d70238e6148a35213475b0873395f3b06946f23c21c49322` |
| 5 | `arm-a-cal-r5.json` | `5bcc94cf0c3b0c2cb41ee7fbb35896ca63798140bd49130cef6ec684995887dd` |

## 3. 每题读数

`index-rebound-space` 五次都走 `deterministic_fast_path`，已从 σ 池排除（设计如此）。其余八题各 n=5。

| 题 | mean | variance |
|---|---|---|
| rebound-duration | 0.20 | 0.20 |
| ruihuatai-valuation | 0.00 | 0.00 |
| weekly-market-cause | 0.40 | 0.30 |
| current-mainline | 0.40 | 0.30 |
| theme-comparison | 0.40 | 0.30 |
| counterfactual-mainline | 0.00 | 0.00 |
| unfamiliar-methodology | 0.00 | 0.00 |
| contextual-follow-up | 1.00 | 0.00 |

pooled variance = `0.1375`（`design_variance_source=pooled_repeats`）。σ_d 代理 `√(2v) ≈ 0.524`。

## 4. 投影

| 项 | 值 |
|---|---|
| 设计 | 30 题 × 3 重复 |
| 95% CI 半宽 | 0.1083（10.8pp） |
| 压住 5pp 所需 n×r | 422.6 |
| `can_resolve_5pp` | false |

## 5. 伴随现象（不改门槛）

45 次 arm：`continuous_glm` 45；模型 terra 40 + fast-path 5。

| 现象 | 计数 | 说明 |
|---|---|---|
| semantic unavailable / passed / repaired | 33 / 10 / 2 | 主度量不是 semantic |
| status degraded / completed / failed | 30 / 10 / 5 | failed 计入 0 绑定率 |
| stop `numeric_lineage_gap` | 19 | 诚实闸，不是窗失败 |
| stop `deterministic_fast_path` | 5 | 全是 `index-rebound-space` |
| stop `runner_exception` | 5 | `theme-comparison`×3（adapter 未到 semantic）；`ruihuatai-valuation`×2（一次 `source_date` 非 ISO，一次未到 semantic） |

这些是噪声来源，不是把 5pp 拧松的理由。

## 6. 明确没做的

- 没有扩 30 题，没有加重复到 n×r≈423。
- 没有上 Arm B，没有注入 `DSH_AB_RELAY_KEY`。
- 没有把 `retain_dsh_runtime` 写成 true。
- 没有切 8792。
