# 新块（D6/D7/D8/D9/W7/[M]/情景树）Mac 复跑验收 Runbook

> 适用：PR #153→#159 链合并（或 checkout 链顶分支 `feat/ask-moneyflow-block`）后，在有生产 DuckDB / 用户记忆台账的 Mac 上执行。

## 0. 准备

```bash
git fetch origin && git checkout feat/ask-moneyflow-block   # 或合并后的 main
python3 -m unittest discover -s intelligence/tests          # 全量单测应零失败
```

## 1. 基准题复跑（每题跑完看两处：d_block_stats 是否命中、答案是否引用对应编号）

| # | 基准题（原判负原因） | 应命中的新块 |
|---|---|---|
| 1 | 数据要素 vs 信创 vs 数据安全 未来 3-6 个月中期赔率对比（单日快照偏置） | D6 中期趋势 |
| 2 | 深信服 财报兑现节奏 / 瑞华泰 业绩（无财报数据判负） | D7 逐季财报 |
| 3 | 后量子密码 PQC 最新事件/催化（消息面全失） | W7 事件检索 |
| 4 | 「我之前对数据安全怎么判断的？现在还成立吗」 | [M] 记忆检索 |
| 5 | 「历史上类似这种高低切换怎么走」 | D8 历史类比 |
| 6 | 涨停股大单资金流 / 某股主买净额与量化单 | D9 资金流 |
| 7 | 厦钨 H1 正极能否扭亏（推演类） | 情景树契约（答案应为 变量表→情景分支(高/中/低+依据，无数值概率)→监控信号 结构） |

跑法（ask CLI，带 market_db_path）：

```bash
python3 -m intelligence.cli ask "<题目>" --market-db db/market_feature_store.duckdb
```

## 2. 验收纪律（判 PASS 的硬条件）

- 每个块的数字可在源头复核（DuckDB SQL / 东财页面 / jsonl 台账）。
- 缺数时块内出现显式缺口声明，答案没有编造（尤其 D8 不给概率、D9 不把缺行说成无资金流入）。
- 未命中意图的普通题（如「今天信创怎么样」）不应出现新块——行为不变性。
- 情景树回答中不出现任何数值概率/概率区间。

## 3. 结果落台账

每题在 `knevo-vs-workbench-技能包对比台账.md` 对应行补「Mac 实测：PASS/FAIL + 一句话证据」。FAIL 的开 fix/ 分支修。
