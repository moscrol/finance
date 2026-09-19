# 在途工作总盘点与收尾规格（2026-09-20）

> 日期：2026-09-20 00:10 CST
> 状态：**已按审阅修正，用户已授权执行**。本文保留原盘点快照；本轮动作与验收结果见 `../../handoffs/2026-09-20-open-work-execution.md`。执行授权不解除各分支的质量门和逐树清理认领条件。
> 数据源（全部 [实测]，可复跑）：`scripts/worktree_board.py --json`（基线 `gitea/main=b22ddf8b0285`，313 棵树，按 `git cherry` 判合入）；Gitea API 全部 786 张 PR；每棵未合树的 `docs/handoffs/inflight/<分支>.md`；`git merge-tree --write-tree` 冲突预演；`~/.finance-runtime/deploy-ledger.jsonl`；`launchctl list`；DuckDB 各 `fact_*` 的 `max(trade_date)`；vault 项目笔记任务看板；`docs/superpowers/specs/2026-09-01-workorders-INDEX.md`。
> 读法：§1 一页结论 → §2 生产与运行面 → §3 未合分支逐条 → §4 冲突矩阵与合并顺序 → §5 需要用户裁决 → §6 姊妹仓 → §7 卫生 → §8 执行顺序。每条「下一步」抄自该分支自己的 inflight，不替作者改口径。

## 1. 一页结论

**快照数字只描述采样时刻，不代表当前状态，不能据此批量删除。** 原盘点为 00:10 的 313 棵；执行起点实测 315 棵，新增的是规格与归档树。后续隔离验收还会增加树数，现值按 §9 脚本重算。带权限 Gitea 查询在执行起点核实本仓 4 张打开 PR；此前 3 张是 #789 创建前的读数。

| 项 | 读数 |
|---|---|
| 注册工作树 | 313 棵：37 棵生产快照、133 棵已合入且干净（需查引用与认领）、35 棵已合入但脏（先保全并认领）、57 条**未合入的工作分支**、51 棵未合工作的运行时冻结副本 |
| 打开的 PR | 本仓 4 张：#789 本规格、#788 收据守卫、#783 历史表达 WIP、#770 E2 材料 WIP；harness-reference #13；知识库 #94 / #26 / #129 / #148 / #149；finance-research-site #2 |
| 未推送到 Gitea 的分支 | 约 30 条，含 6 条核心代码线（保稿 18 提交、财务 R6 返修 24、runtime 合同 16、边界组合 15、R5 合同 17、R6 基线 18） |
| 生产 8792 | `bf662e9310ff`，09-17 06:00Z 切入；`/api/health` healthy、`/api/readiness` ready（09-20 00:03 实测） |
| 数据 | 六张核心 `fact_*` 均到 2026-09-18；09-19 周末夜跑正常跳过 |
| 运行面告警 | 公众号 `publish-daily` 连续 4 次预检失败：**研究站**本地 main 领先 gitea/main 1 提交（`9f60bef`）；金融仓 main 落后 449 是另一件事；夜间生成根跑的是**未合入** `387028b8` |

三条主线都停在同一个位置：**工程绿、真实模型质量未过、等有效独立裁决或用户授权**。合并顺序必须串行，因为六条分支同时改 `episode_semantic_verifier.py` / `continuous_turn_adapter.py`。

## 2. 生产与运行面

| 面 | 现状 [实测] | 缺口 | 动作 |
|---|---|---|---|
| 8792 Workbench | `bf662e93`，healthy/ready；含 #779 #781 | 落后 main 13 张合并（KB 双索引 #786/#787 等） | 切流等 KB 维护链实现（见 §5.3），不单切 |
| 8796 能力边车 | 监听中，launchd 上次退出 -15（被 kill 后重启） | 无 | 观察 |
| KB 双索引 | 代码已合（金融 #786/#787、KB #153/#154）；生产 `.rag_index_full` 仍 `uchg` 防写；`health=fresh+degraded` | **长期受保护维护入口未实现**（hook/ingest/build/update/fetch/publish/回滚） | 先实现维护计划 `2026-09-18-kb-guarded-maintenance-plan.md`，再切换并解防写 |
| 夜跑主链 daily-full | 09-17/18 已恢复两日；周末跳过 | sync/finalize 档位 local 化、L2 独立根保留（`d433b907` 已合） | 按 `docs/l2-deploy-0916` 交接执行「补 09-16 → 过门 → 重跑 finalize」 |
| 夜间生成根 | launchd `daily-full-review-finalize` → `~/.local/bin/nightly_full_review.sh finalize` → 生成根 `~/.finance-runtime/finance-generation-387028b846a2`，09-17 23:44 真实触发 exit 0 | **源码 `fix/generation-root-boundary-guards@387028b8` 未合 main**（09-20 复核仍不在 main），生产跑的是分支代码 | 先独立复核 `387028b8`，守卫线为唯一候选源码线；部署接线随后合流。已有成功触发证据，不能未经缺陷与替代方案评估就回退到缺守卫的 main |
| 公众号 publish-daily | 21:00 任务连续 4 天 `FAIL 本地 main 与 gitea/main 不同步` | `~/公众号/pipeline/steps/00_preflight.sh` 先 `cd "$SITE"`，SITE=`~/finance-research-site`；该仓 main=`9f60bef`，领先远端 1 提交（模拟芯片适配稿），并非落后 | 校验研究站该提交后显式推送 `9f60bef:refs/heads/main`，再单跑真实 `00_preflight.sh`；不靠修改预检掩盖分歧。金融仓的本地快进只是卫生 |
| 数据源 | `fact_market_daily` 425 行到 09-18；`fact_sector_daily` 110716 行 | 无 | — |
| 判官 | 生产 LLM 判官自 09-12 关闭（K3 自审），#781 确定性门模式已合 | 独立判官链未决 | 用户裁决，不在工程线内偷改 |

## 3. 未合入工作分支逐条

字段：尖 / 未推 = 本地领先远端的提交数（N = 远端没有这条分支）；收据 = 该尖有无干净树全量收据；冲突 = 对 `gitea/main` 的 `merge-tree` 冲突文件数。

### 3.1 研究交付与 8792 验收族（共改验证器，必须串行）

| 分支 | 树 | 尖 / 未推 | 收据 | 冲突 | 状态一句 | 下一步（作者口径） |
|---|---|---|---|---|---|---|
| `q/research-data-readiness` | `~/fwp-q-research-data-readiness` | `493824bb` / 已推 | 业务 `6fb37a6e` 12259P/0F | 0 | ARL-0005 五类已修，同一量具 4P10F→14P0F；等有效外审 | 用户定外审窗口（期限/预算/独占根）；裁决后真实会话；合并另授权 |
| `feat/research-answer-preservation` | `~/fwp-wt-research-answer-preservation` | `ce673a9f` / **18 未推** | `cdcbc5a8` 11769P/0F | **9** | 保稿机制工程绿；GLM live 保留候选数 0，机制未触发；三次 live not_passed | 新有界 live 授权 + 新证据根；先 rebase 到含 KB 双索引的 main |
| `fix/8792-financial-r6-repair` | `~/fwp-wt-8792-financial-r6-repair` | `d8d6196b` / **24 未推**，树脏 3（文档） | 12220P/0F | **9** | 只接 RAG 分帧；发布首并发 180s 超时未归因 | 补 runner 持久日志与超时现场；另冻 SHA 归因；不加时限挑绿 |
| `baseline/8792-financial-r6` | `~/fwp-wt-8792-financial-r6` | `0e368516` / 18 未推 | — | 0 | R6 四题 0/4 not_passed，只增文档 | 用户确认返修范围，与 data-readiness/保稿/runtime 作者对齐样本 |
| `fix/8792-financial-contracts-r5` | `~/fwp-wt-8792-financial-contracts-r5` | `1fe2ead2` / 17 未推 | `dfd7b4ff` 工程通过 | 0 | R5 财报/计算合同；旧 R3 0/4 | 新 live 先授权；整合需干净候选重跑门禁 |
| `fix/8792-boundary-integration` | `~/fwp-wt-8792-boundary-integration` | `068e2a46` / 15 未推 | `97ca716b` 工程通过 | 0 | R4 离线边界返修；R3 四题仍 0/4 | 离线分诊选期/截止/缺基线；push 须显式目标枝 |
| `fix/8792-readiness-boundaries` | `~/fwp-wt-8792-readiness-fixes` | `c57633bb` / 2 未推 | `6f9df75a` 四叶通过 | 0 | 三类边界返修 | 独立复核；与最新 main / 数值门 / #770 整合后重验 |
| `fix/citation-numeric-gate-0917` | `~/fwp-wt-citation-numeric-gate-0917` | `3c5f485a` / 2 未推 | 定向 | 0 | E27 引用编号误删修复（已被保稿分支 cherry-pick 为 `478ca199`） | 判定是否已被吸收，吸收则关闭 |
| `feat/research-data-readiness` | `~/fwp-wt-research-data-readiness` | `b4757709` / 7 未推 | `a31b572f` 工程通过 | 未测 | 数据消费与答案正确分层；q 线的前身 | 审边界并对齐 q 线，不复制 WIP；可能已被 q 线吸收 |
| `fix/e2-material-closeout` | `~/fwp-wt-e2-material-closeout` | `b1c1c29f` / 已推 · **PR #770** | `8f6e6eaa` 11316P/0F | 2（含验证器） | 修复轮反馈、矛盾形状；判官 invalid tool call 3/21 | 固定判官无效调用回归；接或删 `rejected_claim_indexes`；合前重探冲突 |
| `feat/history-market-anatomy` | `~/fwp-wt-history-market-anatomy` | `c9bd82ff` / 1 未推 · **PR #783** | `672abcc5` 11579P；尖 11612P/1F | 0 | 表达与夹具返修通过，真实四题仍拒收 | 修同窗 rank / 启动特征 / 控制组，再新 SHA 四叶 + 原四题 |
| `feat/e2-p6-conditioned-input` | `~/fwp-wt-e2-p6-input` | `d2098243` / 2 未推 | 54 测 | 0（09-16 测） | material_grounding 新模块 | 无编号 material_only 准入；live 判官一次；独立 QC |
| `feat/e2-material-contract-impl` / `-design` | `~/fwp-wt-e2-impl-p1`、`~/fwp-wt-e2-material-contract-0913` | 已推，无 PR | — | — | E2 P1–P7 路线文档与实现前段 | P2 载体 + premise_marks；后段 P3–P7 |
| `fix/capability-wiring-closeout` | `~/fwp-wt-capability-wiring` | `e8a63007` / 3 未推 | — | 1（task_frame.py） | 三处「实现了但接不上」的收尾 | 合 `413b7a07` + `6c7bea6e`；06 判据按基线余量重写 |
| `docs/8792-sector-history-diag-0917` | `~/fwp-wt-8792-sector-history-diag-0917` | `40321402` / 2 未推 | 文档 | 0 | ReAct 臂 vs 8792 首轮对照，F1–F7 | 五个修复切片 P0a–P1b（P0a 已由 `478ca199` 完成，其余未做） |
| `docs/qc-8792-readiness-0917` | `~/fwp-wt-qc-8792-readiness-0917` | `0170b6cc` / 3 未推 | 文档 | 0 | 8792 独立质检，三类缺陷待修 | F1→F2/F3 纳入正式回归；`qc_8792_readiness.py` 从 exit1 变 0 |

另有运行时目录 `~/.finance-runtime/reviews/research-components-react-20260918/`（46 文件）是第二轮 ReAct 对照包，**未进任何仓**。

### 3.2 运行底座合同

| 分支 | 树 | 尖 / 未推 | 收据 | 冲突 | 状态 | 下一步 |
|---|---|---|---|---|---|---|
| `fix/runtime-contracts-0918` | `~/fwp-wt-runtime-contracts-0918` | `a7f5cc06` / **16 未推** | 11766P/0F | 3 | 授权快照 `6b70e540` 固定验收通过；P1 整体未完；无跨进程 driver | 补入口绑定、E 号回读、inbox 回执、截止/取消；单写者对账后接同 loop driver |
| `fix/runtime-authority-pc-0918`、`fix/runtime-evidence-probe-0918`、`fix/runtime-child-fence-tests-0918` | 各自树 / tmp | 已 ff 进 `a7f5cc06` | — | — | 子分支，内容已包含在上一行 | 合入上一行后删分支与树 |
| `baseline/runtime-absorption-audit-0918` | `/private/tmp/finance-runtime-audit-report-0918` | `e251d30a` / 3 未推 | 文档 | — | 三轮 runtime 吸收源码核验 | 先补 OPT-08 与接缝反例，不叠框架；树在 /tmp，先推 |

### 3.3 数据链、夜跑、L2

| 分支 | 树 | 尖 / 未推 | 冲突 | 状态 | 下一步 |
|---|---|---|---|---|---|
| `fix/nightly-generation-deploy-0917` | `~/fwp-wt-nightly-generation-deploy-0917` | `f7337bf0` / 3 未推 | 0 | **装机已部署、真实触发 exit 0，源码未合** | 先跟在守卫源码候选之后合流；它仅含部署接线，不当成另一套生成业务实现。固定候选四叶后才能合 |
| `fix/generation-root-boundary-guards` | `~/fwp-wt-generation-root-guards` | `ada20cc8` / 7 未推 | 3 | 生成根边界守卫 `387028b8`，作者验收过，待独立复核 | 先独立复核 `387028b8` → 修复发现 → 固定合流候选四叶；生产正在跑它。不得机械连合 stage 与 guards 两条线 |
| `fix/generation-stage-code-root` | `~/fwp-wt-generation-stage-code-root` | `6e8c5a2a` / 6 未推 | — | **superseded：源码已由守卫线接替**。含 `0f6c2810`，不含 `387028b8`；两枝互非祖先，stage 独有两提交仅交接文档 | 保全并推送；代码只走 `fix/generation-root-boundary-guards`，独有文档按需归档，不再独立合代码 |
| `fix/nightly-review-0917` | `~/fwp-wt-nightly-review-0917` | `6356ffd5` / 7 未推，树脏 2（产物） | 1 | 两日主链已恢复；plan 已 local | 合并另跑固定 revision 四叶 |
| `docs/l2-deploy-0916` | `~/fwp-wt-l2-deploy-0916` | 已推 | 0 | L2 文件源部署已生效，09-16 业务日线缺失 | 补 09-16 经 daily-full 正门；跨日须显式指定日期 |
| `fix/l2-file-source-qc` | `~/fwp-wt-l2-file-source-qc` | 已推 | 0 | 代码已经 #773 进 main，此枝只余文档 | 归档文档；生产切换另授权 |
| `fix/backfill-302132-scoped` | `~/fwp-wt-backfill-302132` | `3736d5bf` / 12 未推 | 0 | 回填 302132 v6 | 第七轮复审 → 合并 → 授权后干净检出执行 |
| `fix/hithink-review-wiring` | `~/fwp-wt-hithink-review-wiring` | `d4d0ee26` / 已推 | 1（`UBIQUITOUS_LANGUAGE.md`） | 作者验收 + k3 独立 QC + P3 修复闭环全部完成 | 用户已批准进队；09-15 `728ecf82` 收据已随 main 漂移失效，先前向合流、按节保留双方术语，再重跑 Python/frontend/E2E/registry |
| `data-source/broad-index-delta` | `~/fwp-wt-broad-index` | `f450f4bb` / 已推，**树脏 3 含代码未提交** | — | `sync_hithink_sector_kline.py` + 测试 9 passed 未提交 | 用户确认后 pathspec 提交；补 `899050.BJ` 无指数码到 #685 spec |
| `feat/finance-query-technical-daily` | `~/fwp-wt-technical-daily` | `6b6d9f36` / 1 未推（PR #396 已合） | — | 第五步已提交未推，树脏 2 | 用户确认后推；摸底后三步不在本 PR |
| `fix/fupanhui-session-hygiene` | `~/fwp-wt-fupanhui-session-hygiene` | `c06a66f3` / 1 未推，无 inflight | — | 09-04 小修 | 判定合并或丢弃 |

### 3.4 评测与判官

| 分支 | 尖 / 未推 | 冲突 | 状态 | 下一步 |
|---|---|---|---|---|
| `feat/judge-calibration-validity` | `19ae9973` / 3 未推 | 5 | P1：`identity_state` 三态跨层无一致性断言，双向静默漂移 | 下沉到两层可 import 的无依赖模块；留给 codex 轨裁决 |
| `eval/k3nj-compat-payload` | `af50e405` / **31 未推** | 1 | 28/30 completed，终件已入仓（在分支上） | 两臂人工评审 + aggregate；先推 |
| `baseline/capability-benchmark-00` | `6bea3197` / 1 未推 | — | 终件 clean 13 / recovered 10 / unavailable 5；review-pack HOLD | 与 k3nj 同尺度同期评审 |
| `feat/i1-availability-attribution`、`perf/wiki-hybrid-25s`、`feat/continuous-research-09-live` | 已推或 1 未推，无 inflight | — | 旧评测/消融产物 | 归档为文档或关闭 |

### 3.5 方法、河、知识

| 分支 | 尖 / 未推 | 冲突 | 状态 | 下一步 |
|---|---|---|---|---|
| `feat/river-correction-hardness` | `e57f56df` / 13 未推（树在 `.claude/worktrees/`） | 3 | 载体 + slice 过滤 + HARDNESS_RANK；spec §4.4–4.6 | 触发刀：判断轨修正链（judgment provider v1 + corrections 载体 + `expired_at`） |
| `feat/theme-stage-vocab-g04` | `b80ba77d` / 已推 · PR #745 已关未合 | — | G-04 词表 + 对照集 | 用户过目 → 重开 PR 合并；按节合 `UBIQUITOUS_LANGUAGE.md` |
| `codex/docs-historical-discovery-spec` | `da254cd3` / 1 未推 | — | 历史发现研究设计正文 | 按 S0→S1→S2 拆实施计划 |
| `docs/knevo-intake-20260917`、`docs/fengyuan-distill-0916`（/tmp） | 已推 | — | Knevo 蒸馏/吸收文档 | 合并为文档或归档 |
| `feat/workbench-tech-premium` | `717d243b` / 2 未推，无 inflight | — | 前端改动 | 判定去留 |
| `codex/feat-workbench-research-journey` | `094daed1` / **19 未推 + 19 脏（08-25）** | — | codex 旧线，含构建产物 | 判定去留；不动他人脏树 |

### 3.6 质检报告分支（只含文档）

`codex/qc-extraction-caba87c7`、`codex/qc-extraction-first-p0-b42dc9bf`、`docs/qc-research-evolution-06-0913`、`docs/qc-research-evolution-repair-0913`、`docs/qc-route-gate-600f2aa9`、`docs/qc-method-29b07912`、`docs/qc-generation-root-0f6c2810`、`docs/qc-hithink-*` ×4、`docs/qc-workbench-probe-*` ×3、`docs/qc-l2-pct-chg-54248fa3`、`docs/qc-pr773-70811c7d`、`codex/review-re06-*` ×2、`codex/review-river-contract-86d61d9e`。
共同点：审查已完成、结论「需返修」，正文在各自 `docs/handoffs/2026-09-1x-*-review.md`，多数未推。**动作**：统一推送，随被审分支一起合入或归档进 `docs/verification/`；审查结论已被吸收的关闭。

### 3.7 文档与 BP

| 分支 | 状态 | 下一步 |
|---|---|---|
| `docs/bp-v1.3-roadshow-align`（5 未推） | 路演 v4.4 材料与测试已提交；桌面交付件齐 | 用户检查口播与计时；合主线跑等价检查 |
| `docs/optimization-status-audit-0916`（1 未推） | 两份审查文档；结论「不能声称所有优化完成」 | 审 P5/P6 补 P7 后再固定候选 |
| `salvage/opc-shims-20260919`（已推） | 三份 OPC shim 逐字节封存 | 无实现工作 |
| `feat/instruction-migration-agents-md`（`~/agroup-build`，1 未推） | 指令迁移 | 判定去留 |
| `spec/continuous-depth-gap-r1`（运行时目录，08-19） | 旧 spec 草稿 | 归档或删 |

### 3.8 本轮新增

`fix/receipt-zero-count-guard` · PR #788 · 零计数收据不可采信；21 测绿、变异 5 红 9 绿；等合并确认。

## 4. 冲突矩阵与合并顺序

### 4.1 对 `gitea/main` 的预演（`merge-tree --write-tree`）

| 干净 | 有冲突（文件数） |
|---|---|
| q/research-data-readiness、fix/8792-boundary-integration、feat/history-market-anatomy、fix/nightly-generation-deploy-0917、fix/backfill-302132-scoped、fix/receipt-zero-count-guard、fix/citation-numeric-gate-0917、fix/8792-readiness-boundaries、baseline/8792-financial-r6、fix/8792-financial-contracts-r5 | preservation 9 · financial-r6-repair 9 · judge-calibration-validity 5 · runtime-contracts 3 · river-correction-hardness 3 · generation-root-boundary-guards 3 · e2-material-closeout 2 · hithink-review-wiring 1 · nightly-review 1 · k3nj 1 · capability-wiring 1 |

9 处冲突的两条分支，冲突集中在 `intelligence/api/app.py`、`rag_worker.py`、webapp 与静态构建产物、门页：都是今天 KB 双索引合入后产生的，属机械冲突，静态产物按「重新构建、不选边」处理。

### 4.2 族内两两冲突（都在改验证器与轮次适配器）

| 对 | 文件 |
|---|---|
| q 线 × 保稿 | 11（门页、app.py、静态产物、验证器、turn_adapter） |
| q 线 × 财务 R6 返修 | 18 |
| 保稿 × 财务 R6 返修 | 12（含 `episode_semantic_verifier.py`、`rag_worker.py`） |
| 保稿 × E2 材料 #770 | 6（`agent_episode.py`、`episode_finalizer.py`、`episode_protocol.py`、验证器） |
| 保稿 × runtime 合同 | 5 |
| 边界组合 × q 线 / runtime / E2 | 各 1（`continuous_turn_adapter.py` 或验证器） |
| 历史表达 #783 × 保稿 / 边界组合 / 财务 R6 | 3–5（`research_progress.py` 与其测试） |

### 4.3 修订后的顺序（每合一张，下一张前向合流并重新冻结收据）

0. **生成根先独立复核**：`387028b8` → 守卫线唯一候选 → 部署接线。stage 线只保全、标 superseded；发现缺陷先返修，保持当前生产，不无条件回退 main。
1. `fix/receipt-zero-count-guard` #788（用户已批准，固定 revision 重跑四叶）。
2. `fix/hithink-review-wiring`（用户已批准；编辑术语表逐节合并双方内容，pathspec 仅控制暂存/提交范围，不解决语义冲突；前向合流后重跑四叶）。
3. `q/research-data-readiness`（干净；前提是用户对外审窗口作出决定，或明示接受工程绿合入）。
4. `fix/8792-boundary-integration`（干净；与 q 线只有 `continuous_turn_adapter.py` 一处）。
5. `feat/history-market-anatomy` #783（继续候选，真实四题未过，当前不批准按工程绿合入）。
6. `fix/e2-material-closeout` #770（继续候选，真实材料/判官未闭环，当前不批准按工程绿合入；达到准入后才解验证器冲突）。
7. `feat/research-answer-preservation`（rebase 掉 9 处机械冲突，再解与 3、4、6 的验证器冲突；合前必须一次真正触发保稿机制的 live）。
8. `fix/8792-financial-r6-repair`、R5 合同、R6 基线（依赖 7；先归因 180s 首超时）。
9. `fix/runtime-contracts-0918`（3 处冲突；P1 未完，可作为独立底座线合）。
10. 其余数据链：`nightly-review-0917`、`backfill-302132-scoped` 按各自验收另排；生成根已前置到第 0 项，不在此机械连续合两条代码线。

红线：任一叶子红不合；合入后旧收据不移签；`.claude/lessons_learned.md` 与门页的冲突一律「取双方」。

## 5. 需要用户裁决

1. **T3 外审窗口**：期限、预算、独占根；请求覆盖到 `6fb37a6e` 的累计 diff。或明示「接受工程绿 + 后置真实会话」直接合并 q 线。
2. **合并批准**：#788 与 hithink-review-wiring 已获用户批准，仍须当前固定候选四叶；theme-stage-vocab 另核去留；q 线不能从工程绿推导批准（见 1）。
3. **KB 双索引切换**：是否先实现维护计划再切 8792；解防写只随维护链上线。
4. **夜间生成根**：先独立复核 `387028b8`，以守卫线为唯一候选，部署随后。无实证缺陷不回滚；若有缺陷，先评估返修及替代版本，不默认选择缺守卫的 main。
5. **公众号 publish-daily**：预检绑定 finance-research-site；实测 main 领先 1 提交 `9f60bef`。修法是经校验后把该既有提交推送到该仓 Gitea main，再复跑真实预检。用户本轮执行指令覆盖该明确动作；金融仓 main 的 ff-only 另记卫生，不宣称它修复发布。
6. **保稿线的 live 授权**：新有界窗口，用封存的第 13 轮格式拒收原件先做离线反例，再一次真实触发。
7. **研究深度切片立单**：首轮诊断的 P0b 查询报错闭环、P0c 集合/排序忠实、P1a 方法论卡与观测卡分离、P1b 板块比较合同、预览按需展开。这五项才是「Workbench 比助手浅」的主体，目前无人认领。
8. **看板陈旧行处置**（vault 任务看板 9 doing / 10 blocked 中至少 7 行已失真）：`28 题产品验收台`×2（08-01，分支只剩远端）、`Adaptive Runtime Phase A/B`（分支已无）、`delta package #179`（GitHub 时代）、`codex sidecar 池 fenno`（配置已移除）、`待办 K 夜跑到 08-04`（数据已到 09-18）、`kb_search hits=0 两张 PR`（已被 KB v4 合并覆盖）。建议标 closed 或 superseded，并写指针。
9. **工单 INDEX 先去重核实**：#23 判官 token 记账、#24 checkpoint rule_id 偏差目录、#25 历史重放引擎均已有实现进入 main：分别见 #593、#592（收口 #747）、#597 的接替指针评论 4609。不得重开同一实现任务；#23 尚缺生产新 run 观察，其他剩余工作沿原单查验，不能把旧实施记录中的“待合”当现状。#20 预算授予 P1 挂起。
10. **清理先出清单再认领**：逐树查 launchctl 实际代码根、deploy-ledger、PR/分支、收据/manifest/verification 与复跑命令中的路径、生产快照与回滚目标。干净 detached 且 SHA 在 Gitea 可达只是可重建的必要条件。SHA 未在 Gitea 或引用/所有者未明，一律保留；不得按 133/35/51 批量 rm 或强制 remove。`candidate-*/registry-pinned` 也有交接路径引用，不能断言无引用。

## 6. 姊妹仓

| 仓 | 未合树/分支 | 打开 PR | 备注 |
|---|---|---|---|
| knowledge-base-private | 7 棵未合：`baseline/ashare-coverage-gap`（未推，脏 771）、`baseline/rebuild-queue-0828`、`concept/l1-precious-industrial-0825`、`disclosure/archive-0813-0828`、`baseline/entity-landing-0816`、`harness/session-facts-and-receipts`（#94）、`theme-radar/ima-slice-0828`；主检出树脏 121 | #94、#26、#129/#148/#149 晨汇回填 | 除 coverage-gap 外均已推；晨汇回填三张 PR 待合 |
| harness-reference | 9 条 docs 分支未合，5 条未推（`financial-r6-mutation-receipts`、`runtime-contracts-0918`、`harness-arch-review`、`ceiling-sensors`、`public-answer-compiler-o1`）；主检出树 `BUILD.md` 他人脏改、领先远端 1 | #13 | SSOT 是 `gitea/main`，先推再合；不动 `BUILD.md` |
| agent-memory | 4 条旧 docs 分支（07-12 至 08-16）+ 4 条 prunable 登记 | 0 | 判定归档；`git worktree prune` |
| dao-proxy-pro | 主检出在 `fix/mode-restore-after-reload`，15 未推、脏 138（desktop/test/vendor）；4 条功能分支未合 | 0 | 与金融线无关，单列处理 |
| finance-base-ab | 干净，无 PR | 0 | ReAct 对照配方仓，第四臂 loop 在此 |

## 7. 卫生

- `docs/handoffs/inflight/` 91 份，其中 8 份超 3K（最大 27.9K `docs-finance-agent-bp.md`、`HEAD.md` 10K）；已合分支的 inflight 应 `git mv` 进 `inflight-archive-2026-09-xx/`（09-08 曾把 101 份压到 8 份，现又回到 91）。
- 本仓 61 条失效 worktree 登记今晚已 prune；agent-memory 与 dao-proxy-pro 各有 prunable 登记未清。
- 主检出树内残留 `tmp/agent-runtime-seam-fix-69f9cf17` 克隆（08-01 看板行）。
- 主检出树 detached 且脏 175（含 L2 运维覆盖层），本地 `main` 引用无人维护。
- 空收据 `20260919T105310Z-d46c2c3b.json` 保留；#788 合入后此类收据不再可采信。
- `vault_lint.py` 全库 19 错 17 警告为存量，多条交接都声明「不扩修他项」。

## 8. 执行顺序

**P0（先做，无需合并）**
1. **先保全，再推送**：旧 52 棵脏树的 status、staged/unstaged `diff --binary`、未跟踪清单/允许原件已在 `~/.finance-runtime/worktree-salvage-20260920/`；执行前核验并补采漂移。固定显式分支名单与 SHA，逐条正常推送，不用通配符、不强推。若用 shell，写 `"refs/heads/${b}:refs/heads/${b}"`，不能写会被 zsh 当 `:r` 修饰符的 `"$b:refs/..."`；本轮采用 Python 参数数组。push 不保存未提交改动。
2. ReAct 归档仅入允许文件；SQLite、pyc、缓存、锁和 **大于 5120 KiB 的 JSON** 都只记原路径/大小/SHA-256，原件保留外部；不拆大 JSON 或改字节绕门。manifest 与入仓/外部集合逐一闭合。
3. 在干净 `~/fwp-wt-main-docs` 快进金融仓本地 main；另校验并显式推送研究站 `9f60bef`，复跑真实发布预检。两项结果分开记录。
4. 生成根独立复核；q 线新外审必须先定期限/预算/独占根，不继承旧失效 PASS。

**P1（合并队列，按 §4.3）**
5. 生成根按 §4.3 第 0 项处置；#788 → hithink 为当前批准队列。其余各线的外审/真实质量/授权前提仍须满足，顺序到达不等于可合。每步：前向合流、四叶、`check_test_receipt.py --expect-revision`、`merge-tree` 复探。
6. KB 维护链先按既有维护方案落实统一入口、单写者、双索引代际 manifest、故障恢复及消费者重启验收；通过之前不解防写、不切 8792，远端资产发布另守授权边界。

**P2（清理与立单）**
7. 逐树生成可审查清理清单并取得认领结果，SHA 不在 Gitea 的一律不动。核 launchctl/台账/PR/文档与回滚引用后再决定具体删除；本轮不按历史数量批量清理。
8. 研究深度五切片按 §5.7 顺序去重立单；#23/#24/#25 沿已有单补剩余验收。陈旧看板标 superseded 并保留替代指针，不静默删行。
9. 姊妹仓逐仓复核，KB 晨汇合并另依本仓验收；harness 未推分支按显式名单保全；prune/remove 同样需核引用，不当作盘点动作顺带执行。

## 9. 复跑

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
git fetch -q gitea
$PY scripts/worktree_board.py --json --timeout 20 > /tmp/wt-board.json      # 动态快照；不要依赖本文旧树数
$PY -c "import json;b=json.load(open('/tmp/wt-board.json'));t=b['trees'];print(len(t),sum(1 for r in t if not r['in_main']),sum(1 for r in t if r['in_main'] and not r['dirty']))"
git merge-tree --write-tree --name-only gitea/main <branch>                   # 逐条冲突预演
curl -s http://127.0.0.1:8792/api/health | head -c 200                       # 生产身份
```

读数会随合入漂移；本文数字只对 `gitea/main=b22ddf8b0285` 与 2026-09-20 00:10 CST 成立。
