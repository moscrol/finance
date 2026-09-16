"""方法论回测：结构化历史标签层 + 声明式规则编译器 + 统计四态。

设计稿 ``docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md``，
P0 工单 ``docs/superpowers/specs/2026-09-04-methodology-backtest-p0-workorder.md``。

分层：
- ``labels``    主库 fact_* 只读 → 旁路库 ``history_labels``（逐日逐实体、确认日语义、版本化）
- ``outcomes``  前瞻结果 3/5/7/10 日（fwd_return / max_return / days_to_peak / drawdown_after_peak）
- ``rules``     规则 JSON schema v0 + 白名单校验（带字段路径，不触库）
- ``compiler``  规则 → 参数化 SQL（谓词值走绑定参数，label/op/metric 走白名单）
- ``stats``     Wilson 95% 区间、基准率、lift、前后半段、Benjamini–Hochberg、四态结论
- ``runner``    在旁路库上执行编译结果，产出读数
- ``receipts``  收据 JSON + md（带成立条件块）

本包只依赖标准库 + duckdb + ``market_feature_store``；不 import ``intelligence.runtime``。
"""
