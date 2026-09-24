# 飞书退役的 skill 能力回收：本地技术位

分支 `feat/local-technical-screen`，基于 `dd1ad32b`。

## 背景

飞书退役（#727）时整删了 5 个 skill。用户反馈：功能要保留，且要能在 agent 里复用，
而不是"在飞书里算"。这个分支把能力搬回本地。

## 判断依据：5 个 skill 各自缺什么

读代码而非读 SKILL.md 自述，得到的实际情况：

| 旧 skill | 计算内核在哪 | 本地已有？ | 结论 |
|---|---|---|---|
| `advancers-chart` | 涨家数 + MA5 + matplotlib | ✅ `reports/daily_review.py` 全套 | **零缺口**，只是没人指路 |
| `up-line` | MA26/STD26/UP/偏离度 | ✅ 早有 `local_query` 读 `fact_stock_daily`，iFinD 只是兜底 | 计算本就本地，缺的是"给任意清单算" |
| `watchlist-ma` | MA10/MA20 回踩 | ❌ | 真缺 |
| `top-gainers-feishu` | MA5/MA10/MA20 两条回踩口径 | ❌ | 真缺 |
| `sector-data` | 板块量价齐升三阈值 | ⚠️ `top-sectors` 只排序不筛选 | 差三个参数 |

**唯一没有本地副本的是那 13 只自选股清单**——指标都能从 `fact_stock_daily` 重算，
清单不能，它是人的意图。

## 做了什么

1. `query.stock_technicals(terms, as_of, windows)`：一条 SQL 批量算均线/STD26/UP/偏离度/回踩标记。
   - 三个旧 skill 的口径合并到这里，判定式原样保留（严格不等式）
   - **带 `as_of`**：飞书版做不到回溯，本地版从第一天就接上（D6 的教训）
   - 不足期给 `None` 不给近似
   - term 解析一次扫表完成（逐只查会把 375 万行表扫 N 遍）
2. `market_feature_store/watchlist.py`：本地清单，`~/.finance-runtime/watchlists/*.txt`。
   **故意不入库**——用户持仓意图不是代码。
3. CLI `stock-technicals` / `watchlist`；`top-sectors` 加三个 `--min-*` 阈值。
4. skill `stock-technicals` + dispatcher 加「已退役 skill 的去处」路由表。
5. 注册表手工精修（新条目 + dispatcher 重算哈希 + repos 计数 34）。

## 过程中撞坏又修好的东西

`cli.py` 里**本来就有两个** `_fmt_num`（1171/1270，后者是前者超集）。我又加了第三个
单参数版，把 `interval-gainers` 的渲染整条打崩——**跑了 71 个相关测试，一个都没红**。

处置：删掉最早那个（运行时本就只有最后一个生效，零行为变化），补两条测试守住：
渲染路径真的被执行一次（含全 None 行）、`cli.py` 不许有重复顶层函数。

## 验收

- 新增 30 条测试（技术位 13 / 清单 8 / CLI 9），**18 种变异全部变红**
- 全量 9217 passed / 77 skipped / 1 xfailed，ruff 干净
- 真库实测：自选股 13 只命中中期回踩 2 只；`--as-of 2026-03-14` 与库尾是两套数

## 欠账

- `intelligence/services/kb_rag.py` 有一对重复的 `_stderr_reason`（116/168），同类问题，
  本 PR 不碰（一个 PR 只做一件事）。要不要加"全仓禁止重复顶层函数"的门禁，得先修它。
- 自选股清单目前 13 只，与 profile 的 `watchlist` 字段是两回事，没有自动同步（有意）。
