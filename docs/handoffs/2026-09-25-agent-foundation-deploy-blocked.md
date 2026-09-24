# 2026-09-25 Agent foundation 部署预检：切换前阻塞

## 背景与授权

用户在本批四张 PR 合入后明确要求「合并部署收尾」，本轮已获部署授权。Finance #907/#908、Harness #16、Memory #4 的 Gitea 回读仍全部为 merged；不重复合并。本轮未获得生产复盘数据回填授权。

本文件记录北京时间 2026-09-25 00:13 的观测，不是成功部署收据。机器证据根：`~/.finance-runtime/reviews/agent-foundation-0924/deploy/`，总状态见 `status.json`。

## 按发现顺序

1. 原生产链接仍指向 `~/.finance-runtime/finance-workspace-3b7e473575b0`；health 报完整 revision `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`、source_dirty=false、code_matches_repo=true。生产启动器使用主检出的共享 venv，与受测环境的依赖版本不同。
2. 切换前 readiness 已返回 HTTP 503。13 个 checks 中只有 `market_data_consistency=false`：行情快照为 2026-09-24，`fact_market_daily` 最新日为 2026-09-22。由候选的 `episode_tools.latest_market_date()` 只读复算，仍是 09-22，不是只抄旧 health 的结果。
3. 按 `docs/workflows/acceptance-workflow.md` 的全项就绪判据，在 bootout/切链之前停止部署。没有修改生产库、启动器或软链，没有触发真实模型探针。
4. 为保留可接续产物，新建干净 detached 候选 `~/.finance-runtime/finance-workspace-ea42fac4254b`，固定完整 SHA `ea42fac4254b9f15a7d8736caaa62a394e48bf43`。通过 `workspace.py bootstrap --install` 创建本树 venv，使用 Python 3.12.13 和开发锁；没有升级共享环境。
5. 候选 doctor ready、errors=[]、dependency_drift={}；与受测 closeout 环境的 57 项包清单完全一致。离线 smoke 2 passed。前端从受测树复制，3 个静态产物逐字节 SHA-256 相同。候选不曾作为服务启动。
6. 并发任务合入 #909 后，主干前进到 `03352758cf9b31e3f5d179b517be48cb89588679`，只有两份文档变化。精确版本门禁仍正确 exit 1：ea42 的收据不证明 033527。没有用「仅文档」放宽判据，也没有在数据阻塞期间重跑很快可能再次过期的整仓门禁。
7. 部署台账对账另报 exit 1：最后明确标为 8792 的 switch/startup 均为 3b7e，但随后有一条 `port=null` 的 f2101ad51929 startup，argv 指向 `capture-sidecar.py 8817`。这使检查器无法可靠归属；不能据此称生产跑在 f210。`homes` 通过，唯一家没有分裂。没有删除历史行或补造 switch 掩盖它。
8. 最终 health/readiness 回读仍是同一旧版本及同一数据日期阻塞；启动器与切前备份字节一致。候选及旧生产快照均干净。

## 决策与被否方案

| 选择 | 被否方案 | 原因 |
| --- | --- | --- |
| 就绪不全通过时停在切换前 | 先切再把 503 称为既有问题 | 工作流要求三项验证齐全；已有红项不能包装成部署成功 |
| 不自动补生产数据 | 为完成部署直接跑 daily-full 或改库日期 | 数据写入有独立授权和 staging/原子换库合同；日期对齐不能靠改标签 |
| 候选持有独立 venv | 升级主树共享 venv或默认沿用旧依赖 | 避免影响其他进程，且受测环境与实际运行环境必须可对账 |
| 原始完整收据继续只绑定 ea42 | 用旧 SHA 证明新主干/本交接提交 | 文档提交也改变版本身份 |
| 保留台账歧义证据 | 追加一次没有发生的生产 switch | 对账红项必须如实保留，不能伪造部署历史 |

## 验证与证据

- `pr-readback.json`：四张原 PR 均已合入。
- `before-health.json`、`before-readiness.json`、`final-health.json`、`final-readiness.json`：生产身份与切前已有的数据缺口。
- `market-date-readback.json`：候选函数对生产 DuckDB 的只读最新日复算。
- `bootstrap.log.txt`、`candidate-doctor.json`、`candidate-smoke.log.txt`、`environment-comparison.json`、`frontend-copy.json`：候选环境与产物准备。
- `main-receipt-check.txt`：主干前进后的精确版本门禁拒绝，不是测试失败。
- `ledger-check.json`：台账版本歧义；原始台账仍为 `~/.finance-runtime/deploy-ledger.jsonl`。
- `start-finance-workbench.before`：启动器备份；`status.json` 保留其 SHA-256。
- ea42 原完整验收仍在 `../merge/acceptance/round-02/`：Python 15363P/88S/2X、前端组件120P、E2E34P/2S，Ruff/registry通过。已复核前端和registry各六步日志哈希；不能据此称最新主干、生产或真实模型质量已通过。

## 接续与边界

1. 先获准按 canonical `daily-full` 链恢复缺失日期的数据；不得手写生产 SQL、回退行情快照日期或关闭一致性检查来过门。
2. 数据就绪后再 fetch，固定当时主干和独占候选，重新跑完整四叶门禁。ea42 候选现在不是最新主干，不可直接切入冒充最新验收。
3. 核实无端口 startup 的归属，按既有合同处理台账，不覆写其他任务的记录。
4. 部署前显式决定并验证生产解释器。现启动器仍硬编码主树 venv；创建候选 venv 不等于启动器已使用它。若改为快照内解释器，回滚必须同时恢复启动器备份和旧软链，因为旧快照没有本轮新建的环境。
5. 真正切换后再验 readiness 全项、health 三读、grounded 会话探针、台账对账及 Gitea 备份。当前没有做这些切后动作。

工具沉淀：本轮复用现有 workspace、收据、readiness、部署账本，没有新增可迁移工具或关闭/绕过门禁；台账歧义与数据缺口已被现有门禁检出。一次阻塞预检不足以另造部署框架，保留一手证据供有明确范围的修复单接续。
