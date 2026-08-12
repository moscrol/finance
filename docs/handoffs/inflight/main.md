# 在途交接 · main

更新：2026-08-13 · Cursor Cloud（#296+#297 已合并；R6 用本地 GLM Coding Plan 质检全 A 组，闭环快照见 `docs/handoffs/2026-08-13-repair-timeout-retry-loop.md`）

## 当前状态

- canonical 8792 **未改模型**：仍是中转 `openai / gpt-5.6-terra`。代码 SHA 以 health 为准。
- 隔离 8794 现跑 **GLM Coding Plan**（`FORESIGHT_BUILTIN_LLM_API_KEY` → `https://open.bigmodel.cn/api/coding/paas/v4`，`glm-5.2` / `continuous_glm`）。官方 `paas/v4` 同一把 Keychain key 会 429「余额不足」，不要再用 `ZHIPU_API_KEY`。
- R6 产物：`intelligence/eval/runs/20260813T0314Z-r6-glm-qc.json`（Mac 私有仓）。逐题修复收据用 `scripts/dump_episode_receipts.py`。
- 生产 run 目录在 `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`，不在仓内 `intelligence/users/`。

## 下一步

1. **白天稳定时段用中转重跑全 A 组做公平对照**（R4/R5 凌晨中转；R6 是 GLM 通道，不能替代中转对照。R5 的窗口尺寸收据 `asked=30.0` 仍是中转侧确定性证据）。
2. **新形状立案（R6 仍在）**：`repair_model_stop`——修复窗内 provider 到货、模型没吐合法 FINISH（R6：A3、A10）。协议问题，不是超时，30s 重试闸门正确空转。
3. A10 仍 0 证据 + 降级；A9 主路径 `model_finish` 但语义/证据核验降级。A5 日期错位待立案。
4. A3 的 `continuous_runtime_failed` 在 GLM 上消失（69s / 3 证据 / `repair_model_stop`），中转侧是否还在要白天对照才算。
5. knevo 后续：suggest_options 缺口镜像、report→track 接力。
6. 工具沉淀待归位（Mac `~/harness-reference`）：「纠正层写自己的收据」「重试窗口尺寸取当前权威不取旧字段」候选 BUILD.md。

## 踩过的坑

- 「本地有 GLM」= Keychain `finance-workbench-glm` + **Coding Plan URL**，不是本机 ollama，也不是官方 `paas/v4`。同一把 key、两个 URL、两套配额。
- `ZHIPU_API_KEY` 会走官方 `paas/v4` → 429 余额不足；必须用 `FORESIGHT_BUILTIN_LLM_API_KEY` 才会默认 coding-plan。
- 429 那轮（R6 半成品）不能当质检结论，已杀掉。
- 归因先翻 episode 产物再下结论；中途读数会骗人。
- 远程复杂脚本用 stdin heredoc，不要 `python3 -c`；不写 token 进交接/commit。
- 验收跑长题用 nohup + 轮询日志（CF 隧道 100s 上限）。

## 已验证

- **R6 GLM 全 A 组**（8794，约 11 分钟）：10/10 `completed`；8/10 无降级；9/10 有证据。**零次 `repair_model_retry`**（GLM 修复首枪 16–24s 就够，30s 重试闸门空转是正确行为）。A1 主路径 TimeoutError 被修复轮救回（`repair_model_finish`，22 证据）。A4 在 16s 修复授予内走通（中转 R4 正是这个窗不够才要 30s 重试）。
- R5 隔离端口（中转，A4–A10）：重试窗全部 30s，A4 走通 `repair_model_finish`，A6/A7 烧爆账本形状进闸门。
- A1 tier 判决：多轮均 `standard`，非路由方差。
