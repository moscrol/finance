---
name: strategy1-matrix
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
