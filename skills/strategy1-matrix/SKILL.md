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

生成策略一矩阵的 6 步流程（日期数据门控 → 从日报事实层定向抽取 → 策略一口径与 T1/T1-/T2/OBS 分层规则 → 结构化 row JSON schema → 小脚本安全写 HTML → 验收禁词与 git diff 检查）见 `references/generation-flow.md`。逐步执行，先抽取分层再用脚本写入。

## 本次经验固化

- 不要把复杂判断塞给 SQL 一次性跑完；先用日报事实层，因为日报已经是 daily workflow 的清洗产物。
- 不要用 shell 写超长 HTML；用 JSON 传结构化内容，用 Python 做 HTML escape 和写入。
- 不要在失败后继续微调同一种办法；第二次失败就换路径：日报事实层 → 结构化 JSON → 小脚本写入。
- 每次生成后必须给出数据证据、文件证据、禁词检查和 `git diff --check`。

## 2026-06-22 经验固化

### 数据前置依赖

策略一依赖 `fact_stock_daily` 和 `fact_stock_high_daily` 有真实行情。
若 fact_stock_daily 全空（东方财富 502 + mootdx 超时），则：
- §7 个股发动机表为空 → T1/T2 判断缺少"成交占前行业 Top20"维度
- 加权涨幅无法计算 → 缺少"根号加权 = sqrt(amount) × pct_chg"排序

**解法**：先确认 `sync-sector-stocks --refresh` 已补真实行情 →
`fill-stock-daily-fallback` → 再开始策略一流程。

### 可用的替代数据源

当 fact_stock_daily 不可用时，可从以下表提取候选股：

| 表 | 用途 | 关键字段 |
|---|---|---|
| fact_stock_high_daily | 创新高股（history/3y/2y/1y/120d/60d/20d） | stock_ts_code, period, pct_chg, amount |
| fact_theme_limit_stock_daily | 涨停股明细 | stock_ts_code, theme_name, boards |
| fact_limit_advance_daily | 多板股（连板数） | stock_ts_code, boards, theme_name |
| fact_sector_stock_daily | 板块成分股行情（若已 refresh） | stock_ts_code, price, pct_chg, amount |

### JSON 构造注意

- `t2` 数组实际包含 T1- 和 T2 两类，tag 字段区分：`{"tag": "T1-", ...}` 和 `{"tag": "T2", ...}`
- `reason` 字段禁用：买/卖/建议/确定/降低/止损/目标价
- `state` 字段写市场阶段描述，不写操作建议
- `verify` 字段写次日验证要点和数据缺失说明
