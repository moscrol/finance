# Codex App Server Spec v2 Verification

Date: 2026-07-29
Status: all prior findings represented; no implementation or live run authorized

## Inputs

- Independent `CHANGES_REQUIRED` findings preserved in canonical handoff §9.
- Local binary:
  `/Applications/ChatGPT.app/Contents/Resources/codex`,
  `codex-cli 0.146.0-alpha.3.1`.
- Protocol generated read-only with:

  ```text
  codex app-server generate-json-schema --experimental
  ```

- Generated v2 bundle SHA-256:
  `bde4852a9f8ef55564c1998621f2d7104eae17b58956ab160b7303cc60e5b69b`.

The official Codex manual helper was attempted first but could not resolve
`developers.openai.com` inside the managed sandbox. OpenAI Docs MCP was not installed, and no
global MCP configuration was changed merely to review a local protocol. The exact binary's
generated schema is therefore the executable protocol source for this revision.

## Finding coverage

| # | Required correction | v2 section |
|---:|---|---|
| 1 | Physical PIT root and lookahead audit | §5 |
| 2 | Isolated Codex config/home | §7 |
| 3 | Controlled read/write radius | §6 |
| 4 | Preregistered artifacts and decision rule | §12–13 |
| 5 | Fair Codex-headless primary control | §4 |
| 6 | Explicit `standard -> medium` mapping | §8 |
| 7 | Structured source lineage and numeric audit | §9 |
| 8 | Existing redaction and self-excluding hash | §12 |
| 9 | Typed transport/terminal error handling | §11 |
| 10 | One complete server-request dispatcher | §10 |
| 11 | Dedicated stdio child only | §6 |
| 12 | Quota and state radius | §11–12 |
| 13 | Instruction-conflict metric | §12 |

## Protocol facts newly verified

- `thread/start` exposes `allowProviderModelFallback`, `runtimeWorkspaceRoots`, `sandbox`,
  `approvalPolicy`, `dynamicTools`, `environments`, and `ephemeral`.
- `turn/start` exposes explicit model, effort, sandbox policy, approval policy, workspace roots,
  environment selection, and output schema.
- `currentTime/read` requires a whole-Unix-seconds `currentTimeAt` response.
- The server-request union includes current-time, approvals, permissions, user input, MCP
  elicitation, dynamic tools, token refresh, attestation, and legacy approval requests.
- Terminal errors expose a broader `CodexErrorInfo` union than transport `-32001`, including
  server overload, usage/auth, context/session budget, sandbox/policy, bad request, internal,
  and stream/connection variants.
- Account rate-limit and usage reads exist as explicit client requests.

## Self-review corrections

- The architecture decision uses the three profile-D cases as the primary causal comparison.
  `current-mainline` and `unfamiliar-methodology` remain descriptive unless separately given a
  fair preregistered headless control.
- The model is explicit `gpt-5.6-sol`; provider fallback is forbidden.
- `read-only` is not treated as a read allowlist. An outer OS-level allowlist plus negative
  sentinel probe is a live prerequisite.
- Isolated authentication is fail-closed. The design does not authorize copying tokens or the
  global Codex home.

## Remaining gates

1. A/B/C/D live artifacts do not exist because `CC_EXEC_PORT=28080` is unavailable and the
   managed sandbox forbids the loopback gateway.
2. Profile D therefore has not proven a physically exercised fair control.
3. v2 still requires an independent spec review before an implementation plan.
4. PIT fixture, isolated-auth readiness, quota receipt, randomized blind rubric, App Server
   runner, and live artifact remain unbuilt/unrun by design.

No part of this verification changes `main`, 8792/8799, the KB merge boundary, credentials,
the five frozen questions, or any existing benchmark artifact.
