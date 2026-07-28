# SDK Delivery and Semantic Deadline Verification

Date: 2026-07-28
Branch: `feat/agent-runtime-backends-verify`
Live-source product revision: `7e91f74b9bd1b45c6fa8c551dc258660011cf821`
Baseline artifact revision: `8f417fe25cd57cb874bf52706323b927c4d497d6`

## Live evidence that selected the seams

The clean five-case artifact at the baseline revision passed two cases. The
remaining traces showed shared execution failures:

- valuation obtained `market_data` and `financial_data`, then called three
  optional tools and exhausted the 60-second SDK window;
- weekly cause obtained `market_data` and `news_search`, then repeated news,
  issued and repaired a typed finance query, called web search, and exhausted
  the same window;
- current mainline produced a structurally completed and useful answer after
  two mandatory tools, but semantic provider attempts consumed the outer
  deadline and released it as partial/unavailable.

No additional live questions were used while debugging.

## Implemented invariants

1. Every evidence-bearing SDK tool result reports the exact still-missing
   mandatory capabilities.
2. When all mandatory capabilities have contributed new evidence, the same
   tool result publishes `mandatory_evidence_complete=true` and a model-visible
   instruction to bind evidence and finish. Optional checks remain available.
3. A standard 60-second SDK run closes research tools after about 45 seconds
   and reserves about 15 seconds for terminal delivery in the same invocation.
4. Tool closure returns typed `research_stage_closed`, never a public gap.
5. Semantic provider retries share at most 30 seconds. The default release-safe
   transient schedule is `15 + 7.5 + 7.5`, replacing `25 + 25 + 25` while
   preserving the existing third-attempt recovery path.
6. Structural and semantic pass predicates are unchanged. Mandatory evidence
   must still be bound into the final answer; authentication, malformed output,
   contract errors, and weak transient classifications remain fail-closed.

## TDD evidence

Three public-seam regressions were observed red before implementation:

- mandatory capability progress was absent from model-visible tool results;
- an optional tool remained open after the intended delivery boundary;
- three semantic transient attempts each claimed 25 seconds (75 seconds total).

After implementation:

```text
OpenAI Agents runtime: 28 passed, 1 skipped
Semantic verifier: 144 passed
Focused runtime/API/adapter/orchestrator composition: 540 passed, 1 skipped
Executable intelligence suite: 2919 passed, 1 skipped
```

The full executable suite unsets host-level userspace/vault overrides and
excludes only two sandbox-incompatible files that bind localhost sockets:
`test_codex_headless_runtime.py` and `test_headless_tool_gateway.py`.

Static checks:

- Ruff on all four changed Python files: pass;
- `git diff --check`: pass;
- risk-file scan: empty;
- no question-specific route or tool was added;
- `episode_verifier.py` was not modified.

## Review judgement

The implementation keeps decision rights in the model: mandatory evidence does
not immediately close tools, and the runtime does not synthesize or auto-pass
an answer. The runtime exposes contract progress and enforces an execution
boundary; the model chooses whether an optional contradiction check is worth
the remaining research window.

The semantic implementation deliberately preserves the third release-safe
retry. Removing it would reduce recovery probability and contradict existing
regression coverage. Bounding the aggregate timeout instead solves the live
tail-latency failure without relaxing the gate.

## Live release gate

The frozen live command was attempted from the Codex process and stopped before
case 1 because macOS Keychain denied that application identity access to the
saved provider. No model call was made and no benchmark artifact was produced.
The same account is accessible from the user's already-authorized Terminal,
which produced the baseline artifact. This is an application-level credential
ACL boundary, not a runtime quality result.

Therefore the candidate remains `offline_green; live_release_pending`. Do not
fast-forward the formal runtime, merge `main`, or switch 8792/8799 until the
exact frozen revision produces a 5/5 hard-gate artifact from the authorized
Terminal process.
