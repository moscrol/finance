# Final Goal Live Execution Gate Audit

Date: 2026-07-29
Status: frozen execution environment prepared; live model transport externally blocked

## What was attempted

Only non-acceptance readiness checks were attempted. No frozen finance question was executed and
none of the A/B/C/D artifact paths was written.

### Direct local Codex CLI

Command identity:

```text
binary: /Applications/ChatGPT.app/Contents/Resources/codex
version: codex-cli 0.146.0-alpha.3.1
model: gpt-5.6-sol
mode: ephemeral, read-only, non-financial prompt
```

The process failed before a provider response. The managed shell could not write
`~/.codex/state_5.sqlite`, then in-process App Server initialization returned
`Operation not permitted`. This is an environment failure, not a semantic-judge result.

### Local-exec route

`lsof` intermittently observed a Python listener on `*:28080`, but the managed shell could not
connect to `/api/ping` and had no ambient `CC_EXEC_TOKEN`. The in-app browser independently
refused access to `127.0.0.1:28080` under its security policy and explicitly prohibited an
alternate-browser or indirect workaround. Terminal and Ghostty UI control are also prohibited
by the desktop-control policy.

Therefore the preregistered `local_exec` transport is not legally usable from this task even
when a host listener is visible.

### VPS fallback

The configured VPS could have run a non-data `gpt-5.6-sol` probe, but this managed shell rejected
the SSH connection with `Operation not permitted`. The VPS also cannot substitute for the local
A/B/C/D experiment because it does not have the frozen local finance and true-Hybrid Wiki roots.

## Frozen experiment readiness

A detached worktree now exists at the exact preregistered source revision:

```text
/Users/a77/finance-workspace-private/tmp/headless-ablation-803367f1
HEAD 803367f16c90cf3b0a0526d4224e4acb55a7a79d
working tree clean
```

The input remains byte-identical:

```text
/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json
SHA-256 bec6d6944ced127166bd41cb80a09a9f9fb0d816e45cee3be13a900bda2966fe
```

All four frozen live artifact paths remain absent. No subprocess transport, dry-run artifact,
newer source revision, different Wiki root, or different model was substituted.

## Decision

The final goal remains active. The next live action is still A→B→C→D through the legal
`local_exec` route when the execution environment exposes it. Until then, offline work may
prepare evaluators and immutable evidence, but it must not:

- infer answer quality from these infrastructure failures;
- implement App Server before profile D provides a fair control;
- run the 28-case board without the preregistered non-zero release policy;
- weaken cutoff, freshness, evidence lineage, invalid-action, or semantic gates.
