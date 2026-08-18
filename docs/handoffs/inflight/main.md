# 在途交接 · main

> 指针（2026-08-13）：复盘会资产线**代码已收口**，完工快照 `docs/handoffs/2026-08-13-fupanhui-public-assets-and-consume.md`。dragon 双表主库回补已完成（summary 390/390、seats 近 60 日 44932 行），两表已进 `GAP_TABLES` 断档门禁。

更新：2026-08-18 11:30 CST · **验收规程跟上 token/队列现状**：`acceptance-workflow.md` 改 Keychain 账号 `-a a77-token`、裁决改走评论（不再写「缺 write:issue 就改描述」）；CHECKING 指针兼指 closeout §1。旧 token 名 `migration` 仍留着（他轨可能握着），钥匙串现用 `acceptance-write-issue-0818`，未作废。#177 已留评论 902，未代 rebase。未切 8792。
更新：2026-08-18 11:22 CST · **验收 follow-up 四项已收**：① Gitea 停服轮转 `queues/common` → `common.preclear-20260818-111706`（queues 备份 `~/backups/gitea-queues-20260818-111706.tar.gz`；未 DB 手术、未升级）。新 PR #192 0.1s `mergeable=true`；空推 0.3s 仍绿；存量 #147 关/开自动刷新。② Keychain `gitea-local`/`a77-token` 同位补 `write:issue`（最小集；旧值 `a77-token-prev`）；`POST` 评论 **201**（#192 comment 896）。③ KC-17 A3 旁路 PASS：sidecar :8797、`run_20260818_111701_388149`，`stock_deep_dive` / 锚 立新能源 001258 / 引用 15，不再 theme 吞没 0 证据；收据 `~/.finance-runtime/live-probe-traceability/kc17-r15-a3.json`。④ **#177 未代动**。未切 8792=`4a3bb31366c2`。台账 `docs/verification/2026-08-18-acceptance-followups-closeout.md`。
更新：2026-08-18 11:20 CST · **验收 session 收官**：验收规程固化 `docs/workflows/acceptance-workflow.md`（拉齐队列→环境铁律→逐张验收→批次门禁→链切五步含验证判据→回写；后续质检 session 从此单进，AGENTS.md 合并纪律节旁已挂指针）。本 session 全链：9 张处置（10:50 行）→ 四件套门禁 → 8792 链切 + #167 生产闭环（11:05 行）→ 移交单四项（`2026-08-18-acceptance-followups.md`，**Gitea 队列根治 P1 / token 补 write:issue / KC-17 A3 复验待领**）。验收树 `fwp-wt-167-merge` 保留复用（webapp node_modules 已装）。
更新：2026-08-18 11:05 CST · **8792 已切到 `4a3bb31366c2`**（#187 台账合并后 tip，含验收批全部 8 个代码合并；目录名=SHA `finance-workspace-4a3bb31366c2`；回滚锚 `finance-workspace-d1be2d0c1fd3` 保留）。bootout→链切→bootstrap 一次成，T+49s ready；readiness 13 项全 True，三读一致 dirty=false，code_matches_repo=true。**#167 生产闭环**：grounded 探针（长电题、`use_llm=False`、生产 env 形状）`data_repo_root=私有仓`、`market_data_source=duckdb`、`snapshot_date=2026-08-17`、「没有连接本地市场数据」消失——对照切前收据 `run_20260818_003133_360184`（source_date=2026-07-15 + 断连降级，恰是病灶实录）。收据 `~/.finance-runtime/live-probe-traceability/cutover-4a3bb31366c2-20260818.json`。gitea 备份按约补打 `~/backups/gitea-20260818-post187.tar.gz`（1.2G，含队列故障现场）。**移交单** `docs/handoffs/2026-08-18-acceptance-followups.md`：① Gitea patch-checker 队列根治（P1）② 验收 token 补 `write:issue` ③ KC-17 A3 旁路复验（前置已齐）④ #177 台账冲突提醒。
更新：2026-08-18 10:50 CST · **验收批次已结（新 session 质检，接 02:25 行②）**：① 队列 9 张全部处置——#167 数据根修复 **PASS 合并**（验收方独立复算：定向 38 绿；live 三项达标 DuckDB=私有仓/`market_data_source=duckdb`/「没有连接本地市场数据」消失；候选已被夜间管线推进到 08-17×50，handoff 预期残差自然消解）；KC 批 7 张合并 #168（KC-01 D7 提供链）/#169（KC-02 质量指标）/#171（KC-03 D13 龙虎榜）/#174（KC-04 D12 资金面，与 #171 相邻缝冲突按 D9→D12→D13 就地解）/#159（KC-17 实体三态）/#162（KC-20 断更清单，live 干跑 8 宿主合理）/#166（KC-13 五元素 lint，advisory 不阻断）；#120 判 **superseded by #119** 关闭（代码+测试树对树零差，唯台账行是回退；裁决全文在 PR 描述）。② 合并后主干门禁（tip=`77c05c7a`，env -i + umask 022）：ruff 绿 + pytest **5428 passed/12 skipped** + webapp 四步绿（65 test）；收据 `~/.finance-runtime/test-receipts/20260818T023737Z-77c05c7a.json`。③ **基础设施故障升格**：Gitea `pr_patch_checker` 队列自 08-18 凌晨起不消费任务（重启/flush/关开 PR 均无效；#168 卡 CHECKING 最终以 SQLite 置 `pull_request.status=2` 解除，随后 API 真合并通过侧证无冲突）。再有 PR 卡 `mergeable=false` 即同因；根治（清 LevelDB 队列目录或升级 Gitea）待用户拍板。④ 8792=`d1be2d0c` **不含本批 9 个合并，追切待裁决**；切前建议连带跑 KC-17 的 A3 旁路复验（执行方自留项）。⑤ 并发注意：另一 session 正交付 KC-C/D 链（#175–#185 在队），本批验收未动其分支；#177 与主干在台账文件顶部有内容冲突（并发追加相邻缝），需其重解。⑥ 验收 token 缺 `write:issue` scope，PR 评论发不出——裁决一律写 PR 描述；后续建议补 scope。
更新：2026-08-18 02:25 CST · **批次收尾（本 session 完，用户将新开 session 质检）**：① 今晚合并——代码 #165 stale 旁路（验收方独立复算 pytest **5378 全绿**/webapp 四步绿 + live `llm_context` 提醒行/286.69/359.62 缺席逐项核，main=`3b01c623`）；docs #170 死资产接线单、#172 评估双单（launchd 六任务修复 + 冻结 30 题基线）、#173 饥饿信号单 + 章审第 5 章判定更正（⚪→🟡）。② **待质检的交付**：#167（数据根修复实现，对应 `2026-08-18-data-root-wiring-fix.md`）已开且 mergeable；KC 系列 8 张 feat/fix（#159/#162/#166/#168/#169/#171/#174/#120）在队。质检起点=各 handoff「验收标准」节 + 本行。③ **已派未交付**：死资产接线、launchd 环修复、30 题基线（先决=#167 验收合并后）、饥饿信号。④ 8792=`d1be2d0c`（**不含 #165 及之后**，追切待裁决）。⑤ 验收环境两条教训（本 session 实测）：shell 继承 launcher 变量→31 假红，umask 077→16 假红（ceiling 权限位审计）；正确姿势=`env -i` 保 PATH/HOME/KNOWLEDGE_WIKI + `umask 022`。⑥ 备份 `gitea-20260818.tar.gz`/`-0215.tar.gz`（下次代码合并后再打）。⑦ 数据资产审计八通道触达收据与断流清单见 roadmap 2026-08-18 段。
更新：2026-08-18 · **数据根接线修复（本 PR，未切 8792）**：病根是 `data_repo_root()` / `ask_types._data_repo_root()` 把 `WORKBENCH_REPO_ROOT`（代码快照）排在 `FINANCE_WS`（私有数据仓）前面。修法：数据根查找序改为 `FINANCE_WS → FINANCE_ROOT → 代码根`；ask_types 删掉复制实现，改走 `paths.data_repo_root`。app.py `REPO_ROOT` 仍是代码根（provenance）；`_run_ask` 日报投影改走 `data_repo_root()`。一手：双设下 DuckDB=`…/finance-workspace-private/db/market_feature_store.duckdb`（exists）；`load_theme_candidates`=2026-08-13×50；`use_llm=False` 长电题 `market_data_source=duckdb`、`snapshot_date=2026-08-13`，warnings 无「本轮没有连接本地市场数据」。预期残差：S 08-13 ≠ DB 08-17（08-14 回补在审 + 夜间管线），不追。收据 `~/.finance-runtime/data-root-wiring-20260818/`。
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
