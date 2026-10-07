# 字段账本：实现、归属、覆盖与待核

**范围：12 个资金面字段 + `STRUCTURE_FIELDS` 中 26 个结构字段 = 38 个。** 这不是整套授课框架的全部标签，也不是云端“约 30 个”的逐名对照。全部为既有实现说明，没有在本轮新增计算定义或阈值。

数据库标签通常冠 `tf.`；表中用去前缀的字段名。采集程序直接调用旧 SQL/纯函数临时计算，**没有经过完整标签构建与缺口门，也没有写入旁路库**；故“非空”仅表示该函数有输出。指定旁路库这 38 个字段实际均无落库行。[落库审计](data/sidecar_audit.json)

## A. 资金面 12 项

**共同归属：agent 候选观察量，不是用户给过的逐阶段判据。** 用户提出 L2 大单、成交占比并邀请探索；这三组是 agent 扩入，09-16 草稿对其判读覆盖度为 none。无须禁止模型使用，但新的解释应保持可修订假设身份。[讨论](sources/discussions/dynasties-and-capital.md)、[缺口](sources/discussions/capital-judgment-gap.md)

**算法共同来源：** [capital.sql](code/capital.sql) + [source_views.py](code/source_views.py)。数值求和经 `DECIMAL(18,6)` 后转 DOUBLE，均值没有在本包另外改精度。分母是 `fact_market_daily` 内 432 个日期；连续窗口也按该表顺序判断，本轮未独立校验交易日历。

| 字段 | 当前实际计算 | 非空日/432 | 最新非空 |
|---|---|---:|---|
| `dragon_count` | 当日净额非空的股票代码去重数。不是上榜席位总数。 | 417 | 09-30 |
| `dragon_net_amount` | 同日所有输入股票净额相加。同花顺 `net_value/1e8` 转亿元；整日无新源才取旧源 `net_amount`。 | 417 | 09-30 |
| `dragon_net_amount_ratio_pm` | `1000 × 净额合计 / 市场总成交额`，分母 >0 才有值；口径为千分比，不是百分比。 | 417 | 09-30 |
| `dragon_buy_sell_ratio` | 正净额股票的净额之和 / 负净额股票的净额绝对值之和，后者 >0 才有值。**不是原始买入总额/卖出总额。** | 417 | 09-30 |
| `dragon_net_amount_ratio_pm_ma5` | 上述净额占比最近 5 个连续日历行的均值，5 天都非空才输出。 | 409 | 09-30 |
| `dragon_buy_sell_ratio_ma5` | 上述正/负净额比最近 5 个连续日历行的均值，5 天都非空才输出。 | 409 | 09-30 |
| `limit_seal_amount_median_wan` | 当日 `limit_status='U'` 的涨停股按代码去重（取 MAX fd），再取封单 `fd_amount` 中位数。字段名声明单位万。 | 394 | 09-02 |
| `limit_seal_mv_ratio_median` | 每只涨停股分别取 MAX fd、MAX mv，计算 `fd/mv`（mv=0 转 NULL），再取中位数。SQL **没有换算为统一币种单位的占比**。 | 394 | 09-02 |
| `limit_thick_seal_share_pct` | `100 × count(fd/mv ≥ 100) / count(fd非空)`；100 是旧代码阈值，不是本次认定的用户阈值。分母含 mv 缺失但 fd 非空者。 | 394 | 09-02 |
| `auction_zt_pct_median` | 昨日确认涨停股今日竞价涨幅中位数（新源仅 `kind='snapshot'`，整日无匹配才回退旧 `zt` 面板）。 | 151 | 09-02 |
| `auction_zt_positive_share_pct` | `100 × count(auction_pct>0) / count(auction_pct非空)`。 | 151 | 09-02 |
| `auction_zt_amount` | 昨日涨停股竞价金额之和；来源适配原样使用新旧 `auction_amount`，未显式归一单位。 | 151 | 09-02 |

### 资金面数据 caveat（限制）

1. **不是纯单日全市场资金流。** 龙虎榜源 `range_days` 有 1/3/10/30 四种，聚合未区分披露区间；净额也不是席位级明细或全市场 L2。表名/字段名不能代替该含义核验。[分组收据](data/input_group_audit.json)
2. **不能把数值比直接印百分比。** 封单 `fd_amount` 与流通市值 `circ_mv` 的币种倍率需核；本轮只验证原始数值及代码运算。旧代码产出百位量级 `fd/mv` 并按 100 切厚薄，不能把它解读成“封单占流通市值 100%”。竞价跨新旧源亦有单位待核。需要核对源契约后才能作严格跨期比较。
3. **行存在≠需要的字段有值。** 涨停表到 09-30，但确认 `U` 的末日为 09-02；竞价新源 `benchmark` 有 174 天，`snapshot` 只有 5 天，后者还需匹配昨日涨停集合。适配后竞价本次仅 151 天且截至 09-02。[源表覆盖](data/source_coverage.json)、[分组审计](data/input_group_audit.json)
4. **重复风险实测为 0，不是代码一般保证。** 新源竞价通过涨停主题表 join，源码没有在 `lim` 做 distinct；这份快照适配后 stock-day 重复数 0，换数据仍需再验。[适配样本及去重检查](data/adapted_source_samples.json)
5. **覆盖不是效力。** 未跑阶段区分力、后验收益、字段判读研究。历史讨论中的统计结果只作历史记载。

### 真实样本（临时重算）

2026-09-02：龙虎榜净额 −1.48039 亿，净额占市场成交 −0.082662759‰，5 日均 0.432888188‰；封单中位数 7507.515（字段名所称万），`fd/mv` 中位数 124.327664（原比例），厚封单占比 61.538462%；昨日涨停股竞价涨幅中位数 3.005%，为正比例 100%，金额和 5.05（源值单位待核）。2026-09-30 的龙虎榜净额为 10.66261 亿，封单/竞价留空。[全部入选样本与覆盖](data/capital_recomputed.json)

## B. MACD 与缠论 26 项

共同源为上证指数日线收盘/高/低。MACD 是指数移动平均线差值指标；EMA 是“越近价格权重越大”的指数移动平均。此处 DIF = EMA12 − EMA26，DEA = EMA9(DIF)，柱 = 2×(DIF−DEA)。这三组 12/26/9 为当前实现值，不是本轮新定义。

**出处与归属：** 用户要求结合 MACD/缠论，并在数据说明后说“执行”；精确操作化由 agent 写成。正式收盘摆动式背离与旧缠论分型式背离是两套字段，不能混用。参考 [讨论](sources/discussions/macd-and-chan.md)、[完整算法](code/structure.py)、[参数](code/selected_params.json)。

| 字段 | 当前算法/对象 | 非空日/432；事件为真天数 | 本次截至当天 vs 全历史检查 |
|---|---|---|---|
| `macd_dif` | EMA12(close) − EMA26(close)；EMA 从首个有效收盘初始化，缺值后重启。 | 432 | 无差异 |
| `macd_dea` | EMA9(DIF)。 | 432 | 无差异 |
| `macd_hist` | 2×(DIF−DEA)。 | 432 | 无差异 |
| `macd_bottom_div_dif` | **旧分型式**：相邻底分型价格更低、极值日 DIF 更高，距离≤lookback；记在后一分型确认日。 | 430；6 | 1 天不同 |
| `macd_bottom_div_hist` | 同上，指标改为 MACD 柱。 | 430；6 | 2 天不同 |
| `macd_top_div_dif` | **旧分型式**：相邻顶分型价格更高、DIF 更低。 | 430；11 | 2 天不同 |
| `macd_top_div_hist` | 同上，指标改为 MACD 柱。 | 430；14 | 4 天不同 |
| `days_since_macd_bottom_div` | 距最近旧分型式 DIF 底背离的日历行距离，当天=0，未出现过为 NULL。 | 409 | 1 天不同 |
| `days_since_macd_top_div` | 距最近旧分型式 DIF 顶背离的日历行距离。 | 413 | 2 天不同 |
| `chan_fractal` | 包含关系合并 K 线后，中间一根高与低均高于两侧为顶，均低于两侧为底；第三根确认。无事件为 NULL。 | 156 | 29 天不同 |
| `chan_stroke_dir` | 以最后已确认笔的反向标当前笔方向。笔由顶底交替、间隔门及端点价格形成，同向更极端分型会替换端点。 | 356 | 186 天不同 |
| `chan_stroke_day` | 当日序号 − 最后一笔终点极值日原始序号。 | 356 | 186 天不同 |
| `chan_stroke_count` | 累计确认笔数量。 | 430 | 186 天不同 |
| `chan_pivot_zg` | 最近已知中枢上边：连续三笔 high 的最小值，要求 zg > zd。 | 322 | 6 天不同 |
| `chan_pivot_zd` | 最近已知中枢下边：连续三笔 low 的最大值。 | 322 | 6 天不同 |
| `chan_pivot_pos` | close 相对 zg/zd 的 above / below / inside。 | 322 | 3 天不同 |
| `chan_pivot_strokes` | 中枢吃到的已确认笔数；实现试图按当日裁剪最终 end_stroke。 | 322 | 108 天不同 |
| `chan_third_buy` | 向上离开中枢后第一笔向下回抽，回抽终点>zg，记其确认日。字段名是术语，输出不是交易指令。 | 430；3 | 6 天不同 |
| `chan_third_sell` | 对称：向下离开后的向上回抽终点<zd。 | 430；0 | 2 天不同 |
| `chan_stroke_bottom_divergence` | 相邻两笔向下笔（中间隔向上笔）后笔创新低、负 MACD 柱面积绝对值更小；实现另有间隔限制。 | 430；2 | 1 天不同 |
| `chan_stroke_top_divergence` | 同向向上两笔，后笔创新高、正柱面积更小。 | 430；3 | 1 天不同 |
| `macd_bottom_div_observe` | **正式收盘摆动式**：前后各 k=2 日内唯一最低收盘为低点；相邻两低，后收盘更低且 DIF 更高，跨度≤60；在后低点+2 日观察。 | 432；4 | 无差异 |
| `macd_bottom_div_confirm` | 连续三低收盘递降且 DIF 递升，首末跨度≤60，第三低点+2 日确认。 | 432；0 | 无差异 |
| `macd_bottom_div_failed` | 观察锚点确认后 20 个日历行内，首次收盘跌破该锚点低点；一次记录可有多个历史锚点来源。 | 432；3 | 无差异 |
| `macd_top_div` | **正式收盘摆动式**：相邻两高收盘更高、DIF 更低，跨度≤60，后高点+2 日记录。 | 432；9 | 无差异 |
| `macd_div_anchor_idx` | 正式事件对应极值位置（从 0 数的输入行序号）；同日事件共用一列，有代码赋值优先次序，不能声称覆盖每个事件的全部锚点。 | 16 | 无差异 |

### 结构字段限制

- **老笔间隔按代码而不是注释猜。** `f.bar - anchor.bar >= 4` 才过门，差=4 意味两个端点之间 3 根；模块注释说“中间至少隔 4 根”，自然语言有歧义。这里原样记录条件，不替用户/作者裁定老笔流派。
- 高/低/收缺一天会断开缠论段，MACD 只因收盘缺值才重启。本次收盘齐 432 天，高低收齐 430 天。旧事件非空天数 430 是条件计算覆盖；`chan_fractal` 非空 156 是有分型事件，不能反推另外 276 天全是数据缺口。[输入覆盖](data/source_coverage.json)
- 正式事件布尔默认 False，代码在缺数据场景也可能保留 False；不能以“字段非空”断言全具备可观察性。本次收盘齐全不代表一般输入都没有这个问题。
- 18 字段有“后来的数据改变过去结果”的实测证据。原因定位/修复不在本轮；本包仅证明前缀不一致，并不把全部 MACD 字段都判错。无差异也只限该数据快照，不是形式化证明。[检查收据](data/structure_prefix_check.json)
- 本次只算指数日线，没有重建板块/个股层、30 分钟线、王朝或完整阶段分数；没有做收益有效性评估。当前 `structure_evidence=true` 的计分接线见 [源码片段](code/structure-score-source.md)，是历史实现状态而非本次授权新增规则。

## 样本与复算位置

- 实际原表少量行：[source_samples.json](data/source_samples.json)；字段类型：[source_schemas.json](data/source_schemas.json)。
- 临时适配视图少量行：[adapted_source_samples.json](data/adapted_source_samples.json)。
- 每个结构字段的覆盖、指数输入及最新/事件样本：[structure_recomputed.json](data/structure_recomputed.json)。
- SQL 和采样方法：[query_log.json](data/query_log.json)、[collect_data.py](tools/collect_data.py)。

**继续核验的优先顺序：** 先拿云端准确标签名单与本表做映射；再分清单位/复权/时间可知性这些事实契约；最后才讨论各字段如何支持可修订的框架假设。不靠把标签直接译成新的硬语义规则来“补齐”。
