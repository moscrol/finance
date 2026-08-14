# Market Overview 数据源

> 本文件由 `skills/market-overview/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

通过 CDP proxy 在已登录的浏览器标签页内调用 XHR，自动携带 session cookie。

```python
def fetch_api(target, api_path):
    js = ("(function(){var x=new XMLHttpRequest();"
          "x.open('GET','" + api_path + "',false);"
          "x.send();return x.responseText;})()")
    r = cdp_eval(target, js)
    return json.loads(r.get("value", "{}"))
```

### API 端点

| 用途 | 端点 |
|------|------|
| 最新交易日 | `/api/v1/client/reviews/latest-date?mode=auto`（字段 `latest_date`） |
| 市场数据 | `/api/v1/client/reviews/market?trade_date=YYYY-MM-DD&days=120&mode=auto` |
| AI 摘要 | `/api/v1/client/reviews/summary?trade_date=YYYY-MM-DD` |
| 市场周期 | `/api/v1/client/reviews/cycle?trade_date=YYYY-MM-DD` |
| 板块数据 | `/api/v1/client/reviews/sector?trade_date=YYYY-MM-DD` |
| 日历 | `/api/v1/client/calendar/month?year=YYYY&month=M` |
| 主线题材 ⭐ | `/api/v1/client/topics/mainline-themes?trade_date=YYYY-MM-DD`（公开，无需 CDP） |
| 主线个股 ⭐ | `/api/v1/client/topics/mainline-stocks?trade_date=YYYY-MM-DD&theme_code=XX`（公开） |
| 题材资金面板 ⭐ | `/api/v1/client/data/theme/panels?trade_date=YYYY-MM-DD`（公开） |
| 历史相似日 | `/api/v1/client/reviews/historical-mapping?trade_date=YYYY-MM-DD`（公开） |

### market API 关键字段

```
data.volume        → 成交额、量能比
data.sentiment     → 涨跌停、涨跌家数
data.industry_spread
  .top3_total_pct  → 前三占比
  .top3_industries → [{rank, name, ratio}]
data.sector_strength → 板块强度列表
data.strength      → 市场强度
data.new_high      → 新高统计
```
