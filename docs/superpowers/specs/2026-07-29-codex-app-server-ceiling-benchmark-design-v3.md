# Codex App Server Ceiling Benchmark Design v3

Date: 2026-07-29
Status: independent `PASS`; fixture/export and five-case headless-control tooling authorized; App Server runner blocked
Model: explicit `gpt-5.6-sol`
Canonical runtime: unchanged; 8792 and 8799 are out of scope

## 1. Decision this experiment is allowed to make

Determine whether native Codex harness ownership adds material answer autonomy after the
existing Codex headless lane receives a physically exercisable, fair budget.

This is a capability-ceiling experiment, not a production migration and not a claim that App
Server is intrinsically better. The completed three-case A/B/C/D run is valid evidence about the
headless budget mechanisms, but it is not the App Server control because it used live data roots
and covered only three of the five decision cases. App Server live execution remains blocked until
a five-case profile-D headless control is rerun against the exact sealed fixture and instruction
view defined here. At least one case must physically execute seven or more tool calls.

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

The executable protocol source is the schema emitted by the exact local binary that would run the
experiment. Generate into a new empty directory and preserve the whole file manifest:

```text
binary: /Applications/ChatGPT.app/Contents/Resources/codex
version: codex-cli 0.146.0-alpha.3.1
command: codex app-server generate-json-schema --experimental --out <empty-dir>
JSON file count: 347
length-prefixed path+content bundle SHA-256: 7c000f25d1b023c953dcdd31be4d81a6226329c1cab3b43e46a06be37ffd4a88
codex_app_server_protocol.v2.schemas.json SHA-256: 0ffceedba04b90b5b97b6f2f2837ff9c81595038f31112849a682dd0cd9d0903
```

The bundle convention sorts UTF-8 relative paths, then hashes for each file:
8-byte big-endian path length, path bytes, 8-byte big-endian content length, and
raw content bytes. This makes the bundle receipt independently reproducible.

Relevant generated-schema hashes:

```text
ServerRequest.json                 5abe765ff9bd94b88f2f2fb417025ec011eac172925ffdfc74d7ccf2542bc114
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

### Fair five-case comparison

The completed v2 A/B/C/D experiment is referenced only for its budget diagnosis:

- preregistration: `docs/verification/headless-budget-ablation-preregistration-v2-2026-07-29.md`;
- result receipt: `docs/verification/headless-budget-ablation-v2-results-2026-07-29.md`;
- valid D artifact SHA-256:
  `75a144399068843580b330e2899ebbbc3093cccbc0f5ac9d01e986c95053e898`.

It cannot be the primary App Server control because it used live roots and contains only three
cases. Before any App Server answer is generated, preregister and run a new five-case profile-D
control from the same code revision, sealed instruction export, physical PIT fixture, model,
provider, service tier, finance-tool surface, deadline, and common publication verifier that will
be used for App Server.

The comparison artifact schema has two immutable answer fields per case:

- `candidate_answer`: the runtime's last natural-language answer before the common publication
  verifier;
- `published_answer`: the answer after the identical cutoff, lineage, structural, and semantic
  publication gates.

The blinded truth and experience decision uses only `published_answer` at the preregistered JSON
pointer for each of all five cases. `candidate_answer` is diagnostic and cannot be substituted
after outputs are viewed. A missing case, missing pointer, or fallback from another backend makes
the whole architecture comparison invalid.

Historical artifacts `0d260bda` through `e179b15c` remain diagnostic evidence. None may be
relabeled as an identical replicate or selected after seeing App Server output.

### Background references

GLM and SDK-GPT artifacts change both model and harness. They may appear in an appendix only;
they are not primary controls and cannot decide whether App Server should be integrated.

## 5. Sealed instruction export and physical point-in-time fixture

Prompt obedience is neither a cutoff mechanism nor an evaluation-secrecy boundary. Before any
live turn, build two content-addressed exports outside the live repositories.

### 5.1 Curated instruction/code export

Do not expose a Git checkout. The export is a regular-file tree with no `.git`, symlink, hardlink,
mount escape, user-memory link, eval artifact, gold answer, historical result, or post-cutoff
handoff. Its manifest pins the originating source revision, every included path/hash/mode, and the
explicit allowlist used to create it.

The allowlist may contain only production runtime code, read-only finance-tool entry points,
neutral project instructions, and production-relevant skill descriptions. It excludes at least:

- `docs/handoffs/`, `docs/verification/`, `docs/superpowers/`, `tmp/`, `.agent-memory/`, `.git/`;
- `intelligence/tests/`, all eval fixtures, question files, acceptance overlays, rubrics, reference
  snapshots, prior benchmark artifacts, and generated review material;
- any file containing one of the five raw questions, `required_outputs`, direct targets, reference
  answers, expected facts, pass rules, or backend labels.

A preflight scanner runs outside the export and uses the frozen evaluator corpus as the forbidden
set. It must report zero normalized full-question matches, zero normalized reference-answer or
required-output matches, and zero character/token n-gram matches above the preregistered threshold.
An independent semantic-leak review then examines the export manifest plus only the scanner's
candidate snippets and must seal `no_answer_or_rubric_leak`. This receipt is committed before the
first App Server answer. Any later export change requires a new five-case headless control.

The deterministic scanner algorithm is frozen before export tooling begins:

1. forbidden corpus = raw questions, conversation context, `required_outputs`, direct targets,
   reference answers, expected facts, pass rules, prior candidate/published answers, and post-cutoff
   handoff/result prose for these cases;
2. text normalization = UTF-8 decode with error rejection, Unicode NFKC, ASCII case-fold, newline
   normalization, then removal of Unicode whitespace and punctuation for the character stream;
3. tokenization = each Han code point is one token; maximal case-folded alphanumeric runs are one
   token; other symbols delimit tokens;
4. fail on any full normalized forbidden-string match, any 12-character n-gram match, any
   6-token n-gram match, or token-set Jaccard similarity `>= 0.80` for a forbidden sentence with at
   least 8 tokens;
5. no exception may suppress a full question, reference sentence, required-output identifier, or
   post-cutoff result fragment. A hashed exception manifest may contain only reviewed generic
   production terms shorter than the n-gram thresholds.

The semantic-leak review is separately pinned to `gpt-5.6-sol`, a fixed prompt/rubric hash, and an
independent reviewer identity. Its positive fixture includes paraphrased questions/answers that do
not share the deterministic n-grams. The scanner test corpus also includes punctuation/whitespace
changes, NFKC/full-width variants, split `required_outputs`, historical answer fragments, and a
post-cutoff handoff; clean production instructions are the negative control. Missing one positive
fixture blocks the export.

### 5.2 Physical PIT data fixture

The data fixture's maximum accessible information date is 2026-07-24. It contains:

1. a read-only finance snapshot with only cutoff-valid rows and exports;
2. a read-only Wiki/index snapshot with pinned manifest, source revision, content hashes,
   include-raw/max-files scope, and a runtime `fresh` receipt;
3. no symlink, hardlink, bind mount, or path escape to the live workspace, live DuckDB, user
   memory, another worktree, or an unpinned knowledge base.

The fixture manifest records every relative file/hash/mode/inode count, per-table maximum date for
all reachable market/evidence tables, index provenance, and the absence of future rows and escaping
links. Text sources are additionally scanned for post-cutoff publication dates.

The App Server process cannot read the finance or Wiki roots directly. Both App Server and
headless access the exact same physical fixture only through the same read-only `finance-tool`
wrapper, which emits typed evidence receipts. This preserves the domain harness while testing
whether native Codex context, recovery, and stopping improve tool use. The sealed instruction
export is the only runtime workspace root visible to App Server.

A post-run audit repeats all file/date/link checks and scans every final claim and evidence receipt
for lookahead. Any mutation or future-data reachability invalidates both arms.

`currentTime/read` returns Unix second `1784876400`, representing
`2026-07-24T15:00:00+08:00`. That protocol response is consistency metadata, not a replacement
for physical isolation.

## 6. Controlled capability, filesystem, network, IPC, and process radius

Run one dedicated stdio child owned by the benchmark. Never connect to the desktop daemon,
`app-server proxy`, a shared control socket, token broker, local model proxy, or previously running
App Server.

The native item allowlist is exactly:

- `userMessage`, `agentMessage`, `reasoning`, `plan`, and `commandExecution`;
- `commandExecution` is the only executable tool item;
- finance evidence is admissible only from the pinned `finance-tool` wrapper and its typed receipt.

`fileChange`, MCP, dynamic tools, apps, browser/web search, computer use, image view/generation,
collaboration/sub-agent items, remote control, hooks, plugin items, and any unknown item type make
the case `unexpected_capability` and terminate the batch. `multiAgentMode` is
`explicitRequestOnly`, the prompt never requests it, and any collab item is still a hard failure.

The launcher uses an OS-level sandbox around the App Server process and all descendants. The
allowlist is limited to the pinned binary and system libraries, the sealed instruction export,
the isolated Codex home, and dedicated temporary state. The App Server cannot read the live user
home, repositories, Keychain, process environment of other processes, process list details,
Apple Events, clipboard, Desktop daemon sockets, or arbitrary Unix/TCP sockets.

Model traffic is the sole outer-network exception and is restricted to the preregistered direct
provider endpoint. The inner Codex shell sandbox sets `networkAccess=false`, so every
`commandExecution` descendant is network-denied even though the parent App Server can reach the
model provider. The command-child environment explicitly excludes `OPENAI_API_KEY` and every
other credential. The `finance-tool` wrapper runs as a separate broker-owned process with no model
credential and access only to the PIT fixture; command children exchange create-if-absent typed
request/response files through the existing per-case mode-0700 mailbox. The mailbox rejects
symlinks, oversized requests, response overwrite, and paths outside the case directory. No network
socket or general local proxy is allowed.

Positive controls prove the instruction export and one finance receipt are readable. Negative
controls must prove denial of: live repo/user-home reads, Keychain, process inspection, Apple
Events, clipboard, non-allowlisted Unix sockets, loopback ports, public network from shell
children, writes outside isolated state, and every forbidden tool/item type. If any control cannot
be enforced and observed, stop as `isolation_unproven`; do not replace it with a prompt promise.

Before/after manifests fingerprint the instruction export, PIT fixture, binary, isolated config,
allowed App Server state, broker binary, and sandbox profile. Any unexpected write or state
radius expansion is a hard failure.

## 7. Isolated Codex configuration

Start the child with a dedicated mode-0700 `CODEX_HOME`, a minimal tested config, a cleared
environment allowlist, `--strict-config`, and explicit `-c` overrides. Do not inherit the user's
global config, provider aliases, MCP servers, plugins, hooks, notifications, memory roots,
custom instructions, analytics choice, or reasoning default.

The isolated config declares:

- model `gpt-5.6-sol`;
- no provider fallback;
- `fast_mode=false`;
- service tier omitted/null for both arms and required to be returned as null;
- no MCP servers, plugins, hooks, or external skill roots;
- apps, browser, web search, computer use, image generation, remote control, and all multi-agent
  feature flags disabled;
- analytics disabled;
- approval policy `never`;
- read-only sandbox and no tool-command network access;
- an empty selected-capability root set and no dynamic tools;
- only the minimal non-secret environment required for the sealed export and finance broker.

The parent App Server receives the environment-only model credential. Its shell-environment policy
uses an explicit allowlist that excludes that credential; a negative control proves
`commandExecution` cannot read it.

Authentication has one permitted mechanism: an ambient `OPENAI_API_KEY` supplied to both arms as
an environment secret, with the direct provider base URL pinned in the preregistration. It is not
accepted in argv/stdin files, copied from the user's global Codex home, read from Keychain, routed
through the Desktop daemon, or written into the isolated home. The runner records only provider
identity and a non-reversible credential-instance fingerprint. If environment-only authentication
does not work, requires token refresh/attestation, or would require a local/shared proxy, record
`isolated_auth_unavailable` and stop before the first case.

After `initialize`, require the returned `codexHome` to equal the isolated path. Use `model/list`
to prove `gpt-5.6-sol` is available with medium reasoning. `thread/start` must return
`model=gpt-5.6-sol`, `modelProvider=openai`, the requested reasoning effort, and the same null
service tier used by the new headless control. Any model-rerouted notification, non-null or
unobservable service tier, provider mismatch, or missing execution receipt makes the comparison
invalid. Do not rely on a model label in a prompt.

The execution-identity receipt is not a prose assertion. The runner seals these observations:

| Property | Requested pointer | Resolved/runtime pointer | Provider-executed pointer |
|---|---|---|---|
| model | `thread/start.params.model`; `turn/start.params.model` | `thread/start.result.model` | required provider response field |
| provider | pinned direct endpoint and isolated config | `thread/start.result.modelProvider` | required provider response field |
| reasoning | `turn/start.params.effort` | `thread/start.result.reasoningEffort` | required provider response field or provider attestation |
| service tier | both request fields are `null` | `thread/start.result.serviceTier` | required provider response field |
| fallback/reroute | `allowProviderModelFallback=false` | zero `model/rerouted` notifications | provider response model equals requested model |
| fast mode | CLI/config override `features.fast_mode=false` | `experimentalFeature/list.result.data[name=fast_mode].enabled=false` | not applicable once feature is disabled |

Recorded/fake protocol tests must make every mismatch fail closed, including the case where all
request values are correct but one returned execution field differs. The pinned 0.146.0 schema
does not expose a provider-response model/provider/service-tier field. Therefore this binary is
currently `execution_identity_unobservable` for a live App Server comparison. Fixture/export
tooling may proceed after spec PASS, but App Server runner code or live turns may not begin until a
new pinned protocol or separately reviewed provider receipt exposes those fields. Config echo and
absence of reroute alone are insufficient.

## 8. Session and turn contract

Use one App Server process for the batch and one new ephemeral thread per case. Never reuse a
finance thread across cases.

`thread/start` sets and records:

```text
cwd=<sealed instruction export>
ephemeral=true
model=gpt-5.6-sol
allowProviderModelFallback=false
sandbox=read-only
approvalPolicy=never
runtimeWorkspaceRoots=[<sealed instruction export>]
dynamicTools=null
environments=[]
experimentalRawEvents=false
multiAgentMode=explicitRequestOnly
selectedCapabilityRoots=[]
serviceTier=null
```

`turn/start` sets and records:

```text
threadId=<new thread>
model=gpt-5.6-sol
effort=medium
approvalPolicy=never
sandboxPolicy={type: readOnly, networkAccess: false}
runtimeWorkspaceRoots=[<sealed instruction export>]
environments=[]
multiAgentMode=explicitRequestOnly
serviceTier=null
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
- `claims`: required array of span-bound claim records;
- `sources`: required array of structured source records joined to runner receipts.

It does not prescribe headings, routes, tool order, paragraph count, or claim wording.

## 9. Immutable Claim/Evidence ledger and truth audit

Both arms emit the same candidate envelope:

```text
answer: string
data_cutoff: ISO date
claims[]: claim_id, span_start, span_end, text, claim_type,
          material_numeric, source_ids[]
sources[]: source_id, tool_call_id, source_type, dataset_or_file,
           bounded_locator, query_hash, result_hash, date_start, date_end
```

`span_start` and `span_end` are Unicode-code-point offsets into the exact `answer`. The runner
rejects overlapping IDs, text/span mismatches, duplicate IDs, nonexistent source IDs, and material
numeric claims with an empty source set.

The runner owns a private append-only `EvidenceLedger` for every case. For each
`commandExecution`, it records command hash, cwd identity, start/end time, exit status, bounded
stdout/stderr hashes, and whether the command matched the finance-tool allowlist. The
`finance-tool` broker stores the complete typed request/result as a content-addressed private blob
outside Git and returns a bounded receipt containing stable evidence IDs, cutoff, source dates,
locators, and blob hash. The App Server cannot invent or rename these receipt IDs.

Append-only is a persistence protocol:

- each blob and ledger file is created with create-if-absent semantics; an existing path is never
  overwritten;
- every ledger event contains `run_id`, `case_id`, monotonic sequence, previous-event hash, payload
  hash, and event hash;
- the final seal contains event count, last-event hash, sorted blob-manifest root, and case artifact
  hash; the public artifact binds this `ledger_root`;
- file and containing-directory metadata are fsynced after atomic creation; a crash may leave a
  verifiable unsealed prefix, but an unsealed case can never publish or enter blind review;
- restart verifies the complete chain and blob set before resuming. It does not repair, truncate,
  reorder, or reuse another case's receipts.

Tests mutate blob content, attempt overwrite/delete, truncate/reorder the ledger, and substitute a
receipt across cases. Every mutation must break the seal and invalidate publication and blind
review.

Only finance-tool receipts can support financial facts or numbers. Reads from the instruction
export may support procedural claims about available methods, but never market, company, or
valuation facts. At finalization, every model-provided source is joined to the runner ledger by
`tool_call_id + result_hash`; unmatched sources are fabricated citations and fail truth.

The common publication verifier reproduces every material number from the exact receipt payload,
checks subject and cutoff, and then invokes the same external semantic judge for both arms.
`published_answer` is created only after that common gate. Public blind views remove backend
identity, raw paths, secrets, and full payloads while preserving normalized claims and sources for
review. Fluent prose cannot offset lookahead, subject mismatch, fabricated citations, or
unsupported numbers.

## 10. Complete server-request dispatcher

One dispatcher owns every server-to-client request in the generated schema. Unknown methods
receive an immediate typed JSON-RPC rejection and are recorded; they never hang until timeout.
The known-method set is generated from the pinned `ServerRequest.json` union rather than copied by
hand. Contract tests must enumerate every union member and fail when a later schema adds one.

| Request | Policy |
|---|---|
| `currentTime/read` | return `currentTimeAt=1784876400` |
| `item/commandExecution/requestApproval` | deny and record attempted command/write intent |
| `item/fileChange/requestApproval` | deny and record attempted file change |
| `item/permissions/requestApproval` | deny all expansion |
| `item/tool/requestUserInput` | reject as non-interactive |
| `mcpServer/elicitation/request` | reject; MCP is disabled |
| `item/tool/call` | reject; Option A declares no dynamic tools |
| `account/chatgptAuthTokens/refresh` | terminate as `isolated_auth_unavailable`; environment-only API-key auth must not refresh ChatGPT tokens |
| `attestation/generate` | terminate as `isolated_auth_unavailable`; no host/desktop attestation handler is authorized |
| `applyPatchApproval` | deny legacy patch request |
| `execCommandApproval` | deny legacy command approval |

Command execution that is already permitted by read-only policy may occur without an approval
request; the outer filesystem allowlist and before/after fingerprints remain authoritative.

## 11. Errors, overload, and quota

Treat JSON-RPC transport errors and terminal turn errors separately.

If transport code `-32001` is actually observed from the pinned binary, classify it as a possible
transient and retain the failed attempt. Do not assume that code is the only overload signal.

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
The original case receives one absolute 180-second deadline; failed attempt, backoff, retry,
interrupt, and grace all consume that same deadline. Retry cannot reset tool, token, or wall-clock
budgets and cannot create a second blind-review answer. Usage limit, unauthorized, bad request,
policy, sandbox, context-window, and budget errors never blindly retry.

After `initialize`, before the first case, before and after every attempt (including retry), and
after the final case, call `account/rateLimits/read` and `account/usage/read`. Persist only
sanitized bucket percentages, reset times, and aggregate usage. Stop before the next attempt if
the preregistered maximum usage delta or minimum remaining quota would be crossed. Missing or
unparseable quota telemetry is `quota_radius_unknown` and makes the live comparison operationally
ineligible; it is never interpreted as zero usage.

Admission is worst-case, not reactive. For every case, the preregistration derives a hard
`case_token_budget` from the sealed five-case headless control:

```text
ceil_to_1000(1.25 * that case's total headless input+output tokens)
```

The runner sets that cap before the turn with
`thread/goal/set.params.tokenBudget=case_token_budget` (no objective change) and records
consumption from `thread/tokenUsage/updated` notifications. It also preregisters an
`attempt_quota_upper_bound` in every active rate-limit/spend-control unit using the direct
provider's pinned limit and price metadata. If a token cap cannot be converted into a conservative
upper bound for any active quota bucket, stop as `quota_admission_unprovable`.

Before an initial attempt, require:

```text
current_used + attempt_quota_upper_bound <= preregistered_max_used
current_remaining - attempt_quota_upper_bound >= preregistered_remaining_floor
```

Before a retry, recompute the same inequalities with only the unconsumed token/quota budget. A
retry never receives a new full cap; if consumed usage is missing, it is rejected before the model
request. Deterministic tests cover both initial and retry states where current telemetry is inside
the radius but the worst-case next attempt would cross it.

## 12. Artifact, privacy, and state integrity

The preregistration receipt is committed before the run and pins:

- the five-case fair headless baseline path and SHA-256;
- for every case, the exact JSON pointer to `published_answer`, normalized `claims/sources`, and
  the hash of that projected blind view;
- question path/hash and all five decision cases;
- sealed instruction-export manifest/leak-scan receipt, PIT manifest hash, and
  binary/version/schema-manifest hash;
- sanitized isolated-config fingerprint, exact provider, environment-only auth mode,
  requested/returned model and service tier, disabled capability set, sandbox-profile hash, and
  finance-broker hash;
- exact output and blinded-review paths;
- 180-second deadline, medium effort, model, quota threshold, rubric, and decision rule;
- tie/missing-case rules, reviewer identity, and label-randomization seed commitment.

The runner writes one immutable artifact outside Git under
`/Users/a77/.finance-runtime/evals/`. Every requested case appears, including infrastructure
failures. No SDK/headless fallback may fill a failed App Server cell.

Reuse the repository's `_sanitize_diagnostic_value`, path/secret redaction rules, and
`_artifact_hash` convention. Artifact SHA-256 is computed with the artifact's own hash field
excluded. Drop reasoning items/deltas, secrets, raw local paths, and full finance payloads from
the public artifact. Preserve candidate/published answers, claim/source ledgers, bounded item
type/status, sanitized command purpose, usage, latency, permission requests, and hashes of the
private content-addressed evidence blobs.

Instruction conflict is a measured outcome. Record attempted writes, repeated denied requests,
and retries caused by write-oriented `AGENTS.md` correction/memory/Git rules as
`domain_instruction_interference`; do not relax read-only policy to help the case finish.

## 13. Blinded comparison and decision rule

Freeze all five baseline projections/hashes, the rubric, missing-case/tie rules, and a
backend-label randomization commitment before the first App Server answer exists. The projection
algorithm uses only the preregistered `published_answer`, `claims`, and normalized `sources`; it
cannot switch to `candidate_answer`, an internal raw completion, or a weaker historical artifact
after viewing results. An independent reviewer sees normalized answer/source views, not runtime
status or backend labels.

Truth and experience are separate:

- truth: cutoff, subject, facts, numeric lineage, citation integrity, unsupported claims;
- experience: directness, useful organization, unnecessary follow-up, latency, and preference.

Use the acceptance verdict seam's principle: operational failure, truth failure, and experience
preference never substitute for one another.

The experiment supports App Server integration design only if all conditions hold:

1. the five-case fair profile-D headless control uses the identical sealed export/PIT/tool/provider
   view, contains every frozen case exactly once, and physically exercises at least seven calls;
2. App Server has zero future-data violations and zero untraceable material numeric claims;
3. App Server wins directness on at least 4/5 overall cases;
4. App Server wins at least 2/3 primary diagnostic cases against the fair same-model control;
5. no primary case has a material truth regression;
6. repository/PIT fingerprints are unchanged and filesystem isolation is proven;
7. quota stays inside the preregistered radius.

If conditions 2, 5, 6, or 7 fail, the experiment cannot be rescued by prose preference. If only
the two descriptive cases win, generic-harness causality remains unproven. A tie, missing baseline
case, invalid projection, or invalid control means no implementation decision, not a default win
for either runtime.

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
2. requested and returned model/provider/service tier are identical to the five-case headless
   control, `fast_mode` is false, effort is medium, fallback/reroute is absent, and a request-correct
   but provider-execution-mismatched fake receipt fails closed;
3. every thread is ephemeral, read-only, approval-never, single-agent, and sees only the sealed
   instruction export;
4. export gold/rubric leakage scans are clean; symlink/hardlink/mount and future-date scans pass;
5. filesystem, Keychain, process, Apple Events, clipboard, IPC, shell-network, and write negative
   controls fail closed while positive instruction/finance-tool controls succeed;
6. only the explicit thread-item/tool allowlist is accepted; forbidden or unknown items stop the
   batch;
7. `currentTime/read` returns exactly `1784876400`;
8. every generated server-request union member receives its declared response and unknown requests
   fail fast;
9. every `CodexErrorInfo` class maps to a typed retry/no-retry result;
10. retry, backoff, interrupt, and grace share one absolute 180-second deadline;
11. quota is read before/after every attempt; admission subtracts the preregistered worst-case
   initial/retry bound, and missing telemetry or conversion fails closed;
12. artifact hashing excludes only its own hash field and redaction removes
   secrets/paths/reasoning;
13. every case, including failures, appears exactly once and never falls back;
14. pre/post export, PIT, config, state, quota, broker, sandbox, and binary fingerprints are
   enforced;
15. claim spans and IDs resolve; every material number joins to a cutoff-valid finance-tool receipt
   and exact result hash; blob overwrite/delete, ledger truncation/reorder, or cross-case receipt
   substitution breaks the bound ledger root;
16. five fixed baseline projections exist and blind labels cannot join backend identity until
   judging is sealed;
17. same-fixture five-case profile-D baseline validity is a hard precondition to the App Server
   live command.

## 16. Non-goals and authorization boundary

- no App Server code is authorized merely because this v3 spec exists;
- no dynamicTools/MCP finance bridge in the ceiling experiment;
- no arbitrary SQL exposed to a production model;
- no new question route, answer template, or per-case tuning;
- no weakening of EvidenceLedger, cutoff, budget, invalid-action, or publication gates;
- no all-28 acceptance run before the five-case architecture decision;
- no `main` merge, KB `9053b0c4` merge, 8792/8799 switch, or legacy deletion.

Fixture/export tooling and the new five-case headless control may be implemented after an
independent spec review passes. App Server runner implementation begins only after that control is
sealed. Live App Server execution begins only after the preregistration receipt is complete and
all deterministic preflight tests pass.
