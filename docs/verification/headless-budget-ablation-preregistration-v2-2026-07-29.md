# Headless Budget Ablation Preregistration v2

Date: 2026-07-29
Status: preregistered after transport-only correction; no v2 answer inspected

## Why v2 exists

The original four live artifacts did not exercise the registered budget treatment. All twelve
cells selected the authorized `finance-tool`, but nested Codex `read-only` sandboxing denied the
wrapper's loopback connection before any tool completed.

The defect is fixed in source commit:

```text
da614908d6a3209398e12d88bb134c84f6608200
fix: allow isolated local exec tool loopback
```

The fix changes only the local-exec child sandbox contract:

- ephemeral cwd uses `workspace-write`;
- loopback network is explicitly enabled;
- ambient `$TMPDIR` and `/tmp` writable roots are excluded;
- finance and Wiki roots remain read-only;
- no `danger-full-access`, extra writable root, prompt, tool, verifier, or budget change.

The least-privilege probe and single-case red/green evidence are recorded in
`docs/verification/headless-local-exec-loopback-seam-2026-07-29.md`.

## Invalid v1 receipts preserved

These files remain immutable failure receipts and must not enter the A/B/C/D interpretation:

```text
a-control        c2cfc3065bfb1468718c639aea5b3081b545dd534762853a34cb25fafe70a4dc
b-floor          10585947e58139dce306fb32c402a09a99bd4272d5165ff1cb1c54cd2cb987f4
c-long-capped    5917bba3b7ba7d523165a73844988df2294228059feb5a4cd7962bcf430d52e0
d-long-expanded  aa81f74d03bde4a1d5707858b3baf46667c9d478bf10321b27771ade8d3643f0
```

Each has zero tool calls and protocol rejection. D is
`invalid_not_physically_exercised`.

## Frozen v2 identity

- Source revision: `da614908d6a3209398e12d88bb134c84f6608200`.
- Source requirement: clean detached checkout of that exact revision.
- Question file:
  `/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json`.
- Question SHA-256:
  `bec6d6944ced127166bd41cb80a09a9f9fb0d816e45cee3be13a900bda2966fe`.
- Selected cases, source order: `rebound-duration`, `ruihuatai-valuation`,
  `weekly-market-cause`.
- Finance root: `/Users/a77/finance-workspace-private`.
- Wiki root: `/Users/a77/知识库/wiki`.
- Per-case cutoff: `2026-07-24`.
- Binary: `/Applications/ChatGPT.app/Contents/Resources/codex`.
- Binary version: `codex-cli 0.146.0-alpha.3.1`.
- Model: explicit `gpt-5.6-sol`.
- Transport: authenticated `local_exec` through port 28080.
- Route token remains process-only and may not enter Git, commands, or artifacts.

## Frozen profiles

| ID | Total | Tool calls | Synthesis reserve | Gateway ratio | Validity |
|---|---:|---:|---:|---:|---|
| `a_control` | 90s | 6 | 30s | 0.65 | exercised when run completes |
| `b_floor_ablation` | 90s | 6 | 30s | 0.0 | exercised when run completes |
| `c_long_capped` | 180s | 6 | 30s | 0.0 | exercised when run completes |
| `d_long_expanded` | 180s | 12 | 30s | 0.0 | valid only with at least 7 observed calls |

The interpretation remains exactly the original preregistration:

- A→B isolates the dynamic floor;
- B→C isolates added wall-clock room at the same six-call cap;
- C→D isolates the call cap;
- repeated calls without new evidence indicate tool-result or stopping/progress failure;
- D below seven calls is invalid, not a quality loss;
- truth violations cannot be offset by prose quality.

## Frozen v2 artifact paths

```text
/Users/a77/.finance-runtime/evals/headless-budget-ablation-2026-07-29-v2-a-control.json
/Users/a77/.finance-runtime/evals/headless-budget-ablation-2026-07-29-v2-b-floor-ablation.json
/Users/a77/.finance-runtime/evals/headless-budget-ablation-2026-07-29-v2-c-long-capped.json
/Users/a77/.finance-runtime/evals/headless-budget-ablation-2026-07-29-v2-d-long-expanded.json
```

Run sequentially A→B→C→D. Do not inspect answers, tune prompts, change roots, or modify gates
between cells. No confirmation rerun is authorized unless the frozen decision would otherwise
change, and any confirmation must use a new filename and the same source/configuration.

## Decision boundary

The App Server experiment remains blocked until v2 profile D is valid. If v2 still fails before
tool execution, diagnose the shared transport seam and preregister again; never interpret an
infrastructure failure as evidence for or against the budget hypothesis.
