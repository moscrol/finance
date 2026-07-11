# Fidelity Replay Phase 2：80 日扩量验收

> 执行日期：2026-07-11
> 分支：`eval/fidelity-replay-acceptance-v1`
> 数据：a77 Mac 只读 DuckDB、finance repo 历史制品、knowledge-base Git 历史
> 状态：自动评测完成；人工金标准与版本缺口仍未通过。

## 任务计划

- 日期范围：2026-03-01 ～ 2026-07-03；
- 候选交易日：85；
- 分层样本：80；
- 分层维度：月份、行情阶段、PIT 数据完整度；
- 结果去向：`readonly`；
- 缺数策略：`pending`；
- 无前视：开启；
- task-plan 代码门：13 项全部通过。

抽样先保留所有精确日期 canonical 报告，再以固定 seed 对
`月份 × 行情阶段 × 数据完整度` 做轮转补样。没有精确日期报告的交易日保留为
negative control，不用今天的报告或邻近日报告替代。

## 分层结果

| 维度 | 结果 |
|---|---|
| 月份 | 3 月 22、4 月 20、5 月 14、6 月 21、7 月 3 |
| 报告状态 | canonical 25、missing negative control 55 |
| PIT 完整度 | partial 18、pending 62 |
| 行情阶段 | 11 类均被覆盖 |

## 五项现状忠实度指标

| 指标 | 分子 / 分母 | pending | 结果 |
|---|---:|---:|---:|
| 数字一致率 | 333 / 335 | 39157 | 99.4030% |
| 实体归类准确率 | 0 / 0 | 1948 | pending |
| 证据覆盖率 | 0 / 47779 | 0 | 0% |
| 截止违规率 | 0 / 563 | 0 | 0% |
| 事实/推断混淆率 | 0 / 0 | 47929 | pending |

数字一致率在 80 日样本仍保持约 99.4%，说明明确字段映射和单位换算较稳定；
但 inferred mapping 只用于数值复核，不计入原始逐声明证据，因此证据覆盖率仍为 0。
扩样不能把“可复算”误写成“有出处”。

### P3：两个 mismatch 的根因

两个 mismatch 都来自同一份
`2026-06-02-20d-plus-new-highs.md`：

- 国瓷材料 `涨幅%=13.50` 被错误映射到
  `fact_stock_daily.pct_chg=13.28`；
- 朝阳科技 `成交额(亿)=1.91` 被错误映射到
  `fact_stock_daily.amount=1.915`。

它们不是两个独立的 rounding 特例。该报告由
`fact_stock_high_daily` 生成，正确值分别是 `pct_chg=13.50` 和
`amount=1.91`。修复采用 **report source contract**：先按 canonical
artifact family 选择源表，再按列名选择字段；不能只看“涨幅%/成交额”这些通用
表头就猜 `fact_stock_daily`。

替代方案是放宽小数容差或给两只股票写例外，但前者仍无法解释 13.50/13.28，
后者会把数据血缘错误伪装成数值修复。source contract 可迁移到其他由专用特征表
生成的报告。

还要注意：2026-06-02 的 `fact_stock_high_daily` 行在当前库中的
`updated_at` 晚于 PIT cutoff。因此修复后这些声明应转为 `unverifiable`，而不是
借用当日已存在的 `fact_stock_daily` 行判成 matched。数字分母缩小是更诚实的
PIT 结果，不是通过隐藏 mismatch 提高分数。

## 声明与历史重放

声明状态：

```json
{
  "matched": 333,
  "mismatch": 2,
  "needs_review": 7626,
  "unverifiable": 39968,
  "missing": 0
}
```

历史重放：

- timeline precision：pending；
- timeline recall：pending 47929；
- stage feature accuracy：pending 1260；
- causal statements：pending 2；
- approved gold：0 / 80；
- 阻断版本缺口：80 / 80 日期。

样本量增加没有消除人工语义裁定和历史版本证据缺口。`pending`、
`needs_review`、`unverifiable` 均不视为通过。

## 物理隔离与完整性

Phase 2 使用三个独立步骤：

1. `inputs` 只写 `as_known_at`，不落 `final_history`；
2. canonical 报告逐声明评测完成后，独立运行 `outcomes`；
3. `compare-batch` 才读取两个物理目录做对照。

核验结果：

- PIT 输入：80；
- outcome：80；
- comparison：80 个 `partial`；
- input 目录不存在 `final_history`；
- outcome 目录不存在 `as_known_at`；
- 55 个无报告负对照在 claim evaluator 中仍为 missing，没有被替换；
- `phase2.negative-controls.json` 单独列出 55 个日期，并验证它们对五项
  fidelity metric 的分母贡献均为 0；
- DuckDB 运行前后签名均为
  `16777231 10239282 3208654848 1783682464`。

远端只读产物：

```text
/Users/a77/fidelity-replay/phase2-v1-20260711/
├── plan/
├── inputs/
├── claims/
├── outcomes/
├── comparison.report.json
└── summary/
```

## 结论

Phase 2 已完成 80 个历史截面的扩量执行，但验收结论仍是：

```json
{
  "decision_eligible": false,
  "approved_gold_count": 0,
  "blocking_version_gap_dates": 80
}
```

扩样证明自动数值对账在更大样本上稳定，也证明真正的瓶颈不是样本量，而是：

1. canonical 报告缺失；
2. 原始逐声明 evidence 缺失；
3. 历史实体、成分、公告和知识版本缺口；
4. 人工 gold 尚未批准。

## 可迁移知识点

- **分层抽样不能修复数据治理缺口**：它只能让缺口暴露得更有代表性。
- **可复算不等于可溯源**：inferred mapping 与 claim-level evidence 必须分开计分。
- **PIT 隔离要靠文件边界证明**：先冻结输入，再生成结果，避免结果字段回流。
- **负对照必须保持为空**：缺资料日期若被邻近或当前报告填充，会制造虚假召回率。
- **表头不是数据血缘**：同名字段可能来自不同事实表；报告族 source contract
  比全局列名映射更可靠。
- **分母缩小不一定是退步**：移除无法 PIT 证明的样本，比把错误来源算作 matched
  更符合审计目标。
