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
