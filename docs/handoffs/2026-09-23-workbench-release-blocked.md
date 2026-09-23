# Workbench 发布执行停在数据门

## 授权与结果

用户在确认部署对象是 Workbench 后回复「执行」。本轮承接的顺序是：核对 09-23 入库，缺口走正式 staging 流程；数据一致性与固定主线发布检查通过才切 8792，任一检查失败保留现网。

2026-09-23 晚间实际结果：**BLOCKED，未部署、未补库、未重启服务**。现网仍为 `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`；抓取远端并在收尾复核的发布目标为 `626d8a508c1c988ff094110b371987e6afdcdd15`。不要将本次「执行」改写为部署成功，也不要当作行情口径五问、候选合并或删除失败现场的授权。

主检出为他人的脏 detached 树；本轮独立树 `/Users/a77/fwp-wt-workbench-release-0923`，分支 `ops/workbench-release-0923`，由上述 main SHA 建立。无业务代码修改。

## 核查顺序与证据

本轮原始证据根：`/Users/a77/.finance-runtime/reviews/workbench-release-20260923/`。

1. GET 8792：`health-before.json` 为 HTTP 200 / healthy，runtime revision 为旧版，dirty=false、code_matches_repo=true；`readiness-before.json` 为 HTTP 503 / not_ready，仅 critical `market_data_consistency` 为 false。快照 09-23，数据库报告 09-22。存活不等于业务就绪。
2. 读取装机夜跑入口、同步源码与当晚日志。`daily-full-review.out.log` / `.err.log` 和 `runlog.md` 已复制留证。18:30 local 同步在 18:46 失败：东财 stock-daily 失败并完成一轮重试，同花顺独立采集成功，但下游 `fact_stock_daily` 无当日行，local 计算连锁失败；same-day gate rc=2，staging 未发布。20:40 finalize 也在 21:06 结束；另有 L2 09-23 日包缺失，但不是 readiness 唯一红项的替代解释。
3. 从干净 main 树执行现有只读检查器，分别指向 production 与 staging：`check_daily_review_data.py 2026-09-23 --phase data --plan local`。环境清空后只传 HOME/PATH、明确 DB 路径、禁 pyc、锁重试 1 次。两个检查均真实执行完成并返回 **rc=2 / INCOMPLETE**，不是锁阻塞；原始日志与 `.exit` 分别为 `production-data-gate.*`、`staging-data-gate.*`。
4. 生产 local 计划所查 19 张表均无 09-23 行；`fact_stock_daily` / `fact_market_daily` 到 09-22，多张板块与派生表仍到 09-18。09-22 的市场总览另有 13 个关键列出现基线外 NULL。staging 有 09-23 市场行与 31 个申万行业行，但市场行 13 个字段为空、个股当日 0 行，不能只凭日期前进就换库。
5. 对候选批次的原始 Python 收据运行 `check_test_receipt.py --expect-revision 626d8a508c1c988ff094110b371987e6afdcdd15 --require-full-scope --base-drift-max 5`，**rc=1**。原收据 `orphan-batch-0923/receipts/gate-SFFAGzfL/pytest.json` 签在 `53c51cfdcada10f6d06b0bb9278f89f6ba135e65`；14639P/0F/0E/85S/2X、collected=14726 对平，解释器/依赖/干净/全范围项通过，revision 与基座项拒绝。日志 `main-receipt-check.*`。
6. 树对树核对 preview 与 main 仅 8 份 docs 差异，清单 `preview-to-main-files.txt`。这解释代码等值，但验收规程明确要求精确 main tip 收据；没有改写旧收据，也未宣称 main 测试失败。共享目录中三份 626d8a50 收据在上一轮已查为 dirty 定向测试，本轮不据此放行。
7. 预检磁盘约 9GB，生产与既有 staging 各约 3.6GB，且多会话全量测试并行。未新增全仓任务，不打断他人进程，不清理备份/临时失败现场。收尾 readlink 仍指旧 runtime，远端 main SHA 未变。

## 处置取舍

| 方案 | 结果与理由 |
|---|---|
| 数据门红时保留当前服务，归档本轮检查 | 采用。满足已承诺的失败即停止条件，避免版本与数据问题混在一次变更里 |
| 直接重跑默认 daily-full | 未执行。默认链仍包含 fupanhui；当前正式夜跑为 local 计划，不能为了执行口令重启停采来源。今晚既有重试已给出同形失败 |
| 把现有 staging 直接换入生产 | 拒绝。当日个股零行、市场关键列为空；生产在 staging 形成后还有 L2 台账写入，旧副本也不能覆盖这些变化 |
| 从在途行情恢复分支拿桥和分母补丁写生产 | 未执行。恢复 owner 的交接仍 HOLD，独立验收和五问/三合同待确认；发布授权不替代金融口径裁决 |
| 改快照日期、放松 NULL 基线或 readiness 使门变绿 | 拒绝。只是隐藏数据缺口 |
| 接受旧 preview 收据冒充 main，或在低空间并发下立即跑全仓 | 未采用。旧证据保留原身份；数据恢复前不新增资源竞争 |

## 恢复入口

- 行情口径裁决页：`/Users/a77/fwp-wt-market-recovery-contracts-0922/docs/handoffs/2026-09-22-market-recovery-decision-page.md`；当时状态见其 inflight，不以本页代答五问。
- 行情修复 owner：`/Users/a77/fwp-wt-market-recovery-qc-fix-0923/docs/handoffs/inflight/fix-market-recovery-qc-0923.md`。本轮观察另有 `market-recovery-qc-20260923/timeout-followup/candidate@5213e9344` 全仓任务在跑；不把旧 inflight 的一次红写成后续任务的最终结果。
- 恢复 owner 完成代码准入与口径决策后，重取生产基线，走正式隔离 staging，恢复需要的历史与当日依赖，检查行数及关键列、same-day/cross-day/相关 L2 门，获准后原子换库；不复用过期 staging 覆盖新生产。
- 数据恢复后重新 GET readiness；协调磁盘和独占测试时段，在届时固定 main SHA 上完成完整 Python、前端、E2E、registry 与精确收据检查。再按 `docs/workflows/acceptance-workflow.md` 链切五步部署，保留回滚锚，核 health 三读、readiness 与真实交付探针，写唯一部署账本。

本轮没有启动后台续跑器，不会在条件改变后自行部署。没有新增通用工具或方法论：既有数据门和收据校验器已可复现本轮阻断，复用现有门即可。
