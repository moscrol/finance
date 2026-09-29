# Daily review / dashboard alignment — 2026-09-29

## User feedback and current scope
The user pointed to the daily HTML produced by the previous full review: much of its data is what they wanted. Inspect before redesigning. The previously delivered generic daily dashboard covers only a subset; retain the established full-review definitions and richer structure as the next design reference. The larger layout migration below is a proposal, not completed work.

## Inspected sources
- `复盘/daily/2026-09-24/2026-09-24-daily-review.html` and previous day.
- `market_feature_store/exports/2026-09-24-daily-review.json` and `.md`.
- `market_feature_store/reports/daily_review.py`, daily renderer scripts.
- `复盘/daily/2026-09-24/2026-09-24-daily-agent.html` is a separate research/evidence/queue report, not market facts.
- `intelligence/services/finance_query.py` and sector daily synchronization definitions.

## Reference content to preserve
1. Index/volume/deviation/market phase and phase day, relative volume and day classifications.
2. Sentiment: breadth, advancers MA5 waves/position/trend, board height, window-qualified money-effect classification.
3. Top-three SWL1 turnover shares and change/concentration.
4. 1/3/5/10-session compounded-return sector rankings, not sum of daily returns.
5. Double-red and single-red grouped by SWL1; focus-industry 15-session subsector matrices.
6. 120-session highs and limit-up themes with 15-session grouped matrices, sector distributions and stock lists.
7. Top-three industries' individual-stock engines: sqrt(daily turnover in 100m CNY) × daily percentage change; new-high and double-red overlaps.
8. Three-or-more-board stocks, market strength/share/MA5/MA20, distinct five-session weighted-stock top ten, coverage checks and assessment.

Matrix definitions: child-sector cells = return / marginal volume / turnover; mother-industry cells = turnover share / return; Shanghai = 120-session volume ratio / return. These heterogeneous rows must not be silently collapsed into a single percent heatmap.
Double red: pct_chg > 0 AND diff_ratio > 10 AND amount > 500 (100m CNY); single red uses <=500 OR missing amount in current report code. Preserve provenance and show missing data explicitly.

## Confirmed label correction — completed
`fact_sector_daily.diff_ratio` means **板块边际量**, not advancer-minus-decliner share. Existing ScanPanel label and new DailyRiverDashboard labels were wrong. Corrected both remote and local source, plus strength card label from 强势股均涨幅 to the report's 强度加权涨幅. Added a regression assertion for the correct sector column and absence of the incorrect label.
Remote typecheck passed; frontend 12/12 tests passed after correction. No broad redesign, deployment, restart, DB write, import, commit or merge.

## Proposed navigation
- Summary: market environment, breadth/MA5, industry concentration.
- Main workspace: SWL1-grouped time matrices switching double-red / new-high / limit-up; shared selected date and industry.
- Drilldown: child-sector then stock engines/boards/new highs; same-date six-track research and public-attention provenance alongside, not conflated with market facts.
- Keep access to the original 15-section daily report and its coverage warnings.

Reuse the report JSON and canonical calculation logic, not HTML scraping or a second set of formulas. Archived report display should be read-only. If interactive charts need raw numeric fields, expose shared read-only calculations rather than reverse-parsing formatted cells or running the report-writing pipeline on page requests. Show trade date, generation time and historical-knowledge limitations separately.

## Existing report defects / caveats, not yet fixed
- 09-24 double-red count is zero, yet a conclusion says all are unmapped; handle empty sets distinctly from mapping failures.
- Today's electronics parent-industry matrix share is missing although summary has 27.10%; investigate coverage/join semantics, do not fill silently.
- 缩量普涨 is a rolling-window derived label, not proof that the selected day broadly rose. Display the observation window and derivation.

Recommended first migration: industry concentration + double-red/new-high/limit-up matrices + stock-engine drilldown, then the fuller market-environment block. No user confirmation of this prioritization yet.


## Implementation update
User confirmed 推进; the proposed first migration is now complete. See `docs/handoffs/2026-09-29-daily-review-dashboard-implementation.md` for current source, verification and boundaries.
