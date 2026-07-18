# Workbench Research Contract Design

## Goal

Replace independent routing, timeout, and natural-language validation decisions
with one turn-level contract shared by the controller, retrieval stages, and
presenter. The acceptance fixtures are A03, A04, A15, A16, A17, and A18.

## Turn contract

`TurnIntent` is the persisted interpretation of one user turn:

```text
primary_subject
secondary_topics
question_type
answer_owner
comparison_entities
inherited_from_turn
evidence_atom_ids
```

The controller is the only component allowed to choose `answer_owner`.
`ResearchPlan` combines that intent with the owner's retrieval stages. The
router may add non-owner tools, but it must not add or replace an answer owner.

Follow-ups inherit the previous completed turn's subject, owner, and evidence
set when they contain a continuation or reference cue and do not explicitly
name a new subject or task type. Explicit switches are resolved before
inheritance. Persisting the contract avoids reconstructing state from prose.

Owner mapping:

```text
stock_deep_dive    -> stock-deep-dive
financial_analysis -> financial-analysis
news_impact        -> news-impact
theme_analysis     -> theme-research
```

## Deadline contract

`ResearchDeadline` stores one absolute monotonic expiry created by the
orchestrator. Every stage receives the same object and derives its local
timeout from:

```python
min(configured_stage_limit, deadline.remaining())
```

No nested call may create a fresh 90/180-second budget. Before starting a
fallback or optional stage, the caller must check the deadline. A timeout
returns completed partial artifacts and prevents another monolithic retrieval
run. Stage telemetry records start/end time, status, artifact type, and degrade
reason.

Thread cancellation alone is not a correctness mechanism: synchronous work
must receive the deadline and stop at subprocess, HTTP, and provider
boundaries.

## Evidence contract

Retrieval stages emit `EvidenceAtom`:

```text
atom_id
claim_text
entity_id
metric
value
unit
period
evidence_tier
source_id
source_date
provenance
```

`AnswerSpec` is built from atoms rather than re-parsing rendered evidence.
Generated factual output uses structured claims:

```json
{
  "claim": "公司披露的事实",
  "evidence_atom_ids": ["atom-12"],
  "claim_type": "fact"
}
```

The validator accepts only known atom IDs, requires factual claims to cite at
least one atom, and keeps inference/expectation visibly distinct. Revision may
recombine allowed atoms but may not repair an answer by deleting unsupported
sentences. The presenter renders validated claims into natural language.

This is more reliable than numeric/company regexes because identity and
provenance are established where evidence enters the system, not guessed from
Chinese surface text after generation.

## Owner-specific retrieval DAGs

Each owner executes only its minimum stages:

- `stock-deep-dive`: company master, company evidence, financial transmission,
  market choice, counterevidence.
- `financial-analysis`: report period, revenue/profit/margin/cash flow, segment
  disclosure, prior-period comparison.
- `news-impact`: original disclosure, event facts, first/second-order impact,
  substitutes and harmed directions.
- `theme-research`: definition, chain stages, company mapping, market
  lifecycle, counterevidence.

Stages share a turn-scoped cache keyed by subject/query/stage and an
`EvidenceAtom` registry. A typed partial artifact is usable even when later
stages time out.

## Migration

1. Persist `TurnIntent`; make controller owner selection unique; make router
   tool-only; verify A04/A15/A16/A17/A18 offline.
2. Propagate `ResearchDeadline` through owner, RAG, module, market, and LLM
   boundaries; disable duplicate full fallback.
3. Introduce owner DAG stage contracts, shared cache, and timing telemetry.
4. Build `AnswerSpec` from `EvidenceAtom`; require structured claim IDs; remove
   regex deletion repair after compatibility fixtures pass.

The same pattern applies to other agent/RAG systems: one orchestration
authority, one absolute budget, typed partial results, and evidence identities
that survive retrieval through presentation.

## Narrative synthesis shadow migration

The production presenter must not switch directly from registry rendering to
free-form model text. The missing boundary is tested first as an opt-in shadow
pipeline:

```text
AnswerSpec + EvidenceAtom
        ↓
DecisionBrief
        ↓
Grounded Composer
        ↓
deterministic entity/number/date/type gate
        ↓
low-temperature entailment judge
        ↓
sentence-level repair
        ↓
shadow artifacts only
```

`DecisionBrief` owns the argument plan (`direct_answer`, `core_tension`,
supports, counterevidence, unknowns, and upgrade/downgrade conditions) while
the composer owns the final wording. Composer sentences may bind multiple
claim IDs, but factual sentences still require known EvidenceAtom IDs.

Enable the experiment with:

```bash
WORKBENCH_SHADOW_GROUNDED_COMPOSER=1
```

The user-visible production answer remains unchanged. Each enabled run writes
`grounded_composer_shadow.json` and, when validation reaches a presentable
result, `grounded_composer_shadow.md`. Promotion requires fixture-level factual
parity plus human improvement on directness, coherence, and analyst-like
writing; only then may the production presenter retain composer wording.

The initial comparison set covers:

- `总结一下 2026-07-16 的行情`
- `中际旭创怎么看`
- `这个逻辑的边际变化呢`
- `光模块怎么看`
- one financial-report question
- one news-impact question
- one valuation question
- one company-relationship question

For each run, compare the production answer and shadow artifact on a 1–5 scale
for directness, coherence, analyst-like writing, and factual fidelity. Any
unknown company/number/date, certainty promotion, or judge rejection is a hard
failure regardless of style score.
