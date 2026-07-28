# Codex App Server Ceiling Benchmark Design v2

Date: 2026-07-29
Status: revised design after independent `CHANGES_REQUIRED`; implementation remains conditional
Model: explicit `gpt-5.6-sol`
Canonical runtime: unchanged; 8792 and 8799 are out of scope

## 1. Decision this experiment is allowed to make

Determine whether native Codex harness ownership adds material answer autonomy after the
existing Codex headless lane receives a physically exercisable, fair budget.

This is a capability-ceiling experiment, not a production migration and not a claim that App
Server is intrinsically better. App Server implementation remains blocked until the frozen
three-case A/B/C/D headless ablation has produced a valid fair control. If profile D cannot
exercise calls 7–12, the control is invalid and App Server must wait.

The experiment may justify one later design: a bounded `CodexAppServerRuntime` adapter behind
the existing `AgentRuntime` seam. It may not authorize a canonical switch, unrestricted SQL,
weakened cutoff/evidence gates, or deletion of the provider-neutral runtime.

## 2. Hypothesis and confounds

Hypothesis: with the same Codex binary, model, reasoning tier, point-in-time data, question,
deadline, and evaluation rules, native App Server threads use repository instructions and
tools more effectively than the headless gateway because Codex owns context, recovery, and
stopping.

The experiment is invalid if any of these vary without being declared:

- effective information set or accessible data dates;
- model, reasoning effort, service tier, or provider fallback;
- wall-clock deadline or benchmark eligibility;
- repository instructions, skills, config, MCP servers, plugins, hooks, or memory;
- answer rubric, blind labels, or baseline selection after answers are viewed.

The native repo-discovery surface is intentionally different from the headless finance gateway.
That combined harness difference is the treatment. More time, future data, or a different model
is not.

## 3. Protocol evidence pinned for implementation

The public Codex manual could not be fetched in the managed sandbox because DNS was disabled.
This spec therefore pins the protocol emitted by the exact local binary that would run the
experiment:

```text
binary: /Applications/ChatGPT.app/Contents/Resources/codex
version: codex-cli 0.146.0-alpha.3.1
command: codex app-server generate-json-schema --experimental
v2 bundle SHA-256: bde4852a9f8ef55564c1998621f2d7104eae17b58956ab160b7303cc60e5b69b
```

Relevant generated-schema hashes:

```text
ServerRequest.json                 5abe765ff9bd94b88f2f417025ec011eac172925ffdfc74d7ccf2542bc114
v2/ThreadStartParams.json          b3685411ceb8ad264a1920e8facd66301e5280948ef9c2a6871b95d4c19da639
v2/TurnStartParams.json            f23021c02d28b60fccb6dcaaace9ff676127065f8254537265d6622656860dca
v2/TurnCompletedNotification.json  96a42581ca7053aba0d86acf7259bc1993628ff782c243f649215652c1562fbd
```

The binary supports `--strict-config`, repeated `-c key=value`, and stdio transport. It does
not advertise an `--ignore-user-config` flag. Any later binary/schema change requires a new
protocol receipt and spec review; it must not be treated as a compatible rerun by assumption.

## 4. Experimental material

### Frozen questions

Question file:

`/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json`

SHA-256:

`bec6d6944ced127166bd41cb80a09a9f9fb0d816e45cee3be13a900bda2966fe`

All cases use `as_of=2026-07-24` and `tier=standard`:

- `rebound-duration`;
- `ruihuatai-valuation`;
- `weekly-market-cause`;
- `current-mainline`;
- `unfamiliar-methodology`.

### Primary causal comparison

The primary architecture-decision set is the first three cases because they are the exact
cases in the preregistered A/B/C/D ablation. The primary baseline must be a valid profile-D
artifact from:

`docs/verification/headless-budget-ablation-preregistration-2026-07-28.md`

Profile D is `180s / 12 calls / gateway ratio 0.0 / 30s synthesis reserve` and is valid only if
at least seven tool calls are physically observed where the treatment requires it.

The other two cases remain descriptive experience controls. They can inform prose/directness
discussion, but they cannot prove the generic-harness hypothesis unless a separate same-contract
fair headless receipt is preregistered before App Server answers are viewed.

Historical artifacts `0d260bda` through `e179b15c` remain diagnostic evidence. None may be
relabeled as an identical replicate or selected after seeing App Server output.

### Background references

GLM and SDK-GPT artifacts change both model and harness. They may appear in an appendix only;
they are not primary controls and cannot decide whether App Server should be integrated.

## 5. Physical point-in-time fixture

Prompt obedience is not a cutoff mechanism. Before any live turn, build a physically isolated
fixture whose maximum accessible information date is 2026-07-24.

The fixture consists of:

1. a clean detached instruction/code root at a pinned commit;
2. a separate read-only finance data root containing only cutoff-valid database/export rows;
3. a separate read-only Wiki/index snapshot whose manifest, source revision, and content hashes
   are pinned;
4. no symlink that escapes from either root to the live primary workspace, live DuckDB, user
   memory, another worktree, or an unpinned knowledge base.

The fixture manifest must record:

- source revision and dirty state for the instruction root;
- every database/export/index file path relative to its root plus SHA-256;
- per-table maximum date for all market and evidence tables the query helpers can reach;
- Wiki/index revision, freshness verdict, include-raw/max-files scope, and receipt hash;
- the absence of future rows and escaping symlinks.

The same fixture is used by the fair headless control and App Server. A post-run lookahead audit
repeats the per-table/date checks and scans final claims/sources for dates after the cutoff.

`currentTime/read` returns Unix second `1784876400`, representing
`2026-07-24T15:00:00+08:00`. That protocol response is consistency metadata, not a replacement
for physical isolation.

## 6. Controlled filesystem and process radius

Run one dedicated stdio child owned by the benchmark. Never connect to the desktop daemon,
`app-server proxy`, a shared control socket, a local HTTP proxy, or a previously running App
Server.

`read-only` prevents writes but does not prove reads are limited to `cwd`. The outer launcher
must therefore add an OS-level read allowlist around the child. Allowed reads are limited to:

- the pinned Codex binary and required system/runtime libraries;
- the clean instruction root;
- the PIT finance and Wiki roots;
- the isolated Codex home and a dedicated temporary state directory.

Allowed writes are limited to the isolated Codex home and dedicated temporary state. The clean
instruction root and PIT roots remain read-only. A preflight negative-control probe attempts to
read a sentinel outside the allowlist and must receive a sandbox denial. A positive-control
probe reads one pinned fixture file. If the platform cannot enforce or demonstrate this read
radius, the experiment stops as `filesystem_isolation_unproven`.

Before/after manifests fingerprint:

- instruction root;
- PIT data and Wiki roots;
- Codex binary;
- isolated config;
- allowed App Server state.

Any repository/private-data write is a hard failure. Expected state writes inside the isolated
Codex home are recorded separately and must not be confused with repo writes.

## 7. Isolated Codex configuration

Start the child with a dedicated mode-0700 `CODEX_HOME`, a minimal tested config, a cleared
environment allowlist, `--strict-config`, and explicit `-c` overrides. Do not inherit the user's
global config, provider aliases, MCP servers, plugins, hooks, notifications, memory roots,
custom instructions, analytics choice, or reasoning default.

The isolated config declares:

- model `gpt-5.6-sol`;
- no provider fallback;
- no MCP servers, plugins, hooks, or external skill roots;
- analytics disabled;
- approval policy `never`;
- read-only sandbox and no tool-command network access;
- only the minimal environment variables required to locate the PIT fixture.

Authentication is a readiness dependency, not permission to copy a secret. The runner must not
copy, print, persist, or commit API keys, ChatGPT tokens, Keychain values, or the user's global
Codex home. If the isolated home cannot authenticate without such copying or interactive login,
record `isolated_auth_unavailable` and stop before the first case.

After `initialize`, require the returned `codexHome` to equal the isolated path. Use
`model/list` to prove `gpt-5.6-sol` is available with medium reasoning. Do not rely on a model
label in a prompt.

## 8. Session and turn contract

Use one App Server process for the batch and one new ephemeral thread per case. Never reuse a
finance thread across cases.

`thread/start` sets and records:

```text
cwd=<clean instruction root>
ephemeral=true
model=gpt-5.6-sol
allowProviderModelFallback=false
sandbox=read-only
approvalPolicy=never
runtimeWorkspaceRoots=[<instruction root>, <PIT finance root>, <PIT Wiki root>]
dynamicTools=null
environments=[]
experimentalRawEvents=false
```

`turn/start` sets and records:

```text
threadId=<new thread>
model=gpt-5.6-sol
effort=medium
approvalPolicy=never
sandboxPolicy={type: readOnly, networkAccess: false}
runtimeWorkspaceRoots=<same three roots>
environments=[]
```

All five frozen cases are `tier=standard`; the only allowed mapping is
`standard -> effort=medium`. No global or account reasoning default may override it.

Every case has the same 180-second wall-clock deadline as the fair long control. Timeout sends
`turn/interrupt` and waits a bounded grace period for terminal `interrupted`; missing terminal
state is a protocol failure.

The user input contains only:

- the frozen raw question;
- the immutable cutoff and default A-share market assumption;
- a read-only instruction;
- a request for direct Chinese judgment, evidence, uncertainty, continuation conditions, and
  invalidation conditions when relevant.

Frozen `required_outputs` remain evaluator data and are not shown to Codex. The output schema
constrains only the final envelope:

- `answer`: required natural-language string;
- `data_cutoff`: required ISO date;
- `sources`: required array of structured source records.

It does not prescribe headings, routes, tool order, paragraph count, or claim wording.

## 9. Structured source contract and truth audit

Every source record contains:

- stable `source_id` local to the case;
- `source_type` such as table, Wiki page, report, or public document;
- repo-relative file identity or table/dataset identity, never a raw absolute path;
- `date_start` and `date_end` when time-bearing;
- a bounded locator or query summary;
- the material claim IDs it supports.

The final artifact keeps the structured records internally. Public blind views remove backend
identity, raw paths, content hashes, and tool payloads while preserving enough normalized source
identity for a separate auditor.

Every material numeric claim is audited, not sampled away. It must resolve to a cutoff-valid
source record and independently reproduce within the applicable tolerance. Any untraceable
material number is a truth failure. Fluent prose cannot offset lookahead, subject mismatch,
fabricated citations, or unsupported numbers.

## 10. Complete server-request dispatcher

One dispatcher owns every server-to-client request in the generated schema. Unknown methods
receive an immediate typed JSON-RPC rejection and are recorded; they never hang until timeout.

| Request | Policy |
|---|---|
| `currentTime/read` | return `currentTimeAt=1784876400` |
| `item/commandExecution/requestApproval` | deny and record attempted command/write intent |
| `item/fileChange/requestApproval` | deny and record attempted file change |
| `item/permissions/requestApproval` | deny all expansion |
| `item/tool/requestUserInput` | reject as non-interactive |
| `mcpServer/elicitation/request` | reject; MCP is disabled |
| `item/tool/call` | reject; Option A declares no dynamic tools |
| `account/chatgptAuthTokens/refresh` | fail readiness unless host can satisfy it without exposing/copying tokens |
| `attestation/generate` | fail readiness unless an isolated non-interactive handler is available |
| `applyPatchApproval` | deny legacy patch request |
| `execCommandApproval` | deny legacy command approval |

Command execution that is already permitted by read-only policy may occur without an approval
request; the outer filesystem allowlist and before/after fingerprints remain authoritative.

## 11. Errors, overload, and quota

Treat JSON-RPC transport errors and terminal turn errors separately.

If transport code `-32001` is actually observed from the pinned binary, classify it and retry
once with bounded backoff. Do not assume that code is the only overload signal.

Parse every generated `CodexErrorInfo` variant, including:

- `contextWindowExceeded`;
- `sessionBudgetExceeded`;
- `usageLimitExceeded`;
- `serverOverloaded`;
- `cyberPolicy`;
- `internalServerError`;
- `unauthorized`;
- `badRequest`;
- `threadRollbackFailed`;
- `sandboxError`;
- `other`;
- HTTP/stream connection and retry-exhaustion object variants.

Only `serverOverloaded` and an observed equivalent transient transport signal may retry once.
Usage limit, unauthorized, bad request, policy, sandbox, context-window, and budget errors never
blindly retry.

Before initialization and after the final case, call `account/rateLimits/read` and
`account/usage/read`. Persist only sanitized bucket percentages, reset times, and aggregate
usage. Stop before the next case if the preregistration's maximum usage delta or minimum
remaining quota would be crossed. Missing quota telemetry is `quota_radius_unknown`, not zero
usage.

## 12. Artifact, privacy, and state integrity

The preregistration receipt is committed before the run and pins:

- fair headless baseline path and SHA-256;
- question path/hash and selected decision/descriptive cases;
- instruction revision, PIT manifest hash, binary/version/schema hash;
- sanitized isolated-config fingerprint;
- exact output and blinded-review paths;
- 180-second deadline, medium effort, model, quota threshold, rubric, and decision rule;
- reviewer identity and label randomization seed commitment.

The runner writes one immutable artifact outside Git under
`/Users/a77/.finance-runtime/evals/`. Every requested case appears, including infrastructure
failures. No SDK/headless fallback may fill a failed App Server cell.

Reuse the repository's `_sanitize_diagnostic_value`, path/secret redaction rules, and
`_artifact_hash` convention. Artifact SHA-256 is computed with the artifact's own hash field
excluded. Drop reasoning items, reasoning deltas, agent-message deltas, secrets, raw local
paths, and full tool payloads. Preserve bounded item type/status, sanitized command purpose,
tool names, usage, latency, permission requests, source records, and final answer.

Instruction conflict is a measured outcome. Record attempted writes, repeated denied requests,
and retries caused by write-oriented `AGENTS.md` correction/memory/Git rules as
`domain_instruction_interference`; do not relax read-only policy to help the case finish.

## 13. Blinded comparison and decision rule

Freeze all baseline hashes, the rubric, and a backend-label randomization commitment before the
first App Server answer is read. An independent reviewer sees normalized answer/source views,
not runtime status or backend labels.

Truth and experience are separate:

- truth: cutoff, subject, facts, numeric lineage, citation integrity, unsupported claims;
- experience: directness, useful organization, unnecessary follow-up, latency, and preference.

Use the acceptance verdict seam's principle: operational failure, truth failure, and experience
preference never substitute for one another.

The experiment supports App Server integration design only if all conditions hold:

1. the fair profile-D headless control is valid;
2. App Server has zero future-data violations and zero untraceable material numeric claims;
3. App Server wins directness on at least 4/5 overall cases;
4. App Server wins at least 2/3 primary diagnostic cases against the fair same-model control;
5. no primary case has a material truth regression;
6. repository/PIT fingerprints are unchanged and filesystem isolation is proven;
7. quota stays inside the preregistered radius.

If conditions 2, 5, 6, or 7 fail, the experiment cannot be rescued by prose preference. If
only the two descriptive cases win, generic-harness causality remains unproven. A tie or invalid
control means no implementation decision, not a default win for either runtime.

## 14. Architecture decision table

| Result | Next action |
|---|---|
| Meets every gate above | Design, but do not yet ship, a bounded App Server adapter plus finance-tool/EvidenceLedger bridge |
| Better prose, truth regression | Keep as benchmark reference; preserve provider-neutral runtime |
| No material primary-set improvement | Stop App Server expansion; improve tool/result semantics and completion judgment |
| Isolation/auth/quota unsafe | Record operationally ineligible; do not work around by copying secrets or widening access |
| Fair headless control invalid or missing | Remain blocked; do not run App Server |

## 15. Acceptance tests required before implementation can run live

The implementation plan must include public-seam tests that prove:

1. `initialize.codexHome` equals the isolated home and schema/binary fingerprints match;
2. requested model is `gpt-5.6-sol`, effort is medium, and provider fallback is false;
3. every thread is ephemeral, read-only, approval-never, and uses only pinned roots;
4. the negative-control outside-root read is denied and positive fixture read succeeds;
5. `currentTime/read` returns exactly `1784876400`;
6. every known server request receives its declared response and unknown requests fail fast;
7. every `CodexErrorInfo` class maps to a typed retry/no-retry result;
8. timeout sends interrupt and missing terminal completion fails closed;
9. artifact hashing excludes only its own hash field and redaction removes secrets/paths/reasoning;
10. every case, including failures, appears exactly once and never falls back;
11. pre/post repository, PIT, config, state, quota, and binary fingerprints are enforced;
12. every material numeric claim requires cutoff-valid source lineage;
13. blind labels cannot be joined to backend identity until judging is sealed;
14. profile-D baseline validity is a hard precondition to the live command.

## 16. Non-goals and authorization boundary

- no App Server code is authorized merely because this v2 spec exists;
- no dynamicTools/MCP finance bridge in the ceiling experiment;
- no arbitrary SQL exposed to a production model;
- no new question route, answer template, or per-case tuning;
- no weakening of EvidenceLedger, cutoff, budget, invalid-action, or publication gates;
- no all-28 acceptance run in this phase;
- no `main` merge, KB `9053b0c4` merge, 8792/8799 switch, or legacy deletion.

Implementation planning begins only after an independent spec review passes and the fair
profile-D control exists. Live execution begins only after the preregistration receipt is
complete and all deterministic preflight tests pass.
