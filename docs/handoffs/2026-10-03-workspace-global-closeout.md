# 全工作区遗留工程收口与第二次发布 · 2026-10-03

本轮通过 [GitHub PR #28](https://github.com/moscrol/finance/pull/28) 合入并实际部署 `ffe1c60d84da1c36e3e5d27a53f3ecf43536905b`。8792 工作台和三个夜跑入口均使用该快照；上一轮 `45a7dcfc219f` 保留为直接回滚。本文是已发生动作的快照，后续纯文档提交不改变运行版本。

## 背景与发现顺序

用户授权接手无人负责的优化，质检、收尾、合并、部署，并核对 GitHub、本地 Gitea 和工作树。上一轮 #24–#26 的发布见 [此前发布记录](2026-10-03-workspace-release-closeout.md)。本轮以 `c84034070451` 为盘点基线，保留 pi 的 `feat/harness-output-provenance-1003`、相关计划/输出归属分支和其解释器依赖。

1. 冻结全部本地、GitHub、Gitea 分支及 75 棵工作树，核对原件、来源和运行引用。旧 #991 已由 GitHub #5 接替；旧 #966 的工程由 #25 接替，历史整批身份仍未证明。分别留下具体理由后关闭旧 PR，保留原 head。
2. #956 原件仍在，不能以“证据丢失”结案。完成原件身份核对和固定 `45a7dcfc219f` 的有界原题重跑、首轮偏差定位及独立内容裁决，再留下 GitHub #24 接替指针关闭旧 PR。原质量未通过，具体见 [遗留优化对账](../verification/2026-10-03-legacy-optimization-closeout.md)。
3. 对闲置树执行具名保全和回收，两轮共 46 棵。主检出 148 项混合改动逐项分类，源码缺口单独恢复；未重置主树、移动数据根或删除恢复引用。
4. 恢复漏收的看板数据日期提示：以最近已收盘交易日核对数据日期，处理未知、非法、未来日期和日历边界；历史浏览选择与数据库最新日期分别表达。冻结时刻、临时 DuckDB、API 和前端消费均有验证。
5. 收尾 AIHOT 离线导入与显式实例拉取 CLI：默认预演，显式 `--apply` 才写私有观察台账；映射显式提供，来源未知保持未知。分页、响应大小、总条数、总期限有界，拒绝不完整批次和重定向扩权。另修复损坏历史台账的拒绝边界。
6. GitHub 暴露超时回归测试只接受一种合法竞态。复核真实 socket 超时与总期限两条路径均拒绝写入，修正测试预期；生产总期限仍受约束。最后候选完成本机完整门禁和独立规格/标准复审后合入 #28。
7. 创建实际合并提交的独立运行快照，核对解释器、依赖、配置包与待恢复任务；停止旧服务后复扫，切换指针和三个夜跑入口，再核验 health、readiness、账本与真实会话。
8. 追加生产离线 CLI 预演、全用户任务扫描和 GitHub→Gitea 备份回读。部署助手的异常恢复审查发现两处问题：原子替换失败会遗留临时软链、部分停止失败会漏恢复原已加载服务。均在私有助手修复并用隔离故障注入验证，未为测试再次切换生产。

## 工程验收身份

- 最终候选 `ea08a208f0a5ff67a1c28c1e83469eb372b8b192`：干净树 Ruff、完整 Python **20,334 passed / 78 skipped / 2 xfailed**，收集 20,414 条，无范围收窄。`check_test_receipt.py --require-full-scope` 在该原版本复核通过。
- 候选与合并提交的 Git tree 均为 `5c7f68933d2954e3b47980e0bdd0e6823bf6d94a`。这是内容相同的证据，未改写收据 revision，也不把它称为合并 SHA 的本机重跑。
- 前端验收：209 项组件测试、52 项 E2E 通过、2 项既定跳过，lint/typecheck/build 通过。最终 delta 只有超时测试，前端与注册表范围逐字未变；原收据身份和差异对账分别保留。
- #28 GitHub python、frontend、e2e、registry-check、workbench-check 全部成功。没有触及条件 data-quality-check 的路径。
- 日期提示独立 Spec / Standards 均 PASS；AIHOT 最终 Spec / Standards 均 PASS_WITH_LIMITS、0 findings，限制包括未接真实上游、未启用采集计划。

原件目录：`~/.finance-runtime/reviews/workspace-global-closeout-1003/`。主要收据：`final-python-receipts/latest.json`、`release-frontend/frontend.json`、`final-unchanged-scope-equivalence.json`、`freshness-spec/`、`freshness-standards/`、`aihot-ci-spec/`、`aihot-ci-standards/`。阶段文件中的“in_progress”保留当时语义；最终结论以此处列明的完整收据为准。

## 实际部署与复检

运行软链指向 `~/.finance-runtime/finance-workspace-ffe1c60d84da`，具有独立 Python 3.12.13 venv。发布配置只改变既定代码/解释器根，数据、用户、日程和 `REVIEW_SYNC_PLAN=local` 保持原合同。Workbench 运行，三个夜跑任务已加载且空闲；本次未手动触发真实同步或 finalize 写库。

- health 的 revision、加载代码指纹、仓库指纹一致，代码树干净；readiness **13/13** 为 true。部署账本 revision 与 health 相符。
- 真实行情事实会话 completed、semantic passed，degrade/content-degraded/judge-unavailable 均 0，secret/public scan 均 0 命中。该单条烟测只证明发布链路与一条事实查询可用，不证明整体金融回答质量。
- 最终只读扫描 1,382 个有效持久化任务：1,340 completed、35 failed、7 cancelled，queued/running 均 0。它是扫描时点的观察，不能保证此后没有新请求。
- 使用生产快照真实 CLI、合成离线输入和禁网钩子预演 AIHOT：accepted=1、unknown_sources=1、mapped/grouped=0、written=false，隔离台账父目录未创建。没有访问真实 AIHOT 或把测试消息写进生产台账。

收据：`production-cutover-steps-ffe.jsonl`、`production-ffe-health-readiness.json`、`production-ffe-grounded-smoke.json`、`deployment-pending-runs-final-20261003.json`、`production-aihot-offline-dry-run.json`。

私有切换助手的局部故障注入覆盖四个初始 bootout 失败位置、候选账本失败、原子软链替换失败和成功路径。各失败情形均恢复五份原配置、旧指针及四个原已加载服务；旧恢复集合的负对照只恢复一个服务，确能检出缺陷。收据 `cutover-rollback-final-verification.json` 绑定助手 SHA。原审查代理连接失效后由总控完成复验，不冒称独立最终签字；没有测试真实 launchd 故障或双重回滚失败。助手是本次一次性脚本，旧状态和既有收据会阻止重跑，不作为通用部署器。

## 远程与工作树收口

2026-10-03 20:54（Asia/Taipei）回读：GitHub、Gitea 开放 PR 均 0。旧 Gitea #956、#966、#991 为 closed/merged=false，均有接替或裁决评论，原分支保留。

20:42 手动备份在 GitHub 元数据阶段失败；20:48 定时任务完成完整成功，后续独立核对 **335 个分支/标签引用全部匹配**，恢复 bundle 哈希正确，GitHub 源端未在该快照后漂移。失败记录保留，不能仅凭旧 success 推断恢复；本次 newer success 已包含生产 `ffe1c60d84da`。证据 `github-gitea-backup-final-verification.json`。

工作树计数为 **75 - 46 + 1 = 30**：回收 46 棵后剩 29 棵，本次新增一棵正式生产快照。逐树理由在 `remaining-worktrees-final.json`，主检出的 148 项分类在 `main-checkout-dispositions-final.json`，未声称主树干净。

保留类别包括生产与回滚、主数据根、当前任务、pi 活动线及其规格/解释器依赖、仍被启动器/安全采样引用的路径、其他 Codex/Claude 会话管理的树。存在祖先路径宽匹配的保守保留项，本轮没有绕过清理工具。分支引用数不等于未交付优化数，恢复备份也不等于代码全部获采纳。

## 决策与被否方案

| 采用 | 未采用 | 原因 |
| --- | --- | --- |
| 择取有效源码并保留来源身份 | 按旧分支整树合并 | 旧树混有私人材料、已否决实验和较旧产品合同 |
| 保留质量失败与工程交付两种结论 | 用门禁全绿改判金融质量通过 | 当前原题重跑仍有可复现的交付失败和口径错误 |
| 未知来源保持未知、导入默认预演 | 猜独立发布者或自动开始采集 | 入口验收不能证明上游内容与映射已审核 |
| 以切换前完整 loaded 集合恢复服务 | 只恢复已记录停止的服务 | 停止操作自己失败时，成功停止列表不是原状态 |
| 具名保全后拆闲置树 | 清空所有工作树或备份分支 | 活动依赖、数据根和其他会话恢复状态仍有用途 |

## 仍未完成的边界

pi 的输出归属/计划归属工作仍在进行，未由本轮代合入部署。只读最终采样时其 HEAD 已到 `ede3bcc5cc49`；这不是验收结论。

回答质量继续未通过：消息材料与财务传导各八问不可用；新数值财务六问可用、两问部分可用，整体 partial。相关产品边界与 pi 在途工作重叠；未通过扩大题型关键词、放宽来源校验或重复抽样制造通过。

AIHOT 尚未接真实资讯源，未配置自动采集；三个夜跑任务部署完成，但真实定时触发、外部 S7 并发锁及跨仓接收边界沿此前发布记录保留。全局收口不表示所有实验假设被证明，也不表示物理工作区没有任何未完成工作。

工具沉淀：可复用日期/导入/台账拒绝与超时回归已在 #28 源码中；一次性本机切换、配置扫描和故障注入留私有证据目录，因固定路径/版本/文件哈希不包装为通用产品工具。复用原则是按切换前状态恢复，而非按中途成功列表恢复。
