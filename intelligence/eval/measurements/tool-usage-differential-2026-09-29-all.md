# 工具授权与调用差值 · 离线审计

- 范围：962 份有效 JSON / 扫描 962 份；日期 2026-08-08 → 2026-09-29；过滤 since=None until=None user=all。
- 样本成分：具名目录 412；探针／其他目录 550/962 (57.2%)。具名目录亦可能混有评测。
- 代码 revision 跨度：UNAVAILABLE: no code revision in artifacts（有记录 0 / 962，缺 962；KB commit 不算代码版本）。
- 容缺：缺预检 13，无效 JSON 0，日期未知 0。

- 有 checks 的 run：949。可算差值：871。
- 至少一个声明工具未被调用：736/871 (84.5%)。
- **output 实例差值 626；声明盲区 suspicious 1850。两数必须并读。**

| 工具 | 声明为 contributor 的 run | 未调用 | 未调用率 |
| --- | ---: | ---: | ---: |
| `capital_data` | 14 | 11 | 11/14 (78.6%) |
| `evidence_lookup` | 164 | 125 | 125/164 (76.2%) |
| `financial_data` | 73 | 56 | 56/73 (76.7%) |
| `graph_lookup` | 248 | 133 | 133/248 (53.6%) |
| `kb_search` | 756 | 523 | 523/756 (69.2%) |
| `l3_lookup` | 74 | 40 | 40/74 (54.1%) |
| `mainline_context` | 124 | 64 | 64/124 (51.6%) |
| `market_data` | 598 | 273 | 273/598 (45.7%) |
| `news_search` | 221 | 151 | 151/221 (68.3%) |
| `web_fetch` | 69 | 56 | 56/69 (81.2%) |
| `web_search` | 169 | 148 | 148/169 (87.6%) |

| output_id | 实例级差值 |
| --- | ---: |
| `direct_assessment` | 167 |
| `direct_answer` | 135 |
| `chain_mapping` | 121 |
| `prime_news` | 67 |
| `prime_quote` | 60 |
| `supporting_evidence` | 37 |
| `relation_map` | 16 |
| `fact_value` | 6 |
| `financial_assessment` | 6 |
| `metric_evidence` | 6 |
| `company_mapping` | 5 |

## 边界
The instrument's range depends on the produces declaration table: an empty declaration hides missed calls. Conversely, a declared-but-uncalled tool does not prove the output was left empty; another tool or prefetch may fill it. Neither the run-level gap nor the output-instance count measures model quality.

只读聚合；不是线上用户质量或路由缺陷的结论。
