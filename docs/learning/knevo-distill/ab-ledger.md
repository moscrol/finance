# Knevo × 本地工作台 双盲对照台账（ab-ledger）

> 纪律：先本地后 Knevo；两份答案当日冻结（git commit 即冻结）；T+1/T+3 按既有 verdict 口径打分；failure_mode 用 A1-A6 归因码（见 forecast-scoring-frameworks.md）。
> 目标：30 天 ≥25 样本，分题式统计胜率差，定位 Knevo 相对本地的真实增量。

## 样本记录格式

```
### AB-NNN | YYYY-MM-DD | 题式 TX | <题目一句话>
- 积分消耗：N（如可见）
- 本地答案（冻结）：<要点/或指向冻结文件>
- Knevo 答案（冻结）：<要点/或指向 qN 语料>
- 到期：T+1 YYYY-MM-DD / T+3 YYYY-MM-DD
- verdict：本地 hit/miss/unverifiable | Knevo hit/miss/unverifiable
- failure_mode：A1-A6（如 miss）
- 增量结论：<Knevo 比本地多看了什么维度/数据，或反之>
```

## 样本

### AB-001 | 2026-07-09 | 题式 T4 | 国产算力当前处于发酵期/共识期/透支期哪一段？
- 积分消耗：待回贴补记
- 本地答案（冻结）：[[AB-001-local]]（ask --compose，盘面 2026-07-09；核心判断=共识期高位分歧段·存量缩量抱团，升级信号=边际量转正+新高+L1→L3 订单落地，降级信号=放量阴线/涨停骤减/互动易口径保守；answer-score 80/B）
- Knevo 答案（冻结）：待回贴 → AB-001-knevo.md
- 到期：T+1 2026-07-10 / T+3 2026-07-14
- verdict：待回检
- failure_mode：—
- 增量结论：待对照

## 周度汇总

| 周 | 样本数 | 本地胜率 | Knevo 胜率 | 主要差距题式 | 已回灌项 |
|---|---|---|---|---|---|
| W1 | | | | | |
| W2 | | | | | |
| W3 | | | | | |
| W4 | | | | | |
