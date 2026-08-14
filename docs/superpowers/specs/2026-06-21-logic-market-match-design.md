# Logic Market Match v0 Design

## Goal

Build the first executable bridge between market movement and the knowledge base. Given a date and a theme/query, classify whether the market signal looks like an old logic wakeup, a new logic candidate, noise/unconfirmed, or a data gap.

This is the "gap radar" layer. It should help decide what data to backfill first instead of blindly repairing every missing concept/source/IMA card.

## Inputs

- `query`: theme, concept, or keyword.
- `date`: optional theme-candidates export date.
- `exports_dir`: optional override for `market_feature_store/exports`.
- `kb_wiki`: optional override for the knowledge wiki root.

## Data Sources

Finance repo:

- `market_feature_store/exports/<date>-theme-candidates.json`

Knowledge wiki:

- `relations/concept_graph.json`
- `relations/entity_exposures.json`
- `relations/evidence_index.json`
- `wiki/sources/*.md`

## Classification Rules

`old_logic_wakeup`:

- market candidate found
- concept match found
- entity exposure found
- evidence found

`data_gap`:

- market candidate found but concept/entity/evidence is missing
- or source trace is incomplete

`new_logic_candidate`:

- market candidate found but knowledge coverage is weak and not enough for old-logic confirmation

`noise_or_unconfirmed`:

- no market candidate and no useful knowledge match

V0 is intentionally rule-based. It should be deterministic and easy to audit before adding scoring, CAR, half-life, or LLM planning.

## Outputs

CLI:

```bash
python3 -m intelligence.cli logic-match "光刻胶" --date 2026-06-11
python3 -m intelligence.cli logic-match "光刻胶" --date 2026-06-11 --json
```

Optional files:

```bash
--out-json market_feature_store/exports/<date>-logic-match-<query>.json
--out-md market_feature_store/exports/<date>-logic-match-<query>.md
```

The output includes:

- classification
- confidence
- matched market theme
- trigger types
- strong stocks
- concept matches
- entity exposures
- evidence items
- source trace status
- data gaps
- next actions

## Non-goals

- No CAR or return backtest in v0.
- No automatic source/concept/entity writes.
- No LLM classification.
- No LangGraph state machine.

Those come after v0 produces useful gap queues on real recent dates.

