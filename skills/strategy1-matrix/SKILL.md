---
name: strategy1-matrix
metadata:
  pattern: generator
  also: [pipeline]
description: 生成或更新策略一每日优先个股矩阵。触发词：策略一生成、生成策略1、策略一矩阵、策略1每日优先个股、strategy1 matrix、更新策略一。用于基于已完成的每日复盘数据，把某个交易日写入 `复盘/matrices/strategy1-priority-stock-matrix.html`，并沉淀 T1/T2/OBS/次日验证；尤其适用于避免长 SQL、长 shell 字符串、手工编辑巨大 HTML 单行导致出错。
---

# 策略一矩阵生成

## 核心原则

策略一生成不是纯脚本任务。先由 agent 做事实抽取和分层判断，再用小脚本做 HTML 安全写入。

禁止直接上来跑长 SQL 或把整行 HTML 塞进 shell 命令。此前失败根因是：

1. 重 SQL 在 DuckDB 上容易被取消或长时间无反馈。
2. 超长 shell heredoc / 单行 HTML 容易被终端截断、转义污染或语法打断。
3. 直接改巨大单行 HTML 风险高，失败后难定位。

## 输入前提

默认要求目标日期已完成每日复盘：

- `market_feature_store/exports/{DATE}-daily-review.md`
- `复盘/daily/{DATE}/{DATE}-daily-review.html`
- 核心表通过 `scripts/check_daily_review_data.py DATE`

若日报未生成，先不要生成策略一，先补全每日复盘。

## Git 安全

开工先执行并汇报：

```bash
git status --short
git branch --show-current
```

不要使用 `git add .`。策略一任务通常只应触碰：

- `复盘/matrices/strategy1-priority-stock-matrix.html`
- 必要时本 skill 目录下文件

## 生成流程

### Step 1：确认日期和数据门控

若用户没有指定日期，默认使用最近已完成复盘日。

```bash
python3 scripts/check_daily_review_data.py YYYY-MM-DD
```

只有 `RESULT: COMPLETE` 才继续。若只缺日报产物，先跑 daily workflow 的生成步骤。

### Step 2：从日报事实层抽取，不直接扫全库

优先读取 `market_feature_store/exports/{DATE}-daily-review.md` 的这些章节：

- `## 1. 指数 / 量能 / 偏离度 / 市场阶段`
- `## 3. 成交前三行业`
- `## 5. 双红题材：按申万一级分组`
- `## 7. 申万一级行业个股发动机：成交占比前三行业`
- `## 10. 涨停题材`
- `## 11. 3板及以上个股`

只做短段抽取。不要全文刷屏；不要读 `exports/` 用 IDE read/grep，如果受 gitignore 限制，用短 Python 读取并打印目标章节。

### Step 3：按策略一口径分层

策略一标准口径：

```text
成交占比前三申万一级
+ 双红题材（pct_chg > 0 AND diff_ratio > 10 AND amount > 500）
+ 行业内开根加权 Top20
+ 新高状态 或 双红题材命中数 >= 3 或 涨停/连板强确认
```

分层规则：

- `T1`：容量前三行业内，命中双红，行业开根加权前排，且具备新高/多双红/涨停/容量核心之一。
- `T1-`：满足大部分条件，但缺少新高或存在一致性/拥挤风险。
- `T2`：强度足或新高/涨停明显，但存在成交额、题材纯度、行业宽度、排名边缘等降级原因。
- `OBS`：链内扩散、后排、容量锚、题材不纯或仅用于验证扩散方向。

不要写交易指令、买卖动作、止损、目标价。用“优先”“观察”“验证”“确认”“降级”这类复盘口径。

### Step 4：生成结构化 row JSON

把判断结果写成临时 JSON，推荐放 `/tmp/strategy1-row-{DATE}.json`，字段如下：

```json
{
  "date": "YYYY-MM-DD",
  "state": "市场/策略状态文本",
  "t1": [
    {"tag": "T1", "name": "股票名", "code": "000000.SZ", "reason": "D0事实和降级风险"}
  ],
  "t2": [
    {"tag": "T2", "name": "股票名", "code": "000000.SZ", "reason": "D0事实和降级风险"}
  ],
  "obs": [
    {"tag": "OBS", "name": "股票名或组合", "code": "", "reason": "观察理由"}
  ],
  "verify": "次日验证要点"
}
```

### Step 5：用小脚本写入 HTML

```bash
python3 skills/strategy1-matrix/scripts/update_matrix.py \
  --row-json /tmp/strategy1-row-YYYY-MM-DD.json \
  --matrix 复盘/matrices/strategy1-priority-stock-matrix.html \
  --dry-run
```

确认输出后去掉 `--dry-run`：

```bash
python3 skills/strategy1-matrix/scripts/update_matrix.py \
  --row-json /tmp/strategy1-row-YYYY-MM-DD.json \
  --matrix 复盘/matrices/strategy1-priority-stock-matrix.html
```

脚本职责仅限：

- HTML 转义
- 生成单行 `<tr>`
- 替换同日期旧行或插入新行
- 更新标题、日期范围和回填进度

脚本不负责选股判断。

### Step 6：验收

必须跑：

```bash
python3 - <<'PY'
from pathlib import Path
p=Path('复盘/matrices/strategy1-priority-stock-matrix.html')
t=p.read_text()
for s in ['YYYY-MM-DD','核心股票1','核心股票2']:
    print(s, t.count(s))
bad=['买入','卖出','交易建议','止损','目标价']
print({b:t.count(b) for b in bad})
PY

git diff --check -- 复盘/matrices/strategy1-priority-stock-matrix.html
```

可选打开工作台或矩阵 HTML 预览。

## 本次经验固化

- 不要把复杂判断塞给 SQL 一次性跑完；先用日报事实层，因为日报已经是 daily workflow 的清洗产物。
- 不要用 shell 写超长 HTML；用 JSON 传结构化内容，用 Python 做 HTML escape 和写入。
- 不要在失败后继续微调同一种办法；第二次失败就换路径：日报事实层 → 结构化 JSON → 小脚本写入。
- 每次生成后必须给出数据证据、文件证据、禁词检查和 `git diff --check`。
