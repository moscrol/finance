# 在途交接 · main

更新：2026-08-13 · Cursor Cloud（#296+#297 已合并；R6 用本地 GLM Coding Plan 质检全 A 组，闭环快照见 `docs/handoffs/2026-08-13-repair-timeout-retry-loop.md`）

## 当前状态

- canonical 8792 **未改模型**：仍是中转 `openai / gpt-5.6-terra`。代码 SHA 以 health 为准。
- 隔离 8794 现跑 **GLM Coding Plan**（`FORESIGHT_BUILTIN_LLM_API_KEY` → `https://open.bigmodel.cn/api/coding/paas/v4`，`glm-5.2` / `continuous_glm`）。官方 `paas/v4` 同一把 Keychain key 会 429「余额不足」，不要再用 `ZHIPU_API_KEY`。
- R6 产物：`intelligence/eval/runs/20260813T0314Z-r6-glm-qc.json`（Mac 私有仓）。逐题修复收据用 `scripts/dump_episode_receipts.py`。
- 生产 run 目录在 `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`，不在仓内 `intelligence/users/`。

## 下一步

1. ~~白天中转公平对照~~ **已完成（R7）**：`eval/runs/20260813T0333Z-r7-relay-daytime.json`。重试 3 次全部 `asked=30.0` 且全部救回（A5/A6/A10 各 3 证据 0 降级）；`repair_model_unavailable` 零出现。**#296/#297 生产判决通过。**
2. **A10 根因已修待合并**：PR #299（`cursor/finance-query-stock-high-d7ac`）——`fact_stock_high_daily` 注册进 finance_query + `high_status` NULL 显示「非新高」不再误导模型。合并后需蓝绿重部署 8792。
3. **R7 仍在的失败待立案**：A3 `deadline_exhausted`（43s 0 证据）、A4 `invalid_model_finish`（0 证据）、A7 `repair_model_stop`（0 证据）。R6 的 A3/A10 `repair_model_stop` 已判明是「模型自评 partial + 无新取证动作」的保守标签，交付质量尚可，非协议崩溃。
4. A5 日期错位待立案。knevo 后续：suggest_options 缺口镜像、report→track 接力。
5. 工具沉淀待归位（Mac `~/harness-reference`）：「纠正层写自己的收据」「重试窗口尺寸取当前权威不取旧字段」「NULL 渲染要按字段业务语义」候选 BUILD.md。

## 踩过的坑

- 「本地有 GLM」= Keychain `finance-workbench-glm` + **Coding Plan URL**，不是本机 ollama，也不是官方 `paas/v4`。同一把 key、两个 URL、两套配额。
- `ZHIPU_API_KEY` 会走官方 `paas/v4` → 429 余额不足；必须用 `FORESIGHT_BUILTIN_LLM_API_KEY` 才会默认 coding-plan。
- 429 那轮（R6 半成品）不能当质检结论，已杀掉。
- 归因先翻 episode 产物再下结论；中途读数会骗人。
- 远程复杂脚本用 stdin heredoc，不要 `python3 -c`；不写 token 进交接/commit。
- 验收跑长题用 nohup + 轮询日志（CF 隧道 100s 上限）。

## 已验证

- **R7 白天中转对照**（8792 生产）：10/10 完成、7/10 无降级；重试 3 次全部 30s 窗、全部救回；`repair_model_unavailable`/`repair_deadline_exhausted` 零出现。A10 完整链路：修复首枪 16s 超时 → 30s 重试 → `repair_model_finish`。
- **R6 GLM 全 A 组**（8794，约 11 分钟）：10/10 `completed`；8/10 无降级；9/10 有证据。**零次 `repair_model_retry`**（GLM 修复首枪 16–24s 就够，30s 重试闸门空转是正确行为）。A1 主路径 TimeoutError 被修复轮救回（`repair_model_finish`，22 证据）。
- **A10 归因**（R6 取证）：fail-closed 边界工作正常（42 条未核验证据没泄漏进答案）；真根因是 `fact_stock_high_daily` 未注册 + NULL 渲染「未知」误导模型宣告假缺口——已修在 PR #299。
- R5 隔离端口（中转，A4–A10）：重试窗全部 30s，A4 走通 `repair_model_finish`，A6/A7 烧爆账本形状进闸门。
- A1 tier 判决：多轮均 `standard`，非路由方差。
