# 2026-08-28 欠账工单索引（分发用）

来源：2026-08-28 两仓欠账盘点（金融仓 + 知识库仓）。九份工单互相独立可分发，每份自带证据路径、步骤、验收与红线。

> ⚠ 术语澄清（已落 correction）：本索引里 #3 的「L2」指**知识库证据分层的 L2 基线**；
> 用户口中的「金融仓 L2」指 **Level2 逐笔委托/大单资金流数据**，对应 #8。两者无关。

## 进度速览（2026-08-29 00:20 复核，以活库路径 + 工作树提交为准）

- ✅ **#1 完成**：summary 18 步全 PASS，08-28 两队列已生成。
- ✅ **#2 完成**：活库已有 `2026-08-26/`；08-26/27/28 receipt 无 `received` 残留（26: skipped 11；27: skipped 8；28: ingested 2 + skipped 14，含 queue-2）。医药占位已升 L1。分支 `theme-radar/kb-queue-drain-0828` @ `7df6ff2a`，未合 main。
- ✅ **#3 完成**：P0 + orphan P1/P2 已消化。重建后 orphan 14 条（旧 69 过期）。P3 八家 `cursor_held`。分支 `baseline/rebuild-queue-0828` @ `a2df431f`（batch06），未合 main。
- ✅ **#4 大头完成**：08-26（4 approved + 7 rejected）/ 08-27（1+6）全清，分支 `theme-radar/backfill-review-0828` 未合 main；**余 08-28 新生成 11 条 pending_review**。
- ✅ **#5 完成**：219 条公告已在 `disclosure/archive-0813-0828` @ `6b14d2c8`；活库 `git status -- wiki/raw/disclosures/` 已干净（相同文件从工作区撤走，以分支为准）。gap P0=0。未合 main。
- ✅ **#7 完成**：ledger-map 已登记晨汇/卖方为手动停更（提交 `8b25a101`）。
- ❌ **#6 未动**（预期内：IMA 通道被个股队列占用）。
- ❌ **#8 未动**（预期内：等用户续期 ClickHouse 凭证）。
- ⏳ **#9 前置队列在途**：个股卡 76/95、0 失败。

| # | 工单 | 优先级 | 主仓 | 一句话 |
|---|------|--------|------|--------|
| 1 | `2026-08-28-daily-workflow-0828-resume-workorder.md` | **P0** | 金融 | ~~export-increment iCloud 死锁 → 15 步 SKIP~~ **已补跑 PASS**（23:32，待验收）；08-28 review 11 条已并入 #4 |
| 2 | `2026-08-28-kb-ingest-queue-drain-workorder.md` | **P0-P1** | 跨仓 | ~~08-26 未 receive~~ **已消化**（活库 08-26 目录 + 三批终态；医药升 L1） |
| 3 | `2026-08-28-entities-baseline-l2-workorder.md` | P1 | 知识库 | ~~orphan 69 pending~~ **P0+orphan P1/P2 已消化**（重建 14；P3 游标） |
| 4 | `2026-08-28-theme-backfill-review-workorder.md` | P1 | 跨仓 | 08-26/27 复核 18 条 pending_review + vertical-slice 10 + quality 52/30 |
| 5 | `2026-08-28-disclosure-governance-workorder.md` | P1-P2 | 知识库 | ~~188 行 untracked~~ **已归档**（分支 `disclosure/archive-0813-0828`；活库 disclosures 干净） |
| 6 | `2026-08-28-ima-deepdive-slice-workorder.md` | P2 | 知识库 | 590 candidates 按题材切片；先清减肥药/贵金属两个在途 |
| 7 | `2026-08-28-ledger-refresh-workorder.md` | P3 | 跨仓 | ~~先诊断故障还是退役~~ **诊断完成待决策**：手动停更+自动源空；已登记 `ledger-map` @ `8b25a101`，未补拉 |
| 8 | `2026-08-28-l2-moneyflow-backfill-workorder.md` | **P1**（前置在用户） | 金融 | Level2 逐笔资金流断在 08-07、08-18 起挂账；凭证续期后删 flag 按日回补 15 个交易日 |
| 9 | `2026-08-28-deepdive-pipeline-workorder.md` | P2 · **接力单** | 知识库 | 主体已有在途队列在做（95 家个股卡 + 8 题材 DeepDive，`kb-wt-ima-stock-0826`）；本单只做收尾后 8/13 以后触发题材的残余缺卡 |

## 续表：2026-08-29 符合性套件系列（缝普查产出）

来源：`docs/verification/2026-08-29-conformance-seam-census.md`（分支
`test/conformance-seam-census`）。判据与套件模式已沉淀 `~/harness-reference/TOOLKIT.md` A+ 节。

| # | 工单 | 优先级 | 主仓 | 一句话 |
|---|------|--------|------|--------|
| 10 | `2026-08-29-runtime-conformance-suite-workorder.md` | P0 | 金融 | ✅ **已验收合并**（2026-08-29 PR #504，独立复算 43p/3s/1xf 一致；批次门禁 @`85e4b1fd` 见台账 08-29 行；8792 未切待裁决） |
| 11 | `2026-08-29-conformance-seam-census-workorder.md` | P0 | 金融 | ✅ **已验收合并**（2026-08-29 PR #505，独立复算 86p 一致、普查 7/14 实数核对；收口 docs PR #507） |
| 12 | `2026-08-29-llm-transport-conformance-workorder.md` | P1 | 金融 | ✅ **已完成合并**（2026-08-29 PR #513，套件 21P，baseline 空）：http/cli×LT-1..5；CLI 类名承载故障 + 1s 地板钉成显式契约——**缝普查 P1 三张全部收官** |
| 13 | `2026-08-29-market-snapshot-conformance-workorder.md` | P1 | 金融 | ✅ **已完成合并**（2026-08-29 PR #512，套件 28P，baseline 空）：旁路+三源×MS-1..5；新增关键面=发布产物过 root contract（此前无测试跑校验器） |
| 14 | `2026-08-29-datablock-conformance-workorder.md` | P1 | 金融 | ✅ **已验收合并**（2026-08-29 PR #510，门禁 7226P/0F @`0fe7d20f` 收据 exit 0）：DB-1..6 × 20 块；装配对账首跑抓到 MARKET_DAILY 绕门控（→ #16） |
| 15 | `2026-08-29-frozen-thirty-kb-state-workorder.md` | P1 | 金融 | ✅ **已修复合并**（2026-08-29 PR #509，台账 `R-20260829-01`）：dry-run 钉解析态夹具+哨兵 + benchmark 缺口检查接别名归一（第二层根因，工单未预判）；全量回到 0F |
| 16 | `2026-08-29-market-daily-gating-workorder.md` | P1 | 金融 | ✅ **已修复**（2026-08-29 台账 `R-20260829-02`，分支 `fix/market-daily-gating`）：mainline_current 档 owner 预取接 provider_enabled 门；裁剪=诚实缺席+缺口声明；棘轮 XPASS 清账闭环首次真实运转 |
| 17 | `2026-08-29-rejudge-pending-replayability-workorder.md` | P2 | 金融 | ✅ **已修复合并**（2026-08-29 PR #516，台账 `R-20260829-04`）：行即夹具（内联请求+答案）+episode_task_id 溯源+可重放/stale 如实分组+CLI 导出夹具（清账准备步固化）；旧 49 条归 stale |
| 18 | `2026-08-29-judge-fallback-chain-workorder.md` | **P1** | 金融 | ✅ **已实现合并**（2026-08-29 PR #515，台账 `R-20260829-03`）+ 增量 `R-20260830-01`（CLI 形态备胎）：判官链主+显式备胎（新词表 FALLBACK_*，backend=grok-cli 走 CLI 传输），槽位轮转换人重试；不退相关自审红线不破。**激活窗口=2026-09-02（用户拍板订正：sol 长期主，grok 以备胎回归——不是原注释的「切回 grok 主」；手册与 #515 同工单）**；当前 sol 单主照跑不受影响 |

## 续表：2026-08-30 检索评测

| # | 工单 | 优先级 | 主仓 | 一句话 |
|---|------|--------|------|--------|
| 19 | `2026-08-30-wiki-aperture-ablation-workorder.md` | P1 | 金融 | ⏳ **待验收**：分支 `eval/wiki-aperture-ablation`，台账 `R-20260830-06`。两轮都停在 L0「无资格」（不是三铲无用）：轮 1 索引 stale → 0/6；轮 2 结构版 `fresh` → **2/6**。90s 现网预算装不下三铲。预算够对照见 #20。报告 `docs/verification/2026-08-30-wiki-aperture-ablation.md` |
| 20 | `2026-08-31-wiki-aperture-budget-workorder.md` | P1 | 金融 | ⏳ **待验收**：分支 `eval/wiki-aperture-budget`，台账 `R-20260831-01`。240s 评测下 L0 **6/6**；L1 增量 C+3.8/K+5、反方 6/6、不挤窗；L2 `mean(A2−A0)=−1.667`、4 题 A2 更低。结论档 4「检索有增量，答案无显著差，保持现状」。报告 `docs/verification/2026-08-31-wiki-aperture-budget.md` |

P2 已登记不立单：ArtifactProvider（6 实现）/ Workbench SkillExecutor（7 skill_id）——见普查报告 §一。

## 依赖与并行约束

- **#4 部分依赖 #1**：08-28 的 review 队列要等 #1 补跑后才生成；#4 可先做 08-26/27 的 18 条。
- **#5 接收 #2 的转出**：#2 分诊出的 disclosure 类任务（约 19 条）转 #5 收口。
- **#6 与 #2 有交集**：医药概念页升 L1 若需新 DeepDive 材料，由 #6 的闭环产出，#2 只负责登记状态。
- **知识库仓写入错峰**：#2/#3/#4/#6 都会写 relations/概念页，**各开自己的分支**，同时最多两单并行，且避免同题材同时写；开工前 `git worktree list` + 逐条认领 `git status`（AGENTS.md「这棵树是否已经有别人在动」一节是硬约束）。
- **#1 补跑期间**，金融仓 DuckDB 不得有其他写入任务。
- **#5 的归档提交**与抓取侧共享 `wiki/raw/disclosures/` 活库，add 必须限定路径。
- **#8 前置阻塞在用户**：ClickHouse 鉴权续期（供应商侧）→ 更新 `~/.secrets/clickhouse.env`，agent 只能等。回补须盘后、避开夜跑锁窗口。
- **#9 等在途队列收尾再开工**：个股 IMA 卡已有 launchd 串行队列在跑（08-28 晚 75/95、0 失败，之后接 8 个题材 DeepDive）。**IMA 通道被它独占**（同一时间只问一次），#6 的 concept 切片和 #9 的残余增量都要排在它后面或错峰；任何人不得并行往 IMA 发批量任务、不得碰 `kb-wt-ima-stock-0826` 树。

## 已确认不欠（别再盘一遍）

- `raw/*full.md` → `report_contexts.json`：249/249 已齐。
- DuckDB 六张主 fact 表：覆盖到 2026-08-28，三日质检全绿，无断档。
- 跨仓队列 08-13 ~ 08-21 各批：已被 triage 处理为 done/skipped（带理由），不是积压。
- 复盘验证/双盲台账停更：夜跑退役的设计决定。

## 通用纪律（每份工单内已各自展开）

开工 `git status --short && git branch --show-current && git worktree list`；大任务开分支；禁 `git add -A`，一律 pathspec 提交；不合 main、不强推；exports 产物与实验台账默认不提交；预注册台账号一律 `python3 scripts/claim_ledger_id.py claim --branch <分支>`，禁手工取号。
