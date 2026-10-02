# finance-workspace-private · Agent 指令

A 股量化复盘 + 研究工具集：fupanhui / iFinD / AKShare 数据经 `market_feature_store` 写入 DuckDB，`intelligence/` 在其上做问答、深挖与前瞻。本文件是所有 agent（Cursor / Claude Code / Codex / Devin / Windsurf）的唯一指令源；`CLAUDE.md` 只是 `@AGENTS.md` 导入加几行 Claude Code 备注。这里只放每个会话都要成立的事实与规则；多步骤流程放 `skills/<name>/SKILL.md`，参考资料放 `docs/`，会漂的数字一律指向生成它的脚本。

## 用户偏好

- 中文交流。用户非科班、边做边学：用到某技术先说它是什么、为什么选它、有哪些替代方案及取舍；能迁移到别处的知识点点出来；术语和缩写首次出现释义一句。
- 完整偏好卡 `.agent-memory/30_conventions/preferences.md`（软链到 `~/agent-memory`）。SessionStart hook 会全文注入；没收到注入的 harness 开工前自己读一遍。

## 开工三件事

`scripts/session_facts.sh` 在 SessionStart 注入：所在 worktree 与分支、合入状态、解释器、代码地图新鲜度、未提交代码改动、上次测试收据、本分支在途交接。没看到这段就手动 `bash scripts/session_facts.sh`。

1. 认领工作树：`git worktree list && git status --short`，逐条问「这个改动是我做的吗」。本仓多棵 worktree 共享一个 `.git`，同一棵树可能有另一个 agent 在动。出现不属于你的未提交改动：另开 `git worktree add <路径> <base>`（推荐；venv 没有 editable 安装，新树直接用主树 `.venv-workbench/bin/python`），或留在原树但只用 pathspec 提交、且不把「全量测试」结论写进交接（那个 exit code 属于混合树，不属于你的 revision）。
2. 解释器：pytest / ruff 一律 `.venv-workbench/bin/python -m …`。宿主 python3 缺依赖，失败数会偏高且看起来完全合理（实测 71 vs 14）。conftest 与 pre-commit 会拦提交，拦不住你已经读错的数字。
3. 读本分支的在途交接 `docs/handoffs/inflight/<分支名，/ 换 ->.md`（hook 已注入前约 2000 字符）。完工用 `handoff` skill 覆写，在动作完成之后写，否则注入给下一个 agent 的是假状态。

新工作树、换机器、搭建 Agent：先 `python3 scripts/workspace.py doctor`；安装与离线样例走 `docs/workflows/agent-foundation.md`。六图来源及更新触发器在 `docs/agent-maps.json`，源文件存在不代表语义已验证或生产已部署。

## 三个正门

- 金融问答：`python3 -m intelligence.cli ask "<问题>"`；追问 `chat`；要模型自选工具才 `agent`（opt-in）。Workbench UI 走 Episode（`TurnOrchestrator.run_turn`），不用 CLI 冒充它的会话 id 合同。作答前可用 `intelligence.cli prime "<问题>"` 拿校准 + 个人库 + 图谱前缀做 grounding。`--kb-mode` / `--wiki-rag-mode` / `--modules` 是逃生口，不写进日常口令。
- 写入复盘事实：`python3 -m market_feature_store.cli daily-full --trade-date <今天>`（staging 写 + 原子换库），**只对当天盘后**；夜跑编排走 `skills/daily-full-review`。**历史日 / 断档回补一律走 `skills/duckdb-backfill/SKILL.md`**——`daily-full`、东财快照、申万 realtime 都是「取最新」语义，把历史日期塞进去就是把今天盘中价写成那天收盘（2026-09-07 实测）；原子换库保的是写入完整性，不保日期语义正确。fupanhui 停抓期间（2026-09-07 起账号风控）只用 `run_review_sync.py --plan local`，full / cheap 会打复盘会，跑了必失败且续期惩罚。不手搓 inline SQL / heredoc 凑数，不用 `daily-update` / `daily-full-exec` 直写生产库。
- 编码任务：先 `python3 scripts/code_map.py query "<问题>"`（stale 先 `build`；status fail-closed；夜间刷新装 `scripts/install_code_map_refresh.py`）。禁止把空图 `get_architecture_overview` 写成架构结论；禁止 `code-review-graph init|install`；禁止 DeepWiki `generate_wiki` / 对本仓 private index。MCP 已连接 ≠ 地图可用。

**所有联网操作统一走 `web-access` skill**（搜索、抓取、需登录态的页面、动态渲染页、社交平台内容），不自起浏览器、不直连。规范源 `~/.claude/skills/web-access/SKILL.md`——它在仓外，非 Claude harness 直接读该路径，不要因为本仓搜不到就当它不存在。运行时细节（CDP proxy `localhost:3456`、Chrome remote debugging、IIFE 包裹）见 `docs/data-sources/runtime-and-pitfalls.md`。

评接口深浅、找产品入口读 `docs/agent-product-door.md`（门 / 两条引擎 / 积木；工具注册表与 `AskOptions` 开关是积木不是门）。骨架形状读 `git -C ~/harness-reference show gitea/main:DESIGN-stack.md`（SSOT 在 gitea，别读脏工作树）；「为什么是闭环不是流水线」读 `.agent-memory/10_knowledge/agent-system-closed-loop-first-principles.md`。分流的目标态 `docs/superpowers/specs/2026-08-30-optimized-orchestration-contract-design.md` 尚未落地，现状以门页为准，门页要与改 runtime 的提交一起改。跑马策略、板块相对强度、后验收益这类仍在**假设验证阶段**的实验，执行规则见 `docs/workflows/strategy-hypothesis-experiments.md`（实验台账七要素、分步最小单元、多窗口后验、指数只作背景、实验产物默认不提交）。

## 数据契约（DuckDB）

- 主库 `db/market_feature_store.duckdb`，星型模型，schema SSOT `market_feature_store/schema.sql`；表清单看 schema，不抄进文档。深挖前先查各 `fact_*` 的 `max(trade_date)` 验鲜（`docs/learning/current-duckdb-source.md`）。
- `fact_sector_daily` / `fact_sector_stock_daily` 是 VIEW，只暴露 `published` 那版板块快照；写入目标是 `fact_sector_*_daily_generation`，主键含 `sector_universe_snapshot_id`，用 `db.get_published_snapshot_id(con, trade_date)` 解析（无 published 回退 `'legacy'`，当日出现 published 后 legacy 自动让位）。往 VIEW 里 upsert 会报 `Catalog Error`。这层存在是因为供应商会换板块代码和名单，没有它答不了「当时用的是哪一版清单」。
- 覆盖率审计只能抓行数，抓不到「行在、值全 NULL」的空壳；重要回填后再抽 `price / pct_chg / amount` 非空或做跨日期 diff。底层 `fact_sector_stock_daily_generation` 已有行级 CHECK（至少带一个行情值），`quality.check_daily` 含空壳板块量具；2026-09-03 维护清过 810 万空壳行，2025-01-06~2026-03-30 成分股行情如实为缺，不是新断档。
- 分析脚本只读 canonical `fact_*` 表（`detect_turning_points.py`、`backtest_sector.py`，库路径可用 `MARKET_FEATURE_STORE_DB` 覆盖，不存在则 fail closed）。
- 复盘事实只走 `daily-full`。已退役 / 停用，勿跑勿恢复成第二条写入链：`scripts/sync_to_local.py`（无副作用 shim）、`scripts/fast_daily_sync.py`（写 VIEW 且拷昨日行改日期，值全空）、`scripts/backfill_sector_marginal.py`（写不存在的旧表）、旧库 `db/market.duckdb`、**飞书整体退役（Bitable 写入、IM 入口、自建应用与凭证，2026-09-11）**——自建应用与仓内全部飞书代码已删除，退役前只读导出在 `~/.finance-runtime/feishu-export-20260911/`，运维告警改走 `scripts/notify_ops.py`（零凭证）。
- 台账（复盘验证 / 晨汇 / 卖方研报…）的 canonical 路径、格式与唯一写入者见 `docs/learning/ledger-map.md`，新增台账先登记。预注册号一律 `python3 scripts/claim_ledger_id.py claim --branch <分支>`，不手工「当日 max+1」（check-then-act 会撞号，号不回收）。
- 数据源、CDP proxy、限流与字段坑：`docs/data-sources/runtime-and-pitfalls.md`（8 张飞书 Bitable 退役后各自的本地去处也在那份的「飞书」一节）。本仓不需要任何外部账号凭证：fupanhui 借用户 Chrome 登录态走 CDP proxy，iFinD 走本地 Node MCP，其余全是本地 DuckDB。

## 断言「我们没有 X」之前

- 权威事实源是 `.agent-memory/10_knowledge/finance-agent-capability-graph.md`（`graph_audit.py` 三级断言校验）。改能力回写它，不另建第二份清单。完整的负面断言纪律由用户级 SessionStart hook 注入，这里不抄（抄件已漂过一次）。
- 数数用解析器，不用固定行号：agent 可调工具全在 `intelligence/services/research_tool_registry.py::_DEFAULT_TOOL_METADATA`（带类型注解，AST 里是 `AnnAssign`），且逐个受 `contract.allowed_capabilities` 门控，定义了 ≠ 这次开着。
- 「有多少能力」先点名分母：`skills/`（仓内全集）、`.claude/skills/`（人工策划的视图子集）、工具注册表——三套不是同一张表，不加总、不写死个数（`comm -23 <(ls skills | grep -v '^lib$' | sort) <(ls .claude/skills | sort)` 看差集）。
- 编排层已存在：`answer_orchestrator` / `question_router` / `route_table` / `ask_planner` / `retrieval_planner` / `research_task_planner` / `research_plan` / `generic_research_owner`（`intelligence/services/`），`conversation_orchestrator`（`intelligence/runtime/`，管 loop 与预算）。
- 已在事故中验证的可迁移原则：配额在副作用前预占而非事后计数；全链 deadline 传绝对时刻；请求去重用 per-key single-flight，不用全局锁包慢 IO；授予的额度必须真传到最下游执行者，只进 telemetry 比不做更危险。

### 技能桥：刻意只开一个

- `intelligence/services/skill_tools.py`（已注册 `serenity-alpha`）；theme-radar 六模式走 `intelligence/services/theme_modules.run_module`。
- 其余 skill 未接入是设计决定不是缺口：多数会拉实时数据（fupanhui / iFinD / AKShare）或写回（DuckDB），接入会破坏 agent 只读 + 无外呼红线。要扩注册表，先论证不破这条线。

## Git 与合并

- 开工先报 `git status --short && git branch --show-current`。日常远程是 GitHub `origin`（`remote.pushDefault=origin`），基线用最新 `origin/main`；PR、评审和合入在 GitHub。Gitea 是本地恢复备份。同步、删枝、历史成果回收或平台故障时，读 `docs/workflows/dual-remote-collaboration.md`；备份保留的旧枝不自动补回 GitHub。
- 大任务从最新 `origin/main` 开 `<type>/<short-task>`（`feat/` `fix/` `baseline/` `pdf-ingest/` `theme-radar/` `data-source/`），小文档修补也走 GitHub PR。合并回 main 必须等用户确认，不强推（`~/.claude/hooks/block-dangerous-git.sh` 也会拦）。
- 提交只用 pathspec：`git add -- <文件>` 与 `git commit -- <文件>`；不用 `git add -A` / `git add .`。裸 `git commit` 提交的是整个索引，别人在你 add 和 commit 之间暂存的文件会被你带走（实测吞掉他人 4 个在途文件，靠 `git reset --soft HEAD~1` 退回）。
- 不提交 `.env*`、`mcp_config.json`、`feishu_config.json`、`*.pdf|zip|duckdb|db|sqlite*|pptx`、`.DS_Store`、`__MACOSX/`、`._*`、缓存与虚拟环境；不写明文密钥（pre-commit `block-forbidden-files` 兜底）。
- GitHub PR 合并前须通过 Actions，并在本机按改动范围核验等价 CI：`.venv-workbench/bin/python -m ruff check . && .venv-workbench/bin/python -m pytest -q`；前端 `cd intelligence/webapp && pnpm lint && pnpm typecheck && pnpm test && pnpm build`。任一叶子（python / frontend / e2e / registry-check）红或无结论都不合，不允许「带红合入回头再修」；聚合 job `workbench-check` 红先看哪片叶子红。`data-quality-check` 是**按 paths 条件触发**的第五道（`scripts/db_delta_*.py`、`tests/test_db_delta.py`、`skills/report-search/scripts/**`、它自己的 workflow 文件）：改到这些路径就必须跑绿，没触发则不算数、也不算缺结论。教训：main 曾连红 142 次照常合入，E2E 被 fail-fast 掩盖 26 天。GitHub main 使用真分支保护：必需检查 `workbench-check` + `registry-check`，strict 不开；管理员同样受保护，禁止强推和删除 main。
- 把一张收据当「全量绿」用之前，先让它自证收集面：`.venv-workbench/bin/python scripts/check_test_receipt.py <收据> --require-full-scope`。收据的 `target` 只记 pytest 的**位置参数**，`--ignore` / `-k` / `-m` / `--deselect` 一个都不显示，所以「仓根路径 + 12000 passed」看起来和真全量一模一样。教训：`a41e86dfc`（2026-08-20）把一个活测试误扫进 `scripts/archive/`，全树 `pytest -q` 此后 33 天停在 collection error 一条不跑；同期收据库里仍有 187 张「≥10000 passed / error=0 / exit 0 / target=仓根」的收据在流通，回查发现其 176 个 revision **全部带着那个坏文件**——它们只可能是收窄过的读数，而收据看不出来。现在 `scope` 段会记下收窄旋钮与 `collected`，并与读数对账（收了 N 条就得有 N 条读数）。
- 关闭 PR 必留接替指针（替代 PR / 提交 / 文档）或废弃理由，不静默关闭。验收 session 规程 `docs/workflows/acceptance-workflow.md`；全仓合入看板 `python3 scripts/worktree_board.py`。
- 门禁与修库不留现场：整库「改前快照 / 备份」一律走 `market_feature_store.db.clone_to_staging`（APFS `cp -c` 克隆，秒级、零额外占盘），不写 `shutil.copy2` / `cp` 整份拷；`run_main_gate.sh` 显式 `--basetemp` 在门禁绿时自动删（红保留，`GATE_KEEP_BASETEMP=1` 可留）；按提交号检出的 detached 门禁树跑完就 `git worktree remove`，批量用 `scripts/cleanup_gate_trees.sh`（默认 dry-run，只拆干净树）；带未提交内容或未合分支的遗留树收口走 `scripts/worktree_closeout.py`（点名、dry-run 收据即计划、先保全再拆），线落没落地看 `scripts/worktree_board.py --landed`。教训：2026-09-23 盘上静置 20 份 3.4 GB 整库拷贝（68 GB）+ 30 GB basetemp + 78 棵干净 detached 树，日烧 30–45 GB。

## 记忆、纠偏与沉淀

- 共享记忆底座 `~/agent-memory`（Obsidian vault，软链 `.agent-memory/`）。开工读 `20_projects/finance-workspace-private.md` 的必读段（hook 已注入）。完工分层沉淀：项目级决策在项目笔记「交接记录」只写一行索引，正文进 `docs/handoffs/inflight/<分支>.md`；跨任务可复用的方法论进 `10_knowledge/`；单次评分 / 纠偏 / 经验样本写项目学习层（`experience_cards.jsonl` / `corrections.jsonl`），不把聊天流水塞进交接。步骤见 `40_playbooks/devin-writeback.md`。
- 用户在对话里纠正系统的判断（「不对」「应该是」「你理解错了」等，不需要固定格式）时，当场落台账并一句话确认，不打断对话：
  `python3 -m intelligence.cli record-correction --correction "<纠正后>" --original "<原说法>" [--principle "<可复用原则>"] [--theme <题材>]`
  落点由 `userspace.users_dir()` 解析（`FORESIGHT_USERS_DIR` 优先）；仓内 `intelligence/users/` 是冻结存档，别写死引用。这是 perspective-lab 循环 A 的唯一入口，每日复盘与 foresight 发问会自动回灌；用户沉默 = 认可，不落。
- 可复用的通用件按「设计 / 搭建 / 审计」三件套归位：总纲 `~/harness-reference/KIT.md`，搭建 `BUILD.md`（七个可迁移模式），审计 `TOOLKIT.md`（成本档位 A–H，能用 0 档复现的不上 4 档），方法论 `PLAYBOOK.md`。本仓写出的 SessionStart 事实注入、棘轮式门禁、带条件测试收据等属「搭建」，改动后回写 `KIT.md`，不另建清单。动 `~/harness-reference` 前确认它的树不脏、底不旧（SSOT 是 `gitea/main`）。
- 错误教训沉淀 `.claude/lessons_learned.md`；跨项目失败形状与审查清单在 `~/agent-memory/10_knowledge/`；agent 模式参考 `~/ai-agent-book/`。检索这些知识源用 grep / 精确路径，不臆测内容。

## 低 token 纪律

知识库体量大。了解项目靠索引、脚本 summary、manifest 与精确 `rg`，不通读 `wiki/entities|concepts|sources|raw/` 正文；只有当前写入、校验或定位目标才读正文。知识库大 JSON（`relations/`）走 `query_relations.py`，不 `cat`。发现自己准备批量读正文，停下换索引。

## 知识库回填与 theme-radar 口径

回填脚本与 ingest 类 skill 已迁到知识库仓（`<知识库>/skills/concept-ingest`、`entity-delta-ingest`、`scripts/ingest.py`）。三种目标模式（context_only / entity_apply / review_only）、Raw Full 回填三层闭环、证据分层 L1–L4、baseline 来源真实性与 PDF ingest 路由见 `docs/knowledge-backfill-rules.md`。一句话版：研报提及默认只进图谱与报告上下文（`graph_only` / `exposure_only`），只有公告、订单、中标、量产、带金额或数量口径的公司级事实才进实体正文。

## Skills 目录

<!-- BEGIN GENERATED: skills-table | scripts/build_registry.py backfill-tables | 成员同步自 skills.registry.json；触发词列人工维护，新增行自动预填 -->
| Skill | 触发词 |
|-------|--------|
| market-overview | 复盘、市场总览、今日行情 |
| limit-advance | 晋级、连板晋级、连板、晋级率 |
| top-gainers | 涨幅排行、涨幅前N |
| high-volume-gainers | 放量上涨 |
| advancers-chart | 涨家数走势 |
| up-line | （已被 stock-technicals 取代，2026-09-30 撤出 `.claude/skills/`；飞书退役后跑不通，目录按 #729 保留作口径参考，不要调用） |
| watchlist-ma | （已被 stock-technicals 取代，2026-09-30 撤出 `.claude/skills/`；飞书退役后跑不通，目录按 #729 保留作口径参考，不要调用） |
| ifind | 无触发词：共享工具库，仅供其他 skill 的脚本导入，不可独立调用 |
| hithink-market-query | 同花顺市场查询 |
| report-search | 研报搜索 |
| sector-data | 边际量、板块数据、抓取板块、sector-data（2026-09-11 飞书退役后**只有写飞书那一步失效**，抓取段输入独立于飞书仍可用，#729 保留；看边际量走 market-overview / `fact_sector_daily`） |
| theme-radar | 题材雷达、新词雷达、题材逻辑拆解 |
| theme-fermentation-tracer | 发酵链路、发酵回溯、起涨补涨、双红怎么加强的（消息面×盘面历史回溯，需本地 DuckDB） |
| opinion-cross | 卖方观点提纯、三重共振机会卡片（注：覆盖密度交叉验证在知识库仓 sellside-coverage-cross） |
| serenity-alpha | 个股弹性预期差、补涨排序 |
| disclosure-archive | 补公告、披露归档（抓取侧；apply 侧在知识库仓） |
| duckdb-backfill | 回填 duckdb、补 market_feature_store、增量补数据、fact 覆盖审计、同步 stock_high/sector_stock/limit_heat |
| strategy-evolve | 策略进化、evolve、策略生成迭代、回测记录、前瞻收益验证（suggest 只建议、不自动改 params.json） |
| strategy1-matrix | 策略一生成、生成策略1、策略一矩阵、策略1每日优先个股、strategy1 matrix、更新策略一。用于基于已完成的每日复盘数据、把某个交易日写入 `复盘、matrices、strategy1-priority-stock-matrix.html`、并沉淀 T1、T2、OBS、次日验证、尤其适用于避免长 SQL、长 shell 字符串、手工编辑巨大 HTML 单行导致出错 |
| top-gainers-feishu | （已被 stock-technicals 取代，2026-09-30 撤出 `.claude/skills/`；飞书退役后跑不通，目录按 #729 保留作口径参考，不要调用） |
| foresight-feedback | 记反馈、记一下、我关注、我对这个感兴趣、想深挖、这个不看了、跳过、不感兴趣、打个分、很重要、猜你想问、越用越懂、自动记反馈 |
| task-planner | 批量任务规划、开工前采访、批量回填前先问、开新题材前先问、运行前规划、采访前置、先问后做、task planner、batch plan、回填前先问 |
| checkpoint-recheck-mac-setup | 夜间回检、checkpoint recheck、可证伪点回检、launchd 安装、远程执行、remote-exec、隧道乱码、codepoint 校验、共享大脑、foresight 台账、多机一致、登点闭环 |
| daily-full-review | 全量复盘、今日全量复盘、跑全量复盘、补完复盘、daily full review（有副作用：写库 + 打上游 API。**未软链进 `.claude/skills/`，没有 `/daily-full-review` 斜杠命令**，按 SKILL.md 代跑或先建视图） |
| dispatcher | 路由、哪个 skill、有没有 skill、dispatcher、route（拿不准该用哪个技能、或要 `prime` 检索前缀时） |
| stock-deep-dive | 个股深挖、深挖、深度分析个股、这只股怎么看、复盘先验、行情前瞻、明日研判、次日研判、前瞻研判 |
| researcher-valuation | 拍估值、估值带、贵不贵、隐含预期、值多少钱、估值分位、估值怎么看、合理估值 |
| handoff | handoff、交接、写交接、回写 handoff、收尾交接、交给下一个 agent、另一个 agent 接手。你说"handoff"就执行本流程、不用等会话结束 |
| perspective-distill | 蒸馏视角、视角蒸馏、KOL蒸馏、学这个博主、喂文章、把这篇文章喂给视角、新建视角、perspective distill |
| finance-longtail-baseline | 无触发词：运行时由 `ASK_LONGTAIL_BASELINE` 确定性注入，不可路由 |
| finance-degraded-fallback | 无触发词：运行时由 `ASK_DEGRADED_FALLBACK` 确定性注入，不可路由 |
| code-map | 代码地图、code-map、code-review-graph、deepwiki、造轮子、现有实现 |
| divergence-distill | 蒸馏分叉、对照蒸馏、蒸 Fable、蒸 Knevo、trace diff 沉淀、diff 完沉淀 |
| watchlist-digest | 自选简报、我的自选今天怎么样、按我的自选出简报、开盘简报（按自选）、我的清单今天该看什么、watchlist digest |
| l2-moneyflow | 大单资金流、主买净额、总买净额、涨停股资金流、资金流榜单、量化单、量化买单、大单扫描、moneyflow |
| 公司画像页 | 公司画像PPT |
| 潜意识模式 | 开启潜意识模式、潜意识模式、进入潜意识、退出潜意识、收工、回读对话、巩固记忆、沉淀这轮、记进沉淀、潜意识开关 |
| 行业概览 | 行业概览 |
| stock-technicals | UP线、偏离度、自选股、回踩、均线、MA10、MA20、技术位 |

跨仓引用（规范源在知识库仓，本仓不放正文）：

| Skill | 触发词 |
|-------|--------|
| concept-ingest（已迁至知识库仓） | concept ingest、概念入库、IMA入库、题材DeepDive、ThemeRadar入库、新概念、提取概念 → 读 `<知识库>/skills/concept-ingest/SKILL.md` |
| entity-delta-ingest（已迁至知识库仓） | entity delta、公司边际变化、更新entity、早知道入库 → 读 `<知识库>/skills/entity-delta-ingest/SKILL.md` |
<!-- END GENERATED: skills-table -->
