# top-gainers-feishu 入库模式 7 步流程

> 本文件由 `skills/top-gainers-feishu/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

### Step 1: 解析日期

用户输入提取日期区间，转 YYYYMMDD。如 "4.3-4.27" → 20260403 ~ 20260427。

### Step 2: 并行查询

同时发起 iFinD 个股涨幅 + AKShare 板块涨幅：

```bash
cd /Users/lbq/Desktop/c c/金融/skills/ifind && node -e "
const { call } = require('./call-node.js');
async function run() {
  const result = await call('stock', 'search_stocks', { query: 'YYYY年MM月DD日到YYYY年MM月DD日涨幅前20的股票' });
  const text = JSON.parse(result.data.result.content[0].text);
  console.log(text.data.result);
}
run().catch(e => console.error(e.message));
"
```

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/top-gainers/scripts/query_sectors.py YYYYMMDD YYYYMMDD
```

### Step 3: 过滤涨幅 > 50% 的个股

### Step 4: 批量查询行业 + 概念板块

分批（每批5只）并行查询申万一级行业和概念板块。行业查询空表时换自然语言重试，概念查询对北交所空时用代码重试。

### Step 5: 整理数据

- **核心题材**：从概念列表选 2-3 个，斜杠分隔，筛除融资融券/深股通/专精特新等噪声
- **行业涨幅上榜**：个股申万行业 ∈ AKShare LEVEL1 前10 → true

### Step 6: 写入飞书

```bash
echo '[JSON数组]' | python3 /Users/lbq/Desktop/c c/金融/skills/top-gainers-feishu/scripts/write.py
```

JSON 每条：`{"date":"YY-MM-DD~YY-MM-DD","code":"688628.SH","name":"优利德","industry":"机械设备","themes":"DeepSeek/AI智能体/芯片","gain":"129.68%","industry_hot":true}`

脚本按日期+股票代码查重，已存在则跳过。写入后自动回读验证，检查所有关键字段（日期、股票代码、股票简称、申万行业、核心题材、区间涨幅）是否完整，有空字段会输出 ⚠ 警告。

### Step 7: 输出入库摘要

对齐表格展示：排名、股票简称、申万行业、核心题材、涨幅(%)、行业上榜(✔/—)。
