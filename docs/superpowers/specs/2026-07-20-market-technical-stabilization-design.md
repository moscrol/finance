# Market Technical Stabilization Design

## 背景与结论

`fix/market-technical-fail-closed@efc2db44` 已经把“科创50支撑位”从通用 RAG 管线切到确定性行情计算，但真实行情质检仍发现三类阻断上线的问题：盘中未完成日 K 被当作正式收盘参与计算；确定性成功被错误记录为 LLM 降级；数据缺口仍进入 Base Finance 五段模板。

本设计保留“确定性头部路由 + 结构化行情成功即停 + fail-closed 出口”的方向，只修正数据时间语义、证券解析、展示契约和可观测性。该子项目完成前不得切换 8792 runtime。

## 目标

1. 技术位只能由已完成交易日数据计算，盘中价格只能作为单独的实时参考。
2. 行情来源、字段和展示用语一致；声称 OHLCV 时必须实际解析成交量。
3. 支持的证券代码和指数别名必须可执行，不能“路由成功但 provider 永远不可用”。
4. 成功答案和证据缺口都使用任务专属展示契约，不进入通用五段模板。
5. 确定性成功、数据缺口、质量失败在 phase、degrade 和 Inspector 中被准确区分。

## 非目标

- 不把技术分析扩展为交易建议或收益承诺。
- 不在本批增加 RSI、MACD 等更多指标；先保证支撑/压力、均线、低点和失效条件的正确性。
- 不以网页搜索替代结构化行情，也不让 LLM 猜测点位。

## 数据模型与时间语义

`market_technical.py` 将外部响应拆成三个公开模型：

- `MarketInstrument`：规范代码、交易所、证券类型、展示名和 provider symbol。
- `LiveQuote`：当前价、provider 时间戳、交易状态和来源。
- `DailyBar`：date、open、high、low、close、volume。

provider 返回 `MarketSeries`，其中明确区分 `completed_bars` 与可选的 `live_bar`。计算函数只接收 `completed_bars`，从类型边界上阻止盘中数据混入指标。

同日 K 线的完成判定采用 fail-closed 策略：

1. 最新 K 线日期早于上海时区当前日期时，视为已完成。
2. 最新 K 线日期等于当前日期时，只有本地时间已过 15:05、provider 报价时间不早于 15:00，且 provider 数据日期一致，才视为已完成。
3. 时间戳缺失、互相矛盾或仍在交易时段时，最新行作为 `live_bar`，不得参与均线、摆动点、周期低点和缺口计算。

答案同时展示两个不同的截止口径：

- “技术位计算基于截至 YYYY-MM-DD 的已完成日线”；
- 若存在实时行情，再写“当前盘中参考价为 X，截至 HH:MM，未用于已确认技术位计算”。

## 证券解析与 provider 能力

新增单一的 `resolve_market_instrument()`，替代分散的前缀猜测：

1. 显式后缀 `.SH/.SZ/.BJ` 优先。
2. 已登记指数别名和指数代码优先于股票前缀规则。
3. 裸代码 `920xxx` 先解析为北交所，不能被通用 `9xxxxx → 上海` 规则截获。
4. 无法唯一判断时返回 typed resolution gap，不盲猜交易所。

指数别名注册表同时保存 provider 映射与能力状态。只有能返回足够历史日线的条目才进入可执行头部路由；已识别但当前 provider 不支持的指数返回 `provider_unsupported`，不伪装为一般网络失败。历史少于计算窗口时返回 `insufficient_history`。

腾讯接口仍作为当前主 provider，因为免认证且延迟低；接口形状和来源标签通过 adapter 隔离。设计保留 provider fallback 接口，但本批只有在存在第二个真实可用的结构化来源时才注册，禁止写空壳 fallback。

## 计算契约

`compute_market_technical()` 只消费已完成日线，并输出带 lineage（计算血缘）的结构化结果：

- MA5/10/20/60；
- 摆动低点、20/60 日低点和有效向上缺口；
- 聚类后的支撑/压力区间；
- 每个区间使用了哪些 bar、指标和参数；
- 收盘跌破或突破后的失效条件；
- 可选的成交量确认信息。

如果展示“放量/缩量”，必须由解析后的 volume 与明确窗口计算得出；否则只提示“尚未加入量能确认”，不能给出方向性量能结论。

## 展示与审计契约

新增两种任务专属 `presentation_kind`：

- `market_technical`：渲染点位、计算依据、数据截止和失效条件。
- `evidence_gap`：只渲染已获得的数据、缺失的数据、不能可靠得出的结论和可执行的补数条件。

二者都由 `AnswerSpec`/EvidenceAtom 审计，但不进入 Base Finance 五元素补全。确定性成功使用 `deterministic_verified` phase，且不得附加 `llm_unavailable_template_answer`。只有本来需要合成而 LLM 不可用时才能使用该 degrade。

`quality_requires_fail_closed()` 只决定是否允许研究正文出站。原始错误代码、内部题材污染文本和 provider 诊断进入 Inspector/trace；用户正文只显示业务化证据缺口。

TurnIntent 同步以 controller decision 为单一事实源。除明确标记的继承型追问外，question type、subject、subject kind、research mode、required outputs 和 owner 必须整体同步，不能只在类型变化时局部覆盖。

## 错误处理

- 代码无法解析：返回 `instrument_resolution_gap`。
- provider 不支持：返回 `provider_unsupported`。
- 响应异常或超时：返回 `market_data_unavailable`，保留 ProviderTrace。
- 历史不足：返回 `insufficient_history` 并说明所需/实际 bar 数。
- 时间语义不确定：排除最新行；若剩余数据足够则使用上一完整交易日，否则报 gap。
- AnswerSpec 质量失败：不展示原研究正文，仅展示业务化 gap；原始原因进入 Inspector。

## 测试与验收

### 单元与契约测试

- 交易时段内同日 K 线不得进入 MA、低点和支撑计算。
- 收盘后且 provider 时间戳满足条件时，同日 K 可以成为 completed bar。
- 盘中价和上一完整收盘价必须使用不同文案。
- volume 被解析并参与量能判断；没有 volume 时不得声称 OHLCV 或放量/缩量。
- `920022`、`920022.BJ`、指数别名和歧义代码解析符合注册表。
- 不支持的指数不会进入可执行 head capability。
- provider 失败只输出短 gap，不出现公司公告、客户验证、题材或五段模板。
- `needs_template=False` 的成功回答不产生 LLM fallback degrade。
- 原始 quality issue 不进入用户正文。
- controller decision 与 routing envelope 的完整字段保持一致。

### 真实 E2E

在临时端口运行同一候选 commit，至少验证：

1. 交易时段询问“科创50的支撑点位在哪”；
2. 收盘后重跑同题；
3. “沪深300压力位在哪里”；
4. 裸代码与带后缀的北交所标的；
5. 一个明确不支持或历史不足的指数；
6. 注入 provider 失败。

每次检查正文、AnswerSpec、phase、degrades、ProviderTrace、耗时和数据截止。通过后才允许把 8792 指向该 commit。

