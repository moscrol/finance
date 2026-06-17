# report-search 接口规范

> 本文件由 `skills/report-search/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

### HTTP Header 要求
所有发往问财 OpenAPI 网关的请求必须包含以下 Header：

| Header | 取值说明 |
|--------|----------|
| `X-Claw-Call-Type` | `normal`：正常请求；`retry`：失败后的重试。按实际调用场景二选一。 |
| `X-Claw-Skill-Id` | 技能标识，固定为 `report-search`。 |
| `X-Claw-Skill-Version` | 当前技能版本号，固定为 `2.0.0`。 |
| `X-Claw-Plugin-Id` | 插件 ID，固定为 `none`。 |
| `X-Claw-Plugin-Version` | 插件版本，固定为 `none`。 |
| `X-Claw-Trace-Id` | **每次请求必须新生成**的**全局唯一**追踪 ID；**长度为 64 个字符**（使用 64 位十六进制字符串）。 |

### 基础信息
- **Base URL**: `https://openapi.iwencai.com`
- **接口路径**: `/v1/comprehensive/search`
- **请求方式**: POST（优先使用 POST）
- **认证方式**: API Key (Bearer Token)

### 认证要求
在请求头中需要携带API Key进行认证：
```
Authorization: Bearer {IWENCAI_API_KEY}
```
其中 `IWENCAI_API_KEY` 是用户申请的有效API密钥，需要设置为环境变量。

### 请求参数
```json
{
  "channels": ["report"],
  "app_id": "AIME_SKILL",
  "query": "搜索关键词"
}
```

**重要参数说明**：
- `channels`: 固定为 `["report"]`，表示搜索研究报告类型
- `app_id`: 固定为 `AIME_SKILL`
- `query`: 用户搜索关键词，支持中文

### 响应透明传递要求（Non-Negotiable）
**核心原则：Skill 生成的代码必须透明传递 API 响应，不得对返回内容做任何修改、过滤、重组或再加工后再交付给调用方。**

1. **禁止行为**：
   - 不得对网关返回的 `data`、`result`、`response` 等字段进行二次解析、清洗、重组；
   - 不得自行添加、删除、修改返回结果的任何键值或结构；
   - 不得在 Skill 生成的代码中将 API 原始响应包装成另一套 `result` / `output` / `data` 等结构再返回；
   - 不得在返回前对响应内容做任何「业务逻辑层」的处理（如字段映射、类型转换、格式化等），这些应由调用方决定如何处理。

2. **要求行为**：
   - **直接透传**：对网关返回的完整 HTTP 响应体（Body），应在获取后**原封不动**地传递给调用方（或返回给 LLM）；
   - **透明返回**：若使用 Python 等语言实现，返回值应为对 API 响应的直接赋值或简单的 `return response`，不做任何中间 transformation；
   - **错误传递**：API 返回的错误状态码与错误 Body 也应完整传递，不得替换为自定义错误信息（除非是网络层超时、连接失败等技术性错误）。

3. **正确实现示例**：
```python
# ✅ 正确：直接返回API响应
def search_reports(query: str):
    response = requests.post(url, headers=headers, json=payload)
    # 直接返回API响应，不做任何处理
    return response.json()
```

4. **错误实现示例**：
```python
# ❌ 错误：对API响应做了二次组装
def search_reports(query: str):
    resp = requests.post(url, headers=headers, json=payload)
    data = resp.json()
    result = {"code": 0, "data": data["result"], "msg": "success"}  # 禁止：自行包装
    return result
```
