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

## 判决与新形状

- A1 三轮 31s/103s/85s **均为 `standard`**，非路由方差；~30s 是 standard 90s 被合成保留（75→2/3 钳 60）挤出的检索分配段。
- 新形状（待立案）：30s 窗内 provider 到货但模型没吐合法修复 FINISH（`repair_model_stop`×4、`invalid_repair_finish`×1）；A3 `continuous_runtime_failed`；A1-R2 主路径超时+零证据。

## 可迁移

1. **纠正层要写自己的收据**：`repair_model_retry` 带 `timeout_asked/seconds_granted` 落产物，窗口对不对一眼可判——没有这两个数，「没重试」和「重试了但窗口太小」不可区分。
2. **重试窗口尺寸取自当前权威（ledger headroom），不能取自被中途替换的旧字段**。
3. **fail closed 的记账要配 settle 兜底**：烧爆账本恰是补救层最该工作的时刻。
4. 工具归位：`scripts/dump_episode_receipts.py`（验收 run → 逐题修复收据表）。

## 环境

canonical 8792 = `a317f37f`；生产 run 目录在 `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`；两轮验收均在凌晨（中转最差时段），公平对照待白天重跑。
