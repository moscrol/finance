# report-search 使用说明

> 本文件由 `skills/report-search/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

### 环境变量配置

#### Unix/Linux/macOS (bash/zsh)
```bash
export IWENCAI_API_KEY="your_api_key_here"
```

#### Windows PowerShell
```powershell
$env:IWENCAI_API_KEY="your_api_key_here"
```

#### Windows CMD
```cmd
set IWENCAI_API_KEY=your_api_key_here
```

### 命令行使用
```bash
# 基本搜索
python research_report_search.py -q "人工智能行业研究报告"

# 限制结果数量
python research_report_search.py -q "芯片行业" -l 5

# 导出为CSV格式
python research_report_search.py -q "新能源汽车" -o results.csv -f csv

# 批量处理
python research_report_search.py -i queries.txt -o ./results -f json

# 时间范围搜索
python research_report_search.py -q "医药行业" --date-from "2024-01-01" --date-to "2024-03-31"

# 获取帮助
python research_report_search.py -h
```

### curl 示例
```bash
# 生成64位十六进制Trace ID
TRACE_ID=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# 使用环境变量中的 API Key
curl -X POST "https://openapi.iwencai.com/v1/comprehensive/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $IWENCAI_API_KEY" \
  -H "X-Claw-Call-Type: normal" \
  -H "X-Claw-Skill-Id: report-search" \
  -H "X-Claw-Skill-Version: 2.0.0" \
  -H "X-Claw-Plugin-Id: none" \
  -H "X-Claw-Plugin-Version: none" \
  -H "X-Claw-Trace-Id: $TRACE_ID" \
  -d '{
    "channels": ["report"],
    "app_id": "AIME_SKILL",
    "query": "人工智能行业研究报告"
  }'
```

**Windows PowerShell 示例：**
```powershell
# 生成64位十六进制Trace ID
$TRACE_ID = python -c "import secrets; print(secrets.token_hex(32))"

# 调用研报搜索接口
$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer $env:IWENCAI_API_KEY"
    "X-Claw-Call-Type" = "normal"
    "X-Claw-Skill-Id" = "report-search"
    "X-Claw-Skill-Version" = "2.0.0"
    "X-Claw-Plugin-Id" = "none"
    "X-Claw-Plugin-Version" = "none"
    "X-Claw-Trace-Id" = $TRACE_ID
}

$body = @{
    channels = @("report")
    app_id = "AIME_SKILL"
    query = "人工智能行业研究报告"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://openapi.iwencai.com/v1/comprehensive/search" -Method Post -Headers $headers -Body $body
```
