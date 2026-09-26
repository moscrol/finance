# #791 已有实现需求核查（只读）

固定候选 `/Users/a77/fwp-wt-history-market-anatomy@c9bd82ff2e25fe2727347329706f7aeb98444ee8`；比较基线 `4ace5ec2e9b7735d90eb15bc2351fa193c1120b8`。开工与收尾工作树 clean。未实现、推送、合并、读生产库或调用模型。code-map 返回 stale/vault unavailable，未据此作能力缺失结论；以下均以固定源码和原件为准。

结论：#791 值得推进，但应补集合语义和“原件→公开结论”的忠实消费，**无需再造相似度算法、并集库或自由文本 judge**。`rank_history` 是事后收益排名，明确不属于这里的相似排序缺口。WindowSelection.reserve 也不在本报告范围。

## 已具备，保留为正常对照

1. **原题的相似度来自 D10**：`market_regime_analogs.py:260` 的 `find_regime_analogs` 先按 `(distance,start_index)` 排候选、去重叠，再装入 `forwards`；`:426` 按 artifact 原序渲染。底层 `market_regime_vectors.py:95` 按日期升序取向量。不能将其文档要求的升序输入故意乱序后当成线上缺陷。
2. **新 history_query 已排序**：`historical_research/query.py:1181` 按 `(distance,entity_code,start)`；`:294` 去重请求 entity_codes，`:1191` 声明重叠样本非独立证据，`:1196` 保存距离定义、不使用后续收益。现有测试 `test_trigger_only_analogue_ranking_ignores_future_values_and_full_path_is_labelled` 已覆盖范围外未来值变化不改结果。
3. **原件与投影部分已贯通**：`historical_research/episode.py::_model_projection/_result` 保留原件引用、总匹配数/返回数/截断、研究用途、每样本 distance/窗口/feature_cutoff/overlap_cluster。复放 09-18 的 PCB 原件：9 个可比、投影 5 个，5 个距离及顺序逐项一致。
4. D10 自带“小样本历史事实，非概率预测”文字；新投影自带 research_only/decision_eligible=false 与独立性限制。已有约束不能写成“系统没有”。

## 可行动缺口

**F1｜集合总量缺少可执行语义（#791 的主要施工点）。** `finance_query.py:1033` 注册热度表，`limit_up_count` 的分组函数是 SUM；`:1063` 已有成员明细表，说明文字要求 stock_code 去重，但公共语义查询合同只有 metrics/dimensions/group_by，未暴露 distinct-key 或 selected-set 的总占比结果。现有 SUM 对单题材时间累计/已知互斥分组可以合法，不能全面禁用。

最小反例使用三份已校验 SHA-256 的 09-15 原始成员材料：储能 9、锂电 10、固态 7，股票代码并集 15；15/32=46.875%。调用候选真正的 `FinanceQuery.run`，仅在内存放三行热度、故意没有成员表，`group_by=[trade_date]` 仍返回 `limit_up_count=26, market_limit_up_count=32`，并产出“涨停家数=26”的证据卡。**这是合法算术加总被当成集合总量的风险，不是程序算错 9+10+7，也不证明候选末端 judge 已接受 81.25%。**

最小接口补口应复用 `FinanceQuery`/已有成员表，明确“统计对象=所选题材成员的股票代码并集”。返回同日的选择题材全集、distinct key、成员可用/完整状态、原始记录数、并集家数、分母来源/口径、比例或明确缺口。先知道日期、题材选择全集、来源版本、市场分母，才能承诺总占比；缺成员不能用题材计数补猜。现有热度表 PK 含 dimension/scope，成员表 PK 是 date/sector/stock 且没有 snapshot_id；不得凭空称两表共享 published sector snapshot，需用真实来源元数据/冻结原件指纹声明已知版本与未知边界。

**F2｜新相似原件的定义在投影处部分丢失。** 09-18 原件有 `distance_definition` 及 36 个 `excluded_candidates`；通过 c9 的 `_result → FinanceResearchHarness.project_tool_result` 后，distance_definition 不在模型证据卡、也不在 telemetry。距离值和顺序本身正确，不能用“后台再排一次”修复。最小补口是在现有投影卡里携带排序方向/规则与固定样本身份，让结果表及公开引用消费同一个已冻结的顺序；没有必要强行把所有 excluded 明细塞进上下文，完整分母与排除原因统计足够，细项仍读原件。

## 字段所有权与末端边界

| 生产者 | 现有字段/内容 | 消费者与边界 |
|---|---|---|
| canonical `fact_theme_limit_heat_daily` / `fact_theme_limit_stock_daily` | per-theme counts / `(date,sector,stock)` membership；source、updated_at | FinanceQuery 编译器→`_rows_to_evidence`；当前跨题材 SUM 没有 union completeness 身份 |
| `find_regime_analogs` | ordered `analogs[].distance/start_date/end_date/forwards` | `regime_block_for_llm`→`asof_prefetch.py:512` 的 PrefetchItem→market_data 证据；保留表格次序，但不是公开稿排序断言 |
| `HistoryQuery._windows` | ordered rows、sample_id、distance_definition、excluded_candidates、universe | 保存原件→`episode._result/_model_projection`→真实 Harness 投影；样本值/顺序通过，定义丢失 |
| 既有写手与 semantic verifier | 引用证据与自然语言公开稿 | 本轮没有调用模型或末端 judge；不得把投影通过写成“常见/胜率禁用、公开稿一致性已验收” |

`finance_query.py:2612` 的 StructuredObservation 目前仅对 sector_daily/sector_stock_daily 的指定指标产生结构化观察；本例题材聚合卡没有该观察，D10 原 E1 也为 observations=[]。这支持在既有证据/公开结果合同中补结构化身份，而非另起自由文本判官。

## 后续最低验收边界（不是实施计划）

- 集合：原 32 股材料 15/32；乱序成员和重复题材/重复股票仍是15；任一被选题材成员不可得/不完整时不给总占比；日期/来源口径/分母冲突不隐式拼接；单题材合法 SUM 正常对照保留。
- 相似：保留原 E1 的 0.313→0.370→0.395；相同距离按既有确定次键，重复 sample 不新增独立分母；改变展示的后续收益不能改变冻结相似顺序；乱序展示输入须按明确“已冻结顺序”合同处理，不能拿 rank_history 的收益排名替代。
- 公开投影：表和公开稿引用同一样本身份/排序/集合基数；小样本不得变成“常见/胜率”。本轮没有宣称自由文本的这些边界已通过；需将结构化公开片段与原件对账，然后做隔离真实入口验收。

证据：`probe_existing.py` 可复跑；`probe-results.json` 含 SHA、原件哈希、实际 SQL、实际证据卡和投影结果；`d10-correct-original.json` 保留正常原 E1；`public-answer-original.md` 保留原错误公开稿。定向既有测试 **26 passed in 1.89s**，见 `targeted-tests.txt`；不代表全仓/前端/末端模型验证。
