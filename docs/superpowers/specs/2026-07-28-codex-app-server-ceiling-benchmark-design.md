# Codex App Server Ceiling Benchmark Design

Date: 2026-07-28
Status: approved option A
Implementation branch: `feat/agent-runtime-backends-verify`
Canonical runtime: unchanged; 8792 and 8799 are out of scope

## Objective

Determine whether the quality gap between the Workbench and interactive Codex
is primarily caused by the generic agent harness.

The experiment runs the already-frozen finance questions through the official
Codex App Server while allowing Codex to use this repository's read-only domain
harness: `AGENTS.md`, applicable skills, local database documentation, and
existing query scripts. It then compares those answers with already-produced
Continuous GLM, SDK GPT, and Codex headless artifacts.

This is a capability-ceiling experiment, not a production runtime migration.
It must be small enough to answer the architecture question before more product
code is built.

## Hypothesis

The Workbench already has useful finance assets and truth gates, but its current
runtime reconstructs part of the generic harness and still constrains model
decisions through precompiled task and delivery contracts. Interactive Codex
performs better because the full Codex harness owns continuous context, tool
choice, recovery, and stopping while the repository contributes finance
instructions and data only when relevant.

If App Server produces materially better answers from the same repository and
question set, the next justified step is a proper App Server adapter behind the
existing `AgentRuntime` seam. If it does not, the main bottleneck remains tool
discoverability, finance semantics, data quality, or the domain contract.

## Scope

### Included

- one long-lived local `codex app-server` process over stdio JSONL;
- one independent ephemeral Codex thread per frozen question;
- the existing five-case adaptive-runtime question file;
- the same question text, `as_of`, tier, and case timeout already recorded by
  the benchmark;
- read-only access to `/Users/a77/finance-workspace-private`;
- automatic project instruction and skill discovery performed by Codex;
- model-owned planning, file discovery, query choice, retries, and stopping;
- capture of Thread, Turn, Item, usage, latency, and final answer events;
- one immutable evaluation artifact outside Git;
- a side-by-side comparison against existing benchmark answers.

### Excluded

- no `ContinuousTurnAdapter`, Workbench API, or UI replacement;
- no `dynamicTools` or MCP finance-tool bridge in this phase;
- no change to the frozen GLM/GPT benchmark arms;
- no production fallback, routing, canary, or feature flag;
- no modification of database, Wiki, memory, user ledgers, or source files;
- no merge to `main` and no canonical runtime switch;
- no claim that App Server is production-ready based on five questions.

## Considered Approaches

### A. Native read-only App Server ceiling benchmark — selected

Codex receives the raw question and immutable time context, loads repository
instructions, and autonomously uses read-only repository tools and scripts.
This most closely reproduces the successful interactive Codex experience and
provides the fastest answer to whether the generic harness is the missing
capability.

The trade-off is that this is not a controlled one-variable comparison of tool
registries. It measures the combined value of the Codex harness plus the
repository's naturally discoverable domain harness.

### B. App Server with `dynamicTools` parity bridge — deferred

Every existing `ResearchToolRegistry` tool would be exposed as an App Server
dynamic tool so all runtimes see the same tool interface. This is a fairer
runtime comparison and is the likely next experiment if option A wins.

It is deferred because `dynamicTools` is experimental and building the bridge
before observing a quality signal would add product code without evidence.

### C. Direct production replacement — rejected

Replacing the current runtime before a frozen comparison would mix runtime,
authentication, UI, permission, and deployment changes. It would not isolate
the cause of quality improvement or regression.

## Architecture

```text
Frozen five-case JSON
        |
        v
AppServerBenchmarkRunner
        |
        +--> AppServerProcess (one pinned local binary, stdio JSONL)
        |         |
        |         +--> initialize / initialized
        |         +--> thread/start (ephemeral, read-only)
        |         +--> turn/start
        |         +--> item/* and turn/* event stream
        |         +--> turn/interrupt on timeout/cancel
        |
        +--> per-case transcript and final answer
        |
        +--> immutable JSON artifact outside Git
        |
        +--> side-by-side comparison renderer
```

`AppServerProcess` is a transport module. It knows JSON-RPC request identity,
process lifecycle, event correlation, and timeout cancellation. It knows
nothing about finance questions.

`AppServerBenchmarkRunner` owns frozen-case iteration and artifact assembly. It
does not implement agent planning, repair, routing, or answer rewriting.

This separation keeps the future production seam open: if the experiment wins,
the transport can be reused behind a later `CodexAppServerRuntime`; if it loses,
the benchmark code can remain isolated or be deleted without changing product
execution.

## App Server Session Contract

### Process lifecycle

1. Resolve a tested Codex binary, preferring the desktop-bundled binary already
   used by the existing headless smoke, then `codex` on `PATH`.
2. Record the resolved path and version without copying credentials or config.
3. Start one `codex app-server --stdio` child process.
4. Keep stdout exclusively for JSONL protocol messages and collect bounded
   stderr diagnostics separately.
5. Send exactly one `initialize` request and one `initialized` notification.
6. Reuse the process across cases, but never reuse a finance thread across
   cases.
7. Terminate the child cleanly after the final case; force-kill only after a
   bounded shutdown grace period.

### Per-case thread

Each case starts an ephemeral thread with:

- `cwd=/Users/a77/finance-workspace-private`;
- read-only sandbox;
- approval policy `never`;
- no additional writable roots;
- quick tier mapped to medium reasoning and deep tier mapped to high reasoning,
  matching the existing Codex headless comparison policy;
- model selected from the active Codex account/config and recorded in the
  artifact rather than assumed;
- no cross-case history.

The client must reject or auto-deny any server request for broader filesystem,
network, or command permission. The experiment never pauses for human approval.

### Turn input

The model receives:

- the raw user question;
- the case `as_of` as an immutable information cutoff;
- the default A-share market assumption already selected by the product;
- an instruction to use repository and database material read-only;
- an instruction to give a direct Chinese judgment, evidence, uncertainty,
  continuation conditions, and invalidation conditions where relevant.

Frozen `required_outputs` remain evaluator data. They are not shown to Codex,
because doing so would reintroduce the precompiled answer plan this experiment
is intended to remove.

The final turn uses a minimal output schema with one required natural-language
`answer` string and optional `data_cutoff` and `sources` fields. It does not
constrain headings, paragraph count, claim markers, routes, or tool order.

## Repository and Domain Harness Use

Codex may use the domain harness that is naturally available in the repository:

- project `AGENTS.md` and any applicable nested instruction files;
- available finance skills selected by their descriptions;
- `CLAUDE.md` and indexed project documentation when the model decides they are
  relevant;
- local read-only query commands and scripts;
- DuckDB, market exports, Wiki, and relation-query helpers within the sandbox.

The runner does not concatenate these files into a giant system prompt. Codex
must discover and load them through its own harness. This is intentional: the
experiment tests the same generic-plus-domain composition that works in an
interactive Codex session.

The experiment does not automatically invoke the Workbench's executable
`EvidenceLedger` or semantic verifier. Those remain comparison dimensions. A
highly fluent but unsupported answer must therefore lose on evidence quality
even if it wins on directness.

## Event and Artifact Model

The runner persists one bounded case record containing:

- case id, question, `as_of`, tier, and timeout;
- Codex binary version and reported model/config identity when available;
- thread id and turn id;
- terminal turn status and error kind;
- final structured answer;
- ordered, sanitized Item summaries;
- tool names and bounded result summaries, excluding raw secrets and hidden
  reasoning;
- input/output token usage when emitted by App Server;
- wall-clock latency;
- permission requests and their denial outcome;
- artifact SHA-256.

The aggregate artifact contains every requested case, including failed cases.
Infrastructure failure must not silently omit a question or fall back to an SDK
answer.

Artifact paths remain under `/Users/a77/.finance-runtime/evals/`. They are not
staged or committed. Public comparison views must not contain credentials,
private configuration, hidden reasoning, raw database paths, or evidence
hashes.

## Failure Handling

- Missing binary or unsupported App Server command: fail the benchmark before
  the first case with a typed readiness error.
- Initialization failure: capture bounded stderr and stop; do not try headless
  fallback.
- Server overload `-32001`: retry once with bounded exponential backoff and
  jitter, then fail that case.
- Case deadline: send `turn/interrupt`, wait for terminal interrupted status,
  and record a timeout result.
- Unexpected approval or permission request: deny it, record it, and continue
  only if the server can proceed safely.
- Child exit mid-case: mark the case as infrastructure failure; restart at most
  once for the next case, never for the same case.
- Malformed JSONL or mismatched request id: fail closed and preserve sanitized
  diagnostics.
- Missing final answer despite `turn/completed`: mark protocol failure rather
  than treating intermediate text as a final answer.

## Comparison Method

The comparison reuses existing questions and existing baseline artifacts. It
does not rerun GLM or SDK GPT.

For each case, the view shows answers without backend labels and evaluates:

1. direct answer to the literal user ask;
2. use of relevant local structured data;
3. subject and time alignment;
4. factual and numeric support;
5. explicit uncertainty, continuation, and invalidation conditions;
6. irrelevant retrieval or topic contamination;
7. template/control-plane leakage;
8. latency and model/tool-call cost.

The first decision signal is qualitative blind preference, supported by the
existing deterministic task-alignment and contamination checks where they
apply. Five cases are sufficient to choose the next engineering experiment,
not to claim production superiority.

## Acceptance Criteria

1. One App Server process completes initialization and serves independent
   ephemeral threads.
2. Every frozen question produces either a terminal answer or an explicit typed
   infrastructure failure in the artifact.
3. The process and all threads remain read-only; no repository or private data
   file changes during the run.
4. The artifact records model, timing, usage, thread/turn ids, terminal status,
   and sanitized event summaries.
5. Existing GLM/GPT artifacts are reused, not regenerated or edited.
6. A backend-blind side-by-side comparison can be reviewed case by case.
7. No change reaches the Workbench composition root, canonical 8792/8799, or
   `main`.

## Decision Gate After the Experiment

- App Server clearly improves directness and useful repo-data use without a
  material truth regression: design option B, exposing the existing finance
  registry through a bounded App Server tool bridge and the shared exit gates.
- App Server improves prose but loses evidence discipline: keep the harness
  candidate, but move `EvidenceLedger` and verifier behind the future adapter
  before any canary.
- App Server does not materially improve answers: stop runtime integration and
  diagnose domain-tool discoverability, data semantics, and instruction
  interference.
- App Server fails operationally under read-only/auth constraints: retain it as
  a non-production reference and continue with the provider-neutral SDK lane.

No result from this five-case experiment authorizes a production switch.
