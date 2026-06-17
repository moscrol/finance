# 区间涨幅排行榜 执行流程

> 本文件由 `skills/top-gainers/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

### Step 1: 解析日期

从用户输入提取日期区间，转为 YYYYMMDD 格式。支持：
- "4月1日到4月30日" / "4月涨幅" / "4.8-4.17"
- "2026-04-01至2026-04-30"
- "本周/本月" → 自动计算
- 只给月份时取该月首尾交易日

### Step 2 & 3: 并行发起所有查询

**同时发起**以下查询（iFinD 个股涨幅 + AKShare 板块涨幅并行）：

**查询 A：iFinD 个股涨幅前20**

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

从返回的 markdown 表格提取：股票代码、股票简称、区间涨跌幅。

**查询 B：AKShare 板块涨幅**

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/top-gainers/scripts/query_sectors.py YYYYMMDD YYYYMMDD
```

输出 JSON：`{"level1": [[名称, 涨幅%], ...], "level2": [...], "concept": [...]}`

### Step 4: 批量查询行业 + 题材

拿到 Step 2 的 20 只股票后，分 4 批（每批 5 只），**并行**发起 8 个 Bash 调用：

**查询申万一级行业（4批）：**
```bash
cd /Users/lbq/Desktop/c c/金融/skills/ifind && node -e "
const { call } = require('./call-node.js');
async function run() {
  const r = await call('stock', 'get_stock_info', { query: '股票A、股票B、股票C、股票D、股票E的申万一级行业' });
  const text = JSON.parse(r.data.result.content[0].text);
  console.log(text.data.answer);
}
run().catch(e => console.error(e.message));
"
```

**查询所属概念板块（4批）：**
```bash
cd /Users/lbq/Desktop/c c/金融/skills/ifind && node -e "
const { call } = require('./call-node.js');
async function run() {
  const r = await call('stock', 'get_stock_info', { query: '股票A、股票B、股票C、股票D、股票E的所属概念板块' });
  const text = JSON.parse(r.data.result.content[0].text);
  console.log(text.data.answer);
}
run().catch(e => console.error(e.message));
"
```

**注意事项：**
- 返回结果可能包含非目标股票（如"申万宏源"），按证券代码匹配过滤
- 概念板块返回量很大（每只股票几十个），需筛选核心题材（见 Step 5）
- **行业查询可能返回空表**（只有股票代码和名称，没有行业列），此时换用自然语言重试：`'圣阳股份、宝丽迪分别属于什么行业'`
- **概念查询对北交所股票可能返回空**，用股票代码重试：`'利尔达(920249)、蘅东光(920045)的所属概念板块'`

### Step 5: 筛选核心题材

从每只股票的完整概念列表中筛选 **2-3 个最核心、最有辨识度的题材**。

**筛除通用噪声：**
- 交易类：融资融券、深股通、沪股通、转融券标的、富时罗素
- 上市类：新股与次新股、科创次新股、注册制次新股
- 通用标签：专精特新、高股息精选、地方国企改革（除非是核心题材）

**筛选原则：**
1. 优先保留市场热点题材（AI智能体、DeepSeek、低空经济）
2. 保留能解释涨幅逻辑的核心题材
3. 用斜杠 `/` 分隔，每只股票不超过 3 个

### Step 6: 输出个股表格

用 ASCII box 风格输出对齐的纯文本表格：

```
═══════════════════════════════════════════════════════════════════════════════
  区间涨幅排行榜  [开始日期] ~ [结束日期]
═══════════════════════════════════════════════════════════════════════════════

排名  股票代码       股票简称    申万行业   核心题材                       涨幅(%)
──────────────────────────────────────────────────────────────────────────────
 1    002580.SZ    圣阳股份   电力设备   储能/数据中心/液冷服务器          90.06
 2    300905.SZ    宝丽迪    基础化工   光刻胶/3D打印                   83.37
...

行业分布：电子(6) > 计算机(3) > ...

热门题材：
- AI/DeepSeek/算力 (9只)：宏景科技、品高股份...
- 半导体/先进封装 (7只)：锴威特、唯特偶...
```

**对齐规则：** 排名右对齐2字符，股票代码11字符，中文占2显示宽度，涨幅保留2位小数。

末尾附行业分布（按数量降序）和热门题材主线（归纳出现频率最高的题材，按涉及股票数降序）。

### Step 7: 输出板块涨幅表格

用 **markdown 表格** 三列并排展示（不用纯文本，不对齐）：

```markdown
| # | 申万一级行业 | 涨幅% | 申万二级行业 | 涨幅% | 概念板块 | 涨幅% |
|--:|:---------:|------:|:---------:|------:|:-------:|------:|
| 1 | 电子 | 7.10 | 电子化学品Ⅱ | 8.42 | MLCC | 10.60 |
| 2 | 通信 | 5.97 | 其他电子Ⅱ | 7.87 | 复合集流体 | 10.42 |
...
```

每列独立排名，各取前10。
