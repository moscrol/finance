# Codex App Server Spec v3 Independent Review

Date: 2026-07-29
Reviewed commit: `b1318e00`
Reviewer: fresh ephemeral read-only `gpt-5.6-sol` Codex CLI process
Verdict: `PASS`

## Closed findings

The reviewer found no remaining P0/P1 issue and confirmed testable fail-closed
contracts for:

- actual execution identity and `fast_mode` observation;
- worst-case quota admission before initial and retry attempts;
- ordered write-once EvidenceLedger with a bound final seal;
- deterministic leakage scanning with frozen normalization, thresholds, and
  positive/negative fixtures.

## Authorization boundary

This PASS authorizes planning and implementation of the curated instruction
export, physical PIT fixture, isolation preflight, and five-case same-fixture
profile-D headless control.

It does not authorize App Server runner code or live App Server execution. The
current 0.146.0 protocol lacks provider-response fields proving actual executed
model/provider/reasoning/service tier and is therefore
`execution_identity_unobservable`.

## Next hard gates

Runner code requires both:

1. a sealed valid five-case same-fixture profile-D headless control;
2. a newly pinned protocol or separately reviewed provider receipt exposing the
   actual executed identity fields.

Live App Server execution additionally requires sealed export/PIT manifests,
all deterministic isolation/preflight tests, five frozen blind projections,
quota radius, label commitment, provider/auth identity, and output paths before
the first App Server answer.
