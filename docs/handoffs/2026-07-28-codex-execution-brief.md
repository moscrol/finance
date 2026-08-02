# Codex Execution Brief — Phase A → A.5 → B/C entry

Date: 2026-07-28
Authority: this brief is an execution wrapper. The reasoning source of truth is
`docs/handoffs/2026-07-28-adaptive-finance-runtime-canonical-handoff.md`.
Where the two disagree, the canonical handoff wins and this brief is wrong.

Scope of this brief: Phase A (finish the uncommitted parity WIP), Phase A.5
(integrate the isolated acceptance assets), and the preregistration step that
gates Phase B. **Do not implement App Server. Do not run the 28-case board.**

---

## 0. Verified starting state

Confirmed by direct inspection on 2026-07-28, not from memory:

```text
cwd      /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
branch   feat/agent-runtime-backends-verify
HEAD     f0742f72
status    M intelligence/tests/test_run_agent_runtime_benchmark.py
          M scripts/run_agent_runtime_benchmark.py
         ?? docs/handoffs/2026-07-28-adaptive-finance-runtime-canonical-handoff.md
```

The canonical handoff is currently **untracked**. Commit it deliberately as
documentation; do not let it disappear in a checkout.

### Git topology you must not get wrong

```text
acceptance assets   8279b2bd67faf0e8a2adc570dadaa8482c973b53
merge base          0430d544
acceptance ahead    10 commits / 31 files
runtime ahead       399 commits
```

Two facts that change how you integrate:

1. **The objects are already in this copy.** `git ls-tree 8279b2bd` and
   `git cat-file` both succeed here, and `0430d544` is present. You do not need
   to fetch anything to read or extract those files.
2. **There is no local branch ref**, and this copy's `origin` is
   `/Users/a77/.finance-runtime/agent-runtime-backends-c4673667` — the *older*
   runtime copy, which does not carry the acceptance work. The branch name
   `eval/acceptance-board` exists only in the primary workspace
   `/Users/a77/finance-workspace-private`.

Therefore: address the assets by **SHA `8279b2bd`**, never by branch name, and
do not add a remote or fetch from `origin` expecting to find them.

---

## 1. Phase A — finish the parity WIP

Goal: the release benchmark and the Workbench must exercise the same
Adapter-owned repair/verification path. The current red is a fake-fixture
contract defect, not a product defect.

Repair only the fake fixture so that it satisfies:

- both mandatory evidence capabilities (`current-mainline` needs
  `market_data` + `mainline_context`);
- all three required outputs bound;
- every `CallbackEpisodeSession.resume()` appends a `model_turn` after
  `repair_goal` and `repair_reentry`.

```bash
env -u FORESIGHT_USERS_DIR \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_run_agent_runtime_benchmark.py \
  -k production_adapter_delivery_repair
```

Then:

1. Run the whole benchmark test file; keep compatibility for runtimes that only
   implement one-shot `run()`.
2. Add the typed-accounting regression: `sdk_timeout` → `invalid_actions == 0`;
   `sdk_invalid_finish` → `invalid_actions == 1`.
3. Run focused benchmark/runtime/Adapter suites, then the executable full
   `intelligence/tests` suite.
4. Commit as one parity concern. Restore a clean tree.

Prohibited shortcuts: raising the timeout, ignoring the protocol issue,
synthesizing an answer directly from evidence, or changing product behavior
merely to make the fake pass. Each of those hides the skipped composition root.

Exit: clean tree, both lanes through `ContinuousTurnAdapter`, tests green.

---

## 2. Phase A.5 — integrate the acceptance assets

Only after Phase A is committed and the tree is clean.

**Rule zero: integrate, do not rebuild.** A second acceptance suite is a
forbidden outcome. If you find yourself authoring new case definitions or
regenerating a reference answer, stop.

### What to bring over

31 files at `8279b2bd`:

```text
intelligence/eval/acceptance.py
intelligence/eval/cases/acceptance_cases.json
intelligence/tests/test_acceptance_board.py
intelligence/eval/cases/reference_snapshots/*.knevo.json      (22 files)
intelligence/eval/runs/20260727T025642Z.json
intelligence/eval/runs/20260727T032229Z.json
docs/learning/knevo-distill/q13-*.md q14-*.md q15-*.md
docs/learning/knevo-distill/question-bank.md
```

Extraction works locally, e.g. `git checkout 8279b2bd -- <path>`, because the
objects are present. Cherry-picking the ten commits is also acceptable if you
want the authorship trail; the compatibility surface to review is small and
confined to the API/Run schema that `acceptance.py` reads.

### Immutability constraints

Preserve byte-for-byte: every frozen answer, `answer_sha256`, `asked_at`,
`via`, `source_meta`, snapshot caveats, and both historical run files. These are
external evidence. Re-freezing a reference after seeing a Workbench answer makes
the examinee the examiner and invalidates the comparison permanently.

### Compatibility check

`acceptance.py` reads live runtime shapes. Verify these still exist on the
current runtime branch before declaring integration done:

```text
POST /api/conversations
POST /api/conversations/{id}/messages
GET  /api/conversations/{id}/messages?user=...
GET  /api/runs/{run_id}/context     -> evidence[], gaps[]
GET  /api/runs/{run_id}/trace       -> [{name: ...}]
message fields: invoked_skill_ids, citations, degrades, run_id, status
```

Note the probe history: an earlier version read `tools_called`, which does not
exist on the message body, so every trace recorded zero tools. If a field is
missing now, fix the probe to read the real field — do not silently record an
empty list.

### Verification

1. Run `test_acceptance_board.py` plus current API/Run-store tests.
2. Run `acceptance board` and confirm it reads both imported historical runs
   **without** claiming they have pass verdicts.
3. Add a provenance note recording source SHA `8279b2bd` and the resulting
   integration commit.

**Do not run the 28 questions during integration.** The purpose is availability
on the runtime branch, not consuming quota before the budget and retrieval seams
are fixed.

Exit: one canonical 28-case definition, 22 immutable snapshots, a working
real-path board, and no duplicated suite.

---

## 3. What the acceptance assets do and do not contain

Read this before interpreting any number from the board.

### Case distribution

```text
high_freq  10   (A1–A10)   daily market, mainline, stage, sentiment
mid_freq    8   (B1–B8)    themes, fermentation, cross-table, valuation
long_tail  10   (C1–C10)   honesty and dirty-data recognition
total      28
```

Special annotations already in the case file:

```text
expect_refusal      C1, C2, C3, C8
forbid_future_data  C7
known_data_bug      C4, C5
```

### The scoring seam is deliberately absent

`acceptance.py` provides preflight, real Conversation API execution with
multi-turn continuity, Run evidence/trace collection, immutable reference
freezing, and a board that classifies not-run / no-output / degraded /
answered-awaiting-judgment.

It does **not** compile `expect_facts`, `pass_rule`, or blind-reference
judgments into a `passed` verdict. Its own source says the deterministic
`agent_eval` gates plus blind review must supply the final count.

Consequently, about the two stored runs:

```text
20260727T025642Z   1 case  /  1 answered turn
20260727T032229Z  10 cases / 12 answered turns
both: preflight ok, runtime revision 17e0b21a, backend sdk_gpt
neither run nor any case carries a `passed` field
```

**The current 28-case pass rate is unknown.** It is not 0, and it is not the
count of completed message envelopes. Reporting either would be a false
baseline. Say "unknown pending the verdict compiler."

### Knevo snapshots: 22, and not a uniform oracle

Missing snapshots, mostly on purpose:

```text
A8-market-stage           A9-sentiment-contradiction
B6-sellside-distillation  C3-empty-table
C4-unit-anomaly           C8-nonexistent-table
```

Those questions lean on local-only definitions, known dirty tables, or internal
ingest semantics where Knevo is not an oracle. Workbench acceptance still uses
all 28. Knevo comparison uses only eligible cases and dimensions — **do not
divide every cross-product score by 22**, and do not buy low-value answers to
fill a denominator.

Limitations already recorded in the snapshot metadata:

- A2 / C7 carry hindsight and cannot validate historical forecast correctness;
- A5 / A6 / A10 reconstruct historical structure from later or partial material,
  useful mainly for narrative organization;
- project-defined vocabulary (双红, stage-day, internal ingest labels) must not
  become an external-agent vocabulary test;
- `must_mention` is a Workbench product-language requirement, not a cross-agent
  literal-word gate;
- Knevo's real reference strength is methodology, retrieval breadth, and answer
  organization; local structured tables remain the oracle for project-defined
  historical cross-sections.

### Gate discipline

`aggregate_gate` is `0.0` on purpose: record, do not block. Keep it
observational until a valid baseline and a calibrated rubric exist, then
preregister a non-zero threshold **before** the scored run. Tuning the gate to
answers you have already read destroys its meaning.

### Codex reference route

The branch planned 28 `codex_exec` references but recorded the sidecar
unavailable on 2026-07-27 (cockpit-cliproxy `:57244` → 503, direct curl → 401).
Recheck rather than repeat that diagnosis. Use the full binary path — `codex` is
not on `PATH`:

```text
/Applications/ChatGPT.app/Contents/Resources/codex
codex-cli 0.146.0-alpha.3.1   (re-verify, do not assume)
```

Use the user-selected model, not the case file's older `gpt-5.5` example. Codex
references are comparative material only; the real Conversation API run is the
sole Workbench product result.

---

## 4. Preregistration that gates Phase B

Do not start Phase B by editing global `ResearchPolicy` constants. Add a
benchmark-only typed budget profile or DI seam so production defaults are
untouched and the artifact records the exact profile.

The confound being isolated:

```text
standard          90s / 6 calls / 20s base reserve
benchmark         30s synthesis reserve
codex timeout     90 - 30 = ~60s
gateway floor     65% of 60 = ~39s
effective window  ~21s before research_stage_closed becomes reachable
```

The outer reserve and the gateway floor overlap — a double reservation, which is
a sharper claim than "90 seconds is short."

Four profiles whose pairwise comparisons are physically exercisable:

| Profile | Total | Calls | Gateway floor | Pairwise purpose |
|---|---:|---:|---|---|
| A control | 90s | 6 | current 0.65 | current behavior |
| B floor ablation | 90s | 6 | 0.65 off; delivery buffer only | A→B isolates premature floor |
| C long / capped | `T_long` | 6 | delivery buffer only | B→C isolates wall-clock room at fixed cap |
| D long / expanded | `T_long` | 12 | delivery buffer only | C→D isolates the six-call cap |

Derive and preregister `T_long` from observed p90 inter-call latency (~8s),
initial model latency, 12 calls, and a delivery buffer. 150s is the minimum
plausible envelope; use 180s if the derived value is not safely under 150. The
point is making cell D able to reach calls 7–12 — **not** proposing 180s as a
product SLA.

If D still cannot exercise the intended cell, mark the ablation **invalid**
rather than reading it as a quality failure.

Three diagnostic cases only: `rebound-duration`, `weekly-market-cause`,
`ruihuatai-valuation`. Same revision, binary, model, PIT data, prompt, verifier.
Preregister profiles and artifact paths before looking at output. Model output is
stochastic, so one result is directional; add at most one bounded confirmation
run when the first pair would change the decision. Do not drift into endless
five-case reruns.

Measure: whether the next intended tool was admitted; useful evidence gained per
call; repeated same-tool and duplicate-query rates; unique evidence hashes per
call; formal bindings and contract status; blind directness; latency;
unsupported claims; and whether research continued after evidence was already
sufficient.

---

## 5. Hard boundaries

From the canonical handoff, non-negotiable without new user approval:

- do not merge `main`; do not switch or restart canonical 8792; do not treat
  8799 as canonical;
- do not delete the legacy answer path;
- do not commit `.env*`, credentials, databases, private memory, benchmark
  artifacts, caches, or user data;
- do not develop in the primary workspace `/Users/a77/finance-workspace-private`
  — it is heavily dirty with unrelated user work;
- do not weaken structural/semantic gates, citation checks, freshness, or
  protocol accounting to make an artifact green;
- do not turn a failing example into a new route, skill, output schema, or
  template;
- do not implement or run App Server: the first spec has an independent
  `CHANGES_REQUIRED` review and 13 mandatory corrections (canonical §9). The
  design header saying "approved option A" is not permission to run it as-is.

Reporting honesty, specifically:

- do not report this working copy as green while the parity test is red;
- do not report the two historical acceptance runs as 0% or as passed;
- do not treat all 22 Knevo snapshots as ground truth.

---

## 6. Definition of done for this brief

1. Phase A committed; tree clean; focused and full suites green.
2. Acceptance assets integrated from SHA `8279b2bd` with frozen evidence intact,
   `test_acceptance_board.py` green, board reading historical runs without
   inventing verdicts, provenance note recorded.
3. Phase B profiles and artifact paths preregistered in writing, with `T_long`
   derived and justified.
4. No 28-case run, no App Server code, no `main` merge, no gate changes.

Report back: what was verified by execution versus what remains assumed. If
Phase A.5 surfaces an API/Run schema drift that the board cannot read, say so
plainly rather than adapting the frozen assets to fit current code.
