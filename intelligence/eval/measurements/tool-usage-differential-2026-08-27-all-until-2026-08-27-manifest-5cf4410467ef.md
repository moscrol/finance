# 工具授权与调用差值 · 离线审计

- 范围：747 份有效 JSON / 扫描 747 份；日期 2026-08-08 → 2026-08-27；过滤 since=None until=2026-08-27 user=all。
- 冻结样本：tool-usage-differential-2026-08-27-reconstructed-cohort.json；SHA256 5cf4410467efc0de6afcbca834acfb5e905d7bc55b23c958993c80f32371b01b；依据：extant continuous-episode.json mtime <= initial workorder be00f83c7 commit 2026-08-27T20:43:39+08:00; original 747-run manifest not retained。此清单为现存产物重建，并非当时保存的原始 manifest。
- 样本成分：具名目录 387；探针／其他目录 360/747 (48.2%)。具名目录亦可能混有评测。
- 代码 revision 跨度：UNAVAILABLE: no code revision in artifacts（有记录 0 / 747，缺 747；KB commit 不算代码版本）。
- 容缺：缺预检 12，无效 JSON 0，日期未知 0。

- 有 checks 的 run：735。可算差值：698。
- 至少一个声明工具未被调用：572/698 (81.9%)。
- **output 实例差值 425；声明盲区 suspicious 1193。两数必须并读。**

| 工具 | 声明为 contributor 的 run | 未调用 | 未调用率 |
| --- | ---: | ---: | ---: |
| `evidence_lookup` | 84 | 55 | 55/84 (65.5%) |
| `graph_lookup` | 199 | 99 | 99/199 (49.7%) |
| `kb_search` | 603 | 406 | 406/603 (67.3%) |
| `l3_lookup` | 5 | 3 | 3/5 (60.0%) |
| `mainline_context` | 59 | 14 | 14/59 (23.7%) |
| `market_data` | 459 | 171 | 171/459 (37.3%) |
| `news_search` | 120 | 89 | 89/120 (74.2%) |
| `web_search` | 89 | 83 | 83/89 (93.3%) |

| output_id | 实例级差值 |
| --- | ---: |
| `direct_assessment` | 123 |
| `direct_answer` | 107 |
| `chain_mapping` | 99 |
| `prime_news` | 39 |
| `prime_quote` | 30 |
| `supporting_evidence` | 21 |
| `company_mapping` | 5 |
| `relation_map` | 1 |

## 边界
The instrument's range depends on the produces declaration table: an empty declaration hides missed calls. Conversely, a declared-but-uncalled tool does not prove the output was left empty; another tool or prefetch may fill it. Neither the run-level gap nor the output-instance count measures model quality.

只读聚合；不是线上用户质量或路由缺陷的结论。
