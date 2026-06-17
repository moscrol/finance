---
name: limit-advance
metadata:
  pattern: pipeline
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

## 批量抓取某月

**核心约束**：写入必须从旧到新串行，确保字段追加顺序正确。

### 方式一：子 agent 并行抓取 + 主 agent 串行写入（推荐）

```
子 agent（并行）           →    主 agent（串行）
  scrape.py --json DATE        接收所有 JSON，按日期排序
  只返回数据，禁止写表          从旧到新逐日 pipe 到 write.py
```

- 子 agent 每批 3-5 个，完成后启动下一批
- 主 agent 收到所有结果后按日期正序写入

### 方式二：纯串行（备选）

```bash
for d in 01-05 01-06 01-07 ...; do
  python3 scripts/scrape.py --json $d | python3 scripts/write.py
done
```

### 流程

```bash
# 1. 检查覆盖
python3 /Users/lbq/Desktop/c c/金融/skills/limit-advance/scripts/check_coverage.py [月份]

# 2. 抓取写入（方式一或方式二）

# 3. 全部完成后再次检查覆盖
python3 /Users/lbq/Desktop/c c/金融/skills/limit-advance/scripts/check_coverage.py [月份]
```

## 覆盖检查与漏抓处理

覆盖检查发现缺失日期时：

1. 先确认该日期是否为节假日（元旦 01-01~01-02、春节 02-16~02-20、清明 04-06、五一 05-01~05-05 等）
2. 非节假日缺失，先用 scrape 检查该日期是否有 3 板+ 晋级数据：
   ```bash
   python3 scripts/scrape.py --json MM-DD
   ```
3. 无 3 板+ 输出 → 该日期确实无数据，不算漏抓
4. 有数据 → 补抓写入

## 注意事项

- 禁止并行写入飞书——会触发字段 ID 冲突和数据丢失
- 禁止跳日期——必须逐日串行
- min_boards 默认 3，只写 3 板及以上晋级股
- write.py 写入后自动回读验证：检查股票简称和日期列是否为空，有空字段会输出 ⚠ 警告
