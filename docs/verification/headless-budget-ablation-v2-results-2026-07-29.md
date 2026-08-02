# Headless Budget Ablation v2 Results

Date: 2026-07-29
Status: fair control valid; budget diagnosis complete; not a release pass

## Integrity

All four cells ran sequentially from the clean detached source:

```text
source revision da6149084bbebd57820bf499941ef12f93912ef1
source_dirty false
model gpt-5.6-sol
binary codex-cli 0.146.0-alpha.3.1
question SHA-256 bec6d6944ced127166bd41cb80a09a9f9fb0d816e45cee3be13a900bda2966fe
finance root /Users/a77/finance-workspace-private
Wiki root /Users/a77/知识库/wiki
cutoff 2026-07-24
```

Immutable artifact hashes:

| Profile | SHA-256 | Validity | Max executed calls |
|---|---|---|---:|
| A control | `b548d6b07df4f3655ea9fbc8fb40e3077a415b14f2842d566d3ef6c48b866c9b` | exercised | 2 |
| B floor ablation | `2ee7f23cbe5614521197da2e56a7a308bcb7c5416784d91ed6026eaa453603ad` | exercised | 4 |
| C long capped | `7d477a5e1b656616055308082d1897084664df30a421c180f5cf492e294459fa` | exercised | 6 |
| D long expanded | `75a144399068843580b330e2899ebbbc3093cccbc0f5ac9d01e986c95053e898` | exercised | 7 |

Profile D satisfies the preregistered physical-validity gate of at least seven calls.

## Per-case outcomes

The table shows executed tool calls, terminal reason, structural status, and unresolved required
outputs. All public statuses remain `degraded` because no live semantic judge was attached to
the benchmark arm.

| Case | A `90/6/floor` | B `90/6/no floor` | C `180/6/no floor` | D `180/12/no floor` |
|---|---|---|---|---|
| rebound-duration | 1 call; model finish; completed; 0 missing | 3; timeout; partial; 5 missing | 3; model finish; completed; 0 missing | 5; model finish; completed; 0 missing |
| ruihuatai-valuation | 2; model finish; partial; `scenario_range` missing | 4; timeout; partial; 5 missing | 5; model finish; completed; 0 missing | 4; model finish; completed; 0 missing |
| weekly-market-cause | 1; model finish; partial; `cause_attribution` missing | 3; timeout; partial; 5 missing | 6; model finish; partial; `evidence_boundary` + `cause_attribution` missing | 7; model finish; partial; `cause_attribution` missing |

Every model-finish cell bound five required-output evidence groups and had zero future-of-cutoff
items. Timeout cells had evidence but no final bindings, which is why operational completion and
answer truth remain separate.

## Preregistered pairwise interpretation

### A → B: the 65% floor is protective at 90 seconds

Removing the floor did not improve any case. It changed all three from model-finish delivery to
`headless_timeout` after 3–4 calls. The model used the remaining research window but had no time
to emit the terminal envelope.

The prior hypothesis that the floor/double reservation was the primary quality defect is
rejected for this exact binary and fixed transport. At the quick 90-second profile, the floor is
a synthesis/delivery guard.

### B → C: wall-clock room is causal

Keeping the six-call cap and floor disabled while increasing total time to 180 seconds restored
model finish for all three cases. Rebound and valuation became structurally complete. Weekly
causality remained partial because external-cause evidence was still unavailable.

This is the strongest result: the product needs an explicit deep-latency contract rather than a
single 90-second envelope.

### C → D: the six-call cap is secondary

D physically exercised seven calls and is valid. Only weekly causality crossed the old cap. It
reduced missing outputs from two to one, but still could not produce `cause_attribution`.
Rebound and valuation were already structurally complete under C; extra call room added no
material completion gain.

Therefore the six-call cap can constrain a difficult causal task, but it is not the primary
cross-case failure mechanism.

## Tool-efficiency evidence

Repeated same-tool request rate increased as the envelope expanded:

| Case | A | B | C | D |
|---|---:|---:|---:|---:|
| rebound-duration | 0% | 0% | 0% | 40% |
| ruihuatai-valuation | 0% | 0% | 0% | 0% |
| weekly-market-cause | 0% | 50% | 50% | 57% |

This is not exact-query duplication: the artifacts report `duplicate_queries=0`. It is repeated
capability use with different queries. Several extra calls were empty, stale, parse-error, or
request-error rather than new evidence.

Observed shared gaps:

- `news_search` returned `request_error` on every weekly-cause attempt;
- valuation `evidence_lookup`, `kb_search`, `web_search`, or `evidence_search` remained empty;
- longer profiles exposed invalid date-filter syntax and stale structured-query branches;
- D weekly gained more structured market/sector evidence but still had no time-aligned external
  cause evidence.

The remaining bottleneck is therefore tool result availability/quality plus model stopping and
query repair, not a generic request for more calls.

## Product and App Server decision

This experiment does not make the current headless lane release-green: all arms remain degraded,
semantic truth is unjudged, and the causal case still lacks external attribution.

It does satisfy the App Server v2 prerequisite of a physically valid fair same-model profile-D
control. App Server implementation is not automatically justified: the v2 ceiling spec still
requires independent review, physical PIT isolation, and a blind decision rule. The controlled
result says the ceiling experiment should distinguish native harness value from the now-proven
tool-result and latency limitations.

No prompt, case, tool contract, cutoff, verifier, or production route was changed between v2
cells. Main, 8792, and KB merge boundaries remain untouched.
