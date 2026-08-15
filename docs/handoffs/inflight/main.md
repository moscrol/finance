# 在途交接 · main

> 指针（2026-08-13）：复盘会资产线**代码已收口**，完工快照 `docs/handoffs/2026-08-13-fupanhui-public-assets-and-consume.md`。dragon 双表主库回补已完成（summary 390/390、seats 近 60 日 44932 行），两表已进 `GAP_TABLES` 断档门禁。

更新：2026-08-16 01:00 CST · **8792 已切到 `437cd5e9`**（R-24 部署窗；当时 main tip）。完工快照 `docs/handoffs/2026-08-16-r24-deploy-window.md`。旧快照 `fdb23114` 保留可回滚。
更新：2026-08-14 18:45 CST · **8792 已切到 `32f73f53`**（#351/#352/#353/#354 合并后的 tip，一次性追平此前落后的 33 个提交）。完工快照 `docs/handoffs/2026-08-14-cutover-8792.md`。
更新：2026-08-14 18:00 CST · #343 完工快照补齐：`docs/handoffs/2026-08-14-review-gate-duckdb-lock.md`（夜跑链路已生效，与 8792 无关）。
更新：2026-08-14 16:30 CST · #345/#346/#347 已合 origin/main，**尚未切 8792**。完工快照：
`docs/handoffs/2026-08-14-smoke-gap-anchor.md`、
`2026-08-14-l3-evidence-title-only.md`、
`2026-08-14-tool-observability.md`。
更新：2026-08-13 17:10 CST · #327 缺口镜像已部署，R25 生产判决通过

## 这个分支做什么

生产基线。今日循环：#316/#317/#319/#321/#323 全部合并，前四个有生产判决。

## 当前状态

- **8792 = `437cd5e9`**（观测台 Phase 1 闸对账：live health `source_revision`；历史「更新」行仍可能过期，以本行 + `/api/health` 为准）。
  其后 docs-only main tip 不追切。readiness 缺 `market_data_consistency` 为收盘后日常节奏。
- **R25 判决通过**（#327 缺口镜像 = knevo 接力第一片）：B1 降级 0 证据时
  消息带 3 张「缺口补齐」卡（type=gap，label+full_prompt，契约口径，
  零模型调用），`/api/runs/{id}/followups` 可读。episode 主路径首次接上
  猜你想问通道。
- **R24 判决通过**（#326）：杀 worker → 探针调度 → T+142s 自动 ready，
  零 kickstart。R22（#319 满窗）判决已过；#323 待明早对照。
- 隧道今日两次 530/502 波动（cloudflared，Mac 侧正常），均自愈。

## 未验证 / 已知边界

- #323 生产判决：需收据出现两次 `repair_model_retry` 且第二笔 grant_id
  带 `-2`、第二发救回——明早 10–11 时复跑 B 组对照 R15/R21。
- 候选②（filters 查询走 worker）未做：改 worker 协议动静大，另行论证。
- R23 产物 `20260813T0805Z-r23-selfheal-inject.json`（Mac 私有仓未提交）。

## 下一步

1. 明早 10–11 时 B 组对照（#319+#323 双发判决）。
2. knevo 接力第二片 **report→track**（q8 蒸馏：delta-only + 观点四态 +
   下期关注触发条件自衔接）：要拍两个板——基线落哪（wiki vs users 私有层）、
   首个题型（推荐 theme-radar）。
3. 缺口文案质量：R25 第二张卡显示 `chain_mapping`——上游部分契约输出的
   description 是机器 ID 风格，镜像如实呈现；改进属 task_frame 契约生成侧。
4. governor 升帽已被取证证伪（成功修复调用 max=27.8s），别再立案。

## 踩过的坑

- 注入判决要盯「被测机制的入口条件」：#317 入口是 worker.query 异常，
  filters 查询根本不进这个入口——测试放行≠生产覆盖。
- `state=cold`（杀进程后）与 `failed`（超时后）是两个不自愈形状，前者
  连 last_error 都不留。
- 修复延迟分布用事件 `at` 时间戳可还原删失（本轮两次手工，第三次用时
  应固化成脚本；未固化原因：需访问生产 runs 目录且口径仍在变）。

## 已验证

- 8792 @ 7d379b07（16:44 实测）；R22 满窗、R23 盲区、R24 探针自愈三判决。
- repair/episode 相关 577 条、rag_worker 18 条、orchestrator 372 条全绿。
- 云端全量 15F/4149P，flaky 归零，15 红全为已立案环境差异。
