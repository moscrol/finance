# 策略一矩阵 生成流程

> 本文件由 `skills/strategy1-matrix/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

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
