# Dual-Lane Producer/Reviewer Loop Design

Date: 2026-07-26
Status: approved direction; implementation pending
Scope: local Finance Agent Runtime development only

## 1. Objective

Codex is the only code Producer. Claude is the preferred independent Reviewer.
The loop must keep development moving when Claude is temporarily unavailable
without letting Codex's self-review masquerade as independent approval.

The design separates three authorities:

1. **development authority**: permission to implement another bounded slice;
2. **slice sealing authority**: independent confirmation that a slice is sound;
3. **release authority**: permission to merge, cut over runtime, or publish.

Producer self-review may provide the first authority only. External Claude
review is required for the second and third.

## 2. Non-goals

- The loop does not merge `main`, switch canonical 8792, or push a release.
- It does not weaken finance truth, verifier, task-fulfillment, benchmark, or
  invalid-action gates.
- It does not let a shell-only checker count as an LLM architecture review.
- It does not make Claude and Codex edit the same worktree.
- It does not run the frozen live benchmark except for `release` requests.
- It does not make old, self-signed verdicts retroactively independent.

## 3. Review states

Each request has exactly one effective gate state:

| State | Meaning | May develop next slice | May seal slice | May release |
|---|---|---:|---:|---:|
| `WAITING_EXTERNAL` | valid request, no valid verdict | no until SLA expires | no | no |
| `EXTERNAL_PASS` | whitelisted independent PASS | yes | yes | only if release gate also passes |
| `CHANGES_REQUIRED` | valid external findings | no | no | no |
| `PROVISIONAL_PASS` | Producer fallback self-review | yes, bounded | no | no |
| `BLOCKED` | same architecture conflict survives two repair reviews | no | no | no |
| `INVALID` | provenance/schema/ancestry failure | no | no | no |

`PROVISIONAL_PASS` is stored separately from official verdicts. It can never be
upcast to `EXTERNAL_PASS` by renaming a field or copying a file.

## 4. Identities and provenance

### 4.1 Producer

The Producer identity is `codex:producer`. Codex and all Codex subagents belong
to the same independence class. A Codex subagent verdict is therefore a
Producer self-review, not an external verdict.

### 4.2 External reviewer whitelist

The first whitelist contains only:

```text
claude:independent-reviewer
```

Adding an identity requires a separate protocol-only review. Reviewer labels
that merely contain `claude` are not accepted; the exact configured identity
must match.

### 4.3 Commit ancestry

A verdict is effective only when all conditions hold:

- verdict review ID matches the request;
- verdict commit exactly matches the immutable request commit;
- the request commit exists;
- the request commit is an ancestor of the current Producer branch tip;
- the request file hash still equals the hash recorded when the worker claimed
  it;
- the reviewer identity is allowed for the requested authority.

A PASS for an abandoned commit is retained as historical evidence but grants no
current development, sealing, or release authority.

## 5. Request contract

The first machine-generated requests use schema version 2. After the first
external falsification cycle, new requests use schema version 3 with the same
public fields plus a stricter invariant: `artifacts` must cover every path in
`parent_commit..commit`. Existing schema-2 history remains valid and immutable.
An artifact may exist at either end of that review range, so deleted files are
declared and reviewable instead of making the contract unsatisfiable.

The request shape is:

```json
{
  "schema_version": 2,
  "review_id": "ARL-0016",
  "commit": "full sha",
  "parent_commit": "full sha",
  "branch": "feat/agent-runtime-backends-verify",
  "producer": "codex:producer",
  "scope": "one independently testable slice",
  "artifacts": ["..."],
  "artifact_tests": {"path/to/x.py": ["path/to/test_x.py"]},
  "required_checks": ["..."],
  "depends_on": ["ARL-0015"],
  "supersedes": null,
  "intensity": "light|milestone|release",
  "created_at": "ISO-8601",
  "status": "ready"
}
```

The submitter writes through one helper. The helper resolves the commit,
discovers required tests, validates dependencies, writes atomically, and stores
the request SHA-256. Hand-written schema-2 requests are rejected by the gate if
the mechanical fields do not match recomputation.

For a superseding repair, the helper follows the complete `supersedes` chain
to its first failed request. The repair's `parent_commit` is that root
request's parent, not the latest dependency commit. Its artifact union covers
every request from the root finding through the latest dependency. Therefore
the external reviewer sees the complete tainted diff, including intermediate
requests that were developed provisionally. A later repair of a failed repair
retains the same review root.
The helper also carries the union of all non-`repair:*` required checks in that
range. A combined repair PASS can seal only slices whose artifacts and checks
were both present in the external review manifest.

## 6. Mechanical artifact-to-test coverage

For every Python artifact, the submit helper and reviewer independently search:

1. `intelligence/services/X.py -> intelligence/tests/test_X.py`;
2. `package/X.py -> package/tests/test_X.py`;
3. tests importing the changed module, discovered with exact `rg` import hits;
4. test files changed in `parent_commit..commit`.

Every existing direct test must appear in `artifact_tests` and the reviewer run
manifest. Missing tests make the request `INVALID`; they cannot be waived by
omitting them from `required_checks`.

Nonstandard mappings require an explicit waiver containing a reason and a
Reviewer finding. Waivers are forbidden for gate/verifier/budget/session
modules.

## 7. External reviewer worker

The worker:

1. acquires a single-instance lock;
2. selects the oldest valid frontier request;
3. freezes the request file hash;
4. verifies the commit is on the current Producer branch;
5. creates a detached worktree at the exact commit;
6. invokes `claude -p` with read-only repository tools and write access only to
   the verdict destination;
7. runs mechanical artifact tests plus request checks;
8. validates the returned JSON before publishing it atomically;
9. removes the detached worktree;
10. records success, inactivity, budget exhaustion, or transport failure.

Budget exhaustion is not retried immediately. The worker applies exponential
backoff and emits `REVIEWER_INACTIVE`. This prevents the existing infinite
`Exceeded USD budget` retry loop.

## 8. Producer fallback lane

### 8.1 Entry

Fallback is eligible when no valid external verdict exists and one of these is
observable:

- Claude exits with a budget, authentication, transport, or usage-limit error;
- the worker is inactive;
- the external-review SLA expires.

Initial SLA: 15 minutes for `light`, 30 minutes for `milestone`. Release requests
have no fallback SLA and always wait for external review.

### 8.2 Self-review

The Producer runs a separate Codex invocation in a detached worktree. It must
run the same mechanical tests and falsification checklist as Claude. The result
is stored under `provisional-verdicts/` with reviewer class
`producer_fallback`.

### 8.3 Speculation limit

At most two unsealed slices may exist after the latest externally sealed
commit. A third request is denied until Claude catches up. This bounds repair
debt while keeping work moving through short outages.

If Claude later returns `CHANGES_REQUIRED` for a provisionally passed ancestor:

- Producer stops creating new slices;
- descendants are marked `TAINTED_BY_ANCESTOR_FINDING`;
- Producer fixes forward without rewriting published request/verdict history;
- all tainted descendants require new external review.

## 9. Producer gate

Before editing the next slice, the Producer runs one gate command. The command
returns a machine-readable decision containing:

- current branch and tip;
- latest valid external sealed commit;
- pending request;
- external/provisional verdict status;
- provisional depth;
- allowed next action: `WAIT`, `FIX`, `IMPLEMENT_NEXT`, or `RELEASE_CHECK`;
- reasons and invalid provenance records.

The Producer must not infer authority by checking whether a file merely exists.
Only this validated decision controls progression.

## 10. Release gate

Release remains impossible unless:

- provisional depth is zero;
- every reachable milestone slice is covered by an external PASS, either on
  its own request or on a superseding repair whose reviewed
  `parent_commit..commit` range and artifact union include that slice;
- the current tip has an external `milestone` or `release` verdict;
- deterministic full regressions pass on the exact tip;
- a release request runs the frozen live benchmark once;
- no unresolved `CHANGES_REQUIRED`, `BLOCKED`, `INVALID`, or tainted descendant
  exists;
- the user separately authorizes `main` merge and canonical runtime cutover.

## 11. Legacy migration

Existing request and verdict files remain immutable. They are classified:

- Codex/subagent verdicts: `LEGACY_SELF_REVIEW`;
- verdicts for non-ancestor commits: `LEGACY_ABANDONED_COMMIT`;
- missing verdicts whose commits are superseded by a reviewed descendant:
  `LEGACY_SUPERSEDED_UNSEALED`;
- `ARL-0014`: first valid external review;
- `ARL-0015`: bootstrap provisional result because Claude exhausted its review
  budget; it grants development authority only.

The first schema-2 request receives a new review ID. Legacy files are never
edited to fabricate compliance.

## 12. Files and ownership

Versioned implementation lives in the Producer repository:

```text
scripts/agent_review/contract.py
scripts/agent_review/submit.py
scripts/agent_review/gate.py
scripts/agent_review/validate_verdict.py
scripts/agent_review/reviewer_worker.sh
scripts/agent_review/producer_fallback.py
intelligence/tests/test_agent_review_contract.py
intelligence/tests/test_agent_review_gate.py
```

Mutable runtime state stays outside Git:

```text
/Users/a77/.finance-runtime/agent-review-loop/
  requests/
  verdicts/
  provisional-verdicts/
  runs/
  locks/
  state/
```

The versioned worker is the source of truth; runtime copies include its commit
and checksum in logs.

## 13. Failure handling

- malformed request: `INVALID`, no model call;
- request mutation after claim: discard review and mark invalid;
- stale/wrong commit verdict: quarantine, never consume;
- non-whitelisted PASS: record as provisional at most, never official;
- Claude budget failure: backoff, allow bounded provisional lane;
- duplicate workers: filesystem lock lets one continue;
- worker crash: idempotent restart from request/verdict state;
- tests fail: `CHANGES_REQUIRED`, never PASS;
- external verdict conflicts with provisional verdict: external verdict governs;
- two consecutive external reviews report the same architecture conflict:
  `BLOCKED` and user escalation.

## 14. Acceptance tests

Deterministic tests must prove:

1. Codex/subagent PASS is rejected as external approval.
2. Exact reviewer whitelist is enforced.
3. Wrong/stale verdict commit is rejected.
4. A verdict for a non-ancestor commit grants no authority.
5. A mutated request is rejected after claim.
6. Missing `test_X.py` coverage makes a request invalid.
7. Claude timeout permits one provisional slice.
8. Two provisional slices are allowed; the third is denied.
9. External `CHANGES_REQUIRED` taints provisional descendants.
10. External PASS clears the corresponding provisional debt.
11. Release is denied while any provisional debt remains.
12. Worker budget failure backs off instead of immediate retry.
13. Duplicate worker lock prevents concurrent claims.
14. Legacy verdicts are classified without mutation.

No acceptance test requires a live Claude or Codex call. Worker integration has
one local smoke using fake reviewer executables; real model calls are a separate
operational smoke after deterministic tests pass.

## 15. Success criterion

The loop is considered active only when:

- gate status is machine-readable;
- one worker instance is healthy or explicitly inactive;
- a new request is automatically consumed;
- Producer can progress through a bounded outage using provisional state;
- external review catches up and seals commits;
- no internal review can authorize release;
- the user does not need to copy findings between sessions.
