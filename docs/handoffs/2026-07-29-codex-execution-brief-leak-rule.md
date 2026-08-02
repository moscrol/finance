# Codex Execution Brief — Sealed Fixture Leak-Rule Repair (Task 2.5 → 4)

Date: 2026-07-29
Authority: execution wrapper. Reasoning source of truth is
`docs/superpowers/plans/2026-07-29-app-server-ceiling-sealed-fixture.md` and the
Task 2 handoff. Where they disagree with this brief, they win.

Scope: close the real-fixture leak gate honestly, then finish Task 3 and Task 4.
**Do not implement the App Server runner. Do not merge `main` or KB `9053b0c4`.**

---

## 0. Corrected starting state

The Task 2 handoff is stale on two points. Verified by execution, not memory:

```text
handoff claims HEAD   9f9b2ae5   (Task 2)
actual HEAD           31c1138a   feat: build physical finance pit fixture
                                 2026-07-29 11:07:05 +0800
branch                feat/agent-runtime-backends-verify
dirty                  M intelligence/eval/ceiling_pit_fixture.py
                       M intelligence/tests/test_ceiling_pit_fixture.py
                      (966 insertions uncommitted on top of 31c1138a)
```

All eight commits the handoff cites do exist and are reachable. But two of its
statements are now wrong and must not be carried forward:

1. **"Tasks 3-7 pending" is wrong.** Task 3 is committed at `31c1138a`, which
   introduced both `intelligence/eval/ceiling_pit_fixture.py` (520 lines) and
   `intelligence/tests/test_ceiling_pit_fixture.py` (237 lines).
2. **"The worktree also contains an untracked `test_ceiling_pit_fixture.py`
   created during concurrent Task 3 work… must be preserved until its
   owner/scope is verified" is resolved.** That file is no longer untracked;
   `git log --diff-filter=A` shows `31c1138a` added it. Ownership is settled —
   it is Task 3's own test. There is no orphaned artifact to protect. What
   *does* need care is the 966 uncommitted lines sitting on top of it.

Current test state, executed:

```text
test_ceiling_leakage.py + test_ceiling_instruction_export.py   18 passed
test_ceiling_pit_fixture.py (with uncommitted WIP)             11 passed
```

So the WIP is green, not red. Decide deliberately whether it is a reviewed slice
worth committing or exploratory work; do not leave 966 green-but-unreviewed lines
drifting while you start new work.

Interpreter (the venv `python` is a symlink, use the full path):

```bash
env -u FORESIGHT_USERS_DIR \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q
```

---

## 1. The leak gate: root cause is confirmed

The handoff's diagnosis is correct, and I verified the mechanism in
`intelligence/eval/ceiling_leakage.py`. `_match_rule` tries rules in order:

```python
if forbidden.char_stream and forbidden.char_stream in candidate_chars:
    return "full_normalized_match", 1.0          # line 221-222
if candidate_char_ngrams & forbidden.char_ngrams:
    return "character_ngram_match", 1.0
if candidate_token_ngrams & forbidden.token_ngrams:
    return "token_ngram_match", 1.0
score = _jaccard_sets(candidate_token_set, forbidden.token_set)
if len(forbidden.tokens) >= 8 and score >= _JACCARD_THRESHOLD:
    return "token_jaccard_match", score
```

Tuned constants:

```text
_CHAR_NGRAM                     12
_TOKEN_NGRAM                     6
_JACCARD_THRESHOLD            0.80
_SEMANTIC_CANDIDATE_THRESHOLD  0.15
```

The asymmetry is the whole bug: the Jaccard rule is length-guarded by
`len(forbidden.tokens) >= 8`, and the n-gram rules are implicitly length-guarded
by needing 12 chars / 6 tokens to produce any n-gram at all. **`full_normalized_match`
has no length guard whatsoever.** It is bare substring containment. A
`required_output` entry of `"总成交额"` or `"反弹阶段"` therefore matches any
production file that happens to contain that phrase, at confidence 1.0.

That explains the observed shape precisely: 1,851 findings where even the neutral
generated `AGENTS.md` trips short `required_output` entries. It is a rule defect,
not evidence of 1,851 leaks.

Do not "fix" this by raising `_CHAR_NGRAM`, dropping `full_normalized_match`, or
excluding `UBIQUITOUS_LANGUAGE.md` and `intelligence/README.md`. Those all fail
open on the case the gate exists to catch — a genuinely pasted answer.

### The data you need is already there

No new plumbing is required to produce the kind-aware breakdown. `ForbiddenText`
already carries `kind: LeakKind`, and `add()` encodes it as the `source_id`
prefix:

```python
source_id=f"{kind}:{source}:{len(entries) + 1}"
```

`LeakFinding` already carries `relative_path`, `source_id`, `rule`,
`sentence_sha256`. So kind, rule, and file are all recoverable from existing
findings by parsing the `source_id` prefix. The one field genuinely missing from
the finding record is **normalized forbidden length**, which the diagnostic needs
in order to separate long gold text from short vocabulary.

The nine kinds in play:

```text
question              conversation_context   required_output
direct_target         reference_answer       expected_fact
pass_rule             prior_answer           post_cutoff_result
```

---

## 2. Step one — diagnose before amending

Produce a deterministic diagnostic receipt aggregating the current 1,851
findings by:

- `kind` (parsed from `source_id`, or plumbed through explicitly);
- normalized forbidden length in characters and tokens;
- `rule`;
- `relative_path`.

Requirements:

- self-hashed and recomputed on audit, like every other control receipt;
- covered by a test that pins the aggregation, not just the totals;
- **must not** change gate behavior. This step is observation only.

Then classify by hand, and write the classification down: which findings are
plausible gold leakage, and which are common finance/runtime vocabulary. That
written classification is the input to step two. Amending the rule before this
breakdown exists means tuning against an unknown distribution.

---

## 3. Step two — preregister the kind-aware rule

Preregister the amended rule **in the spec, with the diagnostic receipt attached,
before** you implement it. The protections that must survive:

- exact long question/reference detection stays unrestricted-substring;
- 12-character and 6-token n-gram overlap stays;
- strict identifier matching stays exact regardless of length;
- semantic-review candidates stay preserved, not suppressed.

The defect to remove: short generic rubric fragments acting as substrings
everywhere. A minimum normalized length for `full_normalized_match` on the short
rubric kinds (`required_output`, `expected_fact`, `pass_rule`) is the obvious
shape, but derive the threshold from the diagnostic distribution and justify the
number. Do not pick it to make the count reach zero.

Kinds that must **not** be length-relaxed: `question`, `reference_answer`,
`prior_answer`, `post_cutoff_result`, `direct_target`. Those are the gold classes
the gate exists for.

Then obtain independent spec review before the real regeneration. Use
`gpt-5.6-sol` for authorized semantic work.

Honest-outcome clause: if after a correct rule the scan still rejects, that is a
finding, not a failure to route around. Report the surviving findings.

---

## 4. Step three — regenerate from an immutable commit

Requirements, all of which already fail closed in code:

```text
files_scanned > 0                 (ValueError if zero)
export root is a real directory   (rejects symlink/missing/non-dir)
deterministic pass
semantic candidates preserved
final tamper audit valid          (recomputes canonical scan hash)
```

Reference point from the prior probe: 312 files, ~5 MB, 112,787 lines, 84
forbidden entries, ~4.4s. The performance regression is closed — forbidden text
is precompiled once via `_prepare_forbidden_text`, and the invariant test pins
it. If a regenerated scan drifts back toward per-pair normalization, that test
should go red; treat it as a blocker, not noise.

---

## 5. Step four — Task 3 disposition, then Task 4

Task 3 is committed. So the remaining Task 3 work is only:

1. decide the fate of the 966 uncommitted lines — review and commit as a
   deliberate slice, or discard;
2. confirm the committed Task 3 satisfies its own plan section: conservative
   temporal-column policy, post-build future-row audit, unknown temporal schema
   fails closed.

Then Task 4: a regular-blob cutoff Wiki export plus a fresh true-Hybrid index,
using KB code `9053b0c4` **in isolation**, with `KB_RAG_PYTHON` set explicitly.
Do not merge that KB revision. Note the two knowledge roots remain distinct
(`/Users/a77/知识库` and `/Users/a77/knowledge-base-private`); pick one
canonical root and prove it is not an alias before exporting.

Not in this brief: Tasks 5–7, the headless control, the App Server runner, the
28-case board.

---

## 6. Hard boundaries

- do not merge `main`, switch 8792, or merge KB `9053b0c4` without authorization;
- do not implement the App Server runner or a live run while provider-executed
  identity is unobservable — record it **ineligible** rather than guessing;
- do not weaken cutoff, freshness, EvidenceLedger, invalid-action, or semantic
  gates to obtain green;
- do not add per-question routes or templates;
- do not commit keys, databases, indexes, model weights, logs, caches, or
  virtualenvs;
- use `gpt-5.6-sol` for authorized semantic/live work.

Reporting honesty:

- do not report 1,851 findings as 1,851 leaks; it is a rule defect plus an
  unknown real subset;
- do not report the 28-case board pass rate — the acceptance assets are present
  (22 snapshots, 2 runs, integrated at `65dbacfe`) but still carry no `passed`
  verdict field;
- do not describe Task 3 as pending, or the PIT test as an orphaned untracked
  file;
- the last recorded full suite was `2993 passed, 14 failed, 2 skipped`, all 14
  reproduced managed-sandbox loopback-bind failures. Re-verify rather than
  reciting; do not let that number launder a new regression.

---

## 7. Definition of done

1. Diagnostic receipt committed, self-hashed, kind/length/rule/file breakdown
   tested, gate behavior unchanged, written gold-versus-vocabulary
   classification produced.
2. Amended rule preregistered in the spec with the receipt attached,
   independently reviewed, implemented with tests, gold classes not relaxed.
3. Real export regenerated from an immutable commit with `files_scanned > 0`,
   deterministic pass, preserved candidates, valid audit — or surviving findings
   reported honestly.
4. The 966 uncommitted lines resolved deliberately; committed Task 3 verified
   against its plan section.
5. Task 4 implemented in isolation with a proven-canonical Wiki root.
6. No App Server code, no `main` merge, no KB merge, no gate loosening.

Report what was verified by execution versus what remains assumed. A handoff or
phase completion is not the stopping condition.
