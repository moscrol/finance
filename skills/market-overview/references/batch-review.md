# Market Overview 批量复盘多日

> 本文件由 `skills/market-overview/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

子 agent 通过 API 抓取（并行），主 agent 串行写入飞书。

### 子 agent prompt 模板

```
在 fupanhui.com 上用内部 API 获取 YYYY-MM-DD 的市场数据：
1. fetch /api/v1/client/reviews/market?trade_date=YYYY-MM-DD
2. fetch /api/v1/client/reviews/summary?trade_date=YYYY-MM-DD
3. fetch /api/v1/client/reviews/sector?trade_date=YYYY-MM-DD
4. navigate to market data page, hover K-line for 周均线/偏离度

返回以下字段（结构化文本）：
- 日期、阶段、天数、冰点（如有）
- AI 摘要（2-3句精简）
- 成交额(亿)、较昨日比(%)、20日均(亿)、相对量能比(%)、量能状态
- 涨停、跌停、涨
- 周均线、偏离度
- 前三占比(%)、集中度、行业1/占比1/行业2/占比2/行业3/占比3
- 行业特征：容量/锐度/宽度/资金 各字段（行业名、成交额、占比）
- 板块涨幅：当日/3日/5日/10日前五（收集所有出现板块的唯一集合）

只返回数据，不要写入任何表格。
```

### 覆盖检查

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/market-overview/scripts/check_coverage.py [月份]
```
