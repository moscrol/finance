# 8792 交互进化收尾 Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: use subagent-driven-development. 本次用户已经授权补齐 Claude 未收尾部分并部署；仍以实际证据和检查结果决定能否上线。

**Goal:** 让 8792 使用可追溯的代码、数据和知识检索部署，纠正能可靠进入个人记忆，审批能写入持久台账；已知未修的金融质量问题必须有真实复现和处理结果。

**Architecture:** 延续现有 Episode、canonical ledger、daily-full/staging 与受管知识库双索引，不另建入口。代码在独立 worktree；生产数据通过原有唯一写入者恢复。审批候选与已批准学习分开，候选不得自动当作用户认可。Claude 正在修改的 Knevo 长答案/审稿时间窗由其继续，最终纳入部署前复核。

**Tech Stack:** Python/FastAPI/pytest、DuckDB、现有知识库 RAG CLI、React/TypeScript、launchd、Gitea。

## 已核事实与选择

- 代码基线 `a892375881211c75598c4d1a2a9a7860448beb4f`；生产 8792 为 `4f334a6da0afb9ad19b7b56981b839cbed0da80d`。主工作树存在其他 agent 的改动，本计划只在 `codex/8792-interactive-readiness-0927` 实施。
- 8792 市场/板块/个股到 09-24，L2/研究队列到 09-18，卖方观点到 07-05。先确认来源与日期含义再恢复，不用当下值冒充历史值。
- 知识库主消费树存在未解决冲突，生产检索缺五项过滤/回执协议；使用独立快照与受管 generation，不在脏树拉取或重建。
- 学习 API 使用代码根目录，overview 使用 `finance_root`；需要以两个不同根目录的回归测试核实并修复。93 条旧候选为 `pending_llm`，不是已批准规则。
- 方案比较：单改 UI 不能修持久性；把全部旧候选直接批准会污染学习；本次选择修真实边界并用隔离用户演练，候选保留人工判断。

## Task 1: 个人记忆的确定性边界

Files: `intelligence/services/workbench_correction_ingest.py`, `corrections.py`（必要时）, `memory_prefetch.py`, `episode_tools.py`, `episode_semantic_verifier.py`；对应 `intelligence/tests/test_workbench_correction_ingest.py`, `test_memory_opening_prefetch.py`, `test_episode_semantic_verifier.py`。

- [x] 先加失败测试：普通「应该是… / 应为… / 不是 A 是 B」行情意见没有针对上一答的指向时，不自动存为纠偏；保留明确否定、明确指向上一答和可对照原句的替换。
- [x] 在同一路径下并发提交同一纠偏，只写一次；去重检查与写入必须在同一跨进程临界区，失败仍不阻断回答。
- [x] 对召回的个人记忆设置明确字符预算；开场预取与显式 memory_lookup 使用同一投影，哈希一致，截断/省略可见，原台账不改。历史截止日期过滤掉部分无日期记录时也披露缺口。
- [x] 用户记忆的文字与 observations 不能给外部市场事实提供数字背书；真实市场结构化证据继续通过。用数字越权的红/绿对照验证，不能仅测试内部 helper。
- [x] 使用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q <上述相关测试>` 与限定路径 ruff；审查后只提交本任务路径。
- [x] 真实跨会话演练发现：个人纠偏召回成功，但纯回顾被分到个股研究合同，造成 `user_premise` 与金融必需证据槽冲突。已沿既有历史引用候选与 Controller 语义分类修正合同；固定 `326aa553c` 最终规格 701P、质量 579P，真实带主题/不带主题回顾、连续 3 日条件和撤回退出均通过；金融证据地板保留。

## Task 2: 学习台账在部署切换后持久可用

Files: `intelligence/api/app.py`, `intelligence/tests/test_workbench_api.py`, `docs/learning/ledger-map.md`（如需澄清运行根）。

- [x] 两个临时根复现：`repo_root` 放旧候选，`FINANCE_WS` 放新候选。读取、批准/拒绝 reflection、rule status 必须读写同一 canonical 数据根；代码快照不得变化。
- [x] 仅将学习根解析改为已存在的 `runtime_paths.finance_root`；同步评估 bootstrap 的 data/artifact 根，不顺手扩大修改。
- [x] 用临时台账完成候选→批准→下次 prompt 消费、拒绝→不消费、切代码根后仍可见；真实用户旧候选不自动审批。
- [x] 核查 `scripts/forecast_learning_loop.py sync-reflections` 的原有恢复能力；93 项属于已退役双盲夜跑的历史队列，不重启该链或自动生成/批准旧规则。当前交互进化验收使用个人纠偏与撤销链。

## Task 3: 数据与知识库恢复

实施补充：L2 修改 `process_l2_archive.py`、`write_to_duckdb.py`，独立 `l2_recovery.py` 校验仅本轮的官方停牌输入，消费层 `market_moneyflow.py` 披露 NULL 得分与净额排序。用真实 CSV→临时 DuckDB→质量门回归，覆盖历史禁即时市值、同日保留、停牌精确日期/原件哈希/名单冲突拒收。09-22 星帅尔停牌公告与 09-25 休市公告证据在树外 data-audit，恢复输入不成为第二份事实台账。

知识库部署需显式 `WORKBENCH_KNOWLEDGE_WIKI` 保留完整图谱/台账/脚本根；仅 RAG 边界把该默认根映射到 manifest 的 `KB_VAULT`，沿用严格身份验证。独立指定其它 wiki、旧未受管部署的语义保持，联合验证 relations 与受管普通/全文检索；不往封存代里临时添加软链。

- [x] 把只读审计落在 `~/.finance-runtime/reviews/8792-readiness-20260927/`，确认交易日历与最新可得交易日。
- [x] 恢复已下载 L2 历史原包时，先解决当日流通市值语义；通过原有 writer/staging 发布，校验非空值、日期和覆盖率。
- [x] 核清研究队列、知识晨汇、卖方观点的唯一写入者和已存在在途提交；采用可追溯输入推进日期，缺失原料如实展示。
- [x] 知识库选择已检验的维护链与独立代码/内容快照，准备和校验普通/全文 v4 双索引；激活前验证五项过滤及回执，记录回滚 generation。

## Task 4: 已登记金融质量尾项

2026-09-27 用户追加约束：个例回归用于揭示根因，不得扩张为易误伤全局能力的文字规则。初版新增的自由文本检出器已撤出候选；改为补齐证据输入的真实语义与正常路径回归。

Specs: `2026-09-22-live-pullback-claim-vs-history-data-workorder.md` (#78), `2026-09-22-selection-criteria-disclosure-workorder.md` (#79), `2026-09-22-fabricated-entity-code-workorder.md` (#80)。

- [x] 对照冻结现场夹具逐项复现，先检查最新 main/其他在途 owner 是否已修，避免重复。
- [x] 确认「回调」与终点收益的不同含义，以证据生产者的窗口、指标与累计语义约束写手；不从自由文本关键词直接推断矛盾或阻断。`be5744e7c` 独立规格/质量通过，D10 冻结数值及算术未改变。
- [x] 候选筛选的实际过滤、排序、行数上限从执行后的查询合同投递给写手；不创建关键词式正文语义判断器。独立五类 SQL/返回差分不变，空窗与补查、预算/去重/lean 仍保留合同；定向 468P/8S，外置边界 10P。
- [x] #80：history 的 entity_codes 与 finance 的精确代码 filters 共用只读检查；未知码与目录不可验证分开。真实 published 按日全集 42 日/16,926 日期×代码零误拦，历史码/legacy/candidate/股票非闭集有隔离回归；正常、恢复、修复终局保留身份诊断 gap。验收原件见 #80 工单，整仓门禁另属 Task 5。
- [x] 最新交易日措辞以日历与数据库日期共同约束；有证据才能声称最近收盘，无证据则披露库内日期。本次休市日历、真实库最新 09-24 与隔离 Episode 查询读数一致；不将单次回答推广成所有问句保证。

## Task 5: 固定版本验收与部署

- [x] 汇总 Claude #877、#945、#946 与本次收尾，完成独立规格和质量复审；文件锁越过截止/取消、混合记忆引言词表误删两个 P2 均修复，旧红例原样转绿。
- [x] 固定干净 `326aa553c571eeeb5342f091a9672a9a9993ac3c` 四叶通过：Python 18,362P/0F/72S/2xf（18,436 项未收窄）、前端 125P、E2E 34P/2S、Ruff/注册表全绿；全 SHA、解释器、依赖和基座漂移 0 校验通过。
- [x] PR #948 快进合入，受测 SHA 不变；新快照经 launchd 实际切换 8792，登记 canonical deploy ledger，保留旧快照与 launcher。首次 bootstrap exit 5 自动回退已验证；按既有运维规程短暂等待后重切成功，旧失败不改签。
- [x] health 三读匹配，readiness 全绿；固定 KB 代四类过滤与回执实测，隔离六轮通过；生产 Episode `run_20260928_011332_274037` 正确查出 09-24 行情，事实表/列名/日期与 canonical 库相符，degrade/secret/public scan 均 0。测试纠偏只进入隔离用户；实际用户旧候选未审批。
- [x] 交接、能力图谱和三项工单已回写，部署与回滚证据见 [09-28 收尾快照](../../handoffs/2026-09-28-8792-interactive-readiness-closeout.md)。收尾文档提交的最终合入、门禁和运行身份由树外 `final-release.json` 与 canonical deploy ledger 记录，不把旧 SHA 收据移签。

2026-09-27 集成进展：Claude `4c111aa1d` 已合入候选 `d68913b27`。L2四日经staging发布并独立核值，日报/研究队列按9/20知识快照恢复，历史预测/个人学习未写；保留晨汇/研报缺档。新增消费复核修复历史资金流截止、NULL得分、去重覆盖与可变来源阈值。夜跑读取快照与待办写回目的地显式分开。四叶与真实隔离交互验证仍由Task5判定。

22:50 复核：L2 消费层与夜跑读写根独立规格/质量均通过；正式资金流 HTML 已更新到 09-24 并查看实际页面。四天历史补建的市场复盘输入齐全，晨汇/个股深读缺档保留 WARN。`d68913b27` 前端与 E2E 通过，Python 全仓仍运行；registry 两个过期摘要已由生成器更新。新到主干 `85bcee6dc` 的记忆缺口修复待整合，纯回顾合同仍待修，故尚不发布。

09-28 收口：以上进展段保留为当时记录，最新实际代码部署为 #948 / `326aa553c`。18:30 sync、20:40 finalize 两任务已安装、哈希与仓内源一致，安装后均 idle，未提前触发生产采集。13 个冲突 KB 页继续隔离，晨汇/IMA/卖方缺档保留。真实单日查数曾额外出现无比较证据的“放量”文字，旧分类 provider 超时也保留；本次不宣称所有金融语义正确、外部输入完整或未来夜跑已通过。
