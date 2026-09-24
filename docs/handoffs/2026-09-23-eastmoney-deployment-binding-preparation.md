# #60 部署绑定准备快照

## 背景

#856 已合入 `27ca084f9ffcb9d148b749944beca340e5f4fa6c` 且合后四叶绿，但仓内绑定与生产仍指旧同步根。用户随后要求「后续也继续推进，直到可以部署」。本轮完成准备、提交、发布与候选验收；依仓库的逐 PR 合入确认规则，已另询 #887 合入确认，尚未收到。不把推进准备的授权写成安装授权。

本页记录本轮完成时点；后续状态读 inflight 和证据目录最新索引。

## 按发现顺序

1. 共享主检出有大量非本轮改动，未触碰。新建独占分支 `fix/eastmoney-deploy-binding-0923`，起点为实际 `gitea/main@2edbe4c46595cbea3eb3abe04fe84a7bd5afd55e`；它已经包含 #856 和后来合入的 #883。#61 的 PR #871 仍 open，补丁未在 main，不纳入本批。
2. 代码地图在新树为空，先 build 再 query。核对安装器、两份 plist、S7 launcher、已安装 staging wrapper 和现有接线/安装测试。运行根从真实 main 独立检出为 `~/.finance-runtime/finance-sync-2edbe4c46595`，锁定 worktree 防误清理；未改旧根。新根的行情模块与同步器相对 #856 实际 merge 无额外差异。
3. 修改四文件五处同步根值，提交 `99bd31c97630988092a4f328126beedc18f74bfc`。安装副本与候选逐字段/字节比对：只变同步根，L2、生成根、S7包装、数据目录、DB、时间表、local档位和共享 helper 不变。定向迭代96P，提交 hooks 通过。
4. 推送并创建 WIP PR #887。创建接口超时，但先回读确认已经创建，未盲目重复 POST；正文逐字一致、head/base一致。
5. 在独占固定检出运行完整四叶；中途主机观测到其他全量并发及高负载，保存观察，不放宽断言、不缩收集面。Python首轮完整结果14620P/0F/0E/85S/2X，收集14707，约39分24秒；没有失败后挑样求绿。
6. 前端六命令全部通过，120单测，E2E34P/2S，六日志哈希通过。注册表最初在分支目录连相邻仓一起通过，又在隔离检出做本仓五项检查通过；合入依据使用后者，缺仓项不冒充已验，反向台账98条 warning保留。
7. Native收据完整范围/依赖/身份/漂移0校验及门禁回放通过，独立解析JUnit与汇总对平。相关96项在全量内且全部通过：wiring33、installer20、breaker18、transport19、snapshot6。
8. 候选nightly-only dry-run通过；真实候选在临时HOME、替身launchctl下模拟安装通过，恰好四个文件、两个job、无kickstart。实际新运行根离线导入/熔断/兜底探针通过，无外呼、无DB打开、无真实采集子进程。
9. 六个小型安装文件做准备快照，逐文件比hash与权限；只读加载配置仍为旧根。最后再次核对安装副本未变、候选根干净。PR正文更新为验收结果并回读一致，WIP仍保留。临时前端/Python门禁树回收，绿色basetemp由runner清理；所有本轮门禁进程已退出。运行候选根和树外证据保留。

## 决策与被否方案

| 选项 | 评价 | 结果 |
| --- | --- | --- |
| 固定当时最新真实main 2edbe4c46595 | 含#856且来自真实main；运行根身份可验证 | 采用 |
| 复用旧候选01e25264f218或原脏热补根 | 前者缺修复，后者混合历史热补与产物，不符合干净根要求 | 否决 |
| 从运行根直接执行installer | 功能代码具备，但其模板仍指旧根，会装错版本 | 否决；装机源须是含绑定的实际main |
| 同一提交既命名运行根又记录自身SHA | 内容改变会再次改变SHA，形成循环依赖 | 否决；功能根与绑定提交分离 |
| 顺带合入#61 | 涉及换源/口径与其他授权，且当前未合 | 不纳入本批 |
| 为赶18:30使用旧Plan B | 不完整且无安装/热补授权，时钟不构成授权 | 否决 |

## 证据

证据根：`~/.finance-runtime/reviews/eastmoney-cb-deploy-20260922/deploy-binding-20260923/`。

- `premerge/python/gate-BhctypuZ/pytest.json`、`premerge/python/junit.xml`、`premerge/receipt-check.log`、`premerge/gate-replay.log`、`premerge/junit-check.json`。
- `premerge/frontend/frontend.json`、六份命令日志；`premerge/registry-isolated/`。
- `premerge-final-preparation.json`、`runtime-offline-probe.json`、`installation-sandbox/record.json`、`installed-snapshot-preparation/record.json`。
- `publication-verified.json`、`deployment-plan.md`；最终索引/哈希读 `README.md`、`summary.json`、`SHA256SUMS`。
- 本地审计引用 `refs/qc/eastmoney-deploy-binding-20260923` 保留被测候选。回放native收据时，先在收据原路径恢复候选干净检出，核完再清理；不要把路径已回收误写成当时树脏。

## 下一步与边界

固定 head `99bd31c97630988092a4f328126beedc18f74bfc`，base `2edbe4c46595cbea3eb3abe04fe84a7bd5afd55e`，预览tree `247f7951741fc41b2be473fe712a0fab9454a9b2`。收到 #887 合入确认后，重新回读身份与预览，使用现有 `scripts/gitea_pr.py` 锁head/base并记录真实授权。漂移即停，不 fetch 后自动改期望值。

合后实际main另跑门禁，再准备干净装机源、复核指针/权限/hash与nightly-only dry-run，方可宣布可部署。安装仍另授权，且必须在安静窗口做新备份；准备期快照不是届时回滚点。未执行安装、服务重载、kickstart、热补、8792切换或生产写库，未证明生产取数/日期/覆盖恢复。

工具沉淀：复用仓内门禁、注册表与PR工具；树外脚本是带固定路径/身份的一次发布证据探针，不新增通用发布框架。运行根/装机源分离已有先前决策，本轮不另建跨项目方法论副本。交接文档只留本地，不改变已验收的远端候选。
