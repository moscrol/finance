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
