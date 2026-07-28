# Acceptance Verdict Seam Verification

Date: 2026-07-29
Status: deterministic seam complete; no live acceptance questions executed

## Provenance

- Branch: `feat/agent-runtime-backends-verify`
- Design/plan commit: `77f7bb5a`
- Implementation commit: `b77e84ec`
- Python: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`
- Canonical case SHA-256 remained
  `a25c68253a92be536b94d2403ffa010b6cd15a20b7eea581450159cb6444a1c6`.
- The canonical 28-case file and all 22 frozen Knevo snapshots were not edited.

## Implemented seam

`intelligence/eval/acceptance_verdict.py` is a pure evaluator with two primary calls:

```python
compile_case_contract(case, overlay)
evaluate_case(contract, case_run)
```

It returns independent immutable verdicts for:

- operational execution: not-run / blocked / failed / degraded / completed;
- deterministic truth: pass / fail / unjudgeable / not-run;
- blind experience: unlabeled / labeled / ineligible.

Missing observations never become passes. Transport failure does not become a truth failure,
and runtime `completed` does not become a truth pass.

The additive overlay
`intelligence/eval/cases/acceptance_verdict_contracts.json` names all 28 cases exactly once.
It records whether each prose `pass_rule` is fully represented by structured checks or still
requires a semantic observation. It does not contain frozen answers or production routes.

Implemented generic deterministic rules cover:

- numeric and literal facts with absolute/percentage tolerances;
- explicit refusal plus required/forbidden text;
- product-language and entity presence;
- citation-tag integrity against minted evidence labels;
- cutoff enforcement using structured citation dates and future realized-claim detection;
- inconsistency disclosure and numeric falsifiability markers;
- conservative multi-turn context-loss detection;
- typed external observations for exact answer sets, inherited golden evaluation, semantic
  pass rules, and blind experience labels.

## Historical calibration

No question was rerun. The evaluator read the committed
`intelligence/eval/runs/20260727T032229Z.json` artifact.

The new board reports:

```text
operational: 18 not run / 0 blocked / 0 failed / 7 degraded / 3 completed
truth:       18 not run / 1 pass / 6 fail / 3 unjudgeable
experience:  28 unlabeled / 0 labeled / 0 ineligible
```

The only mechanically passing historical case is C7 temporal leakage: all four structured
citations are on/before the 2026-07-21 cutoff and the 07-22 language is predictive, not a
realized result.

C1's refusal, required no-data wording, and listed forbidden-phrase checks pass at rule level,
but the overall verdict is intentionally `unjudgeable`: those fields cannot prove the broader
prose requirement that no other market number was fabricated.

C9 remains `unjudgeable`: citation integrity passes vacuously because it emits no invalid tag,
but that does not prove it answered the causal question. C10 fails because the second turn asks
the user to restate context established by the first turn.

The displayed `1/7` is explicitly labeled a **judgeable-subset** rate. It is not a 28-case
product pass rate and is not a release or superiority claim.

## Tests

Focused acceptance/evaluator regression:

```text
67 passed in 0.15s
```

Static checks:

```text
ruff: all checks passed
git diff --check: passed
JSON parse: passed
compileall: passed
```

Full intelligence suite with production path overrides removed:

```text
2981 passed, 14 failed, 2 skipped in 79.49s
```

All 14 failures are the known managed-sandbox loopback restriction:

- 2 tests in `test_codex_headless_runtime.py` cannot bind a local HTTP server;
- 12 tests in `test_headless_tool_gateway.py` cannot bind `127.0.0.1`.

Every failure is `PermissionError: [Errno 1] Operation not permitted` at
`socket.bind()`. None imports or exercises the new verdict module. The previously observed ten
userspace/subconscious failures disappeared when `FORESIGHT_USERS_DIR`,
`SUBCONSCIOUS_VAULT`, and `AGENT_MEMORY_VAULT` were removed from the test environment.

## Honest remaining gaps

- 18 cases have no Workbench run in the latest historical artifact.
- Three historical cases remain unjudgeable rather than being forced into pass/fail.
- Exact-set, inherited `agent_eval`, and prose-quality checks need typed observations from a
  calibrated semantic/blind evaluator.
- The 22 Knevo snapshots have not been normalized into eligible truth/experience labels.
- `aggregate_gate=0.0` remains observational; no non-zero release threshold is registered.
- No live 28-case run, budget ablation, semantic-judge call, App Server run, 8792 cutover, or
  `main`/KB merge occurred.

## Conclusion

The measurement instrument is now materially safer: it can identify deterministic historical
failures without inventing a denominator. This completes the verdict-seam part only. Final
product readiness still depends on fair-budget live evidence, semantic/blind observations,
matched Knevo comparison, and the App Server decision gate.
