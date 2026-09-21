# K3 Workbench Live Evidence

Verdict: **AUTHOR_REAL_ENTRYPOINT_OBSERVED_NOT_ACCEPTED**.

Two real conversations on fixed candidate `786a3b627da9ae37e042881f2c0e8ef12ccac539`, K3 writer, isolated users/port, local-only tools. This is author-side live observation, not independent Spec/Quality acceptance. No source fix, merge, production switch, or data write.

- [Review](raw/REVIEW.md): findings, limits, and next steps.
- [Current answer](raw/current/answer.md) and [historical answer](raw/historical/answer.md).
- [Observations](raw/observations.json), [strict-cutoff diagnostic](raw/cutoff-diagnostic.json), and [citation display audit](raw/citation-display-audit.json).
- [Closure](raw/closure.json): clean identity held; test port closed.
- [Copy manifest](manifest.json): originals, byte sizes, SHA-256 hashes, exclusions.
- Frozen driver/diagnostics use `.py.txt`; log copies use `.log.txt`. Originals are retained.

The first exact source-label check flags five current citations. The subsequent display audit resolves all five by the actual sanitizer; do not treat them as missing evidence. Matching citations does not prove every sentence is supported. Prompt bodies were not captured, only hashes/counts and tool/model events. N=1 per question does not establish an improvement rate.

The old engineering archive and its c57ec654 verdict remain separate. Check this package against a committed Git object with:

```bash
.venv-workbench/bin/python scripts/check_evidence_archive.py docs/verification/2026-09-21-market-date-k3-live --revision <commit>
```
