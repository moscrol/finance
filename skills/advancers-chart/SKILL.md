---
name: advancers-chart
metadata:
  pattern: generator
  also: [tool-wrapper]
description: 涨家数走势数据同步与图表生成。触发词：涨家数折线图、涨家数走势、涨跌趋势图、涨家数图表、看一下涨家数、同步涨家数、更新涨家数走势、sync涨家数、看看涨跌家数、涨跌比走势。
---

# 涨家数走势图

## 触发条件

用户要求查看涨家数走势、涨跌趋势图、同步涨家数数据时触发。market-overview 复盘完成后自动触发同步。

从飞书 Bitable 每日指标表中提取涨家数，同步到独立的「涨家数走势」表格（供飞书原生图表视图使用），同时可本地生成折线图 + 5日均线。

## 两种模式

| 场景 | 脚本 | 说明 |
|------|------|------|
| 仅同步飞书数据 | `sync.py` | 增量同步涨家数 + MA5 到走势表，不生图。适合复盘后自动触发 |
| 同步 + 生成图表 | `feishu_chart.py` | 同步飞书数据 + 本地生成 PNG 折线图。适合用户主动查看 |

## 步骤

### Step 1: 选择并运行脚本

**模式 A — 仅同步（复盘后自动触发）：**
```bash
python3 /Users/lbq/Desktop/c c/金融/skills/advancers-chart/scripts/sync.py
```

**模式 B — 同步 + 生成图表（用户主动查看）：**
```bash
python3 /Users/lbq/Desktop/c c/金融/skills/advancers-chart/scripts/feishu_chart.py "/Users/lbq/Desktop/c c/金融/涨家数走势.png"
```

脚本自动完成：
1. 获取飞书 API token
2. 从「每日指标」表读取涨家数数据
3. 增量同步到「涨家数走势」表格（新增日期自动追加，MA5 自动更新）
4. （模式 B）本地生成 PNG 折线图

### Step 2: 显示图表（仅模式 B）

用 Read 工具读取生成的 PNG 文件，展示给用户。

### Step 3: 简要解读

附上一句话趋势总结。

## 飞书图表视图

「涨家数走势」表格已有日期、涨家数、MA5 三列数据。在飞书中创建折线图视图：
1. 打开表格 → 点击左上角「+ 视图」→ 选择「图表」
2. 图表类型选「折线图」
3. X 轴选「日期」，Y 轴选「涨家数」和「MA5」
4. 保存即可

创建一次后，后续每次运行 skill 同步新数据，图表自动更新。

## 注意

- 日期字段为文本 YY-MM-DD 格式
- 增量同步：只新增不存在的日期记录，并更新最近 5 条的 MA5
- 凭证从 `~/.claude/shared/feishu_config.json` 读取
