# 全工作区遗留收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute each independent task, with Spec review followed by Standards review before acceptance. Steps use checkbox syntax to track actual completion.

**Goal:** 接手 Gitea 与本地的剩余工作，逐项核实、补齐或给出有证据的处置；有效修复经 GitHub 验收合并部署，废弃和被接替记录明确关闭，闲置工作树保全后回收。

**Architecture:** GitHub `origin/main` 是唯一集成基线，Gitea 保留历史与恢复引用。把工程合入、内容质量、历史样本有效性和工作树回收分开验收；先盘点原件与运行引用，再逐树操作。pi 活动线、生产代码与数据根、回滚锚以及仍被进程/启动器引用的路径必须保留。

**Tech Stack:** Git/gh、现有 Gitea API、Python 工作台环境、`worktree_board.py`、`worktree_closeout.py`、既有测试和发布收据。

---

基线：`c84034070451e1d40f8e45ddd8adc40af87f4f34`。当前生产代码 `45a7dcfc219f70fce58c17a7487d05e6c969f403`；二者只差两份发布文档。上一轮证据位于 `~/.finance-runtime/reviews/workspace-closeout-1003/`，本轮原件与操作收据位于 `~/.finance-runtime/reviews/workspace-global-closeout-1003/`。

## Task 1：冻结队列和保留范围

Files: 本计划；仓外 `inventory.json`、`retention.json`、`progress.json`。

- [x] 保存 GitHub/Gitea 开放 PR、完整分支头、75 棵工作树的 HEAD 与脏文件状态；逐项分支表 `all-branch-dispositions.json`，树采样在 `tree-plan/snapshot.json`。盘点为 09:27 UTC，非最终状态。
- [x] 核对 pi 的 output-provenance、plan-ownership、owner-output 及解释器/规格依赖，写入 `tree-plan/retention.json`；未代其修改或发布。
- [x] 核对生产软链、三个夜跑任务、运行进程 cwd/打开文件和启动器引用；逐项保留理由在 `tree-plan/plan.json`。主检出数据根与当前任务树保留。

## Task 2：回答能力遗留 #956

Sources: Gitea PR #956；`docs/verification/2026-09-28-answer-capability-evaluation.md`；`docs/verification/2026-09-29-pi-continuation-review.md`；对应冻结材料和裁决。

- [x] 对照 PR #24 与当前主干完成工程/试验/质量分账及 pi 重叠边界；`quality956/audit.md` 核对 82/82 原件、61/61 内嵌副本，未确认可立即窄修的无人负责产品缺陷。
- [ ] 对仍可复现且无人负责的问题定位第一次偏差，先使用冻结输入与离线探针；只有离线证据不够才做有界、模型身份可核验的真实对照。
- [ ] 有可修代码时另列具体文件和验收针，最小修复后走独立 Spec、Standards 和适当测试；不以更长提示或关闭硬约束冒充质量改善。
- [ ] 原标准不能通过时保留失败/不可追溯裁决及原件，写清已交付与未证明的边界；Gitea 旧 PR 关闭必须带实际接替 PR 或明确废弃理由。

## Task 3：工具差值审计遗留 #966

Sources: Gitea PR #966；`feat/tool-usage-differential-p0-0929@899450108332e40dd2b8cf8e6226ab0764b01b9a`；`scripts/audit_tool_usage_differential.py`；原任务 R-20260827-14。

- [x] 查找原 747 样本 manifest、额外探针身份和可信 run→revision 原件；检索范围与原件身份在 `audit966/`，私人运行正文未进入公开仓。
- [x] 重建清单 747/747 哈希一致、两套算法聚合数一致；恢复 4/747 可信外部版本映射，余 743 保持未证明，未推断整批版本跨度。
- [x] 独立复核 19 份证据文件和四组映射的 20 件外部原件；原严格验收仍 `HISTORICAL_STRICT_ACCEPTANCE_NOT_PROVEN`。同期原始整批清单未恢复。
- [x] 2026-10-03 09:58:07 UTC 留下 GitHub #25 接替和明确历史裁决后关闭 Gitea #966，未合旧分支；回读 `closed/merged=false`，收据 `gitea-pr966-closeout.json`。

## Task 4：旧流程 #991 与工作树逐项回收

Sources: Gitea PR #991；`docs/workflows/dual-remote-collaboration.md`；`scripts/worktree_closeout.py`、`scripts/worktree_safety.py`。

- [x] 核对旧双远程流程已被 GitHub PR #5（`94628fbe800993049f73e2a3d6724516fb0974e9`）与后续备份实现接替；2026-10-03 09:28:46 UTC 留评论后关闭 #991，head 保留。操作与回读见仓外 `gitea-pr991-closeout.json`。
- [x] 75 棵各有一条具名处置；工程落地同时核提交/补丁/源文件身份，旧实验明确保全而不恢复。
- [x] 对第一批 35 棵和原件释放后的第二批 12 棵生成 fresh dry-run，根代理独立复核。第二批一棵因启动器引用保留，未绕过门禁。
- [x] 两轮按原收据 apply：35 + 11 = 46 棵完成保全回收，0失败/0临时跳过；`cleanup-round1-candidates/apply-20261003T174832.json`、`cleanup-round2/apply-20261003T175639.json`。此时余 29 棵；不删除分支或恢复引用，不冒用其他聊天的 artifact。
- [ ] 主检出保留且不丢用户数据；其可识别的在途源码先对账和保全，不把混合树测试当版本验收。旧 refs 和回滚快照不为减少数量而删除。

## Task 5：发布、备份与最终全量对账

Files: 本计划；`docs/handoffs/inflight/codex-workspace-global-closeout-1003.md`；日期交接快照；必要的最小代码修复。

- [ ] 任何产品代码修复都在独立分支通过本机等价检查与 GitHub 所需检查后合并；按实际合并代码创建新运行快照并验证真实会话。纯记录变更不重复重启服务。
- [ ] GitHub/Gitea 每张原开放 PR 必须有已合、明确接替、拒绝或仍在实际处理的证据；不静默关单、不改写旧失败。
- [ ] 重新扫描全部工作树；每棵剩余树有具体保留理由，每项可交付工程有合入与部署身份，真正未完成项单列，不能以“本轮完成”代称全仓完成。
- [ ] 运行 GitHub→Gitea 备份并核验回读；回写能力/项目索引时保持工程与质量结论独立；最后给出当前数量与完整收据。

## Task 6：恢复漏收的看板日期提示

Source: `5944c1d783f1c04185d90f371cdf7de0fc287989`；仓外 `tree-plan/unlanded-source.json`、`staleness-5944c1d78-original.patch`。这是旧功能收尾，不恢复整个旧 App、样式或静态构建包。

Files: `intelligence/services/workbench_overview.py`；`intelligence/tests/test_market_freshness.py`；相应 overview/API 测试；`intelligence/webapp/src/{types.ts,App.tsx,styles.css,components/StaleDataBanner.tsx,components/StaleDataBanner.test.tsx}`；必要的应用接线测试。

- [ ] 对照原提交，只恢复最近已收盘交易日的日历计算、overview 字段、类型、提示组件和当前页面接线。沿用上海时区与盘后 15:30 阈值，缺日列表最多 30 个，不触发抓取或写库。
- [ ] 补齐无日期、坏日期、未来日期、未知日历、节假日/盘中/盘后边界，不能误把未知或非法日期说成最新。历史查看日期与数据库最新数据日期分别表达，不能用历史选择制造同步告警。
- [ ] 使用冻结时刻和临时 DuckDB 验证真实 overview 响应及前端消费；覆盖提示、隐藏、未知状态和窄屏展示。当前路由、检查器默认状态及主题样式不随旧提交倒退。
- [ ] 独立 Spec、Standards 审核后纳入本轮 GitHub PR 与部署。

## Task 7：收尾 AIHOT 手动导入入口

Source: 主检出 `docs/handoffs/2026-09-29-river-aihot-attention.md` 与冻结的两个 CLI、分页测试；当前主干已有 `opinion_attention` 适配/追加与只读 UI。

Files: `scripts/{import_aihot_attention.py,pull_aihot_attention.py}`；`tests/test_{import_aihot_attention,pull_aihot_attention}.py`；`docs/learning/ledger-map.md`；`docs/examples/aihot-attention-mapping.example.json`（已有则核验）；必要的使用文档。共享服务只在真实导入缺陷可复现时最小修改。

- [ ] 恢复离线导出导入和显式实例拉取入口；默认只预览，只有 `--apply` 追加既有私有观察台账，共用原文件锁与版本链。映射必须显式输入，不猜来源独立性/板块归属。
- [ ] 网络拉取仅访问给定实例；分页、响应大小、条数、时限有界，分页不完整/重复游标/坏契约/冲突重复项整批拒绝，不写部分结果、不继续访问文章原文。HTTP 重定向也不能隐式扩大目标范围。
- [ ] 离线 CLI 与模拟 HTTP 测试覆盖 dry-run 零写入、`--apply` 临时台账幂等、坏输入零追加、分页完整性及边界。原件错误不通过修改原件遮掩；不运行真实生产导入、不配置新后台采集或定时任务。
- [ ] 注册唯一台账路径/写入者，提供无密钥且明确占位的映射模板与操作说明；说明上线入口不等于已接入真实 A 股资讯源。
- [ ] 独立 Spec、Standards 审核后纳入本轮 GitHub PR 与部署。
