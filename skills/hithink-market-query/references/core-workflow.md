# hithink-market-query 核心处理流程

> 本文件由 `skills/hithink-market-query/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

### 步骤 1: 接收用户 Query

接收用户的自然语言查询请求，分析用户意图，识别行情数据相关查询类型：
- 股票价格/涨跌幅查询
- 成交量/资金流向查询
- 技术指标/ETF行情查询

### 步骤 2: Query 改写

将用户问句适当改写为标准的金融查询问句，保持原意不变：

**改写规则：**
- 保留用户核心意图（如：股票价格、涨跌幅、成交量等）
- 将口语化表达转为标准金融术语
- 适当简化过于复杂的复合条件
- 改写后需保持原意不变

**常用查询改写示例：**
| 用户原始问句 | 改写后查询 |
|-------------|-----------|
| 同花顺今天多少钱 | 同花顺最新价格 |
| 主力资金流向怎么样 | 主力资金流向 |
| 上证指数行情如何 | 上证指数行情 |
| MACD金叉的股票 | MACD金叉 |

### 步骤 3: API 调用

调用问财 OpenAPI 网关获取数据，使用 `scripts/cli.py` CLI 或直接在 skill 逻辑中构造 HTTP 请求。所有发往网关的请求必须严格携带以下 Header：

| Header | 取值说明 |
|--------|----------|
| `Authorization` | `Bearer <API Key>`，API Key 仅从环境变量 `IWENCAI_API_KEY` 读取 |
| `Content-Type` | `application/json` |
| `X-Claw-Call-Type` | `normal`（正常请求）或 `retry`（失败后的重试） |
| `X-Claw-Skill-Id` | `hithink-market-query`（与 skill name 一致） |
| `X-Claw-Skill-Version` | `1.0.0`（与本文档版本一致） |
| `X-Claw-Plugin-Id` | `none` |
| `X-Claw-Plugin-Version` | `none` |
| `X-Claw-Trace-Id` | 每次请求必须新生成的 **64 字符**全局唯一追踪 ID（推荐 `secrets.token_hex(32)`） |

**请求体示例：**
```json
{
  "query": "改写后的查询语句",
  "page": "1",
  "limit": "10",
  "is_cache": "1",
  "expand_index": "true"
}
```

**Python 调用示例（含 Claw Headers）：**
```python
import os
import json
import secrets
import urllib.request

url = "https://openapi.iwencai.com/v1/query2data"
api_key = os.environ["IWENCAI_API_KEY"]
trace_id = secrets.token_hex(32)  # 64 字符唯一 ID

payload = {
    "query": "同花顺最新价格",
    "page": "1",
    "limit": "10",
    "is_cache": "1",
    "expand_index": "true"
}

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "X-Claw-Call-Type": "normal",
    "X-Claw-Skill-Id": "hithink-market-query",
    "X-Claw-Skill-Version": "1.0.0",
    "X-Claw-Plugin-Id": "none",
    "X-Claw-Plugin-Version": "none",
    "X-Claw-Trace-Id": trace_id,
}

data = json.dumps(payload).encode("utf-8")
request = urllib.request.Request(url, data=data, headers=headers, method="POST")
response = urllib.request.urlopen(request, timeout=30)
result = json.loads(response.read().decode("utf-8"))

# 解析返回数据
datas = result.get("datas", [])           # 当前页数据列表
code_count = result.get("code_count", 0)  # 符合条件的总记录数
chunks_info = result.get("chunks_info", {})  # 查询字句信息

# 分页提示：如果 code_count > len(datas)，通过增加 page 参数翻页
```

**注意：** 默认返回 10 条数据，但符合条件的总数可能更多，需关注 `code_count` 字段并通过分页获取全部数据。

### 步骤 4: 空数据处理

如果 `datas` 为空或无数据，适当放宽或简化查询条件后重新请求（**最多尝试 2 次**）：

- **首次重试**：去掉过于苛刻的条件，保留核心查询条件
- **二次重试**：进一步放宽条件或使用更通用的表述

每次重试都算作一次改写，最终返回时需说明最终使用的查询问句。

### 步骤 5: 数据解析

解析返回的 `datas` 数组，提取相关指标：

```python
for item in datas:
    code = item.get("股票代码")       # 如 "300033.SZ"
    name = item.get("股票简称")       # 如 "同花顺"
    # 其他字段根据查询类型而定，如最新价、涨跌幅、成交量等
```

### 步骤 6: 数据扩展决策

skill 需要自行决策当前数据是否足够回答用户问题：
- 如果数据完整：直接返回格式化后的结果且保证表格数据正确解析为表格展示
- 如果需要更多背景信息：可以调用其他金融工具或者搜索工具获取相关资讯

### 步骤 7: 回答用户

组织语言回答用户问题，确保：
- 结果清晰易懂
- 如果改写了问句，需特别说明最终使用的查询问句
- **必须强调数据来源于同花顺问财**
