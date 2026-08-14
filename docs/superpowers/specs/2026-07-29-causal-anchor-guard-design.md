# Causal Anchor Guard Design

Date: 2026-07-29
Status: approved through the user's instruction to execute the reviewed causal
handoff without another human gate

## Objective

Make generic market-causal evidence search fail closed when it lacks a safe
topic anchor or evidence from the requested market window. The fixed regression
is:

```text
这一周行情下跌的主要原因是什么
cutoff=2026-07-24
```

The result must not promote company/topic terms from approximate first hits,
and no target-week evidence or no target-window counter-evidence must prevent
`success`.

This slice also makes a non-executed `budget_exhausted` attempt mechanically
different from a healthy non-degraded attempt.

## Verified failure chain

The current drift is not caused by one bad stopword list:

1. `_narrow_queries` adds `实体 代码` and `公司 题材` variants when no entity
   anchor exists.
2. `_extract_terms` harvests arbitrary company/topic terms from the first five
   approximate hits.
3. `_broad_queries` and `_counter_queries` splice those terms into the original
   question.
4. `_relevance_terms` expands short generic Chinese terms into 2-grams, so a
   sell-side page can satisfy overlap without being a causal source for the
   requested week.
5. `EvidenceSearch` marks any non-empty projected evidence as `success`, even
   when target-window evidence and counter-evidence are both absent.

True Hybrid changes which wrong branch wins but does not repair the chain:
BM25 drifts to 牧原/猪周期; Hybrid drifts to 半导体/光纤光缆.

## Alternatives

### A. Expand `_GENERIC_TERMS` and tighten 2-gram matching

Rejected. A stoplist cannot enumerate every company/concept in the Wiki, and
the first-hit premise promotion remains structurally possible.

### B. Disable first-hit term promotion only

This prevents the known topic pivots but still lets off-window, zero-counter
evidence report `success`. It fixes retrieval strategy but not the delivery
contract, so it is incomplete.

### C. Typed causal policy controlling expansion and completion

Selected. An explicit `EvidenceSearchPolicy` tells the generic retrieval module
when it must stay query-only and what source window/counter coverage is required
for success. Defaults preserve all non-causal callers.

## Types and interfaces

### Retrieval execution state

`RetrievalAttempt` gains:

```python
executed: bool = True
```

Real retrieval responses remain `True`. The budget guard creates an attempt
with `executed=False`; its empty mode fields and `degraded=False` now mean
"not executed", not "healthy Hybrid". Inspector serialization includes the
field. Trace mode aggregation continues to skip attempts with no executed
retrieval telemetry.

### Expansion policy

`closed_loop_retrieval` defines:

```python
RetrievalExpansionPolicy = Literal["anchor_or_hits", "query_only"]
```

`retrieve_closed_loop(..., expansion_policy="anchor_or_hits")` remains backward
compatible. Under `query_only` with `anchor=None`:

- narrow uses only the original query;
- broad uses stable market-mechanism suffixes, not hit-derived terms;
- counter uses stable counter/alternative-explanation suffixes;
- hit terms never enter relevance expansion or later queries.

An explicit `EntityAnchor` keeps the existing anchored behavior even if a
caller accidentally supplies `query_only`; a known subject is safer than
guessing from approximate hits.

### Evidence-search policy

`evidence_search` adds an immutable policy:

```python
@dataclass(frozen=True)
class EvidenceSearchPolicy:
    expansion_policy: RetrievalExpansionPolicy = "anchor_or_hits"
    required_source_start: date | None = None
    required_source_end: date | None = None
    require_counter_evidence: bool = False
```

The default preserves current valuation/theme behavior. Episode composition
passes a causal policy only when the research contract profile is
`time_aligned_market_causal`.

## Target window

`episode_tools` already computes `market_window_end`. It additionally computes
`market_window_start`:

1. use an explicit date in `frame.timeframe` when present;
2. otherwise use Monday of the calendar week containing `market_window_end`.

For the fixed case the window is `2026-07-20..2026-07-24`. For the historical
fixture `2026年7月1日至5日` with timeframe `2026-07-01`, it is
`2026-07-01..2026-07-05`.

Compact `YYYYMMDD` dates in Wiki paths are parsed in addition to ISO dates.
Yearless `MMDD` filenames remain unknown and cannot satisfy a required window.

## Evidence projection and status

When a required window exists, off-window or undated entries do not enter the
model observation. Coverage records:

- `target_window_count`;
- `target_window_counter_count`;
- `window_rejected_count`.

Gaps are explicit:

- no target-window evidence;
- no target-window counter-evidence.

Provider status becomes:

- `success`: evidence exists and every policy requirement is met;
- `partial`: some target-window evidence exists but a required counter is
  missing;
- `empty`: no policy-eligible evidence exists;
- `future_of_cutoff`: unchanged when future rejection is the relevant terminal
  condition.

`partial` is added to the typed `ProviderStatus`; using `fallback_success` would
misrepresent a contract gap as a provider fallback.

## Data flow

```text
TaskFrame + ResearchContract
  -> episode_tools computes causal source window
  -> EvidenceSearchPolicy(query_only, window, require_counter=True)
  -> retrieve_closed_loop runs query-only apertures
  -> cutoff filter rejects future hits
  -> source-window filter rejects old/undated hits
  -> coverage/gaps evaluate target-window counter evidence
  -> trace status success | partial | empty
```

Freshness, cutoff, content hashes, evidence lineage, semantic judge ordering,
and per-attempt mode telemetry remain unchanged.

## Tests

Tests must prove:

1. budget-exhausted attempts serialize `executed=false`; healthy Hybrid
   attempts serialize `executed=true`;
2. query-only retrieval never emits `实体 代码`/`公司 题材` variants and never
   copies 牧原、猪周期、半导体 or 光纤光缆 from first hits;
3. explicit entity anchors retain anchored expansion;
4. compact `YYYYMMDD` dates are parsed, yearless dates are not guessed;
5. off-window-only causal evidence yields no observation and not `success`;
6. target-window support without counter yields `partial`;
7. target-window support plus counter yields `success`;
8. the Episode registry applies `2026-07-20..2026-07-24` and query-only policy
   to the fixed market-causal frame;
9. existing valuation/theme and cutoff tests remain green.

All finance tests use
`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`; do not use
`/usr/bin/python3` 3.9.

## Non-goals and guardrails

- No valuation entity filtering in this slice.
- No semantic-judge tuning or verifier relaxation.
- No cross-repo merge of KB commit `9053b0c4`.
- No index rebuild, 28-case run, App Server work, main merge, or 8792/8799
  promotion.
- No generated access logs, venvs, weights, indexes, secrets, or databases are
  committed.
