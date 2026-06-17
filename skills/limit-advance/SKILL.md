---
name: limit-advance
description: 连板晋级数据抓取与飞书入库。触发词：晋级。
---

# 连板晋级筛选

## 触发条件

用户说"晋级"或要求查看连板晋级数据时触发。

## Step 1: 抓取并展示

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/limit-advance/scripts/scrape.py [日期] [--min-boards=N]
```

- 日期可选，格式 MM-DD（如 05-07），默认最新交易日
- `--min-boards=3`（默认）筛选3板以上

脚本通过 fupanhui 内部 API 获取连板梯队数据（`/api/v1/client/limit/ladder`），无需页面 DOM 解析。输出对齐表格 + 时间轴甘特图。

直接将脚本输出展示给用户。

## Step 2: 写入飞书

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/limit-advance/scripts/scrape.py --json [日期] | python3 /Users/lbq/Desktop/c c/金融/skills/limit-advance/scripts/write.py
```

飞书表格「连板晋级」：
- 序号（数字）：按首板日期正序排列，首板越早序号越小
- 股票简称：行标识
- 日期列（如 01-05、01-06...）：从首板到当日填入股票名称
- 查重：按股票名称去重，已存在则合并日期列
- 每次写入后自动按首板日期重排序号

## 批量抓取与覆盖检查

批量抓取某月的协同方式（子 agent 并行抓取 + 主 agent 从旧到新串行写飞书 / 纯串行备选 / check_coverage 流程）与覆盖检查漏抓处理（节假日确认 → scrape 验证 → 补抓）见 `references/batch-scraping.md`。批量回补时按该文件执行，务必串行写入。

## 注意事项

- 禁止并行写入飞书——会触发字段 ID 冲突和数据丢失
- 禁止跳日期——必须逐日串行
- min_boards 默认 3，只写 3 板及以上晋级股
- write.py 写入后自动回读验证：检查股票简称和日期列是否为空，有空字段会输出 ⚠ 警告
