# Independent final Spec review — managed RAG worker retirement

Verdict: **Spec PASS** for final candidate
`c4f33c5bcd6835bcc9b15536dc2d0eb1bf6f1279` (repaired code
`cb4bbf1ce6cd9b1af4b71dcbb13668877dbc54be`). The prior S1 blocker is closed.

## Evidence → Finding: S1 closed

The failed candidate leaked filesystem exceptions from first managed capture into
the ordinary `OSError` fallback. The repair now:

- validates the limited manifest container/value shapes before path use
  (`intelligence/services/rag_generation_identity.py:276-305`);
- translates missing candidate/code/source/wiki/standard/full/interpreter
  artifacts to artifact-specific `RagGenerationUnavailable` reasons
  (`:331-386`);
- catches `RuntimeError` only around interpreter `Path.resolve(strict=True)`,
  covering a symlink loop without swallowing unrelated programming errors
  (`:331-334`);
- applies a final `OSError` fence only when the three managed core keys form a
  complete binding, while re-raising the same error for legacy capture
  (`:401-424`).

The exact adapted consumer probe retains the original two fixtures and all
consumer assertions, removing only the obsolete diagnostic that required raw
`FileNotFoundError`. Its SHA256 is
`f3d2a1541bfac85446631c4825e590a44709458a9e3a539c28f2573d7e8b5d42`.
On the repaired candidate it passed **2/2**: missing full index and missing
interpreter both returned `persistent_worker_generation_unavailable`, status
`error`, registered zero workers, and made zero CLI calls.

The repository generation suite independently passed **29/29**. This includes
the two consumer regressions, missing code/wiki/full/interpreter classification,
limited malformed manifest shapes, interpreter symlink loop, managed permission
translation, legacy permission passthrough, retired-generation no-fallback,
ordinary protocol fallback, and legacy behavior. Therefore the fix closes S1
without broadening the managed detector or disabling ordinary fallback.

## Independent commands and results

All test processes used a clean environment containing only `HOME`, `PATH`,
`LANG`, `TMPDIR`, `FWP_TEST_RECEIPT=0`, `PYTHONDONTWRITEBYTECODE=1`, and
`PYTHONPATH`:

```text
env -i HOME=/Users/a77 PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin LANG=C.UTF-8 TMPDIR=/private/tmp FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/a77/fwp-wt-rag-retirement-closeout-0920 <workbench-python> -m pytest -p no:cacheprovider -q <consumer-probe>
=> 2 passed

env -i HOME=/Users/a77 PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin LANG=C.UTF-8 TMPDIR=/private/tmp FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/a77/fwp-wt-rag-retirement-closeout-0920 <workbench-python> -m pytest -p no:cacheprovider -q intelligence/tests/test_rag_worker_generation.py
=> 29 passed

env -i HOME=/Users/a77 PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin LANG=C.UTF-8 TMPDIR=/private/tmp FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/a77/fwp-wt-rag-retirement-closeout-0920 <workbench-python> -m pytest -p no:cacheprovider -q intelligence/tests/test_rag_worker_keepalive.py::test_keepalive_touches_an_idle_warm_worker_without_reloading
=> 1 passed
```

JUnit receipts in this directory are `consumer-no-fallback.junit.xml`,
`generation-suite.junit.xml`, and `keepalive-known-race-single-run.junit.xml`.
No test was skipped or deselected in these independent runs.

The author's final directed receipt reports **121 passed** and related Ruff
green. It is corroborative and is not added to the independent counts. Likewise,
the older 118/120 receipts are not added to 121.

## Preserved keepalive red: real test race, not a Spec failure

The retained `8d50a333` run has a legitimate **1 failed / 119 passed** observation.
The test waits for `keepalive_sent >= 2` at
`intelligence/tests/test_rag_worker_keepalive.py:61`, immediately snapshots status,
then expects `queries_served >= 3` at line 69. Production increments
`keepalive_sent` before `_serve()` completes (`rag_worker.py:327-330`), so the
second keepalive may be in flight and `queries_served == 2` is a valid observation.
The unchanged rerun's 120 green and this review's single-test green do not erase
that race.

This does not contradict the retirement specification or indicate a keepalive
runtime defect. It **does require a minimal test synchronization repair before a
stable Quality/four-leaf gate is claimed**: wait for the existing completed-query
counter (or an explicit completion event) while retaining the original assertions
and timeout. Do not change production counter semantics to satisfy the test.

## Identity, evidence scope, and exclusions

The candidate started and ended clean at
`c4f33c5bcd6835bcc9b15536dc2d0eb1bf6f1279`; the remote branch resolved to the
same SHA. The read-only KB protocol tree started and ended clean at
`3a21010323eababb54ce8519093fd60dbacb9451`. No candidate or KB file was edited.

The final author manifest SHA256 was independently checked as
`23a2da594ecdae6df47e3c8c3e61509e79f93fdcd3291aca150717aaf33258c2`.
The original alpha→beta→rollback real scratch remains evidence for code
`d6812e6220b46ff939dfbcf51ac6c6b93246d361`; it was **not rerun at cb4bbf1c** and
is not represented as such here. This review ran no new real scratch, network,
BGE, production index, port 8792, launchd, database, frontend, whole-repository
suite, PR, merge, or deployment.

The RSS change remains documentation only: it accurately describes the existing
first-successful-query sample cache and does not expand monitoring behavior.
