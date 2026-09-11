# 工单 #48：相关样本——同日共振与重叠窗口不再冒充独立证据（OPT-05 第一刀）

> 日期：2026-09-11
> 上游：补强 spec `2026-09-08-research-foundation-optimization-design.md` OPT-05；叠在工单 #42（OPT-04 晋升认证，分支 `feat/methodology-promotion-certification`）之上
> 用户 09-11 拍板：「处理同日共振、重叠窗口，防止把大量相关样本误当独立证据」
> 分支：`feat/methodology-correlated-samples`（树 `~/fwp-wt-opt05-correlated-samples`）
> 统计依据：Petersen (2009) 金融面板相关性、日期块 bootstrap 惯用法；引用不等于门已过，估计器已用本项目合成样本验证

## 0. 一句话

原统计路径把事件序列展平成布尔序列（`readout(successes)`），N = 事件数——同一天 400 个
板块共振就是 400 个「独立」样本，复制相关样本能白造统计力量。本刀让**独立单元 = 日期块**：
Wilson 读数降为描述性，最终四态由「独立假设 × 依赖感知」保守合成。

## 1. 三件事

1. **日期块重采样**（`stats.block_bootstrap_readout`）：事件 `(entity, date, success)` 不展平；
   circular block bootstrap 在**唯一事件日序列**上取块（块长 = `rule.success.horizon`，盖住
   outcome 重叠范围），一个块携带该段日期的**全部**实体事件——同日共振与窗口依赖原样保留在
   块内。B=500、种子固定 20260911，method / seed / n_boot / CI 全入收据。完整非重叠块数
   < min_blocks=10 → `insufficient_blocks`，**不回落**成把事件数当 N 的二项检验。
2. **保守合成**（`stats.combined_verdict`）：顶层 verdict = 两道一致才 supported / refuted；
   不一致 → `not_distinguishable`（note 写明两道读数）；块不足 → `insufficient_n`。
   **refuted 同样要两道**——同日负样本同样不独立；「推翻不用预注册」说的是晋升流程的
   不对称，不是显著性豁免。BH（scan 模式）继续作用在合成后的 verdict 上，只降不升。
3. **跨窗 purge**（`runner._purge_cut_date`）：窗末最后 `horizon` 个交易日（日历 =
   `history_labels` 唯一交易日）内的事件，其 outcome 落在窗外——发现窗读了验证窗的价格。
   剔除并在收据 `events.n_purged_cross_window / purge_cut_date` 如实计数。基准窗随剩余
   事件日收缩，基准也不用跨界日。

样本身份同时入账：`dependence` 段带 `n_events / n_dates / n_clusters / span_dates`（spec
「同时报原始样本数、交易日数、事件簇数、跨度」）。事件簇 v0 口径：同实体、相邻触发自然日
间隔 ≤ block_len 归一簇（自然日是交易日距离下界，判「断开」偏松、簇数只多不少——报告字段
的安全方向）；簇数只报不判。

## 2. 验收（对 spec OPT-05 逐条，全部已转回归）

- [x] 「复制同日相关板块不会凭复制次数提升有效独立证据」：420 事件散 60 日 → supported；
  同 420 事件挤 6 日 → `insufficient_blocks` 且不出区间（`test_同日复制不提升有效独立证据`）。
- [x] 「有效块不足时输出 insufficient，不能退回原始二项检验宣布通过」：块不足时连 refuted
  也不出（`test_全负事件_块足时才refuted`；端到端 `test_synthetic_positive_control...` 小夹具段）。
- [x] 「固定种子重复统计结果一致」：同输入逐字段相同；换种子分布不同且种子入账。
- [x] 「发现窗末尾 T+5 outcome 跨界被剔除」：窗口终点压到事件日 → `n_purged > 0`、留存事件
  全部 ≤ cut（`TestPurge`）。
- [x] 合成矩阵 8 种组合 + 不一致 note；收据带 `dependence` 段与 purge 计数。
- [x] 真阳性不被误杀：合成夹具放大到 240 日（事件日 ~72、14 块）后阳性对照两道均 supported
  ——门拦的是「事件多、日期少」的形状，不是拦掉一切。
- [x] `RECEIPT_SCHEMA` 未升版：新增字段向后兼容，旧收据仍被 lifecycle 读取。

## 3. 边界 / 未做（后续刀）

- **尝试账**（登记先于执行、多重检验分母、留出集访问登记）：OPT-05 后半，另开一刀——它要
  新账本，先登记台账地图。
- 阶段桶（`by_market_stage`）verdict 保留独立口径：桶是规则内解释用，晋升只看顶层合成；
  桶级依赖读数等横截面样本量上来再议。
- 事件簇归组只报数，不改 N；「按声明归组去重」的规则级声明字段（grouping policy）等
  OPT-09 规则 schema 扩展时一并做。
- 块长 = success.horizon 是 v1 冻结口径；逐日自适应块长按 spec 须先冻结更新协议，不做。
- `_summarize_horizons`（多窗口收益描述表）未接 purge：它是描述性读数、不进 verdict。
