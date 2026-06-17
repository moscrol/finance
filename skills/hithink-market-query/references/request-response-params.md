# hithink-market-query 请求与响应参数

> 本文件由 `skills/hithink-market-query/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

## 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| query | STRING | 是 | 用户问句 |
| page | STRING | 否 | 分页参数，默认值：1 |
| limit | STRING | 否 | 分页参数，默认值：10 |
| is_cache | STRING | 否 | 缓存参数，默认值：1 |
| expand_index | STRING | 否 | 是否展开指数，默认值：true |

## 响应参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| datas | ARRAY | 金融数据列表，对象数组，每个对象包含股票代码、股票简称、最新价、涨跌幅等字段 |
| code_count | INT | 符合查询条件的总记录数量（注意：可能大于当前返回的 datas 条数） |
| chunks_info | OBJECT | 用户问句查询返回的字句信息，包含查询条件的解析结果 |

**响应示例：**
```json
{
  "datas": [
    {
      "股票代码": "300033.SZ",
      "股票简称": "同花顺",
      "最新价": "120.50",
      "涨跌幅": "2.35%"
    }
  ],
  "code_count": 5236,
  "chunks_info": {
    "query": "同花顺最新价格",
    "parsed_conditions": ["同花顺", "最新价格"]
  }
}
```

**重要提示：**
- `datas` 默认只返回 10 条数据（可通过 `limit` 参数调整）
- `code_count` 表示符合条件的总记录数，可能远大于 `datas` 的长度
- 当 `code_count > len(datas)` 时，需要通过 `page` 参数翻页获取更多数据
- 返回的表格数据需要解析 `datas` 数组中的对象字段
