<!-- 由 scripts/gen_runtime_catalog.py 从源码生成，不要手改。
     再生成：python3 scripts/gen_runtime_catalog.py ；校验：--check（pytest test_runtime_catalog 也会比对）。 -->

# 研究工具目录

来源：`research_tool_registry.default_registry`（用哑 runner 装配）+ `_TOOL_CONTRACTS`。`query_scope=episode` 的工具参数表为空，截止日在 context 上而不在参数里。说明书只写实测过的失败模式，空即合法。

14 个工具

| 工具 | 能力 | 成本 | 新鲜度 | 查询范围 | 最小窗(s) | 参数键 | produces | 描述 |
|---|---|---|---|---|---|---|---|---|
| `evidence_lookup` | evidence_lookup | local | stable | query | — | `query` | supporting_evidence | 本地证据索引 |
| `evidence_search` | evidence_search | external | current | query | 30.0 | `query` | counterpoint, supporting_evidence | 对本地知识证据执行窄口径、宽口径和反方闭环检索 |
| `finance_query` | finance_query | external | current | query | — | `query` | data_date, market_change, risk_signals, supporting_evidence | 按语义数据集、指标、维度、筛选和时间范围查询本地结构化金融数据 |
| `financial_data` | financial_data | external | current | episode | — | `report_period` | financial_assessment, metric_evidence, supporting_evidence | 结构化逐季财务指标 |
| `graph_lookup` | graph_lookup | local | stable | query | — | `query` | chain_mapping, company_mapping, relation_map | 知识图谱实体与关系 |
| `kb_search` | kb_search | local | stable | query | 20.0 | `query` | direct_answer, direct_definition, direct_explanation, supporting_evidence | 本地知识库检索 |
| `l3_lookup` | l3_lookup | external | current | query | — | `query` | fact_value, supporting_evidence | 官方公告与互动证据 |
| `mainline_context` | mainline_context | external | current | episode | — | — | mainline_structure, supporting_evidence | 同日主线与板块结构 |
| `market_data` | market_data | external | current | episode | — | — | current_baseline, data_date, market_summary, prime_quote, supporting_evidence | 结构化行情与市场时序 |
| `memory_lookup` | memory_lookup | local | stable | query | — | `query` | prime_memory | 用户自己过去的判断与纠偏原则（历史先验，不是市场事实） |
| `news_search` | news_search | external | current | query | — | `query` | event_facts, impact_transmission, prime_news, supporting_evidence | 财经新闻检索 |
| `sub_research` | sub_research | external | current | query | 60.0 | `goals` | supporting_evidence | 把 1–3 个可独立取证的子问题并行交给子研究分支，各支带自己的工具预算跑到终态后一次返回证据 |
| `web_fetch` | web_fetch | external | current | query | — | `url` | event_facts, supporting_evidence | 按 URL 取网页正文全文（取页，不是检索；URL 先由 web_search / news_search 给出） |
| `web_search` | web_search | external | current | query | — | `query` | event_facts, impact_transmission, supporting_evidence | 全网网页检索 |

## 说明书（`ToolSpec.contract`）

### `evidence_lookup`

查的是已回填的本地证据索引，每条自带来源、日期与质量标记，引用时要把这三项一起带出：券商研报来源的条目属二手材料，不能直接升级成公司级硬事实；标着「无日期」的条目不能用来支撑时效性结论。索引是回填产物、覆盖并不均匀，无命中只说明没有登记过相关证据，应写成证据缺口，不是否定结论。

### `evidence_search`

这是一次调用内跑 narrow→broad→counter 三轮的闭环检索，返回的证据列表**同时包含支持与反方两类**，立场只标在观察文本的[支持] / [反方] 前缀上，证据条目本身不带立场字段：引用前必须回观察文本核对该条属于哪一方，不要把反证当成支持性证据。它也是最慢的工具（实测冷调用可达 28 秒），只在确实需要反证或替代解释时用；单纯找资料用 kb_search。

### `finance_query`

结果会按 Agent 上下文预算截断（当前上限 25 行），返回的是满足条件的前若干行而不一定是全集：不要据此写「全市场最高」「只有这些」这类全称断言，需要更完整的切片就加筛选、分组或排序后再查一次。日期要放进 time_range，不要写成 filters 条件。当前任务未授权历史窗口时，旧日期的查询不会被执行而是直接退回，此时按提示把时间窗调回截止日附近，不要反复重试同一个窗口。返回为空只说明该 dataset 在这组条件与时点下没有结构化结果，应写成证据缺口，不得据此推断事实不存在。新高家数/新高结构类问题用 stock_high_daily（表内只含当日创新高的个股，按 high_period/sw_l1 分组计数即新高结构）；sector_stock_daily.high_status 显示「非新高」是事实标注，不是数据缺失。下周/周末大事、事件日历用 event_daily（复盘会编辑催化，不是官方日程全集；event_date 可以晚于信息截止日）。

### `financial_data`

返回的是已披露报告期的季报数据，不是当前状态：引用时必须带报告期，不要把「三季报净利」说成「当前净利」。数值为累计口径（中报=上半年累计、三季报=前三季累计），本工具不做单季还原；要单季必须显式声明是自己推算的。返回为空只说明这两个源没取到，应写成证据缺口，不得据此推断公司没有该项财务表现。默认只取最近 6 期；问的是更早的某一期（如两年前的年报），要在 report_period 里写明该期，否则那一行不在返回里，不等于没有该期数据。每行的日期是该期披露日（缺披露日时为报告期截止日），引用时按此写 as-of，不要用取数日。

### `graph_lookup`

返回的是图谱里已登记的映射关系，不是经过确认的公司级事实。概念项的「匹配分」只是文本匹配强度，不代表业务关联强度，不要当作重要性排序。公司项后面的 strength/evidence_layer 是这条映射的可信度分级：peripheral 或研报推断来源的产业链归类只能作为线索，要断言某公司确有该业务，需要 l3_lookup 的公告或 kb_search 的一手事实确认。图谱无命中说明尚未登记该映射，不等于不存在关联。

### `kb_search`

命中的是本地知识库页面正文，而这些页面按来源分层：「边际变化」是公告/订单/中标这类一手公司事实，「高信度研究线索」是券商研报的待复核判断，「观察列表」更弱。检索结果不带这层标记，引用前先看命中片段落在哪一节：券商来源的结论只能作为待验证线索，需要 l3_lookup 的公告确认后才能当硬事实。返回文本明确说「检索未能执行完成」时那是工具故障，不是知识库为空，此时既不能写成证据缺口也不能下否定结论，应改写检索词重试或换工具；只有在确实「无命中」时，才说明知识库没有回填过，且仍不等于该事实不存在。

### `l3_lookup`

查询成功不等于查到了证据：实测存在「company 查询成功但没有解析到可用证据」的情况。返回为空时只能说明本次没检索到，不能据此断言该公司没有相关公告，应写成明确的证据缺口而不是否定结论。

### `mainline_context`

同日主线结构来自本地库的主线表，而这几张表的覆盖并不是每个交易日都齐全，题材与个股两张的起始日明显晚于板块表，较早的日期查不到。返回为空或提示「题材级主线未知」，说明该交易日没有回填主线数据，不能据此说当天没有主线；数据比行情快照旧时会退回并说明，此时应写出数据截至日期，不要当作提问当天的主线。

### `market_data`

返回的是最近一个已收盘交易日的快照，不是实时也不一定是今天：当日盘中或次日开盘前查询会回退到上一交易日，此时应明写数据截至日期，不要把它当作提问当天的行情。美股按北京时间 21:30→次日 04:00 跨日，北京时间凌晨查到的「前一天」通常是正在进行的那一场，不是数据过期。隔夜或外盘混合预测会附带美股指数与龙头的结构化报价（费半/英伟达/美光/海力士/闪迪）；引用涨跌幅以该块为准，新闻标题里的数字不作为精确行情。

### `memory_lookup`

返回的是这位用户自己的历史判断与纠偏原则，属于先验而非市场事实，不能当作证据支撑当前世界的结论；绑定时用 user_premise。空命中只说明该主体此前没有留下记录，不等于用户没有看法，更不能反推市场事实——如实写「用户记忆无相关命中」即可。

### `news_search`

新闻是二手材料，同一条消息被多家转载不构成交叉验证。涉及公司经营事实时需要 l3_lookup 的公告确认；只有新闻来源时写成「待验证线索」，不要升级为既定事实。

### `sub_research`

返回的是各分支查到的证据条目本身（每条带来源、日期、档次），不是分支写的总结：结论要绑到这些证据上，分支的状态说明不能当依据引用。证据的档次与日期继承自分支里实际调用的工具（公告仍是一手、网页仍是二手），不因为经过子研究而升档。某支 completed 但零证据，只说明该方向本轮没找到可绑定的证据，是缺口不是否定结论；某支 failed 会带失败原因，表示该子问题没有被研究过，不是没有答案。参数只有 goals：1–3 个彼此独立、能直接取证的子问题；空、重复或超过 3 个会被拒绝而不是截断。每支分支有自己的调用与时间预算（≤ 60 秒），适合并行拆几个互不依赖的取证方向，不适合把一个需要先后依赖的推理链拆开。

### `web_fetch`

取回的是网页正文原文，属二手公开材料（与 web_search 同档）：数字可以读、可以引，但公司级硬事实仍以 l3_lookup 公告或 financial_data 一手数据为准，只有网页来源时写成「待验证线索」并点明缺的一手材料。证据日期取页面自述的发布/更新日；页面没有日期时记为抓取日并在观察值里标明，引用时不要把抓取日说成数据日期。「取页失败」（HTTP 错误 / 超时 / 无法解析）是工具故障，不是页面没有该信息，可换 URL 或改用 web_search；「取页成功但无正文」同样不能当否定证据。参数只有一个 url，必须是 web_search / news_search 给出的完整 http(s) 地址，不接受站点名或检索词。

### `web_search`

网页与研报是二手材料，默认只能作为线索和上下文，不能直接当作公司级硬事实。订单/中标/产能/量产这类结论需要 l3_lookup 的公告或互动证据确认；只有网页来源时，写成「待验证线索」并点明缺的是哪一份一手材料。

