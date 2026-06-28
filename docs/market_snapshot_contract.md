# Market Snapshot Contract

用途：另一台有 DuckDB 的 Mac 每日导出盘面快照，本 Mac 只读 JSON，不直接依赖本地 DuckDB。

默认目录：

- 环境变量：`MARKET_SNAPSHOT_DIR`
- 默认值：`<finance repo>/market_snapshot`

目录结构：

```text
market_snapshot/
  2026-06-11.json
  latest.json
  meta.json
```

`YYYY-MM-DD.json` 最小字段：

```json
{
  "schema_version": "1.0",
  "trade_date": "2026-06-11",
  "generated_at": "2026-06-11T18:00:00+08:00",
  "market": {
    "stage": "主升",
    "total_amount": 12345.6,
    "amount_ratio": 12.3,
    "advancers": 3200,
    "decliners": 1800,
    "limit_up": 68,
    "limit_down": 5,
    "capacity_top3": [{"name": "电子", "ratio": 29.0}]
  },
  "themes": [
    {
      "concept": "光刻胶",
      "priority_score": 184.57,
      "trigger_types": ["double_red", "limit_heat"],
      "limit_up_count": 5,
      "new_high_count": 14,
      "strong_stock_count": 8
    }
  ],
  "strong_stocks": [
    {
      "stock_name": "华特气体",
      "stock_ts_code": "688268.SH",
      "concepts": ["光刻胶"],
      "pct_chg": 20.0,
      "amount": 36.4
    }
  ]
}
```

`meta.json` 最小字段：

```json
{
  "schema_version": "1.0",
  "latest_trade_date": "2026-06-11",
  "updated_at": "2026-06-11T18:01:00+08:00"
}
```

检查命令：

```bash
python3 scripts/check_market_snapshot_contract.py --root market_snapshot --date 2026-06-11 --pretty
```

返回 `PASS` 表示文件和关键字段齐；`WARN` 表示可读但有字段缺失或日期不一致；`FAIL` 表示缺每日文件、日期缺失或核心结构不可用。
