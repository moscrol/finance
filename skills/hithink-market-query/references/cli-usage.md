# hithink-market-query CLI 使用方式

> 本文件由 `skills/hithink-market-query/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

本 skill 提供跨平台 CLI 脚本 `scripts/cli.py`，基于 Python 3 标准库实现，无第三方依赖。

### 命令行参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--query` | STRING | 是 | 直接传入查询字符串 |
| `--page` | STRING | 否 | 分页参数，值必须为正整数，默认值：1 |
| `--limit` | STRING | 否 | 每页条数，值必须为正整数，默认值：10 |
| `--api-key` | STRING | 否 | API 密钥（默认从环境变量读取）|
| `--call-type` | STRING | 否 | 调用类型：`normal`（正常请求）或 `retry`（重试请求），默认值：normal |
| `--timeout` | INT | 否 | 请求超时时间（秒），默认值：30 |

### 使用示例

```bash
# 查询股票最新价格
python3 scripts/cli.py --query "同花顺最新价格"

# 查询主力资金流向
python3 scripts/cli.py --query "主力资金流向"

# 查询上证指数行情
python3 scripts/cli.py --query "上证指数行情"

# 翻页查询
python3 scripts/cli.py --query "股票行情" --page 2 --limit 20

# 重试请求（放宽条件后使用 retry 标记）
python3 scripts/cli.py --query "同花顺最新价格" --call-type "retry"

# 指定超时时间（复杂查询可适当增加）
python3 scripts/cli.py --query "同花顺最新价格" --timeout 60
```

### curl 示例（脱敏）

```bash
curl -X POST "https://openapi.iwencai.com/v1/query2data" \
  -H "Authorization: Bearer $IWENCAI_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Claw-Call-Type: normal" \
  -H "X-Claw-Skill-Id: hithink-market-query" \
  -H "X-Claw-Skill-Version: 1.0.0" \
  -H "X-Claw-Plugin-Id: none" \
  -H "X-Claw-Plugin-Version: none" \
  -H "X-Claw-Trace-Id: $(openssl rand -hex 32)" \
  -d '{
    "query": "同花顺最新价格",
    "page": "1",
    "limit": "10",
    "is_cache": "1",
    "expand_index": "true"
  }'
```

**Windows (PowerShell) 等价示例：**
```powershell
$bytes = New-Object byte[] 32; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes); $traceId = -join ($bytes | ForEach-Object { $_.ToString("x2") })
Invoke-RestMethod -Uri "https://openapi.iwencai.com/v1/query2data" -Method POST -Headers @{
  "Authorization" = "Bearer $env:IWENCAI_API_KEY"
  "Content-Type" = "application/json"
  "X-Claw-Call-Type" = "normal"
  "X-Claw-Skill-Id" = "hithink-market-query"
  "X-Claw-Skill-Version" = "1.0.0"
  "X-Claw-Plugin-Id" = "none"
  "X-Claw-Plugin-Version" = "none"
  "X-Claw-Trace-Id" = $traceId
} -Body '{"query":"同花顺最新价格","page":"1","limit":"10","is_cache":"1","expand_index":"true"}'
```
