# 工具授权与调用差值 · 离线审计

- 范围：748 份有效 JSON / 扫描 962 份；日期 2026-08-08 → 2026-08-27；过滤 since=None until=2026-08-27 user=all。
- 样本成分：具名目录 387；探针／其他目录 361/748 (48.3%)。具名目录亦可能混有评测。
- 代码 revision 跨度：UNAVAILABLE: no code revision in artifacts（有记录 0 / 748，缺 748；KB commit 不算代码版本）。
- 容缺：缺预检 12，无效 JSON 0，日期未知 0。

- 有 checks 的 run：736。可算差值：699。
- 至少一个声明工具未被调用：573/699 (82.0%)。
- **output 实例差值 425；声明盲区 suspicious 1198。两数必须并读。**

| 工具 | 声明为 contributor 的 run | 未调用 | 未调用率 |
| --- | ---: | ---: | ---: |
| `evidence_lookup` | 85 | 56 | 56/85 (65.9%) |
| `graph_lookup` | 199 | 99 | 99/199 (49.7%) |
| `kb_search` | 604 | 406 | 406/604 (67.2%) |
| `l3_lookup` | 5 | 3 | 3/5 (60.0%) |
| `mainline_context` | 59 | 14 | 14/59 (23.7%) |
| `market_data` | 460 | 172 | 172/460 (37.4%) |
| `news_search` | 120 | 89 | 89/120 (74.2%) |
| `web_search` | 90 | 84 | 84/90 (93.3%) |

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
