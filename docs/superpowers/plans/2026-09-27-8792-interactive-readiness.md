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

- [ ] 先加失败测试：普通「应该是… / 应为… / 不是 A 是 B」行情意见没有针对上一答的指向时，不自动存为纠偏；保留明确否定、明确指向上一答和可对照原句的替换。
- [ ] 在同一路径下并发提交同一纠偏，只写一次；去重检查与写入必须在同一跨进程临界区，失败仍不阻断回答。
- [ ] 对召回的个人记忆设置明确字符预算；开场预取与显式 memory_lookup 使用同一投影，哈希一致，截断/省略可见，原台账不改。历史截止日期过滤掉部分无日期记录时也披露缺口。
- [ ] 用户记忆的文字与 observations 不能给外部市场事实提供数字背书；真实市场结构化证据继续通过。用数字越权的红/绿对照验证，不能仅测试内部 helper。
- [ ] 使用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q <上述相关测试>` 与限定路径 ruff；审查后只提交本任务路径。

## Task 2: 学习台账在部署切换后持久可用

Files: `intelligence/api/app.py`, `intelligence/tests/test_workbench_api.py`, `docs/learning/ledger-map.md`（如需澄清运行根）。

- [ ] 两个临时根复现：`repo_root` 放旧候选，`FINANCE_WS` 放新候选。读取、批准/拒绝 reflection、rule status 必须读写同一 canonical 数据根；代码快照不得变化。
- [ ] 仅将学习根解析改为已存在的 `runtime_paths.finance_root`；同步评估 bootstrap 的 data/artifact 根，不顺手扩大修改。
- [ ] 用临时台账完成候选→批准→下次 prompt 消费、拒绝→不消费、切代码根后仍可见；真实用户旧候选不自动审批。
- [ ] 核查 `scripts/forecast_learning_loop.py sync-reflections` 的原有恢复能力；93 项属于已退役双盲夜跑的历史队列，不重启该链或自动生成/批准旧规则。当前交互进化验收使用个人纠偏与撤销链。

## Task 3: 数据与知识库恢复

实施补充：L2 修改 `process_l2_archive.py`、`write_to_duckdb.py`，独立 `l2_recovery.py` 校验仅本轮的官方停牌输入，消费层 `market_moneyflow.py` 披露 NULL 得分与净额排序。用真实 CSV→临时 DuckDB→质量门回归，覆盖历史禁即时市值、同日保留、停牌精确日期/原件哈希/名单冲突拒收。09-22 星帅尔停牌公告与 09-25 休市公告证据在树外 data-audit，恢复输入不成为第二份事实台账。

知识库部署需显式 `WORKBENCH_KNOWLEDGE_WIKI` 保留完整图谱/台账/脚本根；仅 RAG 边界把该默认根映射到 manifest 的 `KB_VAULT`，沿用严格身份验证。独立指定其它 wiki、旧未受管部署的语义保持，联合验证 relations 与受管普通/全文检索；不往封存代里临时添加软链。

- [ ] 把只读审计落在 `~/.finance-runtime/reviews/8792-readiness-20260927/`，确认交易日历与最新可得交易日。
- [ ] 恢复已下载 L2 历史原包时，先解决当日流通市值语义；通过原有 writer/staging 发布，校验非空值、日期和覆盖率。
- [ ] 核清研究队列、知识晨汇、卖方观点的唯一写入者和已存在在途提交；采用可追溯输入推进日期，缺失原料如实展示。
- [ ] 知识库选择已检验的维护链与独立代码/内容快照，准备和校验普通/全文 v4 双索引；激活前验证五项过滤及回执，记录回滚 generation。

## Task 4: 已登记金融质量尾项

Specs: `2026-09-22-live-pullback-claim-vs-history-data-workorder.md` (#78), `2026-09-22-selection-criteria-disclosure-workorder.md` (#79), `2026-09-22-fabricated-entity-code-workorder.md` (#80)。

- [ ] 对照冻结现场夹具逐项复现，先检查最新 main/其他在途 owner 是否已修，避免重复。
- [ ] 确认「回调」与终点收益的不同含义，只有证据能确定的方向矛盾才阻断；缺路径证据要说明范围。
- [ ] 候选筛选依据缺失先走现有 advisory 通道，不凭关键词创建容易误杀的硬门。
- [ ] 工具入口校验 entity_codes 的存在性，对真实 published 集合做零误报对照；未知代码回结构化错误，不改后缀猜测。
- [ ] 最新交易日措辞以日历与数据库日期共同约束；有证据才能声称最近收盘，无证据则披露库内日期。

## Task 5: 固定版本验收与部署

- [ ] 汇总 Claude 的最终提交与本次收尾状态，独立 spec review 和 code-quality review，修完重要发现。
- [ ] 按 `docs/workflows/acceptance-workflow.md` 执行四叶检查：Python、前端、E2E、registry；收据绑定最终干净代码 revision，不能沿用旧版本绿灯。
- [ ] 通过后合入 Gitea main，建立新只读 runtime snapshot；用现有 launchd 切换 8792 并登记 deploy ledger，不覆盖旧快照。
- [ ] 验收 health/readiness、数据新鲜度、严格知识筛选、真实 Episode 一轮问答和隔离用户纠偏→下一轮召回→撤销退出。实际用户学习库不得写入测试偏好。
- [ ] 使用 handoff skill 写最终交接、更新能力图谱与工单状态，附部署/验证/回滚路径。必须区分已完成、可使用但证据不足、外部输入仍缺三种状态。
