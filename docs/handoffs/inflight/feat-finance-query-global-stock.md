# feat/finance-query-global-stock

## 这个分支做什么

把隔夜外盘核心股接到 `finance_query`，并与已注册的指数表对齐双日历。
#399 已合 `gitea/main@92686a9c`。

## 当前状态

树 `/Users/a77/fwp-wt-finance-query-global-stock`。
- `global_stock_daily`：`full`，每日 194；`trade_date`=A 股对照日；`session_date` 只做维度
- 指数表补 `session_date`，coverage 从「个位数」改成固定 5 个
- 不开放 `market_cap_usd`（原样美元）
- 其余四张候选改写成先量后判的豁免，不注册

合 main 未授权。不要切 8792。不要做 sw_l1.amount、不要注册 theme_flow。

## 未验证 / 已知边界

- 全仓 pytest 数字以提交前实测为准。
- 从未 live。回填墙同前，不能做 08-12 前 PIT 重放。

## 下一步

全仓绿后开 PR，等用户合。

## 踩过的坑

- 08-25 全部 194 行 session=08-24，是时差/隔夜，不是缺数。
- ticker 用 `NVDA`，不要复用 A 股 `stock_code` 语义。
- theme_flow 08-25 合计 1884 vs 大盘 18316 vs 板块加总 216801，先不对齐。

## 已验证

- 全仓 pytest：**6528 passed / 12 skipped / 0 failed**；ruff 绿。
- 门禁：21 注册 + 19 豁免 + 2 VIEW。
- 生产库：NVDA 08-25 对照日、会话 08-24；证据日是 08-25。指数五只同轴。
