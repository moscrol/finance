# 在途交接 · main

更新：2026-08-13 16:15 CST · #323 已部署；#317 注入判决=部分证伪（自愈盲区）

## 这个分支做什么

生产基线。今日循环：#316/#317/#319/#321/#323 全部合并，前四个有生产判决。

## 当前状态

- **8792 = `dd3d6b64`**（含 #323 熔断 1→2），rag ready（预热 107s）。
- readiness 缺 `market_data_consistency`：收盘后快照=08-13、DuckDB 待今日
  复盘回填——**日常节奏非故障**，跑完 daily-full 自然绿。
- **#317 注入判决（R23）＝部分证伪**：杀 worker 子进程后跑 B1（144.7s
  completed），worker 全程 `cold/active=0` 没被拉起。机制：`kb_rag` 只在
  `worker_enabled and not filters` 才走 worker，**带 filters 的分层检索
  直接走 CLI**——查询不经过 worker 就永远不触发查询失败式自愈。
  「进程死亡 + 后续全是 filters 查询」= readiness 永久红，只能 kickstart。
- #323 上线未判决；#319 满窗已过 R22 机制判决。
- 隧道 15:35–16:00 曾 530（cloudflared 波动，Mac 未睡未重启），已自愈。

## 未验证 / 已知边界

- #323 生产判决：需收据出现两次 `repair_model_retry` 且第二笔 grant_id
  带 `-2`、第二发救回——明早 10–11 时复跑 B 组对照 R15/R21。
- R23 产物 `20260813T0805Z-r23-selfheal-inject.json`（Mac 私有仓未提交）。

## 下一步

1. **修自愈盲区**（R23 打出的洞）：二选一——①自愈入口从「查询失败」扩到
   「status 发现 enabled 且 active=0 且非 warming」（readiness 探针处调度）；
   ②kb_rag 让 filters 查询也走 worker（需 worker 协议支持 filters 参数）。
   ①改动小且不动检索语义，推荐先做①。
2. 明早 10–11 时 B 组对照（#319+#323 双发判决）。
3. knevo 接力（suggest_options 缺口镜像、report→track）：材料齐，等拍板。
4. governor 升帽已被取证证伪（成功修复调用 max=27.8s），别再立案。

## 踩过的坑

- 注入判决要盯「被测机制的入口条件」：#317 入口是 worker.query 异常，
  filters 查询根本不进这个入口——测试放行≠生产覆盖。
- `state=cold`（杀进程后）与 `failed`（超时后）是两个不自愈形状，前者
  连 last_error 都不留。
- 修复延迟分布用事件 `at` 时间戳可还原删失（本轮两次手工，第三次用时
  应固化成脚本；未固化原因：需访问生产 runs 目录且口径仍在变）。

## 已验证

- 8792 @ dd3d6b64 rag ready（16:14 实测）；R22 满窗判决；R23 注入判决。
- repair/episode 相关 577 条、orchestrator 相关 372 条全绿。
- 云端全量 15F/4149P，flaky 归零，15 红全为已立案环境差异。
