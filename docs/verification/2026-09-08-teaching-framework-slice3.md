# 验证记录 · 授课框架 slice 3 · 结构视角（MACD 背离 / 缠论）· 2026-09-08

分支 `feat/teaching-framework-slice3-structure`，基线 `gitea/main@368b7a66`（#653 / #665 已合）。

```text
模块：intelligence/services/teaching_framework/structure.py
  macd(12/26/9)；merge_inclusion → fractals → strokes（老笔，gap ≥ 4）→ pivots（三笔重叠 + 延伸）；
  背离：同类分型两两比（价格更低 / 指标更高），DIF 与柱两口径；笔背驰：同向两笔柱面积；三买 / 三卖：离开段后第一笔整段在区间外的回抽
  事件全部记在确认日；缺高低价断段；MACD 逢 None 重起
接线：flags.compute_flags 整段一次算完并入 rec；index_stage EVENT_PREDICATES 加 8 个结构事件；STRUCTURE_SCALARS 进 view scalar；
  label_readouts 新增 structure_events（事件 × 阶段、中枢位置 × 阶段）；参数块 structure.divergence_lookback = 60
真库（/tmp/mfs-snap2.duckdb，402 可用日）：两次全新构建（19:00Z / 20:00Z）哈希一致 c615e934028ba240；加参数块与中枢笔数按当日已知笔算后 tf-v0.2+80dd72e0 / 223f7e6f8a1983f3
  标签行 47436 → 56682（+20 列）；阶段分布、平均 η² 0.149、一致率 44.5% 与 slice2 末态相同（结构列只写出）
  事件：底背离 DIF 6 / 柱 6，顶背离 DIF 10 / 柱 13，笔底背驰 2 / 顶背驰 3，三买 3 / 三卖 0；事件日与事后走势见骨架 §8.18
  底背离日期：2025-01-23、02-06、02-20、03-25、10-15、12-15；三买：2025-05-30、09-05、11-06
pytest intelligence/tests/test_teaching_framework_*.py 121 passed + 1 skip（新增 test_teaching_framework_structure.py 7 条：EMA 重起、包含处理、
  分型 / 笔 / 中枢 / 三买的确认日、背离判定、端点替换与不成笔、缺高低价断段、flags 接线）；ruff 通过
30 分钟探测：push2his.eastmoney.com / push2.eastmoney.com / web3.ifzq.gtimg.cn 解析到 198.18.0.x（fake-ip），TLS 握手成功后服务端空回复（curl 52）；
  push2delay 通但不给 kline；hq.sinajs.cn / quote.eastmoney.com 通 → 本机代理规则拦了 K 线主机，加 DIRECT 后再探深度
```

## 全 A 个股日线 MACD 背离变体（/tmp/tf22_stock_divergence.py，53 s）

```text
快照 fact_stock_daily 5,568 只 × 414 日（3,725,274 行）；摆动低点 = 5 根 K 线最低、第 3 天确认；两低 ≤ 60 交易日；
结果 = 确认日后 20 交易日超额（对当日全市场中位）> 0；基准 = 全部个股日 2,019,914 个，50.0%；readout(min_n=30)
底·DIF·两低 27644 0.529 [0.523,0.535] 0.510/0.548 supported +0.54% ｜ 底·柱·两低 36198 0.528 supported +0.52%
底·DIF·三低 3086 0.566 [0.548,0.583] 0.539/0.592 supported +1.25% ｜ 底·柱·三低 8791 0.555 supported +1.03%
对照 两低不背离 74707 0.504 [0.500,0.508] +0.08% ｜ 任意摆动低点 262945 0.501 not_distinguishable
顶·DIF·两高 22889 0.528 supported −0.60% ｜ 顶·柱·两高 29788 0.510 not_distinguishable −0.20% ｜ 对照 两高不背离 87595 0.510 −0.20%
按阶段 底·DIF·两低：缩量右底 1931/0.58/+1.3 共建主线 5648/0.58/+1.4 左底向下 4979/0.52 左底向上 1708/0.52 主升 2273/0.51 2.0 1076/0.51 高位震荡 6877/0.51
```

## 第二十三段：正式口径 + 证据候选 + 板块 / 个股层（`tf-v0.2+b5be80b8`）

```text
structure.py：close_swings / divergence_events（swing_k=2、lookback=60、fail_horizon=20，参数块 structure.*）→ 四个正式事件并入 structure_daily
  观察 = 两摆动低点收盘更低 DIF 更高（记第二低点确认日，anchor = 该低点）；确认 = 三低递降 DIF 递升；失效 = 20 日内收盘跌破锚点；顶 = 两高 DIF 更低
stage_rules：H:macd_bottom_div → 缩量右底（受周均线门）+ 共建主线；参数 structure_evidence（默认 true；false 只写出不计分、目录不列）
index_stage：EVENT_PREDICATES / STRUCTURE_EVENTS / EVIDENCE_INPUTS 加四个正式事件
scripts/teaching_framework.py：build-structure（板块按名字接序列、∏(1+pct_chg) 合成点位、entity_id 取事件日代码；个股收盘；<120 可用日不算；
  只删 / 只哈希自己四个标签；收据 build_kind=structure_events）；structure-screen --date [--events]（事件清单 + 市场粗段 + 板块角色；分析师侧）
  build-sector-roles 改为只删 / 只哈希 SECTOR_LABELS（原先清整个 entity_type='sector'，会抹掉结构行）
真库两次全新构建：build-labels 23:30Z / 02:00Z 哈希一致 1f0d266d7f53991a；平均 η² 0.1490 / 训 0.1548 / 验 0.1989、一致率 0.4454、未决 54、
  七段分布与 80dd72e0 完全相同；H:macd_bottom_div 亮 4 天（共建主线 3、缩量右底 1）
  build-structure 23:40Z / 02:10Z 哈希一致 29c9d9dc6a2fcb5e（sector efdec366… / stock dd531f05…）；板块 549 序列（116 跨代码）2,916 行：
  观察 899 / 确认 70 / 失效 501 / 顶 1,446；个股 5,568 只 74,594 行：观察 29,817 / 确认 3,313 / 失效 17,423 / 顶 24,041；两层都到 2026-09-03
  structure-screen --date 2026-09-02：market_stage=ambiguous，板块 6 行（失效 5 / 顶 1，都带四个角色标签），个股 214 行（确认 1 / 观察 11 / 失效 105 / 顶 97）
板块层事后读数（绝对 20 日收益，见骨架 §8.19）：观察 749/65.8%（基线 58.2%）、确认 47/63.8%、失效 386/58.5%、顶 1,430/53.8%；
  观察按阶段：缩量右底 78/85.9%（基线 62.7%）、共建主线 170/80.6%（61.0%）、左底向下 118/46.6%（53.0%）
pytest intelligence/tests/test_teaching_framework_*.py 124 passed + 1 skip（新增：正式事件四态 + 镜像顶背离、证据只给两段 + 门 + 开关、
  build-structure / structure-screen 端到端含「重跑只删自己的标签」）；ruff 通过
```

## 第二十四段：fine「触碰周均」（`tf-v0.2+b5be80b8`，哈希 b2c0556aa97739c5）

```text
stage_rules.stage_fine：左底向上 ∧ above_week_ma → 触碰周均；index_stage.stage_fine_exits（fine ≠ coarse 的日子之后第一个不同的有效粗段，30 可用日内，未决跳过）
真库两次全新构建 23:50Z / 03:00Z 哈希一致 b2c0556aa97739c5；粗段分布、η² 0.1490/0.1548/0.1989 与 1f0d266d… 相同
fine 分布：触碰周均 38、左底向上 3、二次探底 8、缩量右底 20、见顶 21、高位震荡 58（其余同粗段）
exits：触碰周均 {左底向下 19, 缩量右底 18, 共建主线 1}；二次探底 {共建主线 8}；见顶 {主流主升2.0 11, 左底向下 9, 缩量右底 1}
lint_output("阶段：左底向上（细分 触碰周均）") == []
pytest 126 passed + 1 skip（新增 fine 规则 + exits 两条）；ruff 通过
```

## 第二十五段：候选维度（`tf-v0.2+b5be80b8`，哈希 de23f56ee05f7536）

```text
BREADTH_SQL 加：above_ma5_share_pct / new_low_20d_count / new_high_20d_count / new_low_1y_count（窗口内逐日有行才算）；
_merge_divergence_breadth：全部个股跑 divergence_events（与 build-structure 同口径，<120 可用日不算），5 日内出过底背离观察 / 顶背离的个股占比
index_stage.CANDIDATE_METRICS 六项 → stage_separation()["candidates"]（不进 summary 平均）
真库两次全新构建 00:10Z / 04:00Z 哈希一致 de23f56ee05f7536；标签行 61,506；官方 16 项 η² 0.1490/0.1548/0.1989 不变；build-labels 28 s（+8 s 背离广度）
候选 η²（全/训/验）：20 日新高 0.463/0.445/0.525；个股 MA5 上方占比 0.371/0.431/0.298；20 日新低 0.273/0.346/0.231；一年新低 0.184/—/0.182（96 天）；
  底背离广度 0.039/0.112/0.068；顶背离广度 0.032/0.080/0.098
个股 MA5 上方占比阈值：40% → 底部两段在下方 0.74 / 上行三段在上方 0.88；50% → 0.89 / 0.77
pytest 126 passed + 1 skip；ruff 通过
```

## 第二十六段：三个维度进靶子 + 进证据（`tf-v0.2+c2c3faa1`，哈希 07398377fe207962）

```text
BAND_VIEWS += new_high_20d_count / stock_above_ma5_share_pct / new_low_20d_count；calibrate-stages --train-until 2025-12-31 --quantiles 0.25 0.75 --min-days 8（样本钉 de23f56e…）
SEPARATION_METRICS 16 → 19；CANDIDATE_METRICS 剩 一年新低 / 底背离广度 / 顶背离广度
五变体（/tmp/tf25_band_variants.py，旧 16 项靶子 全/训/验）：V1 三个 0.1608/0.1618/0.2012 ✓；V2 新高+MA5 0.1548/0.1582/0.2018 ✓；V3 MA5 0.1542/0.1644/0.2000 ✓；
  V4 新高 0.1486/0.1542/0.1978 ✗；V5 新低 0.1474/0.1517/0.1909 ✗；基线 0.1490/0.1548/0.1989 → 取 V1
真库两次全新构建 06:00Z / 07:00Z 哈希一致 07398377fe207962；19 项靶子 0.2078/0.2111/0.2419；旧 16 项 0.1608/0.1618/0.2012；一致率 0.3815；未决 35
分布：左底向下 72 / 左底向上 45 / 缩量右底 28 / 共建主线 81 / 主升 48 / 2.0 29 / 高位震荡 64 / 未决 35；触碰周均 40 → 回落 36（左底向下 11、缩量右底 25）、升级 4
river_objects 新增 teaching_breadth；reading 新增「广度」行（夹具 28% / 240 / 812）；pytest 126 passed + 1 skip；ruff 通过
```
