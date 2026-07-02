---
name: researcher-valuation
metadata:
  pattern: pipeline
  also: [reviewer]
description: 研究员拍估值的输出契约与质检门——不给单点目标价，而是把研究员的估值推理固化成五段契约：估值现状（PE/PS/EV 分位）、可比公司估值带、隐含增长率反推（市场已 price in 多少）、悲观/中性/乐观情景估值表（每情景绑定可验证条件）、证据审计（硬数据 vs 研报推断）。最终稿必须过 valuation_lint.py（exit 0，含单点目标价红线）才能交付。触发词：拍估值、估值带、贵不贵、隐含预期、值多少钱、估值分位、估值怎么看、合理估值。
---

# Researcher Valuation / 研究员拍估值（输出契约 + 质检门）

## 定位

让 agent 学"研究员拍估值"的推理过程，而不是报一个目标价。挂载方式与
stock-deep-dive 同构：本契约（当次必读）+ `scripts/valuation_lint.py`
（exit-code 门）。规则管结构，LLM 管表达。

主链底座：`intelligence/services/valuation_gap.py`（估值四问框架版）；
路由：ask CLI 的 `valuation_estimate` 问题类型（触发词见 frontmatter）。

只读 skill：不写 DuckDB、不写飞书、不改知识库。

## 标准流程（严格按序）

### 第 0 步 · 验鲜

查 canonical `db/market_feature_store.duckdb` 关键表 `max(trade_date)`；
财务/估值数据必须标注截止日期。未验鲜不得声称使用最新数据。

### 第 1 步 · 取数

标准命令（--compose 自动注入编排计划与数据块；缺公告级证据时加 --l3-lookup）：

```
python3 -m intelligence.cli.ask "拍估值 XX" --compose --l3-lookup --detail
```

估值问题类型会自动生成 **D5 估值数据块**（`intelligence/services/valuation_estimate.py`）：
目标 PE(TTM)/PB/总市值 + 同题材可比估值带与横截面分位。取数走东财免费快照接口
（不依赖 iFinD），可比集取本地 DuckDB 同板块成交额前排；`FINANCE_VALUATION_FETCH=0`
可关闭网络取数（块内会显式标注全缺口）。历史分位当前数据源不可得，按缺口处理。

### 第 2 步 · 五段输出契约（valuation_lint 维度）

1. **估值现状**：当前 PE/PS/EV-EBITDA 历史分位 + 同业横截面位置；
2. **可比公司估值带**：同链/同商业模式 3-5 家，给区间不给点位，说明可比集口径；
3. **隐含增长率反推**：当前市值隐含了什么增速/份额假设，市场已经 price in 了多少；
4. **情景估值表**：悲观/中性/乐观三情景，每个情景绑定可验证条件
   （公告/订单/产能口径），不许只给形容词；
5. **证据审计**：区分硬数据、研报推断（L1 降权）与缺口；
   研报盈利预测只能作 L1 参考，不能当硬输入。

结尾给升级/降级/证伪条件（条件化结论），不输出买卖指令。

### 第 3 步 · 质检门（必过）

```
python3 skills/researcher-valuation/scripts/valuation_lint.py <answer.md>
```

exit 0 才能交付。红线：出现"目标价 X 元"式单点结论直接 FAIL。
两轮不过 → 答案开头标注低置信再交付。

## 红线

- 禁止输出单点目标价，只能给条件化的估值区间；
- 情景必须绑定可验证条件；
- 未验鲜的财务/市值数据不得使用；缺数据只能做框架推演并显式声明；
- 缺可比公司数据时必须说明可比集缺口，不能用印象估值带补齐。
