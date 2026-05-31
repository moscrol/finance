---
name: ifind
description: iFinD（同花顺）MCP API 共享工具库。此 skill 不可独立触发，仅供其他 skill 调用。
---

# iFinD API 共享工具库

此目录是 iFinD（同花顺）MCP API 的客户端封装，不是独立可触发的 skill。其他 skill 通过脚本调用此处的模块来获取行情、行业分类、概念板块等数据。

## 文件说明

| 文件 | 用途 |
|------|------|
| `call-node.js` | Node.js MCP 客户端，支持 `call(serverType, toolName, params)` 和 `listTools(serverType)` |
| `call.py` | Python MCP 客户端，API 与 Node.js 版一致 |
| `mcp_config.json` | auth_token 配置 |

## 使用方式

其他 skill 的 SKILL.md 中通过 Bash 调用：

```bash
cd /Users/lbq/Desktop/c c/金融/skills/ifind && node -e "
const { call } = require('./call-node.js');
async function run() {
  const result = await call('stock', 'tool_name', { query: '查询内容' });
  const text = JSON.parse(result.data.result.content[0].text);
  console.log(text.data.result);
}
run().catch(e => console.error(e.message));
"
```

## 可用服务端点

| serverType | 服务 |
|-----------|------|
| `stock` | 股票行情、个股查询 |
| `fund` | 基金数据 |
| `edb` | 宏观经济数据库 |
| `news` | 新闻资讯 |
