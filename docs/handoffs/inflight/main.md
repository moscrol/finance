# 在途交接 · main

> 指针（2026-08-13）：复盘会资产线**代码已收口**，完工快照 `docs/handoffs/2026-08-13-fupanhui-public-assets-and-consume.md`。dragon 双表主库回补已完成（summary 390/390、seats 近 60 日 44932 行），两表已进 `GAP_TABLES` 断档门禁。

更新：2026-08-18 02:55 CST · **死资产接通消费（#170 实现，#175 待合）**：四表进 `_DATASETS`，两 JSON 归档不接。树 `/Users/a77/fwp-wt-dead-assets` `feat/dead-assets-consumption`。语义层 9 条先红后绿（真库 200 万行 limit/time_range 0.45s）。四件套：ruff 绿；pytest **5387 passed** / 12 skipped；webapp 四步绿。收据 pytest `~/.finance-runtime/test-receipts/20260817T181939Z-ac6c43cd.json`。**live 三问已跑、均未调 `finance_query`**（#152 sidecar `:8796`，已停；8792 未动）：竞价→`market_forecast` 写「没有个股集合竞价」；研报→`theme_analysis` 吃 4–6 月 wiki；催化→`general_finance_qa` 吃 7 月商业航天。库里 zt 面板/08-13 算力研报/13 条 is_future 都在。属「够得着≠想得到用」，本单不硬修。读数 `docs/verification/2026-08-18-dead-assets-live.md`。ADR `docs/adr/0004-dead-assets-consumption.md`。
更新：2026-08-18 00:58 CST · **stale_notes 旁路（已决 D）实现待合**：`collect_evidence_index` 截断外按 target 扫 superseded/invalidated（含 overlay 硬回链），每宿主至多一行进 gap；top-8 / prompt / #146 闸不动。六条单测先红后绿。live 探针 `stale-note-changdian`：`llm_context.json` 一手有「长电科技 有 2 条证据已被取代」+ `2026-04-08` baseline，落「反证与缺口」/`claim_id=gap:`；R 链 `evidence:R4` 仍有 286.69；359.62 未进链。本单未切 8792。收据 pytest `~/.finance-runtime/test-receipts/20260817T165652Z-d1be2d0c.json`（5377 passed；`test_installed_codex_sandbox_denies_network_and_unix_socket` 环境红，未改树同红）；live `~/.finance-runtime/live-probe-traceability/stale-note-changdian.json`。ADR `docs/adr/0003-stale-notes-bypass.md`。
更新：2026-08-18 00:47 CST · **8792 已切到 `d1be2d0c`**（自 `877e1f72` 后新进：#152 探针钩（默认关）/#157 锚定实体数字修复/#158 休市短路 + docs #154/#151/#156 ADR/#160/#161 执行单。目录名=SHA `finance-workspace-d1be2d0c1fd3`；回滚锚 `finance-workspace-877e1f721e05` 保留）。bootout→链切→bootstrap（一次瞬时 I/O 错误重试即成，与 21:57 同型）；readiness 13 项全 True，三读一致 dirty=false。门禁收据：#157 合并时合流树全量 pytest 5368 全过、预览树 5370 全过、webapp 四步绿；grounded 旁路复验长电题数字+标签在场（收据 ~/.finance-runtime/live-probe-traceability/users/live-probe/runs/run_20260818_003133_360184）。
更新：2026-08-17 23:35 CST · **#153 接手诊断已结**：H1/H2/H3 均 REJECTED。根因是 `collect_evidence_index` 用图谱暴露概念（长电→`1.6T CPO`）过滤锚定实体自己的证据，整包 `found=False`，R 名额被盘面候选占满。修复：锚定实体 `get_evidence` 不带该 concept。未切 8792。诊断 `docs/verification/2026-08-17-evidence-number-density-diagnosis.md`。
更新：2026-08-17 23:10 CST · **DRAM 靶降桶探针 live 复验已跑**（零代码、未动 8792=`877e1f72`）。trace 化探针未交付，走 in-process + 落盘 `synthesis_messages`。一手：`prepared_synthesis_messages` 含 `⚠️已被新证据取代` ×4（R6=05-18 招股书 508 亿 / R7=07-24 华西深度），证据等级=落盘上下文级。建议题「长鑫科技…DRAM…」**打不中** DRAM 宿主（`get_evidence` 精确 target，锚到长鑫科技 5 条全 active）；本发题面改为恰好 `DRAM`。模型见了 stale：508 写成「已被上市新证据取代，只能作历史参照」，现况走 07-27 上市口径；`tier_note_present=false` / marker=0 仍是 prompt 门禁（预期）。华西 2776.90 **未进上下文**（证据行 `[:80]` 截断）。收据 `~/.finance-runtime/claim-tiering-20260817/live-dram-superseded.json`；读数 `docs/verification/2026-08-17-dram-superseded-live-recheck.md`。
更新：2026-08-17 21:57 CST · **8792 已切到 `877e1f72`**（#145 docs 更正 + #146 claim 分层/修订轮/降桶标注/契约豁免；目录名=SHA `finance-workspace-877e1f721e05`；回滚锚 `finance-workspace-96446a933491` 保留。bootout→链切→bootstrap，~30s ready，三读一致 dirty=false。合并前四件套绿：ruff / pytest 5351 全过 / webapp lint+typecheck+65 test+build，收据 `~/.finance-runtime/test-receipts/20260817T135048Z-570fff2c.json`，预览树=合后 main 树 `ab4ec044`。注意：umask 077 下 pytest 会假红 16 个 ceiling 权限位审计，022 下消失，裸 main 同现——环境项非回归）。降桶标注 live 探针（长电科技题，收据 `~/.finance-runtime/claim-tiering-20260817/live-superseded-tiering.json`）：tier note 的模型侧可达性由 prompt 教学门禁挡住（`SYNTHESIS_PROMPT_TEACHES_CLAIM_MARKERS=False`，#146 设计内豁免——prompt 教语法之日闸自动回来），渲染/判据段有单测+变异测试兜底。**更正（同日 22:25，trace-first 复核）**：初版此行误写「superseded 证据进上下文、模型未滥用」——确定性重跑检索段证明该边**根本没进上下文**：`max_evidence=8`，长电 34 条证据 top-8 全 active，2 条 superseded 排在外；「拒报旧数」是因为没见过，不是见了没用。该发对降桶路径的 live 覆盖为**零**（证据侧+marker 侧都未触达）。已扫出可让 superseded 进 top-8 的靶：**DRAM**（7 条中 2 条 superseded 全进 top-8）、mSAP、电子特气；富证据宿主（长电/MLCC/电子布）在默认截断下结构性够不着。
更新：2026-08-17 16:10 CST（补记）· **8792 曾切到 `96446a93`**（#144 tip；目录名=SHA `finance-workspace-96446a933491`；链切时间取自软链 mtime，切换会话未记账；21:30 实测三读一致、ready 全绿）。
更新：2026-08-17 09:42 CST · **8792 已切到 `31ee58ce`**（#124 结转；R-22/R-23 已在祖先）。同题 live 未同形，R-17-01/22/23 仍 pending。交接 `docs/handoffs/2026-08-17-r22-r23-carry-draft.md`。文档 tip `45566d65` 不追切。下方「当前状态」段过期，以 `/api/health` + 该交接为准。
更新：2026-08-16 18:36 CST · **8792 已切到 `6cd0756e`**（闸 2 处置 #93：judge 三元组埋点 + standard judge 窗地板 50s；同窗完成 #88 目录卫生，目录名=SHA `finance-workspace-6cd0756e4a61`；回滚锚 `finance-workspace-773b3d7e73d7` 保留）。GATES `budget_regression_landed=true`（眼 agent 18:36，引用 #93 + R-06 交接/收据）。交接 `docs/handoffs/2026-08-16-judge-transient-r06.md`。收据 `docs/verification/2026-08-16-judge-transient-r06.md`。
更新：2026-08-16 14:00 CST · **8792 已切到 `773b3d7e`**（长尾对照窗现状臂；就地切树，目录名未改）。交接 `docs/handoffs/2026-08-16-deploy-window-773b3d7e.md`。收据 `docs/verification/2026-08-16-8792-773b3d7e-inplace-cut.md`。
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

- **8792 = `6cd0756e`**（观测台 Phase 1 闸对账：live health `source_revision`；历史「更新」行仍可能过期，以本行 + `/api/health` 为准；检阅方 2026-08-16 20:34 实测三读一致、dirty=false）。
  目录名 `finance-workspace-6cd0756e4a61`（SHA 同名，#88 卫生已了；HOLD 解除）。回滚锚 `finance-workspace-773b3d7e73d7`。默认其后 tip 不追切。
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
5. **fph2026 旁路库接主库 ask**（缠论/背离/双红/隔夜数据消费注册，用户已拍板）：
   排队项，触发条件=R-13 收据落盘且处置形状已知（H-a 则并进架构案）。
   交接 `docs/handoffs/2026-08-16-fph2026-ask-wiring.md`。**别忘**。

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
