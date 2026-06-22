# Logic Match Batch Gap Queue Design

## Goal

Use recent market-triggered theme candidates to generate a high-priority data backfill queue. The queue answers: "Which missing source/concept/entity/evidence items matter for current market analysis?"

## Inputs

- recent N dates or explicit dates
- top N candidates per date
- knowledge wiki root
- theme-candidates exports

## Output

- Batch JSON report
- Batch Markdown report
- Priority gap queue sorted by market score plus gap severity

## Priority Logic

Each candidate is matched through `logic_market_match`. Items enter the gap queue when:

- classification is not a clean `old_logic_wakeup`
- or the match is an old logic wakeup but has source trace gaps

Gap weights:

- missing source trace: high priority
- missing evidence: high priority
- missing entity exposure: medium priority
- missing concept: medium priority
- missing market signal: low priority

## Non-goals

This does not repair the knowledge base. It produces the queue that tells us what to repair first.

