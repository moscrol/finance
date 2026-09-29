# 工具授权与调用差值 · 离线审计

- 范围：24 份有效 JSON / 扫描 962 份；日期 2026-08-25 → 2026-08-26；过滤 since=2026-08-25 until=2026-08-26 user=all。
- 样本成分：具名目录 6；探针／其他目录 18/24 (75.0%)。具名目录亦可能混有评测。
- 代码 revision 跨度：UNAVAILABLE: no code revision in artifacts（有记录 0 / 24，缺 24；KB commit 不算代码版本）。
- 容缺：缺预检 0，无效 JSON 0，日期未知 0。

- 有 checks 的 run：24。可算差值：24。
- 至少一个声明工具未被调用：21/24 (87.5%)。
- **output 实例差值 23；声明盲区 suspicious 108。两数必须并读。**

| 工具 | 声明为 contributor 的 run | 未调用 | 未调用率 |
| --- | ---: | ---: | ---: |
| `evidence_lookup` | 3 | 3 | 3/3 (100.0%) |
| `graph_lookup` | 8 | 3 | 3/8 (37.5%) |
| `kb_search` | 24 | 16 | 16/24 (66.7%) |
| `market_data` | 17 | 6 | 6/17 (35.3%) |
| `news_search` | 12 | 9 | 9/12 (75.0%) |
| `web_search` | 3 | 2 | 2/3 (66.7%) |

| output_id | 实例级差值 |
| --- | ---: |
| `prime_news` | 9 |
| `direct_answer` | 4 |
| `chain_mapping` | 3 |
| `direct_assessment` | 3 |
| `prime_quote` | 3 |
| `company_mapping` | 1 |

## 边界
The instrument's range depends on the produces declaration table: an empty declaration hides missed calls. Conversely, a declared-but-uncalled tool does not prove the output was left empty; another tool or prefetch may fill it. Neither the run-level gap nor the output-instance count measures model quality.

只读聚合；不是线上用户质量或路由缺陷的结论。
