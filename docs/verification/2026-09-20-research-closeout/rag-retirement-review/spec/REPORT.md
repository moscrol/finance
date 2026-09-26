# Independent Spec review — managed RAG worker retirement

Verdict: **Spec FAIL** at candidate `bc43ece9fc0550663645c2e8c57d57d7618b8e0d`
(code freeze `d6812e6220b46ff939dfbcf51ac6c6b93246d361`, base
`4ace5ec2e9b7735d90eb15bc2351fa193c1120b8`). One actionable blocker remains.

## Finding S1 — explicit managed artifact loss falls through to the legacy CLI (P1)

**Evidence.** `capture_generation()` resolves the declared interpreter with
`strict=True` and stats every declared candidate/code/source/standard/full path
without translating filesystem failures to `RagGenerationUnavailable`
(`intelligence/services/rag_generation_identity.py:313-342`). The first worker
lookup calls this capture directly (`intelligence/services/rag_worker.py:584-617`).
`kb_rag.retrieve()` only fail-closes the dedicated exception at lines 1740-1749;
the leaked `FileNotFoundError` is an `OSError`, so lines 1750-1766 classify it as
an ordinary worker failure and execute the CLI fallback.

The independent counterexample uses a complete, internally consistent managed
binding and the real `kb_rag.retrieve()` consumer path. Two bounded mutations were
tested separately:

1. query the still-present standard index after deleting the same manifest's full
   index directory;
2. update the manifest, digest, current pointer and environment to an absent venv
   entry, leaving the managed binding complete and internally consistent.

In both cases a direct control first observed raw `FileNotFoundError`, then the
consumer invoked `subprocess.run()` exactly once for the CLI. The approved
assertions “CLI not called” and fallback reason
`persistent_worker_generation_unavailable` both failed: **2 failed**. Evidence:
`test_missing_managed_artifact.py` and `missing-managed-artifact-v2.junit.xml` in
this directory.

**Finding.** This violates the approved requirement that explicit managed
identity errors block `RuntimeError`/`OSError` fallback to a newly loaded old-root
CLI. It also makes the first capture behave differently from an already-created
worker, whose `_check()` translates missing artifacts to observable generation
reasons. Convert filesystem failures while capturing each bound artifact to the
dedicated generation exception (with the matching artifact reason), and retain a
consumer-level regression proving zero CLI calls. Ordinary protocol failures must
continue to use the existing fallback.

## Requirements independently corroborated

The remaining approved behavior is represented in the fixed diff and passed the
candidate's generation suite: retirement is visible before the next query;
status is read-only; query/prewarm/keepalive/recovery reject retired instances;
pool identity partitions generations; an old registered instance keeps aggregate
readiness red; independent roots coexist; ambient changes do not relabel a pinned
instance; legacy non-managed settings remain valid; partial/alias bindings fail;
ordinary query/protocol errors preserve their prior semantics; rollback creates
new serving instances; venv launcher identity is distinct from its resolved host
Python.

The author's real scratch result was checked at SHA256
`9641aab531ec9b100e0c9cc0728683dd59d2edd3b6a6002d60bafff3b5e6dfb9`.
It records 13 stages, finance `d6812e62` and KB `3a210103` clean before/after,
hash/BM25 only, no network/production service, alpha→beta→rollback, and 8/8
worker processes closed. The two mutation logs have the manifest-listed hashes
and fail on removal of the current-generation check and ambient relabeling,
respectively. Those are useful controls, but neither exercises first-capture
artifact loss.

## Independent runs and skip audit

- `intelligence/tests/test_rag_worker_generation.py`: **16 passed**.
- Author-selected seven-file command with the corrected pytest expression:
  **94 passed, 2 skipped, 126 deselected** in 7.26s.
- Counterexample before and after adding the direct-exception control: **2 failed**
  both times; the v2 JUnit is authoritative.
- One command preserved as `author-selection-independent.junit.xml` selected no
  tests because the `-k` expression was passed in its hyphenated log form; it is
  superseded by `author-selection-independent-v2.junit.xml` and is not evidence.

Both skips came from `test_kb_receipt_integration.py:84` and `:102` because
`KB_RECEIPT_CODE_ROOT` was intentionally unset. They cover generic cross-repo
receipt/production compatibility, which this review did not claim. They do not
hide the retirement core: the 16 focused tests ran, and the existing fixed-SHA
KB scratch exercised the real alpha→beta→rollback path. The skips are reasonable
for the approved scope.

## Scope and boundaries

Start and end state were clean at candidate
`bc43ece9fc0550663645c2e8c57d57d7618b8e0d` and KB
`3a21010323eababb54ce8519093fd60dbacb9451`. No candidate or KB files were
modified. No new real scratch, network, BGE, production index, port 8792,
launchd, database, frontend, whole-repository test, PR, merge or deployment was
run.

RSS is now sampled after a successful query and cached until the process stops;
`status()` itself does not spawn `ps`. That sampling-time semantic is outside the
retirement contract and should be described accurately if exposed as monitoring;
this review did not expand it into a monitoring-system change.
