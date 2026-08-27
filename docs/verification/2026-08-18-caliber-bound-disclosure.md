# Phase 4.5 口径绑定交付（2026-08-18）

- 树：`/Users/a77/fwp-wt-caliber-p5` `feat/caliber-bound-disclosure`
- 叠在：`feat/caliber-phase4-wiring` @ `3c2f98a3`（#202）
- 设计：`docs/superpowers/specs/2026-08-18-measured-value-caliber-contract-design.md`
- 未切 8792

## 为什么是这一刀

Phase 4.4 把 C4/C5 送进 research 车道，28 题 sidecar 仍 ❌：generic owner 取了 08-17 全市总览 + 网页，没碰到板块表。C3 已经证明：脏口径/空口径不能交给模型自觉。这一刀沿同一条交付缝，把**标的级取值**在 `deterministic_lane_answer` 短路。

不是第二份 `MetricSpec`。全市成交额仍走 `fact_market_daily`；板块成交额走 `fact_sector_daily`。

## 改了什么

`honesty_gates.bound_caliber_disclosure`，接在休市罐头之后：

1. **C4** ISO 日期 + 具名板块 + 成交额 → 读 `fact_sector_daily.amount` 原值。`amount≥100000` 或超过同日中位数 50 倍 → 标「单位异常」，禁止写成亿元/万亿。全市/大盘不走这条。
2. **C5** 个股 + 两个日期 + 收盘/涨了多少 → 读 `fact_stock_daily`。两日 close 与 pct_chg 完全相同 → 标「口径内部不一致」。
3. **A5** 日期 + 「涨停集中/题材热度」→ 读 `fact_theme_limit_heat_daily`，按涨停家数排序。不借道主线表。

库不可读或无行：fail-open。注入 `sector_row` / `stock_rows` / `heat_rows` 供单测，不连主库。

## 代码门

| 问句 | 注入 | 读数 |
|---|---|---|
| `2026-07-21 MLCC 板块成交额多少` | amount=6112588.6，中位数 405 | 含 `6112588.6` / `fact_sector_daily` / `单位异常`；不含 `611万亿` / `6112588亿`；不调 LLM |
| 同上 | 库不可读 | None |
| `2026-07-21 全市成交额多少` | 即使注入行 | None |
| `电子 板块成交额` amount=380.2 | 正常量级 | 含原值，不含「单位」 |
| `立新能源 2026-07-20 和 07-21 …收盘价` | 两日 close=10.01 pct_chg=10 | 含 `fact_stock_daily` / `不一致` |
| 两日 close 不同 | 9.10 vs 10.01 | 报两个数，不含「不一致」 |
| `2026-07-23 涨停集中在哪些题材` | 储能 40 / 风电 29 | 含 `fact_theme_limit_heat_daily` / `储能 40`；不含「主线」 |
| `涨停家数多少` / `今天市场怎么样` / `茅台现在股价多少` / `立新能源怎么看` | — | None |

## 对 FINANCE_WS 主库的现场探测（非 sidecar）

`FINANCE_WS=/Users/a77/finance-workspace-private`：

| 问句 | 现场 |
|---|---|
| C4 MLCC 07-21 | `amount=611.26`，**未**标单位异常。脏行已不在该日：`amount>100000` 全库只剩 2026-06-18 / 06-22 的 MLCC |
| C4 全市成交额 | None |
| C5 立新能源两日 | `close=10.01 pct_chg=10` 两日相同，标不一致 |
| A5 涨停集中 | `储能 40 家、风电 29 家、电网设备 29 家、光伏概念 25 家…` |
| 茅台现在股价 | None |

C4 题集仍冻着 `amount_raw=6112588.6`。当前库该日是 611.26，所以**验收真值列仍可能失败**——失败原因变成「冻结算子对不上已清洗的行」，不再是取错全市总览。不要把 611.26 改写成 6112588.6 去讨好尺子。

A5 overlay 仍是 `semantic_required`（排名语义），即使正文有储能 40，看板真值列也可能停在 ❔。

## sidecar 三题（8796，`20260818T2002Z-caliber-p5-c4c5a5`）

前置：`revision=880ac3b3 backend=continuous_glm`，未 `--force`。8792 未切。

| 题 | 耗时 | 读数 |
|---|---|---|
| A5 | 9.6s / 证据 0 | 罐头。储能 40 / 风电 29 / 电网设备 29 / 光伏概念 25。交付层把 `limit_heat` 译成「涨停热度」，表名显示成 `fact_theme_涨停热度_daily` |
| C4 | 9.6s / 证据 0 | 罐头。`amount=611.26`，未标单位异常（该日脏行已洗掉） |
| C5 | 9.5s / 证据 0（`df4ae260` 复跑） | **✅ 通过**。`fact_stock_daily 立新能源 2026-07-20 close=10.01 pct_chg=10；2026-07-21 close=10.01 pct_chg=10。两日收盘与涨幅完全相同，口径内部不一致。` |
