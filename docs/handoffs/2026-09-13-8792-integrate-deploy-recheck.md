# 2026-09-13 8792 版本对齐 + 部署 + T2/T3 复验 决策快照

## 背景

用户清单推进到「整合主干＋材料路由修复，验收后部署，固定参赛版本；复跑 T2→T3；补数据与 L2」。
开工前的事实：8792 跑 2efdff46（落后主干 100 提交）；路由长度闸与探针在
`claude/knevo-8792-config-validation-d17b44`（未合）；交易日修复在 `fix/trading-day-calendar`（未合）；
撤 Grok 改 K3 自审 09-12 已切生产（启动器侧，与本仓代码无关）；09-11 行情三表已补、
L2 只有 limitup 33 行。

## 按发现顺序

1. 读 intake 交接 + 两分支交接，确认待合的只有上述两条分支（task-frame-clarify 与 L2 顺序分支已在主干）。
2. 开 `fix/8792-integrate-routefix-tradingday`（基 127fa513），两分支 merge --no-ff 均无冲突。
3. **假象事故**：合并后核对 diff 时报「789 文件 −116k 行」——实为 bash 每条命令重置回主检出树，
   HEAD 是别人脏树 b4a35fa2，不是集成树。用 `git -C` 复核后集成真实 diff 仅 16 文件 +1817/−148。
   同一陷阱后续又让全量 pytest 在主树白跑两次（4 failed 全是别树/既有问题），
   集成树真实结果 9540 passed / 0 failed。教训已入 `.claude/lessons_learned.md`。
4. 部署：新快照 worktree `finance-workspace-2ee664fae9c4` + 移 symlink + `deploy_workbench_runtime.sh`
   （WORKBENCH_REPO_ROOT=集成树，FINANCE_WS=主检出树——账本写主仓 state/）。健康全绿。
5. 小样检索题验证新构建全链（llm.used、judge repaired、complete）。
6. T2 第 1 次弃权（TimeoutError→judge_unavailable）；第 2 次实质答卷，双分母/边界全对。
7. T3 第 1 次 failed（HTTP 502×2）、第 2 次弃权（judge_unavailable）、第 3 次实质答卷，
   K01/K02/K04/K05 逐条命中。网关直测健康（200/4.6s）→ 失败是**自审调用**在长上下文上不稳，
   不是写手链路。
8. L2：ops 台账显示 09-11 top100=failed（input_count=0，当时行情零行）、quant 未跑。
   行情已补后直接跑 canonical 管道（无 --force-rescan：非全 complete 自动重跑），
   复用缓存 7z（尺寸匹配跳过下载），limitup=33/top100=100/quant=37 全 complete 非空。

## 决策表

| 决策 | 方案对比 | 结果 |
|---|---|---|
| 合并策略 | A 两分支顺序 merge --no-ff 进 main（选）／B 各自开 PR 等审／C 只部署路由修复 | A：用户已拍板「整合主干」路线；B 多一轮无门禁的等待；C 被用户在上一轮否过 |
| 部署形态 | A 新快照 + 移 symlink（选）／B rsync 盖 2efdff46 快照 | B 会让快照内容与 HEAD 脱节（source_dirty=true），且丢回滚锚 |
| 自审 50s 预算 | A 先归档失败样本、不改（选）／B 当场提预算 | B 是 runtime 改动：无环境旋钮，需设计+测试，不在「部署已验证修复」范围内 |
| L2 补数 | A canonical 管道（选）／B inline SQL | 项目红线：写入只走既有管道 |
| 复验时机 | A 部署后立即复验（选）／B 等数据全齐 | 材料题不依赖当日盘面（intake 已定） |

## 验证与收据

- 集成树 pytest：9540 passed / 77 skipped / 2 xfailed / 0 failed（2ee664fa，5 分 31 秒）。
- 对照：主树 b4a35fa2（脏）4 failed、127fa513 干净检出 3 failed（conversation_orchestrator
  + scripts_module_references ×2）——main 既有，非本次引入，未处置。
- 部署收据：deploy-ledger switch → 2ee664fae9c4；健康 source_dirty=false。
- 探针 run：小样 run_20260913_034456_704436；T2 run_20260913_035722_162700（第 2 次）；
  T3 run_20260913_041146_035132（第 3 次）。 RESULTS-2026-09-13.md 有逐轮指标。
- L2 台账：ops_pipeline_run_daily 09-11 三 step 全 complete。

## 后续要做 / 不要做

**要做**：未见新题全新会话正式 PK（先冻结 8792 原答）；自审预算缺口的正规修复
（旋钮化 → 提预算/重试，验收用本次 3 个失败 run）；hithink 换库等 QC 复审 + 用户授权。

**不要做**：
- 不要把这次 T2/T3 通过当能力结论——单一样例、揭盲后、T3 上下文非纯净。
- 不要在主检出树提交任何东西：那里有 6+ 个别人的在途改动（含 theme_flow sync 脚本）。
- 不要把 ASK_EVIDENCE_JUDGE 关掉就当「关判官」——它与终稿自审是两条链（启动器注释有史）。
- 不要凭 2efdff46 旧快照的存在就假设可回滚配置：启动器配置与快照是两份状态，
  回滚要同时回 symlink 与启动器（bak-20260912-pre-nogrok）。
