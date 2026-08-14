# Acceptance Verdict Seam Design

Date: 2026-07-29
Status: approved by the existing canonical handoff and the user's no-human-loop authorization

## 1. Goal

Turn the existing 28-case acceptance assets into a reproducible measurement seam without
pretending that an answered turn, a completed runtime status, or a missing observation is a
quality pass.

This slice does not run the 28 live cases, change any frozen reference answer, set a non-zero
aggregate gate, or compare App Server quality. It builds the measurement instrument required
before those actions are meaningful.

## 2. Existing facts

- `intelligence/eval/acceptance.py` records real Conversation API runs and prints operational
  progress. It intentionally does not calculate a pass rate.
- The two historical run artifacts contain answers and traces but no `passed` field.
- `acceptance_cases.json` contains structured fields such as `expect_facts`, tolerances,
  `expect_refusal`, forbidden phrases, future-data and citation checks, plus prose
  `pass_rule` requirements.
- `agent_eval.py` is valid for three inherited theme golden cases. It is not a generic scorer
  for numerical tolerances, refusal, cutoff safety, or multi-turn consistency.
- The 22 Knevo snapshots have case-specific eligibility and caveats. They are not a uniform
  truth oracle.

## 3. Alternatives considered

### A. Add regex checks directly to the board

This is small initially but shallow: the board would own contract compilation, text parsing,
truth aggregation, display, and file I/O. A number appearing anywhere in prose could be
mistaken for a correctly attributed fact. Rejected.

### B. Use an LLM judge for every case

This can interpret prose but is non-deterministic, provider-dependent, and currently blocked
for the live semantic-judge lane. It is suitable later as an explicitly separate semantic
observation adapter, not as the deterministic truth foundation. Rejected for this slice.

### C. Typed contract compiler with fail-closed observations

Chosen. A pure module compiles the case schema into typed checks, evaluates only observations
that are actually present, and returns `pass`, `fail`, `unjudgeable`, or `not_run`. The board is
only an adapter that loads JSON and renders the result.

## 4. Module and seam

Create `intelligence/eval/acceptance_verdict.py` as a deep module with two public functions:

```python
compile_case_contract(case: Mapping[str, Any], inherited: CaseSpec | None = None) -> CaseContract
evaluate_case(contract: CaseContract, case_run: Mapping[str, Any] | None) -> CaseVerdict
```

The interface stays small. Compilation, deterministic extraction, rule accounting, and
aggregation remain implementation details.

The public immutable result types are:

- `OperationalVerdict`: whether the product path ran, completed, degraded, or failed;
- `TruthVerdict`: deterministic rule results and coverage;
- `ExperienceVerdict`: an empty or externally supplied blind label, never inferred from truth;
- `CaseVerdict`: the three axes for one case.

Truth uses four states:

- `pass`: every compiled hard truth rule is observed and passes;
- `fail`: at least one observed hard rule fails;
- `unjudgeable`: no hard failure exists, but one or more required rules lack a trustworthy
  observation or remain prose-only;
- `not_run`: no case run exists.

There is no fallback from `unjudgeable` to `pass`.

## 5. Contract compilation

The canonical case file remains byte-identical. A separate additive overlay,
`intelligence/eval/cases/acceptance_verdict_contracts.json`, records whether each prose
`pass_rule` is fully represented by the existing structured fields or still requires an
external semantic observation. This avoids rewriting the frozen question suite while making
coverage explicit and versionable.

The compiler translates current fields plus that overlay into generic rule types:

| Case field | Typed rule |
|---|---|
| `expect_facts` + tolerances | numeric or literal fact rule |
| `expect_refusal` | explicit unavailable/refusal rule |
| `forbid_phrases` | forbidden text rule |
| `forbid_future_data` + `date` | cutoff rule over bound citation dates and dated factual claims |
| `check_citation_registry` | citation-tag integrity rule |
| `expect_answer_set` / `exact_set` | answer-set rule |
| `require_flag_inconsistency` | inconsistency-disclosure rule |
| `require_falsifiable` | falsifiable-condition rule |
| `check_cross_turn_consistency` | multi-turn consistency rule |
| `inherit_from` | inherited `agent_eval` rule |
| `pass_rule` | prose requirement ledger entry |

`pass_rule` is never discarded. Where its meaning is fully represented by structured rules,
the overlay marks it `structured`. Otherwise it remains a required semantic rule with no
observation, forcing `unjudgeable`. The overlay may add generic text requirements such as
`required_any_phrases`; it may not add per-case production routes, answer templates, or frozen
answers. This prevents C9 citation integrity, for example, from passing merely because it
emitted no invalid citation while failing to answer the causal question.

The first implementation may conservatively leave semantic rules unjudgeable. It must not
invent case-specific answer routes or templates to make coverage look complete.

## 6. Deterministic observations

The run adapter may derive only evidence-backed observations:

- terminal status, error and degradation from the trace;
- explicit unavailable language from answer text using a small domain-independent vocabulary;
- forbidden phrase occurrence;
- numeric literals compared to expected values and tolerances;
- citation dates from structured `citations[]`;
- cited tags from answer text and minted tags from structured evidence labels;
- all-turn text required by generic consistency checks.

Absence of a structured observation is not evidence of correctness. `invoked_skill_ids` must
not be relabeled as tool calls. Exact answer-set exclusion, semantic contradiction disclosure,
and inherited golden scoring remain unjudgeable unless their required typed inputs exist.

## 7. Aggregation and board behavior

The board keeps its current operational tally. It gains truth columns and a summary with
separate denominators:

- operational: run/completed/degraded/failed/not-run;
- truth: pass/fail/unjudgeable/not-run;
- experience: labeled/unlabeled.

The board must not print a product pass rate until at least one truth verdict exists, and any
rate must use only explicitly eligible, judged cases while also printing the unjudgeable and
not-run counts. `aggregate_gate=0.0` remains observational.

## 8. Historical calibration

Calibration uses the two existing run files only. No live question is executed.

Required worked examples:

- C1: explicit no-data response passes refusal and forbidden-phrase checks;
- C7: bound citations do not exceed the 2026-07-21 cutoff and the answer stays predictive;
- C9: citation integrity alone may pass, but the overall truth verdict remains unjudgeable
  because the causal-answer requirement is not structurally observed;
- C10: three completed turns do not imply consistency; without a trustworthy set/count
  observation the result is unjudgeable, not pass.

## 9. Error handling

- Unknown contract fields are preserved in diagnostics, not silently ignored.
- Invalid tolerances or malformed run data produce an explicit contract/evaluation error and
  an unjudgeable truth verdict.
- A transport failure remains operational failure; it does not become a truth failure.
- A deterministic hard violation may fail truth even when runtime status is `completed`.
- A degraded but honest refusal may pass a refusal truth rule while remaining operationally
  degraded.

## 10. Testing seam

Tests cross only `compile_case_contract` and `evaluate_case` plus the public board command.
They use literal case/run fixtures and assert:

- operational and truth states never collapse into one another;
- missing evidence yields `unjudgeable`;
- tolerance boundaries are deterministic;
- future structured citations fail the cutoff rule;
- dangling citation tags fail while no-tag answers are only vacuously clean for that rule;
- unrepresented prose keeps the overall verdict unjudgeable;
- historical run calibration is stable;
- the existing 28 cases and frozen references remain byte-identical;
- the overlay names all 28 cases exactly once and cannot silently claim `structured` coverage
  while leaving a prose requirement unrepresented.

## 11. Non-goals

- no LLM judge call;
- no 28-case live run;
- no blind experience scoring UI;
- no App Server implementation;
- no mutation of frozen Knevo snapshots;
- no change to production runtime gates, 8792, `main`, or KB commit `9053b0c4`.

## 12. Completion criteria

This slice is complete when:

1. every case compiles without silently losing a field;
2. the four-state truth contract is covered by focused tests;
3. historical traces produce reproducible, honest verdicts;
4. the board reports operational, truth, and experience axes separately;
5. focused and relevant full regression suites pass;
6. a handoff records what is mechanically judged and what remains unjudgeable.
