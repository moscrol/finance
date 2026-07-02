# Read-only FinHot Evidence Hunter Design

## Context

The finance agent already separates market-triggered themes, knowledge-base grounding, evidence layers, and research queues. `today_find_official_evidence` is the existing action bucket for themes or companies that need announcements, research notes, orders, customer validation, capacity, certification, or similar evidence. `finhot` is the existing subscribed-source system for finance alerts, RSS, bloggers, hotwords, event clustering, admission scoring, and machine-readable feeds.

This design connects those two systems without writing to the knowledge base. The first version turns pending verification work into structured tasks, searches `finhot` for candidate evidence, classifies matches by evidence layer, and renders a human-reviewable report.

## Goals

- Convert `today_find_official_evidence` items into a reusable `verification_tasks.json` schema.
- Search `finhot` sources for candidate evidence for each task.
- Distinguish current catalyst evidence from baseline evidence and weak narrative signals.
- Produce read-only JSON and Markdown reports with matched evidence, rejected items, confidence, and next action.
- Keep the output format reusable by future sources such as theme readiness, manual news input, ingest gaps, and annual report baseline extraction.

## Non-goals

- Do not write to `evidence_index.json`, `entity_exposures.json`, concept pages, or RAG indexes.
- Do not auto-upgrade ingest status, evidence status, or concept confidence.
- Do not treat all `finhot` hits as official evidence.
- Do not solve annual report ingestion in this phase.
- Do not require the `finhot` web service to be running.

## Evidence model

The hunter uses a conservative evidence ladder:

| Layer | Meaning | Typical source | Use |
|---|---|---|---|
| `L1_signal` | Narrative or market clue | media, blogger, RSS article, reposted alert | discovery only |
| `L2_official_baseline` | Official proof of business/product/capability | annual report, semiannual report, prospectus, official website | company capability baseline |
| `L3_historical_official_fact` | Official hard fact that may not be the current catalyst | annual report or report section with order, customer, shipment, revenue, certification, capacity | historical validation |
| `L3_candidate` | Alert or secondary source claims a hard fact but original official source is not confirmed | finance alerts, media reposts, broker note summary | candidate requiring source trace |
| `L3_current_official_catalyst` | Recent official hard fact related to the task claim | announcement, exchange interaction, official website news, order/contract, certification, customer validation | current catalyst validation |
| `rejected` | Not evidence for this task | entity mismatch, theme-only hit, old duplicate, source too weak | excluded with reason |

Annual reports are not treated as blanket L3. They usually provide `L2_official_baseline`. They may provide `L3_historical_official_fact` only when they contain explicit hard facts such as named customers, orders, certifications, mass production, capacity release, revenue contribution, or contract amounts.

## Verification task schema

Each task is a structured hypothesis-verification request.

```json
{
  "task_id": "2026-06-26-daily-find-official-001",
  "source": "daily_research_queue",
  "trade_date": "2026-06-26",
  "theme": "PCB",
  "concept": "高速PCB",
  "claim": "缺 L3 官方验证，需找公告、调研、订单、客户验证或产能证据。",
  "entities": ["胜宏科技", "沪电股份"],
  "strong_stocks": ["胜宏科技", "沪电股份"],
  "target_layer": "L3_current_official_catalyst",
  "target_evidence_types": ["announcement", "order", "customer_validation", "capacity", "mass_production", "certification"],
  "query_terms": ["PCB", "高速PCB", "AI服务器", "订单", "产能", "客户", "量产"],
  "priority": "P0",
  "lookback_days": 14,
  "metadata": {
    "research_queue_reason": "已有 L2 或 L3 候选，但缺 L3 官方验证。"
  }
}
```

Required fields are `task_id`, `source`, `theme`, `claim`, `target_layer`, `target_evidence_types`, `query_terms`, and `lookback_days`. `entities` may be empty for early theme-level tasks, but entity-level matching is preferred when available.

## Candidate evidence schema

Each searched item is normalized before scoring.

```json
{
  "task_id": "2026-06-26-daily-find-official-001",
  "item_id": "finhot:12345",
  "source": "财联社",
  "source_tier": "T1_alert",
  "published_at": "2026-06-26T10:12:00+08:00",
  "title": "...",
  "text": "...",
  "url": "...",
  "matched_entities": ["沪电股份"],
  "matched_theme_terms": ["PCB", "AI服务器"],
  "matched_fact_terms": ["订单", "客户"],
  "evidence_type": "order",
  "evidence_layer": "L3_candidate",
  "confidence": 0.72,
  "reason": "同时命中目标公司、题材词和订单/客户事实词，但来源为快讯转述，尚未确认官方原文。"
}
```

Rejected items use the same core fields and add `reject_reason`.

## Source interpretation rules

- Company announcements, exchange interactions, official websites, annual reports, semiannual reports, and prospectuses can qualify as official sources.
- Finance alerts and media articles can produce `L3_candidate` when they claim hard facts, but do not become `L3_current_official_catalyst` without official source trace.
- Blogger, Weibo, Xueqiu, and public social feeds are discovery signals only unless they link to or quote an official source that the system can identify.
- A hit must match the task theme or concept and at least one fact term. If entities are present, a high-confidence candidate should also match an entity or accepted alias.
- Items that only match the theme but not the entity are kept as low-confidence context or rejected, depending on task granularity.
- Items that only match a company but not the theme or claim are rejected.
- Old duplicated items are rejected unless they are the only available source trace for the task.

## Matching and scoring

The first implementation should use deterministic scoring:

- Entity match: company name, code, alias, or strong stock name.
- Theme match: theme, canonical concept, related query terms, and extracted hotword.
- Fact match: terms such as 公告、互动易、订单、中标、合同、定点、客户、认证、送样、量产、扩产、产能、收入、涨价、供应商.
- Source strength: official source > T1 finance alert > media/RSS > social/blogger.
- Recency: recent items inside `lookback_days` score higher.
- Admission quality: reuse `finhot` admitted/score/cluster metadata when available.
- Rejection penalty: entity mismatch, theme mismatch, no fact term, social-only speculation, stale duplicate.

Confidence is a deterministic numeric score from 0 to 1. The report should include enough matched terms and reasons for manual review instead of hiding decisions behind a score.

## Data flow

```text
daily agent report or daily research queue JSON
  -> daily queue adapter
  -> verification_tasks.json
  -> finhot SQLite searcher
  -> normalized candidate/reject items
  -> evidence classifier and scorer
  -> evidence-hunter-YYYY-MM-DD.json
  -> evidence-hunter-YYYY-MM-DD.md
```

The first version reads `finhot` SQLite directly so it does not depend on the FastAPI server being alive. A later adapter can read `/feed/hot.json` or `/api/term/{term}` as an alternative source.

## CLI shape

```bash
python scripts/build_evidence_hunter_report.py \
  --daily-agent-json /tmp/bf/2026-06-26-daily-agent-new.json \
  --finhot-db khazix-skills/finhot/data/finhot.db \
  --lookback-days 14 \
  --out-tasks /tmp/bf/verification-tasks-2026-06-26.json \
  --out-json /tmp/bf/evidence-hunter-2026-06-26.json \
  --out-md /tmp/bf/evidence-hunter-2026-06-26.md
```

The same command should also accept prebuilt tasks:

```bash
python scripts/build_evidence_hunter_report.py \
  --tasks /tmp/bf/verification-tasks-2026-06-26.json \
  --finhot-db khazix-skills/finhot/data/finhot.db \
  --out-json /tmp/bf/evidence-hunter-2026-06-26.json \
  --out-md /tmp/bf/evidence-hunter-2026-06-26.md
```

If both `--tasks` and `--daily-agent-json` are provided, `--tasks` is the authoritative input and the daily report is ignored.

## Report content

The JSON report contains:

- `generated_at`
- `trade_date`
- `inputs`
- `summary`
- `tasks`
- `matched_items`
- `rejected_items`
- `warnings`

The Markdown report contains:

- Summary counts by status and evidence layer.
- P0/P1 tasks with best candidate evidence.
- Candidate table with source, time, entity, fact terms, layer, confidence, URL, and reason.
- Rejected table with reject reason.
- Next action per task.

Task statuses:

- `candidate_found`: at least one candidate above threshold.
- `official_candidate_found`: an official-source candidate was found.
- `only_weak_signal`: only L1 or weak media/social signals were found.
- `not_found`: no useful hit inside the lookback window.
- `needs_alias_mapping`: likely entity mismatch or missing alias prevents reliable matching.
- `input_gap`: task lacks enough theme/query/entity data to search reliably.

## Error handling

- Missing `finhot` database returns a report with `input_gap` warning and zero candidates.
- Missing daily report or missing research queue returns a clear CLI error.
- Empty `today_find_official_evidence` generates an empty report instead of failing.
- Unknown `finhot` schema should fail fast with a schema diagnostic that lists available tables and columns.
- Unparseable timestamps are allowed but reduce recency score and add a warning.
- All write outputs are explicit paths or deterministic default report paths; no knowledge-base writes occur.

## Testing plan

- Task adapter tests:
  - daily queue item with theme, strong stocks, evidence gaps becomes a stable verification task.
  - empty queue produces an empty task list.
  - missing entity still produces a theme-level task with lower confidence expectations.

- SQLite search tests:
  - temporary SQLite database with a company/theme/fact hit produces a candidate.
  - theme-only hit is rejected or low-confidence according to task granularity.
  - company-only hit is rejected.
  - old duplicated item is rejected when a fresher cluster item exists.

- Classifier tests:
  - official announcement text maps to `L3_current_official_catalyst`.
  - finance alert claiming an order maps to `L3_candidate`.
  - annual-report baseline text maps to `L2_official_baseline` unless hard fact tokens are present.
  - blogger speculation maps to `L1_signal`.

- Renderer tests:
  - Markdown includes task summary, candidates, rejects, evidence layer, confidence, and next action.
  - JSON is deterministic enough for regression assertions.

## Rollout plan

1. Implement read-only task schema, daily queue adapter, `finhot` SQLite searcher, classifier, and renderer.
2. Run against one daily agent JSON and inspect the Markdown report manually.
3. Add aliases for obvious company-name misses found in inspection.
4. Add an approved evidence manifest in a later phase after report precision is acceptable.
5. Build annual report baseline hunter as a separate module that emits the same candidate evidence schema.
6. Only after manual precision is stable, add dry-run KB update manifests and optional apply flow.

## Design decisions

- Start with `today_find_official_evidence` because it is already the agent's explicit request for official evidence.
- Keep the task schema source-agnostic so later inputs do not require a new hunter.
- Read SQLite first because it is more reliable than assuming the local FastAPI service is running.
- Keep all outputs read-only and review-first to prevent noisy social or alert signals from polluting the knowledge base.
- Treat annual reports as a baseline channel, not a substitute for current-catalyst validation.
