# 市场上下文的覆盖、证据角色与时间合同设计

本稿记录已选方案，供下一位实现者独立执行。基线为 `82de3fb730a4175170b4e6ba472e130e5ef87ab7`，分支 `codex/market-context-contract-1008`。本轮只写设计与计划，不实施源码、不调用模型/API/网络、不读写生产数据。用户已连续授权优化、上线再验；此稿不再增加一次“是否继续”的人工关口。实现须分为 A、B 两个独立任务，A 先落地并验收工程合同，再做 B。

目标是给模型足够且如实的研究输入，让它自主比较与判断。这里修取证 Interface（调用方必须知道的类型、约束、错误及范围），不替模型预写市场观点，不要求固定章节，不增加判官、工具、注册表、台账、开关或根预算。`ASK_SEMANTIC_JUDGE` 保持用户已选的 off；`ASK_EVIDENCE_JUDGE` 的既有配置与预算不在本轮变更。本题 evidence_search 调用 0 不证明后者现役关闭。原回合预算 900 秒 / 120 步不变。

## 1. 实证与结论边界

原件只读保留在运行目录：

- `~/.finance-runtime/answer-evidence-quality-1007/next-diagnosis/report.md`、`machine.json`、`repro_coverage_temporal.py`：确定性离线复现约 0.26 秒，exit 1。
- 同根 `current-answer-review/report.md` / `machine.json`：唯一新首发答卷有部分实质改进，全文仍 `NOT_PASSED`；生产发布成功与确定性验证通过不能代替内容批准。
- 同根 `prod-current-input-01/first-public-answer.md`：run `run_20261007_235624_365041`、message `msg_dcc04abfd9284bb890328b5313dab3ad` 的首次公稿。源作者检出固定为 `~/.finance-runtime/finance-workspace-82de3fb730a4`。

已复现：

| 问题 | 真实路径与独立控制 | 本设计处理 |
| --- | --- | --- |
| 主题遗漏 | `ask_blocks._mainline_context_block_for_llm` 全局 `LIMIT 30`，之后每组 `[:8]`；31 个 AAA 板块 + 1 个 ZZZ 板块，ZZZ 在文本、卡、模型三层全丢 | 全组摘要与 SQL 每组有界预览 |
| 第二层遗漏 | 6 个主题各 1 行，没有触发 SQL 30 行上限；`block_lines_to_evidence(limit=12)` 被 5 条规则及日期/历史元数据占位，仍丢最后主题 | 从事实对象建短卡；范围不占事实卡名额 |
| 方法伪装事实 | D4 五条 FY/SPT `ReadingRule` 盖成本地 DuckDB、9/30、`L4_structured`，被三个输出槽引用 | 方法保原来源，进入指导通道，不能进入事实账本 |
| 指标升级 | `diff_ratio` 是今昨成交额环比；旧分类把 amount=NULL 也叫“真正双红/增量启动” | 复用 canonical 双红资格，只输出价量意义 |
| 日期权限错配 | 原题目标 9/30，`requested_information_cutoff` 未绑定“截至当日”，factory 用 10/7/runtime_default；另一目标日和区间末日同红 | 可信输入先冻结双角色时间合同 |
| 未来内容仍可交付 | 真实 registry 的 10/1 夹具在错误 context 下普通 success；显式 9/30 标 future，但非 history-intent 全未来分支仍标注后交付正文 | 消费者真正扣除越界事实与原观察正文 |

不扩大上述结论：原答卷全部卡日期不晚于 9/30，未见真实未来行情消费；本题三个输出槽的 `evidence_type_floor` 为空，五条方法卡被使用不等于它们导致本题下限放行；当日 68 行关联成交额非空，NULL 金额是同源潜在缺陷。冻结本表的四个主题不是市场主线全集。不能把去重诊断中的新能源/医药组合、集中度或“主线”结论硬编码为事实。

## 2. 领域口径与现有位置

先遵循 `UBIQUITOUS_LANGUAGE.md`：供应商主线 `mainline_vendor`、成交占比前三 `mainline_volume_top3` 与细分题材双红是不同口径；双红不参与“主流板块”定义。`docs/agent-product-door.md` 是入口与两引擎的现状正门，Episode 的 `mainline_context` 是内部积木。`docs/adr/0002-knevo-catchup-s10-decisions.md` 的“不另建平行台账”继续成立。地图当前 empty，只能引用实查路径，不宣称已完成全架构覆盖。

本设计新增四个精确术语，代码类型及 docstring 为合同 SSOT（唯一规范源），此稿为设计说明：

| 术语 | 含义 | 不能替代 |
| --- | --- | --- |
| 本表主题覆盖 | 指定日期、指定查询过滤下 `fact_mainline_sector_daily` 的全部主题及行统计 | 全市场主题齐全、没有其他主线 |
| 板块事实预览 | 按既有排序选择的每主题最多 8 个实际板块行，保值与来源 | 全部板块排名、唯一强势板块 |
| 派生量价信号 | 由同一行价量输入及 canonical 阈值得出的描述与资格 | 净资金流、指数贡献、长期趋势 |
| 双角色时间合同 | 原用户指定的市场目标日/窗口与资料授权上界分别保存，附原消息身份及相对绑定锚 | `timeframe` 字符串、库最新日、模型生成日期 |

## 3. A：D4 结构快照，完整覆盖与角色分离

### 3.1 选择与接缝

比较过三案：只删 `LIMIT 30` / 增大 token 限额不能修卡层遗漏、方法身份与量价语义；取全当日明细再 Python 分组能修首层，但传输与内存随总明细增长；选全组聚合 + `row_number() over(partition by theme_name)` 每组预览，传输规模是主题数与 `8 × 主题数`，保全范围且明细有界。SQL（结构化查询语言）的窗口函数能对每组独立编号，不让字母排序靠前的主题占满所有名额。

Module 留在 `intelligence/services/ask_blocks.py`，沿用同文件 `D3Structure` 的不可变结构对象模式，避免大拆文件。增加 `mainline_context_snapshot(...)` 与 `market_review_mainline_context_snapshot(...)` 两个现有语义的结构入口；共用一个私有 loader。原 `_mainline_context_block_for_llm` / `_market_review_mainline_context_block_for_llm` 只调用 loader 后渲染旧文本，保留旧入口和同日判断。Episode 的 `episode_tools.mainline_runner` 跨这个 Seam（可以替换行为的位置），直接消费结构对象，返回 `ToolRunResult`。同一文件提供 `mainline_snapshot_tool_result(snapshot)` 供引擎 B 的 `ask._generic_mainline_context` 这个既有适配点复用；B 的双红补充仍按自己的事实生产者处理，不能再把它与 D4 方法文本混起来统一反解析。不重写 B 的编排。不再把混合 Markdown 的每个 bullet 反解析成事实。

### 3.2 数据类型与读取约束

采用 frozen dataclass，字段如下（日期在对象内用 ISO 字符串；数字为真实值或 None）：

- `MainlineSectorFact`：`trade_date, theme_code, theme_name, sector_ts_code, sector_name, sort_no, today_pct, limit_up_count, net_inflow_1d, amount, cycle_status, cycle_level, startup_date_small, high_status_label, near_breakout_label, sector_pct, diff_ratio, sector_amount, sw_l1, pct_source, amount_source`。`amount/net_inflow_1d` 保原表值与原单位，关联 `sector_amount` 为亿元；不擅自给净流入换单位。
- `MainlinePriceVolumeSignal`：`trade_date, theme_code, theme_name, sector_ts_code, state, strict_double_red, inputs_complete, missing_inputs`；以事实三元键 `(trade_date,theme_code,sector_ts_code)` 对应输入，theme_name 只是展示名；`strict_double_red` 的值为 `True / False / None`，None 表示资格输入缺失。
- `MainlineGroupCoverage`：`theme_name, total_rows, non_null_counts, preview_rows, omitted_rows`。`non_null_counts` 覆盖原主线 `today_pct / limit_up_count / net_inflow_1d / cycle_status / cycle_level / amount`，以及关联价量 `sector_pct / diff_ratio / sector_amount / sw_l1`；计数范围是全组，不是前八行。0 个非空表示未知，不造真值零。
- `MainlineHistoryCoverage`：`theme_name, day_count, first_date, last_date, sector_rows, has_snapshot_day`。历史聚合保存窗口内全部主题，不用 `LIMIT 8` 隐掉历史范围；文本可预览但 `query_basis` 保全。
- `MainlineContextSnapshot`：`status, market_date, snapshot_date, requested_as_of, target_theme, total_rows, groups, facts, signals, history_start, history_end, lookback_days, history, guidance, gap_messages`。`status` 为 `available / stale / empty / unavailable`；`guidance` 使用原 `ReadingRule`。缺表/打不开/查询失败返回无事实的 unavailable；无行是 empty，不能称事实不存在；市场复盘明细不同日是 stale，不能复用旧行作当日事实。

`MAINLINE_PREVIEW_ROWS_PER_THEME = 8` 只由 loader 拥有。聚合与预览用相同 `latest <= as_of`、同一主题过滤与同一 joined CTE（公用查询结果），相同连接的只读事务中读取；结束提交只读事务并关闭连接。主线粒度保持 `(trade_date, theme_code, sector_ts_code)`，事实不能只靠 sector_name 识别。分组保持原 `theme_name` 语义，不把行业/题材合并。

保留 `fact_sector_daily` canonical published VIEW，禁止改读 generation 全版本或写库。保留 `coalesce(s.pct_chg,m.today_pct)` 与 `coalesce(s.amount,m.amount/10000.0)`，同时记录具体命中来源，避免两个来源被误认为同一量。排序保留 `theme_name, sort_no NULLS LAST, sector_name`，完全并列时以 `theme_code, sector_ts_code` 作稳定末级排序。历史窗口为 `snapshot_date - lookback_days` 至 `snapshot_date`，含两端，默认回看 20 自然日；不改成交易日或 20 行。

### 3.3 同一份结果，三种角色

事实卡由 `MainlineSectorFact` 一板块一短卡构建，标题含主题与板块，日期用该事实的 `trade_date`，来源标 canonical DuckDB 表，`L4_structured` 仅说明结构行情档次。原主线值与关联值分别展示；缺值写未提供，真实零仍写 0。不要将事实值、分类结论和 ReadingRule 拼成一个“核心板块”长卡。每组 8 行是唯一 D4 预览上限；D4 不再套用通用 bullet 数 12 作为事实范围。

派生信号进 `query_basis.price_volume_signals`，保输入对应键、`diff_ratio=(当日成交额-上一交易日成交额)/上一交易日成交额×100` 的公式、输入资格与 canonical 规则描述。SSOT 是 `market_feature_store.signals.is_double_red` 和 `DOUBLE_RED_DESCRIPTION`；缺少任一输入不具严格双红资格，不能用 `amt is None or amt > 500`。state 只可描述：严格双红量价条件、上涨且成交额环比下降、上涨且成交额环比非负但未满足严格双红、下跌且成交额环比上升、输入不足/待确认。删去源端的“增量启动/存量抱团/真正”资格升级；净流入只能引用非空 `net_inflow_1d` 自身。保阈值严格性：500 不过、501 过；diff_ratio=10 不过，负值不双红。

`ReadingRule` 在 observation 的指导部分保 `id/title/rule/source`。五条 FY/SPT 原规则不删除、不改人格；关闭既有 reading_baseline 开关时仍为空。它们不创建 `AgentEvidence`，没有当日 source_date/本地 DuckDB/L4 标签，不进入 E 编号、引用绑定或 `evidence_type_floor`。派生信号与规则是帮助模型推理的指导，不能充当补足缺失净流入/持续性的数据。

### 3.4 模型可见范围

`ToolRunResult.query_basis` 必须包含 schema 标识 `d4_mainline_snapshot_v1`、`scope=current_table_all_themes` 或 `current_table_single_theme`、`snapshot_date/market_date/requested_as_of`、`target_theme`、`theme_names`、`total_rows`、全组 `groups`、`preview_limit_per_theme/ordering`、历史窗口与完整历史聚合、`metric_semantics`、`price_volume_signals`。它不含 SQL、物理路径、原始私有 trace。`scope` 明说只是本表，不改称全市场主线。

现有 `FinanceResearchHarness.project_tool_result` 已把 `query_basis` 放进审计及共享模型投影；`budget_tool_observation` 只裁 prose。复用这条通路，用真实 registry → shared projection 测试钉住全主题元数据，即使 observation 或某卡 detail 被 4000/800 字符预算裁剪，主题存在、覆盖及省略仍可见。不提高这些上限，不用“没有显示所以不存在/唯一”的推断；统计摘要也不赋予唯一性、资金或长期趋势结论。

## 4. B：在可信输入编译时冻结双角色时间合同

### 4.1 选择与类型

只在 factory 根据 `frame.timeframe` 补相对日期会把模型可变分析字段当权限；只扩 `requested_information_cutoff` 正则又无法保证 continuation、恢复与消费者一致。选在原用户输入先编译 `TemporalContract`，之后 controller/QueryEnvelope/TaskFrame 都投影同一对象。新 focused Module `intelligence/services/temporal_contract.py` 只承载类型、编译与权限选择；日期词法与区间连接规则提炼复用已有函数，不能另造一套九月三十日特例解析器。

类型为：

- `TemporalSource(message_id: str | None, message_sha256: str, excerpt: str)`：当前完整原用户消息或恢复的完整原用户消息；digest 为归一化换行后的全文 SHA256；相对授权另外指向目标 source 的 digest。不使用 assistant、summary、资料引文或模型输出作为权限来源。直接调用理解服务可没有 message_id，但必须保 digest。
- `ResearchDateWindow(start: str, end: str, source: TemporalSource)`：单日 start=end；多日期仅有明确直接相连区间才成为窗口，多锚比较不能偷偷取 max。
- `TemporalContract(market_target: ResearchDateWindow | None, information_cutoff: str | None, cutoff_origin: str, cutoff_source: TemporalSource | None, relative_anchor_sha256: str | None, errors: tuple[str,...])`。origin 闭集 `none / explicit_user / relative_target / runtime_relative / inherited_user / legacy_user`；errors 非空阻止无界研究。runtime 默认尚未指定时保持 `information_cutoff=None, origin=none`，只在 factory 生成有效运行日上界。

`QueryEnvelope`、`TaskFrame`、`TurnIntent`、`ResearchRunContext` 在尾部新增 `temporal_contract: TemporalContract | None = None`。`QueryEnvelope.to_dict / TaskFrame._payload / TurnIntent.to_dict` 对 None 不输出键；旧 frame 的序列化与 hash 字节保持兼容。新合同纳入 frame hash，source 与相对锚参与 hash；公开投影只给日期、来源种类、scope，不公开原消息 id/digest。`from_dict` 校验闭集、合法 ISO、窗口顺序、digest 形状与相对锚；存在但无效的合同拒绝，不能当缺字段回退。持久恢复带新合同时原样核验并传递，不能重新解析为更宽权限。

### 4.2 可信编译、继承与错误

生产入口 `TurnOrchestrator._run_turn_ledgered` 在 `self.turn_controller(...)` 之前，用已加载 `conversation_messages` 中当前 run 的完整 user 消息核对 `query`，冻结 current contract；前轮恢复只读既有有界完整 user 消息窗口。`decide_turn` 直接调用也在 resolver/模型之前做同一编译，支持入口传入已冻结对象。controller 无论默认、注入或 legacy，都必须由入口用原编译对象覆盖时间权限投影；用户目标可以澄清，权限不能从 `decision.timeframe`、`frame.user_goal`、return dates 或材料正文获得。

解析复用 `top_level_message_text` 的保护区/引文/边界不确定规则、`honesty_gates.explicit_information_cutoff_dates` 的否定/日期角色/冲突处理、`market_review_requested_date` 的 ISO/中文/无年份最近不晚于运行日语义，及 `historical_research.intent` 的直接连接/压缩区间规则。需要所有日期候选时从这些现有 parser 提炼共享 primitives，旧 parser 改调共享函数并保原测试，不 import `query_understanding` 回 `task_frame` 造成循环。

先给日期标角色，再绑定相对授权：明确资料截止日期优先；“截至今天”绑定可信运行日，允许与旧市场目标日不同；“截至当日/该日”只能绑定唯一目标日；“截至区间结束日”只能绑定唯一明确目标窗口 end；收盘站立日保既有权限含义。目标日单独出现不自动限制所有资料。当前原用户明确授权可以收紧或放宽前轮许可；工具参数、模型文本、库最新日只能收紧，不能扩权。当前无新资料授权的 continuation 继承前轮用户资料上界；如目标窗口尚未重指定，也继承目标。新研究没有权限指令才使用 runtime default。

多目标且相对指代不唯一、无效日期、多个相冲突截止、保护区边界不确定：errors 明确进入既有 `ambiguities/clarification_question` 与 `project_turn_decision` clarification 车道。可保留已冻结旧上界作审计，但错误未澄清前不检索，不以 `None` 偷回 runtime default。旧持久化没有新字段：在入口用可核的原 user 消息编译 `legacy_user`；若原消息不完整而 continuation 需要继承许可，澄清停止研究，不从旧 assistant/summarized intent 猜授权。直接核心调用的旧 hand-built frame 可由原 `raw_question` 编译 legacy 合同；factory 不从 timeframe/goal 恢复权限。

### 4.3 实际消费者守界

`build_episode_context` 先消费冻结合同。非空 cutoff 形成既有 `InformationCutoff(...,"requested")`；显式 injected `information_cutoff` 与 history strict-window 上界只能进一步 min 收紧；不能覆盖成更晚日期。合同 errors 非空拒绝构建 research context。仅合同 origin=none 且真正未指定，才 `_default_information_cutoff(today=...)`；库最新日仍是 provider freshness，不能当权限。`ContinuousTurnAdapter` 必须把相同合同交给默认和 injected context_factory，并在 context 返回后核对/收紧，避免只写 trace 或字段没人读。

`episode_tools._structured_as_of` 消费 `context.temporal_contract.market_target.end` 与现有 freshness/cutoff 的 min；所以用户复盘 9/30 并允许截至 10/7 资料时，D4 仍查 9/30，资料工具可见到 10/7。`news_search/evidence_search/history` 继续使用 `InformationCutoff` 作最大上界，各动作自身事件窗可进一步收窄；权限上界不会强迫新闻解释窗延长到目标日以后。

`ResearchToolRegistry.execute` 的 future filter 按已有 typed 来源可得时点执行，全部被拒时在所有 research mode 都返回无事实 + “已检索但内容晚于信息截止日，未交付；不是源里没有”诊断，保状态 `future_of_cutoff`、计数、private trace；删掉非 history-intent “标注后交付”分支。混合结果只交合法卡，并由合法卡重建 observation，不能回填原 prose。无 evidence 而 provider `source_trade_date` 明确是晚于截止的资料可见时点，也不得交原正文；未知日期行为保现有 scope 合同，不在此轮宣称严格日内可得性。另核 `episode_tools._overnight_news_evidence` 的同类 fallback，避免它先把未来新闻卡贴标签后绕回消费。发生拒绝时原 `query_basis` 可能携带越界预览，整份停止送入模型；范围/计数通过过滤诊断及 private trace 留证，正常 D4 的完整 metadata 不受影响。消费者测试必须查看最终 shared model_content，不只检查 trace.status。

权限时间与发生时间必须分开。现有 `finance_query` 的 `event_daily` 已有 `allow_future_time_range=True, cutoff_column=updated_at`：`event_date` 是计划发生日，可能晚于 cutoff；该日程只要已在授权截止前取得仍可研究，卡的 `source_date/served_date` 用已知时点。沿用这个 typed 合同及其来源局限（不是严格官方发布时点），不以正文日期、目标日期、事件发生日期做全局删除。最小正控是 8/21 已知的 8/26 日程保留，负控是 8/24 才写入的同窗日程不交付；两者都走真实 finance_query → registry → shared projection。

## 5. 最小验收合同

A 的最小红控制：31 AAA + 1 ZZZ；6 主题各一行；单主题查询与并列排序；amount=NULL、真实 0、500/501、diff=10/-1；方法启用/关闭及来源保留；未来快照、非同日 stale、published/legacy 选择、coalesce 来源、含边界历史窗。完整闭环为真实 DuckDB → snapshot/兼容 renderer → build_episode_registry/execute → FinanceResearchHarness.project_tool_result。预览不足必须由 coverage 如实表达，不能签全市场完整。

B 的最小红控制：原题及另一日期、区间末日；显式 cutoff 早于/晚于目标；公司截至今天；ISO 收盘、无年份日期；引文/否定/多锚/无效/冲突；旧许可无新指令继承、当前明确新许可、模型改日期不扩权、legacy 恢复失败澄清。完整闭环为可信 user input → controller/frame/continuation → ContinuousTurnAdapter/context → 真实 registry + 10/1 未来哨兵 → shared model projection；未来正文和数值不可送达，不能只测 helper 或浅 mock。

实现后的工程绿与内容 QA（独立质量审查）分开。先固定 A、B 提交的离线红绿收据，再 Spec→Standards 两阶段独立复核；按仓库要求跑准确全量 scope 的本机等价 CI 与 GitHub 所需叶子。授权合入/部署之后，在新目录保存一个新首答及完整原始事件，用同一原题、当前合法冻结输入、真实现役模型/部署身份做首次质量审查；不重开旧评测批、不覆写旧答卷、不声称同输入 A/B 或假胜率。评审继续检查范围、量价/资金资格、重叠标签、同命题同时间反证与用户问题覆盖，不通过仍记录不通过。

provider `repair_finalize` 40 秒未闭合 JSON 的 finish 问题属另一条只读 triage，本设计不混入修复预算/流式策略；若另选修复，必须独立任务与独立验收。A/B 工程验收不能顺带签修订流稿成功、全文质量提升或长期泛化。
