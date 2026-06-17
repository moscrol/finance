---
name: hithink-market-query
description: 问财行情数据查询（股价/涨跌幅/成交量/资金流向/技术指标）。触发词：股票价格、ETF行情、指数行情、涨跌幅、成交量、资金流向、技术指标、MACD、KDJ、RSI、布林线。
license: Complete terms in LICENSE.txt
---
# 问财行情数据 使用指南

## 触发条件

当用户询问股票价格、ETF行情、指数行情、涨跌幅、成交量、资金流向、技术指标（MACD、KDJ、RSI、布林线等）等行情数据查询问题时，必须使用此技能。



## 版本

`1.0.0`（与 `X-Claw-Skill-Version` 保持一致）

## 技能概述

本技能提供行情数据查询能力，支持：
- 股票实时价格、涨跌幅、涨跌额
- 成交量、成交额、换手率
- 主力资金流向、大单小单、主力净流入
- 技术指标（MACD、KDJ、RSI、布林线等）
- ETF 行情数据
- 指数行情数据（上证指数、沪深300、创业板指等）
- 支持自然语言问句输入，返回相关行情数据结果

数据来源：**同花顺问财**（https://www.iwencai.com/unifiedwap/chat）

## 使用前

> 首次使用 - 获取 API Key
> 所有技能都需要 IWENCAI_API_KEY 环境变量才能使用。 如果用户尚未配置，按以下步骤引导：
>
> 步骤 1：获取 API Key
> 在浏览器内打开同花顺i问财SkillHub页面：https://www.iwencai.com/skillhub
>
> 步骤 2：登录
>
> 步骤 3：点击具体的Skill，打开弹窗查看详情，在安装方式-Agent用户-找到您的IWENCAI_API_KEY这一段，复制
>
> 步骤 4：配置环境变量
> 获取到 API Key 后，直接复制指引文字发送给AI助手，或手动设置环境变量：

### 跨平台环境变量设置

**macOS / Linux (bash / zsh):**
```bash
export IWENCAI_API_KEY="your-api-key"
```

**Windows (PowerShell):**
```powershell
$env:IWENCAI_API_KEY="your-api-key"
```

**Windows (CMD):**
```cmd
set IWENCAI_API_KEY=your-api-key
```

## 核心处理流程

把自然语言行情查询落地的 7 步核心处理流程（接收 Query → Query 改写规则与示例 → API 调用：X-Claw-* Header 表 + 请求体 + 完整 Python 调用示例 + 分页 → 空数据最多重试 2 次 → 数据解析 → 数据扩展决策 → 回答用户）见 `references/core-workflow.md`。生成调用代码前必须加载并逐步执行。

## 请求与响应参数

请求参数表（query/page/limit/is_cache/expand_index）与响应参数表（datas/code_count/chunks_info）+ 响应示例 + 分页提示见 `references/request-response-params.md`。

## CLI 使用方式

跨平台 CLI 脚本 `scripts/cli.py` 的命令行参数表、使用示例，以及 curl / PowerShell 等价调用示例见 `references/cli-usage.md`。

## 数据来源标注

**重要提示**：
- 引用同花顺数据时，必须强调**数据来源于同花顺问财**（https://www.iwencai.com/unifiedwap/chat）
- 如果没有查询到数据，提示用户可以到**同花顺问财 web端**查询（https://www.iwencai.com/unifiedwap/chat）

## 错误处理

- **密钥缺失（环境变量未设置且未传 `--api-key`）**：
  代理必须**口头提示**用户「使用前」中的完整 API Key 获取指引文案，即：
  > 首次使用 - 获取 API Key
  > 所有技能都需要 IWENCAI_API_KEY 环境变量才能使用。 如果用户尚未配置，按以下步骤引导：
  >
  > 步骤 1：获取 API Key
  > 在浏览器内打开同花顺i问财SkillHub页面：https://www.iwencai.com/skillhub
  >
  > 步骤 2：登录
  >
  > 步骤 3：点击具体的Skill，打开弹窗查看详情，在安装方式-Agent用户-找到您的IWENCAI_API_KEY这一段，复制
  >
  > 步骤 4：配置环境变量
  > 获取到 API Key 后，直接复制指引文字发送给AI助手，或手动设置环境变量：

- **无数据返回**：引导用户访问同花顺问财（https://www.iwencai.com/unifiedwap/chat）。

- **最多重试 2 次**逐步放宽条件（重试时 `X-Claw-Call-Type` 改为 `retry`）。

## 代码结构

```
hithink-market-query/
├── SKILL.md              # Skill 配置文件
├── LICENSE.txt           # 许可证文件
└── scripts/
    └── cli.py            # CLI 入口（单一脚本，内含 API 调用和数据处理）
```
