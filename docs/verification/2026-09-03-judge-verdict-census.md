# 判官拒句账普查

生成 2026-09-03T16:38:51+08:00；since=2026-09-03。

- 扫 run 815：带字段 **1**、无字段（历史）5、不可读 0、按日期跳过 809
- 拒句 1 条：stage {'judge': 1}；decision {'deleted': 1}；reason {'judge': 1}

## 被删的句子

- 共 1；**有出处**（引到本轮 E 号）0，占比 0.0%
- 只引了表外 E 号 0；没引任何 E 号 1
- 有出处被删的来源档分布：—

## 降成 issue（没删）的句子

- 共 0；来源档分布：—

**结论**：可判：见 deleted.with_source_share 与 with_source_tiers

阈值判定（spec §3.3 第 3 条）：`deleted.with_source_share` 中 `public_web` 等低档来源占比 ≥ 阈值才动判据；否则停在这里并把停下写进收据。
