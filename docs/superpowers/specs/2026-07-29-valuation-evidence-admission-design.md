# Valuation Evidence Admission Design

Date: 2026-07-29
Status: approved by the user's instruction to continue the final goal without a
human gate

## Objective

Prevent an entity-anchored valuation search from presenting bare Wiki
co-occurrence as valuation evidence. The fixed regression is 瑞华泰 valuation
under the pinned true-Hybrid index, where `天奈科技` and `方邦股份` currently
enter the model evidence even though their retrieved chunks contain no valuation
fact about 瑞华泰.

The deterministic filter runs before the semantic judge. It must reduce judge
cost and exposure without replacing the judge's responsibility for nuanced
entailment.

## Verified failure

The direct true-Hybrid probe used `瑞华泰 估值` and returned ten fresh hits.
`neighbor_hits=0`; the two known contaminants both have `via_neighbor=false`.
The failure is therefore not graph-neighbor expansion.

- `天奈科技.md::3` contains only a related-entity list ending in `[[瑞华泰]]`.
- `方邦股份.md::6` says `[[瑞华泰]] — PI薄膜企业，同属功能薄膜赛道`.
- multiple concept/digest chunks contain 瑞华泰 only inside long entity lists.

Dense similarity and fragmented terms (`华泰`, `瑞华`, `泰估`) make those pages
retrieval candidates. Candidate recall is working as designed; the missing seam
is evidence admission.

## Alternatives

### A. Allow only files whose path/title names the subject

This is safe for the known case but rejects legitimate comparable-company or
supply-chain evidence. It also hard-codes storage layout into business meaning.

### B. Add more query terms or similarity thresholds

Rejected. RRF scores are close (`0.195625..0.176101`), and a single global
threshold would remove relevant concept/source chunks together with pollution.
Query terms also cannot distinguish a bare entity list from a stated relation.

### C. Typed provenance-local admission

Selected. For explicitly anchored valuation searches, classify every retrieved
chunk as `direct`, `relation_clue`, or `reject` from the local chunk text and
source identity. The semantic judge receives only direct candidates. Explicit
relations remain auditable clues; bare co-occurrence is discarded.

## Policy and interface

Extend the immutable `EvidenceSearchPolicy` with:

```python
anchor_admission: Literal["open", "subject_local"] = "open"
```

`open` preserves all existing callers. `subject_local` has an effect only when
an `EntityAnchor` exists. The Episode composition root sets it only for
`valuation_current_anchor`; causal, theme, stock-deep-dive, and unanchored calls
remain unchanged.

No company name or file path is placed in an allowlist.

## Admission rules

Build the searchable body from `llm_evidence`, falling back to
`display_excerpt` and `excerpt`. Keep source identity separate from body text.
Recognize both the full ticker and its six-digit raw code.

### Direct

A hit is direct when either:

1. its title or file path identifies the anchored entity/ticker; or
2. its body identifies the anchored entity/ticker and also contains a
   valuation assertion cue such as `估值`, `市值`, `PE`, `PB`, `PS`, `EV`,
   `可比估值`, `目标价`, `合理价格`, or a valuation multiple.

Direct conclusion/counter hits remain eligible for semantic judging and model
projection.

### Relation clue

A non-direct hit is a relation clue only when its body identifies the anchored
entity/ticker and states an explicit relation such as `同属`, `可比公司`, `同行`,
`竞争`, `上游`, `下游`, `供应商`, `客户`, `替代`, or `产业链`.

Relation clues move to `ClosedLoopRetrievalResult.clues`. They do not enter the
model evidence and cannot satisfy counter coverage, but they remain visible for
inspection and future query planning. A section heading such as `相关实体` or a
separator-delimited `[[公司]]` list is not by itself an explicit relation.

### Reject

All other non-direct hits move to `discarded`. This includes long entity lists,
bare Wiki links, similarly named companies, and chunks with no anchored identity.

Diagnostics record direct, clue, and rejected counts. Attempts, retrieval mode,
freshness, cutoff decisions, content hashes, and original hit provenance stay
unchanged.

## Data flow

```text
true-Hybrid candidate recall
  -> cutoff filter
  -> narrow/broad/counter buckets
  -> subject-local deterministic admission
       direct -> semantic judge -> model evidence
       explicit relation -> clue ledger only
       bare co-occurrence -> discarded
  -> any source-window policy
  -> EvidenceSearchResult + ProviderTrace
```

Admission precedes the semantic judge so deterministic rejects do not consume
LLM context or API budget.

## Fixed expectations

For the pinned 瑞华泰 replay:

- direct 瑞华泰 pages remain eligible;
- `天奈科技.md::3` is rejected;
- `方邦股份.md::6` is preserved as a relation clue, not model evidence;
- bare concept/digest entity lists do not enter model evidence;
- a synthetic comparable chunk that says 瑞华泰 and 方邦股份 are comparable and
  includes a PB/PE valuation assertion remains direct;
- every executed attempt remains true Hybrid in live replay.

## Semantic judge replay

First prove the ordering with a deterministic capture judge: it must never see
the rejected or clue-only candidates. Then attempt the configured live semantic
judge with the already configured provider. If provider credentials or the local
proxy are unavailable, record `blocked_external` and do not ask the user for a key
inside this loop; deterministic admission and all offline gates remain valid.

A semantic pass may reject more candidates but may not restore deterministic
rejects or clues to model evidence.

## Tests

Public seams:

1. `EvidenceSearch.search` keeps subject pages and rejects bare cross-entity
   co-occurrence under `subject_local`.
2. It demotes an explicit non-valuation relationship to `clues` and keeps it out
   of evidence/counter coverage.
3. It admits an external comparable chunk with a direct valuation assertion.
4. Default `open` behavior is unchanged.
5. `EpisodeToolRegistry.execute("evidence_search", ...)` applies
   `subject_local` only to valuation contracts.
6. A capture semantic judge sees only deterministically direct candidates.
7. The pinned true-Hybrid replay excludes 天奈科技/方邦股份 from model evidence
   without degradation.

## Non-goals and guardrails

- Do not change ranking weights, embeddings, the KB index, or knowledge files.
- Do not make filename-only, company-specific, or score-threshold allowlists.
- Do not relax semantic verification or valuation financial anchors.
- Do not merge KB commit `9053b0c4`, touch `main`, 8792/8799, run 28 cases, or
  implement App Server in this slice.
- Do not commit generated access logs, model weights, venvs, secrets, databases,
  or index artifacts.
