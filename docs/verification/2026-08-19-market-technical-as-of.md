# 技术位 as_of 截断读数（2026-08-19）

- 树：`/Users/a77/fwp-wt-technical-as-of` `fix/market-technical-as-of`
- 派单：`docs/handoffs/2026-08-19-market-technical-as-of-dispatch.md`（#207）
- 未切 8792

## 改了什么

1. `resolve_market_technical(..., as_of=None)`：非空时把已完成日线截到 `bar.date <= as_of` 再算。
2. 早于窗口 → `TechnicalGap`（reason 含最早可得日）；截断后 <60 根 → 同样 fail closed。不回落到最新一根。
3. 非交易日：取该日前最近一根，`TechnicalLevels.as_of` 报实际那天。
4. `episode_tools.run_deterministic_fast_path` / `ask._answer_market_technical` 透传锚点；adapter 把 `_latest_data_date` 传进去。口径对账披露留下作兜底。

## 验收

| 判据 | 读数 |
|---|---|
| **A. 指定日期真生效** | 腾讯实盘：`as_of=None` → `2026-08-18` close `1790.87`；`as_of=2026-07-24` → `2026-07-24` close `1787.2`。夹具单测同方向。 |
| **B. 与源对账** | 腾讯 raw `sh000688` 2026-07-24 行 close `1787.200`，与 A 逐位相同。`fact_stock_daily` 无 `000688.SH` 指数行，指数源即本路径的腾讯 K 线。 |
| **C. 窗口不足 fail closed** | `as_of=2020-01-02` → `TechnicalGap`：`窗口不足，最早可得 2026-02-25`。未返回 `TechnicalLevels`。 |
| **D. 非交易日** | `as_of=2026-07-25`（周六）→ 报 `2026-07-24`。 |
| **E. 旧行为不变** | 不传 `as_of` 的既有 `test_market_technical` / fast-path 单测仍绿；实盘最新仍是 `2026-08-18` / `1790.87`。 |
| **F. 两个调用点都通** | `test_fast_path_forwards_as_of_into_resolve`、`test_ask_forwards_options_date_as_as_of`、`test_fast_path_forwards_round_anchor_to_runner`。 |
| **G. 那两道题转正** | 真 `run_deterministic_fast_path` + adapter，`latest_data_date=2026-07-24`：`index-rebound-space` / `sci-tech-support` 均为 `status=completed`、`as_of=2026-07-24`、正文无「口径提示」。 |
| **H. 变异** | `test_as_of_truncation_mutation_turns_criterion_a_red`：把 `bars_at_or_before` 换成原样返回后，`as_of=2026-07-24` 不再停在那天。 |

相关 pytest：`test_market_technical` + `test_episode_tools` + `test_continuous_turn_adapter` **155 passed**。收据 `~/.finance-runtime/test-receipts/20260818T171903Z-99fc0c9a.json`（当时 HEAD 仍为 main tip；合入后以分支 tip 为准）。

## 本单不做

快路径答案模板仍按「反弹空间」写死：G 两题 `as_of` 已对齐，但正文仍逐字节相同。那是 §3.1 的①（按标的而非按问题意图），不在本派单。
