# 在途交接 · main

更新：2026-08-13 · Cursor Cloud（#296–#299 全部合并部署；R6/R7/R8 三轮验收闭环，快照见 `docs/handoffs/2026-08-13-repair-timeout-retry-loop.md`）

## 当前状态

- **canonical 8792 = `bcd3b6ce`**（#298 交接 + #299 finance_query 修复已上线），中转 `openai / gpt-5.6-terra` 未变，health/ready 全绿。旧 runtime `a317f37f38f4` 保留作回滚。
- ⚠ health 的 `code_snapshot_matches_repo=False` 是因为 Mac 开发区 HEAD 还在旧提交且有他人在途改动（source_dirty）；loaded worktree 固定在 `bcd3b6ce64f7`，以 `loaded_code_root` 为准。**不要去动开发区**。
- 隔离 8794 跑 **GLM Coding Plan**（`FORESIGHT_BUILTIN_LLM_API_KEY` → `.../api/coding/paas/v4`）。官方 `paas/v4` 同一把 key 429 余额不足，不要用 `ZHIPU_API_KEY`。
- 验收产物：R6 `20260813T0314Z-r6-glm-qc.json`、R7 `20260813T0333Z-r7-relay-daytime.json`、R8 `20260813T0357Z-r8-a10-postfix.json`（Mac 私有仓 `intelligence/eval/runs/`）。收据用 `scripts/dump_episode_receipts.py`。
- 生产 run 目录在 `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`。

## 下一步

1. **PR #301（A3 冷启动修复）待用户确认合并**：`cursor/repair-cold-restart-d7ac`。零证据饿死型 episode（`stop_reason=deadline_exhausted` + 零证据）获一发带工具的冷启动修复授予（≤30s，cycle 1 一发定音）。隔离 E2E 四轮：R12 完整点火走通（饿死 → 冷启动带工具 → 证据 0→5 → finalize 超时 → 瞬态重试 30s → `repair_model_finish`，交付 2 证据 0 降级）；R10/R11 未饿死时正确不触发。合并后需蓝绿重部署 8792。
2. **判据教训（已写进代码注释）**：第一版拿「试过工具」当饿死判据，被 R9 零 trace 形状证伪——首个模型轮就吃光窗口时一次工具都没轮到。饿死的共同观察量是 stop_reason，不是 trace。
3. **A4 伪造哈希的边界案例**：模型给的哈希 `54a5b453de9366b` 是 **15 位**（真哈希 16 位）——更像抄漏一位而非编造。现行 INTEGRITY 硬拒是刻意设计且有测试钉死；可议的口子是「unknown hash 恰为唯一已知哈希的前缀 → 按 FORMAT 处理」，动之前先过设计评审。
4. A7/A10 的 `repair_model_stop` + 核验降级：交付层按证据边界过滤是正确行为；剩余优化在语义核验预算。A5 日期错位待立案。模型自估 quick 但 governor 观察信号支持 deep 的升档问题（R7-A3 `model_requested_quick`）也留设计评审——governor 现在只把关不主动升档。
5. knevo 后续：suggest_options 缺口镜像、report→track 接力。
6. 工具沉淀待归位（Mac `~/harness-reference`）：「纠正层写自己的收据」「重试窗口尺寸取当前权威」「NULL 渲染按字段业务语义」「饿死判据用 stop_reason 不用 trace」候选 BUILD.md。

## 隔离环境现状

- **8797** = `cursor/repair-cold-restart-d7ac` @ 中转 terra（E2E 用，验证完可关：`lsof -nP -iTCP:8797` 找 pid kill；worktree `finance-workspace-5d611d19e6a3` 已 checkout 到 `54887fc0` 之前的 fix 提交）。
- **8794** = GLM Coding Plan（R6 质检遗留，可复用可关）。
- E2E 产物：`intelligence/eval/runs/20260813T04{30,37,44,50}Z-r{9,10,11,12}-a3-*.json`（Mac 私有仓，未提交）。

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
