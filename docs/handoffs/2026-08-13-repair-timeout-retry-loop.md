# 2026-08-13 · repair 超时重试闭环（#296 + #297）

一晚完成「实现 → 部署 → 生产验收 → 按收据修缺陷 → 隔离验证 → 再合并再部署」两圈。云端 agent 经 Mac 隧道（`rx.py`）远程执行取证与部署。

## 问题

`agent_episode.resume()` 对修复轮 LLM 超时一击终局（`repair_model_unavailable`）。修复授予 `min(剩余,30,缺口×8)` 常仅 16s/8s，`llm_timeout=75`，第一发 timeout=整笔授予，烧穿后余量≈0——provider 链内重试拿不到窗口。R2 四题、R3 A7 死于此。

## 第一圈：#296（`190abf21` 合并）

瞬态判据单一真本源 `is_transient_model_error`（补 HTTP 504 / model deadline exhausted）；`grant_for_transient_model_retry` 从 root hard-cap 未分配余量铸 ≤30s 重试窗；repair/repair_finalize 共用熔断 1 次；失败保草稿保绑定。4 条烧真实时钟测试钉死首版空操作（ScriptedModel 瞬时返回、时钟不动的假绿）。

**R4 生产验收**（`eval/runs/20260813T0159Z-r4-repair-retry.json`）：重试触发 5 次**全部再超时**——

- 缺陷 1：铸窗尺寸抄 `goal.remaining_seconds`（admission 已替换成刚烧穿的 16s/8s 授予），对 P50≈28s 中转原样再撞（A4/A5/A8/A9/A10）；
- 缺陷 2：耗时略超账本残余 → `consume_seconds` fail closed → `budget_alive=False` → 连重试闸门都进不去（A6/A7）。

但机制本身生效：A1/A2 修复成功；A2/A5/A8 保草稿兑现（失败不再归零）。

## 第二圈：#297（`a317f37f` 合并）

尺寸改 `min(hard_seconds_cap−allocated_seconds, 30)`；记账失败先 `settle_seconds` 结平再铸。新增 A6/A7 形状回归（overshoot 0.5s 烧爆账本仍重试）。

**R5 隔离验证**（8794 @ fix 分支，`eval/runs/20260813T0245Z-r5-headroom-fix.json`，A4–A10）：重试窗全部 `asked=30.0`；A4 完整走通（`repair_model_finish`，2 证据 0 降级）；A6/A7 进闸门；降级 6/7→2/7，带证据 2/7→5/7。

## 第三圈：R6 本地 GLM 质检（不改 8792）

用户要求「不用中转、用本地 GLM」。本机没有 ollama/vllm；本地 GLM = Keychain `finance-workbench-glm` + Coding Plan。

| 通道 | 环境变量 | URL | 结果 |
|------|----------|-----|------|
| 官方 GLM | `ZHIPU_API_KEY` | `.../api/paas/v4` | HTTP 429 余额不足（半成品已杀，不当结论） |
| **Coding Plan** | `FORESIGHT_BUILTIN_LLM_API_KEY` | `.../api/coding/paas/v4` | 冒烟 8.2s「收到」；全 A 组可跑 |
| 中转 terra | 8792 生产 | `x.ailzd.com` | **未动** |

**R6**（8794 @ `a317f37f` / 源 `97642e26`，`eval/runs/20260813T0314Z-r6-glm-qc.json`，A1–A10）：

| 题 | 秒 | 证据 | 降级 | stop | 修复授予 |
|----|----|------|------|------|----------|
| A1 | 87.6 | 22 | 0 | `repair_model_finish` | 24s（主路径 TimeoutError 后救回） |
| A2 | 71.4 | 7 | 0 | `repair_model_finish` | 30s |
| A3 | 69.3 | 3 | 0 | `repair_model_stop` | 24s |
| A4 | 81.5 | 9 | 0 | `repair_model_finish` | **16s 首枪走通** |
| A5 | 28.7 | 4 | 0 | `model_finish` | — |
| A6 | 50.8 | 3 | 0 | `model_finish` | — |
| A7 | 57.0 | 9 | 0 | `model_finish` | — |
| A8 | 73.4 | 19 | 0 | `model_finish` | — |
| A9 | 77.6 | 6 | 1 | `model_finish` | —（语义/证据核验降级） |
| A10 | 45.0 | 0 | 1 | `repair_model_stop` | 16s |

对照 R5（中转，仅 A4–A10）：同题普遍更快、证据更多；A6 0→3 证据且不再降级。**零次 `repair_model_retry`**：GLM 修复首枪 16–24s 够用，30s 重试闸门空转是正确行为，不是漏触发。中转 R4 正是 16s 窗不够才需要那次重试。

R6 **不能**替代白天中转公平对照——换的是模型通道，不是把 R4/R5 的超时分布重跑了一遍。

## 第四圈：R7 白天中转公平对照（8792 生产，与 R6 并行跑）

**R7**（8792 @ 中转 terra，`eval/runs/20260813T0333Z-r7-relay-daytime.json`，A1–A10，白天时段）：

10/10 `completed`；7/10 无降级。**`repair_model_retry` 触发 3 次（A5/A6/A10），
全部 `asked=30.0 granted=30.0`，三题全部救回**（各 3 证据 0 降级）——这正是
R2/R4 里死于 `repair_model_unavailable` 的形状，`repair_model_unavailable` /
`repair_deadline_exhausted` 在 R7 **零出现**。A10 的完整链路：修复首枪 16s
超时 → 30s 重试 → `repair_model_finish`。A1/A2/A8 主路径超时由修复轮首枪救回。

R7 仍在的失败（下一批立案对象）：A3 `deadline_exhausted`（43s 0 证据）、
A4 `invalid_model_finish`（30s 0 证据）、A7 `repair_model_stop`（0 证据）。

三轮横向（同题同库）：

| 轮 | 通道 | 时段 | 完成 | 无降级 | 重试触发/救回 |
|----|------|------|------|--------|---------------|
| R4 | 中转 | 凌晨 | 10/10 | 3/10 | 5 次 / 0（窗 16/8s 太小，缺陷） |
| R6 | GLM Coding Plan | 凌晨 | 10/10 | 8/10 | 0 次（首枪够用，闸门正确空转） |
| R7 | 中转 | 白天 | 10/10 | 7/10 | **3 次 / 3**（30s 窗全部命中） |

## 判决与新形状

- A1 三轮 31s/103s/85s **均为 `standard`**，非路由方差；~30s 是 standard 90s 被合成保留（75→2/3 钳 60）挤出的检索分配段。
- 新形状（待立案）：修复窗内 provider 到货但模型没吐合法 FINISH（R5：`repair_model_stop`×4 + `invalid_repair_finish`×1；R6 GLM：A3、A10 仍是 `repair_model_stop`）。A1-R2 主路径超时+零证据（`tools_open=False` 时 `admit_repair` 拒）仍是另一条链。
- A3 `continuous_runtime_failed` 在 GLM 上消失，中转侧是否还在要白天对照。

## 可迁移

1. **纠正层要写自己的收据**：`repair_model_retry` 带 `timeout_asked/seconds_granted` 落产物，窗口对不对一眼可判——没有这两个数，「没重试」和「重试了但窗口太小」不可区分。
2. **重试窗口尺寸取自当前权威（ledger headroom），不能取自被中途替换的旧字段**。
3. **fail closed 的记账要配 settle 兜底**：烧爆账本恰是补救层最该工作的时刻。
4. 工具归位：`scripts/dump_episode_receipts.py`（验收 run → 逐题修复收据表）。
5. **同一把 key、两个 URL、两套配额**：`ZHIPU_API_KEY` → 官方 `paas/v4`（可能 429 余额不足）；`FORESIGHT_BUILTIN_LLM_API_KEY` → Coding Plan。health 都报 `zhipu/glm-5.2`，看 URL 才能分清。这在任何「兼容 OpenAI 的多入口供应商」都能用。

## 环境

canonical 8792 = 中转 terra（本轮未切模型）；隔离 8794 = GLM Coding Plan。生产 run 目录在 `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`。R4/R5 凌晨中转；R6 是 GLM 通道质检。中转公平对照仍待白天重跑。
