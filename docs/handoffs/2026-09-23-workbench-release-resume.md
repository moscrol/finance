# Workbench 发布续办：口径已定，候选门仍红

## 授权与结论

承接上一轮发布前检查后的用户「执行」，继续核对行情恢复与发布前置。本轮没有写库、合并、部署或启动新全仓任务。先前记录中的「五问三合同仍待用户拍板」已过期，不能继续作为阻塞理由。

## 新发现与证据

1. 22:14 重新 fetch，远端 main 仍为 `626d8a508c1c988ff094110b371987e6afdcdd15`；主树仍有他人改动，发布工作只在 `ops/workbench-release-0923` 独立树进行。
2. Gitea #861 评论 **6463**（21:29:53）记录了用户委托 Claude Code 代拍的原话、会话出处和逐项结论；#871 评论 **6468** 回指确认。是复用已有裁决，不是本会话自行代拍：
   - (a) 按 5565 声明范围恢复，5553 有 bar、12 具名停牌；保留 `official_historical_universe_verified=false`。这是原恢复日期的范围，不能直接套到 09-23。
   - (b) `turnover` 留 NULL，仅保留观测值，不冒充官方分母。
   - (c) `frozen_identity` 下停牌留分母，不造平盘 bar、不计涨跌家数；日更默认不变。
   - (d) 53 只公司行动争议保留缺行，第三源逐只仲裁，不放宽桥；两只分红金额分歧也不任选一方。
   - (e) 已停采来源和从未产出的占位表单列，13 张本地派生表仍属本轮恢复目标。
   - 三合同为 **1=B（过渡，目标 D）、2=A、3=A**。该评论的合并计划为 #871/#861/#874，经组合四叶后再合；没有因此批准绕过质量门或直接换库。
3. 恢复候选 `5213e9344b77e4094221734722b478705611a865` 基于上述 main。22:21:54 完整 Python 结束：**14903P / 4F / 0E / 85S / 2X，14994 collected，exit=1**。在原干净候选树跑 `check_test_receipt.py --expect-revision 5213e9344b77e4094221734722b478705611a865 --require-full-scope --base-drift-max 0`：身份、全范围、依赖、零基座漂移全部成立。校验器 rc=0 表示收据可信，**不表示测试通过**。
4. 四个失败均在 RAG worker（知识检索后台进程）的生命周期测试：`test_recovery_respects_cooldown`、`test_second_consecutive_timeout_kills_and_self_heals`、`test_single_bad_query_does_not_reclassify_worker_as_retired`、`test_close_stops_keepalive_thread`。未据此断言都是机器负载导致，也未将它们擅自豁免。
5. 同一候选前端完整测试 **118P/2F**，两项轮询测试超时；已有隔离诊断 **2P/79S**，不能覆盖完整红。候选另有 lint/typecheck/build/E2E exit=0，仍不足放行。原件见 `~/.finance-runtime/reviews/market-recovery-qc-20260923/timeout-followup/{full-gate,frontend-receipt,frontend-two-diagnostic}/`。
6. 空间从约 5.6GiB 变为约 21GiB，是并发会话的变化，非本轮清理所得。现有 `cleanup_gate_trees.sh` 的只读预览在 45 秒扫描期限后 rc=4，审计未完成，未删除树。对话中一度称「8GiB 是流程硬门槛」未经源码证实，已明确纠正，不将其写成约束或放行线。
7. 收尾现网 health=200、readiness=503，唯一 critical 红项仍 `market_data_consistency`；库 09-22、快照 09-23。runtime 仍 `3b7e473575b0`，干净且代码身份匹配。没有重复执行上一轮数据检查器，也没有把上一轮逐表结果标为本轮新读数。

本轮封存原件：`~/.finance-runtime/reviews/workbench-release-20260923/resume-2214/`，包含 #861 评论、候选 Python/前端收据和现网 health/readiness。此前数据检查继续引用 `../production-data-gate.log` 与 `../staging-data-gate.log`，不是本轮重跑。

## 决策与后续

| 选择 | 未选方案及原因 |
| --- | --- |
| 采纳已有明确口径授权 | 不再次要求用户回答五问；本地旧交接晚于事实更新不代表它权威更高 |
| 有效红收据阻止发布 | 不把收据校验 rc=0、隔离测试绿或高负载猜测当成全量通过 |
| 将新失败交还当前恢复/检索修复线 | 不修改他人的候选树或并开同一修复，避免版本与收据失配 |
| 保留现网 | 不因用户重复「执行」而跳过已约定的失败停止条件 |

继续入口：现有恢复 owner 先处理四个 Python 失败、两个前端失败，并与在途 RAG 修复协调；组合批准后的修复，固定版本跑完整门禁，再按现有合并授权收口。数据恢复需从新生产基线生成隔离 staging，按已裁定范围逐日验证，不能把 09-21 的范围常量或当前快照套到其他日期，也不能直接发布旧 staging。完整数据门与最新固定 main 的发布门通过后，才能切 8792 并完成探针和部署账本。

本轮没有后台自动续跑器。无需新增通用工具；既有收据检查器和只读清理预览已足够定位本轮边界。
