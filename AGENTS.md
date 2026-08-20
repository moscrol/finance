## 👤 用户偏好（核心，必读 —— 教学模式）

- **语言：中文。** 目标是**边做边学**（非科班背景），不只是把活干完。
- **讲原理 + 讲技术选型**：用到某技术先简述它是什么、为什么用；**务必给替代方案对比**（反复强调的重点）；能迁移到别处的知识点请点出“这在 X 场景也能用”。面试常考点可顺带点一句。
- **学习重点**：RAG、Hybrid 检索（向量 + BM25 + rerank）等；实现时优先选能学到主流/前沿做法的方案并解释取舍。
- **Git 约定**：开工先 `git status --short && git branch --show-current`；大任务必开分支（`<type>/<short-task>`），**合并 `main` 必须等我确认**，不强推；小文档修补可直接 `main`。
- 🚫 **红线**：禁提交 `.env*` / 密钥 / `*.pdf|zip|duckdb|db` / `.DS_Store` / 缓存或虚拟环境；不写明文密钥；知识库大 JSON（relations/）走 `query_relations.py`，别直接 `cat`；不擅自合并 `main`、不强推。
- 完整偏好见 `.agent-memory/30_conventions/preferences.md`（repo 内软链 → `/Users/a77/agent-memory`，已 gitignore）。

> 📒 **台账地图**：所有台账（复盘验证/晨汇/卖方研报等）的 canonical 路径、格式与唯一写入者，见 `docs/learning/ledger-map.md`；新增台账先在那登记。

## 🚪 金融问答正门

默认只收一句话：`python3 -m intelligence.cli ask "<问题>"`。追问用 `chat`；要模型自己选工具才用 `agent`（opt-in）。Workbench UI 走 Episode（`TurnOrchestrator.run_turn`），不要用 CLI 冒充那套会话 id 合同。

评接口深浅、找产品入口：读 `docs/agent-product-door.md`（门 / 两条引擎 / 积木）。工具注册表和 `AskOptions` 数据块开关是积木，不是门。

检索旗标（`--kb-mode` / `--wiki-rag-mode` / `--modules`）是逃生口，不要写进日常口令。问「有多少能力」时点名分母：`skills/`、`.claude/skills/`、或工具注册表——三套不是同一张表，不要加总。

写入正门是 `python3 -m market_feature_store.cli daily-full`。`fact_sector_daily` 是 VIEW。编码任务走下一节代码地图 CLI，不要用问答正门冒充。

已决策、不是缺口：技能桥只开一个、飞书 Bitable 写入退役、飞书 IM（`intelligence.cli feishu-bot`）退役。

## 🗺️ 本地代码地图（编码任务先走这里）

编码任务先 `python3 scripts/code_map.py query "<问题>"`。禁止把空图 `get_architecture_overview` 写成架构结论；禁止 `code-review-graph init|install`；禁止 DeepWiki `generate_wiki` / 对本仓 private index。MCP 已连接 ≠ 地图可用。

## 🔁 用户纠偏必落 correction（强制，任何 agent 会话）

用户在对话里对系统的判断/解读表达纠正时（信号词如「不对」「应该是」「不是这样」「你理解错了」等否定/修正表述，**不需要用户使用任何固定格式**），agent 必须当场把纠偏落进台账：

```bash
python3 -m intelligence.cli record-correction --correction "<纠正后的说法>" --original "<系统原来的错误说法>" [--principle "<可复用原则>"] [--theme <相关题材>]
```

- 落点：`intelligence/users/<user>/corrections.jsonl`（gitignored 用户私有层）。
- 回灌：无需用户触发——每日复盘的「框架解读」步（`perspective framework-daily`）与 foresight 发问会自动加载最近 corrections 作为上下文。
- 用户沉默 = 默认认可，不落任何记录；只有明确纠正才落。
- 这是 perspective-lab 循环 A（学用户视角）的唯一入口，漏落 = 框架无法迭代。落完在回复里用一句话确认即可（如「已落 correction」），不要打断对话流。

## 🧠 共享记忆底座（开工前先读）

本机有一个跨 Agent 共享的记忆底座（Obsidian vault）：`/Users/a77/agent-memory`（仓库 `linxiaoqi5111-del/agent-memory`）。

**开始任务前先读：**
- `.agent-memory/30_conventions/preferences.md` — 用户偏好与人设（教学模式：讲原理 + 讲技术选型/替代方案对比 + 标注可复用知识点；Git 约定；红线）
- 本项目对应笔记 `.agent-memory/20_projects/finance-workspace-private.md` — 项目背景、关键决策、任务看板

**完成后沉淀：** 先判断层级：项目级代码/配置/流程/架构/数据管线决策才追加到 `.agent-memory/20_projects/finance-workspace-private.md` 的「交接记录」；稳定且可跨任务复用的方法论提炼进 `.agent-memory/10_knowledge/`；单次问答评分、用户纠偏、经验样本优先写项目内学习层（如 `experience_cards.jsonl` / `corrections.jsonl`），不要把聊天流水塞进项目交接。
详细回写步骤见 vault `.agent-memory/40_playbooks/devin-writeback.md`。

## 📚 外部知识源（检索起点）

本项目依赖三处外部知识源，agent 遇到问题时可主动检索：

1. **`~/agent-memory/10_knowledge/`** — 已沉淀的失败形状、审查清单（跨项目可复用方法论）
   - 如：`evidence-hygiene-three-failure-shapes.md`（证据卫生三大失败形状）
   - 触发场景：agent 自审、证据链校验、测试对账失败归因

2. **`~/ai-agent-book/`** — agent 使用模式、最佳实践（通用方法论）
   - 触发场景：不确定某类任务的标准做法、需要参考既有 pattern

3. **`~/harness-reference/`** — 工具包总纲 + 检索源索引（**先读 `KIT.md`**）
   - `KIT.md`：三件套总纲（设计 / 搭建 / 审计）与各件现状、缺口
   - `PLAYBOOK.md`：方法论——两条铁律（先定位再查源、先解决问题再优化）+ 五阶段 + 反模式清单
   - `TOOLKIT.md`：**审计**工具包，按成本档位 A–H 组织（选档规则：能用 0 档复现的绝不上 4 档）
   - `INDEX.md`：7 个信源族 + **精读状态**（`仅见标题` 不得进入结论）+ **不可搬运量纲**
   - `README.md`：五条纪律，含"资料给形状、量纲自己算""同族一致不算交叉验证"
   - 触发场景：需要审查工具、需要查证某个 API 行为、需要交叉验证某个事实

**使用约束**：检索时必须用 `grep` / `find_file_by_name` 等工具明确查找，不得臆测内容或路径。若某份知识在上述三处都没有，则说明尚未沉淀——可在本轮任务完成后按沉淀规则补录。

## 🧰 工具包三件套（2026-08-12 确立的原则）

**搭建 agent 的能力要沉淀成三件套：正确的设计、正确的搭建、正确的审计。
检索源只提供方法论（形状），工具包提供可执行的组件与判据。
任何写出来且可复用的组件与工具，必须落进对应那一件，不留在一次性脚本里。**

三者的**失败方式完全不同**，混在一起就都做不好：设计错了骨架，后面每步都在补救；
搭建没编目，同一个坑踩 N 遍；审计没有可判定的观测量，就会拿噪声当信号、或红着不看。

| 件 | 现状 | 入口 |
|---|---|---|
| 正确的设计 | ⚠ 材料齐备未收口 | `~/agent-memory/10_knowledge/`（骨架判据）+ `70_tutor/` 20 篇（按 agent 分层） |
| 正确的搭建 | ✅ 已建（2026-08-12） | `~/harness-reference/BUILD.md` —— 七个可迁移模式 + 16 个零件 |
| 正确的审计 | ✅ 已成型 | `~/harness-reference/TOOLKIT.md` —— 按成本档位 A–H |

**落地要求**：本仓写出来的通用件（如 SessionStart 事实注入、棘轮式路径门禁、
带条件的测试收据、按分支归属而非 mtime 的交接判定）属于「搭建」那一件，
新增或改动后回写 `KIT.md`，**不另建第二份清单**。

## Git Branch Safety Rules（强制）

`main` 是当前共享基线，不代表已经完美稳定；本项目仍在持续修缮。任何 agent 开始工作时必须先执行并汇报：

```bash
git status --short
git branch --show-current
```

规则：
- **大任务默认不开在 `main` 上做**：baseline 批次、PDF ingest 规则/脚本、Theme Radar 规则、数据源脚本、DuckDB/飞书写入逻辑、批量生成或跨仓库修改，都必须先从最新 `main` 新建任务分支。
- 推荐流程：`git checkout main` → `git pull` → `git checkout -b <type>/<short-task>` → 工作 → commit → push 分支；合并回 `main` 必须等用户明确确认。
- 小型文档/规则修补可以直接在 `main` 做，但提交前仍要检查风险文件。
- 分支命名：`baseline/<批次或公司名>`、`pdf-ingest/<日期或材料名>`、`theme-radar/<题材或能力>`、`data-source/<来源名>`、`fix/<问题>`。
- commit 前必须检查不要提交：`.env*`、`mcp_config.json`、`feishu_config.json`、`*.pdf`、`*.zip`、`*.duckdb`、`*.db`、`*.sqlite*`、`*.pptx`、`.DS_Store`、`__MACOSX/`、`._*`、缓存和虚拟环境。

### 🟢 合并纪律：CI 绿才可合（强制）

日常远程是本机 Gitea（`gitea` / `remote.pushDefault=gitea`）。GitHub `origin` 保留，但不假设会解封。Gitea 不跑 Actions，这条纪律仍是合并闸。**任何 agent 合并 PR 前必须在本机跑完等价检查**：

```bash
# 叶子：python / frontend / e2e；聚合仍叫 workbench-check
.venv-workbench/bin/python -m ruff check . && .venv-workbench/bin/python -m pytest -q
cd intelligence/webapp && pnpm lint && pnpm typecheck && pnpm test && pnpm build
```

- `python` / `frontend` / `e2e` / `registry-check` 任一红或未出结论：**禁止合并**，先修红或等结论，不允许「带红合入、回头再修」。
- `workbench-check` 是聚合 job：叶子是并行的 `python` / `frontend` / `e2e`。聚合红时先看是哪片叶子红，不要再假设「前面红了后面没跑」。
- `data-quality-check` 按 paths 触发：触发了就必须绿；没触发不算数。
- 教训在案：2026-07-18 → 08-13 main 曾 142 次连红仍照常合并，E2E 被 fail-fast 掩盖 26 天，期间合入的门禁回退零信号（#337/#339 修复、#342 根治步骤掩红、本文件把串行单 job 拆成并行叶子）。
- 若 GitHub 解封且升级 Pro / 转公开仓，第一时间把本条固化为真分支保护（required checks：`workbench-check` + `registry-check`，strict 不开），并更新本节。

> 📋 **验收/质检 session**（对执行方交付的 PR 批次做独立验收→合并→切 8792→回写台账）：规程 `docs/workflows/acceptance-workflow.md`。

### 🟢 PR 关闭纪律（强制）

关闭 PR 必须留下接替指针（替代 PR / 提交 / 文档路径）或废弃理由。禁止静默关闭。合入后由托管端删除已合并分支。

### 🔴 开工前必查：这棵树是否已经有别人在动

`git status` + `git branch` **不足以判断你能不能动手**。本仓有多棵 worktree 共享同一个 `.git`，
而**同一棵树可以同时有两个 agent 在工作**——此时你们共用同一个 git 索引（staging area）。
开工前必须加这两条，并**逐条认领** `git status` 的每一行：

```bash
git worktree list      # 有几棵树、各在哪个分支、哪棵是我要用的
git status --short     # 逐条问：这个改动是我做的吗？
```

**只要出现不属于自己的未提交改动（他人足迹），先停下**，选一条：

- **另开干净树**（推荐）：`git worktree add <新路径> <base-ref>`，在新树干活。
  venv 里没有 `.pth` / editable 安装，加载哪份代码由 cwd 决定，
  所以新树里可以直接用主树的 `.venv-workbench/bin/python`。
- **留在原树**，则：① 只能用 pathspec 提交（见下）；
  ② **不得跑「全量测试对账」类验收**——那个 exit code 只对
  「混着他人未提交改动的树」成立，**不对你的 revision 成立**，写进结论就是假证据。

**提交纪律（两条硬约束）**：

- 🚫 **禁用 `git add -A` / `git add .`** —— 会把他人未跟踪文件一并暂存。
- ✅ **一律 `git commit -- <明确文件列表>`**（pathspec 模式）。
  裸 `git commit` 提交的是**整个索引**：如果他在你 `git add` 与 `git commit` 之间
  把自己的文件暂存了，那些文件就会被你的 commit 带走，而你的 `git add` 完全无辜。

**实测事故（2026-08-07）**：`dae9c8c7` 本应只含 1 个文档，实际吞掉另一个 agent 的 4 个在途文件
（2 个源码模块 + 1 个既有测试 + 1 个新建测试 187 行）。他当时 `git status` 会看到自己的活凭空消失。
用 `git reset --soft HEAD~1` 退回（`--soft` 不碰工作树，文件内容一字未动），
改 pathspec 重提为 `7dd25ba6`。**根因是「`git commit` 提交整个索引」，不是 `git add` 写错。**

<claude-mem-context>
# Memory Context

# [金融] recent context, 2026-05-27 12:00pm GMT+8

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (16,658t read) | 432,523t work | 96% savings

### May 26, 2026
S1393 Full.md processing workflow validation and data quality verification (May 26 at 5:33 PM)
S1395 Theme-radar batch processing quality verification and field fixes for graph_only confidence and baseline evidence layering (May 26 at 5:44 PM)
S1397 修复 fupanhui 研报详情页结构异常问题（新上传的空芯光纤研报结构与其他不同），并改进实体回填管线的上下文提取质量。之后用户决定恢复原始文件，转向搭建截图中的新功能。 (May 26 at 6:20 PM)
S1398 Scaffold the basic framework for a screenshot-based "theme-radar" feature in the 金融 project, starting with architecture and tolerating incomplete data (May 26 at 9:42 PM)
S1400 User confirmed Option A (Theme Radar Workbench) — agent preparing detailed design (May 26 at 9:46 PM)
S1401 User questioned why a web UI is needed — suggesting Claude conversation + theme-radar skill may already suffice (May 26 at 9:46 PM)
S1403 Continue ingesting Desktop/研報 PDFs into finance wiki knowledge graph — process next date directory (2026-04-28 batch) (May 26 at 9:51 PM)
2546 10:19p 🟣 Source note classification pipeline completed for 2026-04-29 batch
2547 " 🔵 2026-04-28 directory scoped with 5 unique PDFs for next batch
2549 10:21p 🟣 2026-04-28 batch extraction launched via automated Python pipeline
2548 10:29p 🔵 2026-04-28 source note extraction already complete from previous session
2550 10:30p 🟣 2026-04-28 batch extraction completed — 5 source notes written successfully
2551 " 🔵 0427狙击龙虎榜 OCR content reveals three key themes
2552 " 🔵 0427调研日报 covers 亿纬锂能, 益生股份, 聚灿光电 with L3-level IR record data
2553 10:31p ⚖️ 0427狙击龙虎榜 source note deleted due to poor OCR quality and unsuitable source type
S1405 继续往下做 — 处理下一个日期目录的 PDF ingest pipeline，以及 "那你再做两个日期" 要求再处理两个日期 (May 26 at 10:31 PM)
S1402 Process Desktop/研報 PDFs into finance wiki knowledge graph, one date directory at a time, oldest first, using pdf skill pipeline (May 26 at 10:31 PM)
2554 10:33p 🔵 2026-04-27 batch: 6 unique PDFs after SHA256 dedup, mixed date labels
2555 10:34p ✅ 2026-04-27 batch: 6 source notes extracted with stub ingest-plans
2556 10:42p ✅ 2026-04-27 batch fully classified: 6 source notes processed, 3 must_write entities flagged
2557 10:49p 🔵 PDF deduplication rationale explored in primary session
2559 " ⚖️ User directs primary session to process two more date directories
S1404 继续往下做 — continue processing the PDF ingest pipeline for the next earliest date directory (May 26 at 10:49 PM)
2558 10:55p 🔵 Knowledge base backfill workflow consumes excessive tokens
2577 " 🟣 Closed-loop backfill to baseline workflow completed for 比亚迪
2560 10:56p 🔵 2026-04-26 directory contains 风口研报 format instead of standard naming
2561 " 🔵 风口研报 PDFs in 2026-04-26 are image-based, require OCR
2562 " 🔵 2026-04-23 batch content preview: 超节点, 钠电, 白酒, 燃气轮机
2563 " 🟣 OCR extraction pipeline deployed for image-based 风口研报 PDFs
2564 " 🔵 OCR extraction task (session 39595) may have hung — primary session attempted Ctrl+C
2565 10:58p 🔵 OCR extraction confirmed not hung — tesseract actively processing page 2 of 风口研报1
2566 " 🔵 Tesseract OCR completed page 2 of first 风口研报 — pipeline progressing
2567 " 🔵 OCR pipeline progressing: 风口研报1 done, 风口研报2 page 1 rendering
2568 10:59p ⚖️ Primary session aborted slow OCR extraction by killing parent Python process
2569 " ✅ Background extraction session 39595 confirmed killed (exit code -1)
2570 " 🔵 No source notes survived the abort — 0/6 PDFs extracted
2571 " 🔵 0426风口研报1 source note survived the kill — written at 22:58:42
2573 " 🟣 0423 text-based PDFs successfully extracted — 3 source notes created instantly
2574 " 🔵 Improved OCR at 140 DPI making fast progress — on last page of last PDF
2572 " 🔵 0426风口研报1 content: 强一股份 MEMS探针卡 + 伊戈尔 SST/数据中心
2575 11:06p 🟣 Improved OCR pipeline succeeded — all 6 source notes for batches 0426 and 0423 extracted
2576 11:08p 🔵 Entity existence check: 9 of 12 entities already exist in wiki/entities/
2584 " 🔵 Primary session surveys next 5 date directories for PDF ingest pipeline
2578 11:10p 🔵 Agent stuck in read-apply-verify loop on AGENTS.md
2579 11:11p 🔵 比亚迪 entity page verified with full baseline and preserved historical delta
2580 11:22p 🔵 entity_exposures.json confirmed with multi-source evidence layering for all three companies
2581 " 🔵 evidence_index.json confirmed with all 5 比亚迪 evidence entries
2582 " 🔵 Knowledge base inventory: 1133 entities, 292 concepts, 362 sources
2583 " 🔵 Knowledge base now uses multiple baseline data sources beyond iFinD
### May 27, 2026
2587 1:45a 🔵 AGENTS.md contains session logs, backfill workflow rules, and evidence layering constraints
2585 1:49a 🟣 PDF extraction completed for 5 date directories (2026-04-22 through 2026-04-13)
2586 " 🟣 Classification phase started on 19 new source notes across 5 date directories
2591 1:50a ✅ Write-back pipeline completed for 19 classified source notes
2588 1:56a 🔵 AGENTS.md operational rules read in full ahead of optimization
2589 " 🔵 AGENTS.md session logs document completed backfill achievements
2590 " ✅ AGENTS.md baseline sourcing rules refactored from iFinD-only to multi-source
2592 1:59a ✅ Write-back pipeline verified — all 19 source notes successfully backfilled
2593 2:05a 🔵 theme-radar radar.py requires --term flag, not positional argument
2594 " 🔵 theme-radar reports generated for 算力PCB and 3D打印钛合金
2595 12:00p ✅ 今日复盘请求

Access 433k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>

## Agent Token Discipline / 低 Token 工作约束

本项目知识库体量较大，agent 默认不得通过通读目录正文来“了解项目”。Codex、Windsurf、Claude 或其他 agent 在本目录工作时，都必须优先使用索引、脚本 summary 和精确命中读取，避免不必要的 token 消耗。

### 总原则

- 优先读取 `AGENTS.md`、`CLAUDE.md`、最近任务摘要、脚本输出 summary、manifest 或 JSON 统计。
- 优先使用 `rg --files`、`find`、`wc`、`jq`、Python 脚本生成索引或 manifest。
- 禁止为了探索而批量读取 `wiki/entities/`、`wiki/concepts/`、`wiki/sources/`、`wiki/raw/` 正文。
- 只有当某个具体文件是当前写入目标、校验目标或错误定位目标时，才读取正文。
- 每次读取正文前先判断：能否用文件名、frontmatter、脚本 summary、manifest 或精确 `rg` 解决；如果可以，就不要读正文。
- 如果 agent 发现自己准备读取大量文件正文，必须停止并改用索引、manifest 或脚本 summary。

### 回填目标必须先确认

当用户说“回填知识库”时，agent 必须先确认或从上下文判断本轮目标，不得混用流程：

1. `context_only`：只把 `raw/*-full.md` 研报写入 `relations/report_contexts.json`，并生成 `wiki/raw/entity-delta-backfill/*.entity-delta.json` payload；不更新 `entities/*.md`。
   - 使用：`python3 scripts/backfill_entities_from_full_reports.py --write-context ...`
   - 输出必须明确说明：本轮是 report context / payload 回填，不是实体正文写入。
2. `entity_apply`：尝试把 hard delta 写入 `entities/*.md`。
   - 使用：`python3 scripts/backfill_entities_from_full_reports.py --write-context --apply ...`
   - 只有 payload 中存在非 `graph_only` / 非 `exposure_only` 的 hard delta 时，才可能更新实体正文。
   - 如果 `updates=0`、`written=0`，或全部候选都是 `graph_only` / `exposure_only`，必须报告“本批无可写实体正文”，不得伪造实体更新。
3. `review_only`：只生成 payload 和 summary，人工抽查后再决定是否 apply。
   - 使用：不加 `--apply`；必要时只抽查 1 个 payload 和 1-3 个目标文件。

### Raw Full 回填专用规则

- `raw/*-full.md` 回填必须优先跑脚本，不要让模型自己逐篇阅读 full.md 正文。
- 默认使用 `scripts/backfill_entities_from_full_reports.py` 生成 payload / summary。
- 每批只处理小批量，例如 3-5 篇；不要一次让模型审完整 raw 目录。
- 质检时最多抽查 1 个 payload 和 1-3 个目标 entity/concept 文件。
- 需要确认实体/概念是否存在时，用 `rg --files` 或精确 `rg 公司名/概念名`，不要读整目录。
- raw full 研报提及默认写 `report_context` / `graph_only` / `exposure_only`。
- raw full 研报中的二手公司级强事实（送样、样品、长协、明确客户/供应关系、控股/持股关键产业链公司、出货/销量/收入同比、良率、市占率/项目数量等带数字口径事实）可升级为 `evidence_layer=L1_L3_candidate` + `update_type=review_candidate`，但默认仍保持 `graph_only=true` / `exposure_only=true`，只进图谱和证据索引，供 theme-radar 排序与人工复核。
- 只有公告、订单、合同、中标、认证、量产、投产、扩产、产能、客户导入、项目落地、带金额/数量口径的公司级财务或出货事实，才允许写实体正文。

### Raw Full 完整回填闭环

完整 raw full 回填闭环不是只跑 `--write-context`。闭环顺序是：

1. `full.md -> report_contexts.json + entity-delta payload`
   - 生成研报级产业链上下文，供 theme-radar 使用。
   - 生成 `wiki/raw/entity-delta-backfill/*.entity-delta.json`，作为候选审查材料。
2. `payload -> hard delta -> entities/*.md`
   - 只有 payload 中存在非 `graph_only` / 非 `exposure_only` 的 hard delta，才进入 `--apply`。
   - 如果本批没有 hard delta，闭环应在 report context / payload 层停止，并明确报告停止原因。
3. `entities 新候选/重要暴露公司 -> multi-source baseline`
   - 只有新增实体、重要核心暴露公司、或缺少基础画像且确有后续研究价值时，才触发 baseline 补全。
   - baseline 可以来自 iFinD、AKShare、年报/定期报告、公告、交易所互动、公司官网、监管披露或其他明确公司基础资料。
   - baseline 只能写真实主营业务、主营产品、收入结构、毛利率、行业分类、证券基础信息等稳定事实；不得把 raw full 研报判断、短期催化或 unsupported `core` 结论写入 baseline。
   - 写入时必须标明真实 `baseline_source_type`、raw source 路径和证据层；不得把 AKShare、公告、官网、人工核验资料标成 iFinD。

执行完整闭环时，agent 必须逐段报告当前停在哪一层：`report_context/payload`、`entities`、或 `baseline`。如果没有进入下一层，必须说明是因为 `updates=0`、全部为 `graph_only/exposure_only`、缺少 hard delta，还是缺少 baseline 触发条件。

### 遇到“继续回填知识库”时

1. 先读本文件的最近任务摘要或用户指定的 `start-after`。
2. 确认任务类型：`raw full 回填`、`PDF source note 回填`、`baseline 回填`，不要混用流程。
3. 确认目标模式：`context_only`、`entity_apply` 或 `review_only`。
4. 用脚本处理下一小批。
5. 只看脚本 summary；必要时抽查少量命中文件。
6. 输出批次摘要：处理文件数、payload 数、updates 数、graph_only/exposure_only 数、hard delta 数、真正写入实体数、baseline 是否触发、未进入下一层的原因、异常、下一批游标。

## Project Memory: Theme-Radar Alignment

All future knowledge-base updates in this workspace must be aligned to the `theme-radar` skill as the downstream consumer. Treat theme-radar as the organizing contract for ingestion quality:

- Keep evidence layers separate: L1 industry translation from reports, L2 baseline from structured or explicitly sourced company fundamentals, L3 facts from announcements/orders/certifications/production/customer validation, and L4 market signals.
- Do not treat `raw/*full.md` report mentions as entity deltas by default. Full-report backfill must split report context, graph-only/exposure-only company exposure, and true company-level delta.
- Second-hand but specific company facts from `raw/*full.md` may be kept as `L1_L3_candidate` / `review_candidate` in graph/evidence only. This is a theme-radar prioritization signal, not an entity正文 delta and not an L2 baseline.
- Research-report PDFs and daily/market-logic PDF digests are valid upstream sources for discovering entities and evidence, after OCR/Markdown extraction, but they must follow the same gate: name-only mentions stay in report context/watchlist, weak industry-chain mentions become graph-only/exposure-only, and only repeated core A-share candidates or hard company-level facts should create/update entity pages.
- Generic upstream materials, upstream equipment, downstream demand/customer-side, and ecosystem companies should normally be `graph_only` / `exposure_only` with `peripheral` or weak `related` strength unless company-level hard evidence exists.
- Company baseline must come from real structured baseline sources or explicitly sourced company fundamentals: iFinD, AKShare, annual reports/periodic reports, announcements, exchange interactions, official websites, regulatory filings, or manually verified public fundamentals. Never write placeholder baseline text, automatic-batch evidence, or unsupported `core` claims.
- Baseline source identity must be truthful. Use source labels such as `baseline_source_type=ifind|akshare|annual_report|announcement|exchange_interaction|official_website|regulatory_filing|manual_verified`; the entity page and relation JSON must name the actual source type and raw source path.
- If a source returns rate-limit/empty/error text such as `用户使用工具已超限`, the baseline batch must stop for that source/company. Do not manually compile a baseline and label it with that failed source type, `L2`, or `update_type=baseline` until a valid raw file with usable fields is available.
- AKShare/public/manual verified data can support `L2` baseline only for stable fundamentals that the raw source actually contains or the manual verification explicitly documents. Do not label AKShare/public/manual data as `iFinD 基础资料 / 公司摘要`.
- Every new ingestion or cleanup script should preserve the fields theme-radar needs: `chain_layer`, `evidence_layer`, `update_type`, source links, raw source traceability, and conservative `core/related/peripheral` strength.
- If a data update would improve entity pages but degrade theme-radar company ranking, evidence separation, or supply-chain clarity, prefer the theme-radar-compatible representation.
