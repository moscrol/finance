---
title: Strategy1 Limit-Up Mapping and MA5 Impact Validation
date: 2026-06-08
branch: strategy1/limit-up-ma5-impact
status: approved-design
---

# Strategy1 Limit-Up Mapping and MA5 Impact Validation

## 1. Objective

Validate whether two daily-review signals improve Strategy1:

1. **Limit-up mapping**: whether a double-red theme has same-day limit-up support, and whether that support is concentrated.
2. **Advancers MA5 interval**: whether market breadth position/trend changes Strategy1 performance.

The validation has two layers:

1. **Stock layer**: test whether Strategy1 stock candidates perform better after adding limit-up and MA5 factors.
2. **Theme layer**: test whether these factors help classify double-red themes into continuation, reflow, retreat, or rotation candidates.

This is hypothesis validation, not a trading rule. Results must be labeled as initial support, no support, insufficient sample, or requires further validation.

## 2. Existing Context

Strategy1 currently uses:

- Main liquidity pool: top 3 SW L1 industries by trading amount share.
- Double-red themes: `pct_chg > 0`, `diff_ratio > 10`, `amount > 500亿`.
- Stock engine: in-industry weighted strength, computed as `sqrt(amount_yi) * pct_chg`.
- Enhancement factors: high-status stock, multi-theme hits, and relative strength during divergence days.
- Validation outputs under `research/market-hypothesis/`.

Daily review already computes:

- Advancers MA5 series and interval summary in `market_feature_store/reports/daily_review.py`.
- Limit-up mapping matrix using `fact_theme_limit_stock_daily` joined to `fact_sector_stock_daily`.
- Top 3 SW L1 stock engines and double-red theme hits.

## 3. Data Sources

Use local DuckDB through `market_feature_store.db.connect`.

Required tables:

| Table | Usage |
|---|---|
| `fact_market_daily` | Trading dates, top 3 industries, advancers, limit-up/down, market amount, index context |
| `fact_sector_daily` | Double-red theme events and lifecycle anchors |
| `fact_sector_stock_daily` | Theme constituents, stock pct/amount, SW L1 mapping, theme membership |
| `fact_stock_daily` | Forward close-to-close return windows |
| `fact_stock_high_daily` | Stock high-status factor |
| `fact_theme_limit_stock_daily` | Same-day limit-up stocks for limit-up mapping |

Default validation window:

```text
2026-04-08 ~ 2026-06-05
```

## 4. Factor Definitions

### 4.1 Limit-Up Factors

For each Strategy1 stock candidate on event date `t`:

| Field | Definition |
|---|---|
| `limit_theme_hit` | At least one of the stock's same-day double-red themes has mapped limit-up stocks on `t` |
| `limit_theme_count_max` | Maximum mapped limit-up stock count among the candidate's hit double-red themes |
| `limit_theme_count_sum` | Sum of mapped limit-up stock counts across hit double-red themes |
| `limit_stock_hit` | Candidate stock itself is a same-day limit-up stock |
| `limit_sw_count` | Total same-day limit-up stocks mapped to the candidate's SW L1 industry |
| `limit_theme_rank_in_sw` | Best rank of the candidate's hit double-red themes by limit-up count inside its SW L1 |

Initial tags:

```text
limit_strong = limit_theme_count_max >= 2 OR limit_stock_hit
limit_medium = limit_theme_count_max == 1
limit_weak = no mapped limit-up support
```

### 4.2 MA5 Interval Factors

Reuse the daily-review MA5 logic with deterministic fields per event date:

| Field | Definition |
|---|---|
| `ma5_value` | Advancers MA5 on event date |
| `ma5_position` | `高位区` / `中位区` / `低位区` / `震荡区间` / `窄幅震荡区` |
| `ma5_trend` | `上升` / `下降` / `震荡` |
| `ma5_interval_type` | Current interval label, e.g. `波谷→当前`, `波峰→当前`, `当前震荡区间` |
| `ma5_interval_delta` | MA5 change within current interval |
| `ma5_favorable` | True when MA5 is `上升`, or `低位区`/`中位区` with positive interval delta |
| `ma5_risk` | True when MA5 is `高位区` and trend is `下降`, or current interval is a confirmed post-peak decline |

If the daily-review algorithm returns shock/震荡, do not force a directional label.

## 5. Stock-Layer Validation

Base sample:

- Reconstruct Strategy1 candidates from DuckDB in the validation script, rather than relying on one CSV only.
- Keep fields compatible with existing Strategy1 outputs.

For every candidate, compute forward performance:

| Metric | Window |
|---|---|
| `ret_3d`, `ret_5d`, `ret_7d`, `ret_10d` | Close-to-close returns |
| `peak_ret_10d` | Best close-to-close return within 10 trading days |
| `peak_day_10d` | Trading-day offset when peak occurred |
| `max_drawdown_after_peak_10d` | Worst post-peak pullback within 10 trading days |
| `ret_ge_5`, `ret_ge_10`, `ret_ge_20` | Threshold hit flags based on peak return |

Compare groups:

1. Strategy1 base sample.
2. `limit_strong` only.
3. `ma5_favorable` only.
4. `limit_strong + ma5_favorable`.
5. `limit_weak + ma5_risk`.
6. lifecycle-specific slices: d1, d2, d3, mature/multiple reflow.

Primary question:

```text
Does limit-up support and/or favorable MA5 improve Strategy1 peak return, threshold hit rate, and drawdown profile?
```

## 6. Theme-Layer Validation

Base sample:

- All double-red theme events from `fact_sector_daily` within the validation window.
- Lifecycle labels are assigned from the first double-red date after the cycle start date.

For each theme event, compute:

| Field | Definition |
|---|---|
| `lifecycle_stage` | d1, d2, d3, mature, long-gap reflow |
| `limit_mapped_count` | Same-day mapped limit-up stock count for this theme |
| `limit_mapped_rank_in_sw` | Rank inside SW L1 by mapped limit-up count |
| `limit_concentration_tag` | none / weak / concentrated |
| `ma5_position`, `ma5_trend`, `ma5_interval_delta` | Event-date MA5 context |
| `next_double_red_gap` | Trading days to next double-red event for the same theme |
| `next_reflow_return` | Theme pct change at next double-red event or fallback forward window |
| `reflow_result` | continuation / quick_reflow / long_gap_reflow / no_reflow / retreat |

Primary questions:

1. Do double-red themes with limit-up support reflow sooner or more reliably?
2. Does a favorable MA5 interval strengthen reflow probability?
3. Does limit-up support during MA5 risk zones signal climax rather than continuation?
4. Did mechanical equipment's 2026-06-05 upgrade into top-3 capacity have earlier warning through limit-up mapping?

## 7. Outputs

Create one script and four outputs:

```text
research/market-hypothesis/_scripts/strategy1_limit_ma5_impact.py
research/market-hypothesis/strategy1-limit-ma5-impact-detail.csv
research/market-hypothesis/strategy1-limit-ma5-impact-factor-summary.csv
research/market-hypothesis/strategy1-limit-ma5-impact-theme-summary.csv
research/market-hypothesis/strategy1-limit-ma5-impact.md
```

Output purpose:

| File | Purpose |
|---|---|
| detail CSV | Stock-level event rows with factors and forward metrics |
| factor summary CSV | Grouped stock-layer performance comparison |
| theme summary CSV | Theme-event reflow and lifecycle comparison |
| Markdown report | Human-readable conclusions and daily-review usage guidance |

## 8. CLI Design

Script defaults:

```bash
python3 research/market-hypothesis/_scripts/strategy1_limit_ma5_impact.py \
  --start-date 2026-04-08 \
  --end-date 2026-06-05
```

Optional arguments:

```text
--start-date YYYY-MM-DD
--end-date YYYY-MM-DD
--output-dir research/market-hypothesis
--top-pct 0.20
--forward-days 10
```

## 9. Validation Checks

Before writing conclusions:

1. Confirm required tables exist and have coverage for the window.
2. Confirm event dates have trading-day continuity.
3. Confirm limit-up table coverage is non-empty for event dates.
4. Confirm MA5 fields are available for event dates.
5. If data coverage is incomplete, report the gap instead of inferring a conclusion.

Code checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile research/market-hypothesis/_scripts/strategy1_limit_ma5_impact.py
python3 research/market-hypothesis/_scripts/strategy1_limit_ma5_impact.py --start-date 2026-04-08 --end-date 2026-06-05
```

## 10. Acceptance Criteria

The branch is complete when:

1. The validation script runs successfully on `2026-04-08 ~ 2026-06-05`.
2. All four output files are generated.
3. The Markdown report states whether limit-up mapping and MA5 interval improve Strategy1 at stock and theme levels.
4. The report separates signal from noise and does not convert early findings into hard rules.
5. The final summary gives daily-review usage guidance, especially how to use the two factors when selecting candidates after each daily review.

## 11. Out of Scope

This branch does not:

- Change the daily review template.
- Change Strategy1 production selection rules.
- Sync new external market data.
- Push results to Feishu or Obsidian.
- Build a UI.

Any production rule change must wait for the validation report and user confirmation.
