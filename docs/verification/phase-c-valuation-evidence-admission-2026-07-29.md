# Phase C Valuation Evidence Admission Verification

Date: 2026-07-29
Status: **deterministic valuation contamination seam closed**

## Objective

Stop an entity-anchored valuation search from turning bare Wiki co-occurrence
into model evidence. The fixed case is `瑞华泰的合理估值` against the pinned
true-Hybrid index.

## Red baseline

Before admission, a direct true-Hybrid probe for `瑞华泰 估值` returned:

```text
rank 5  wiki/entities/天奈科技.md::3
        [[汉威科技]] · [[福莱新材]] · [[瑞华泰]]

rank 7  wiki/entities/方邦股份.md::6
        [[瑞华泰]] — PI薄膜企业，同属功能薄膜赛道
```

Telemetry reported `neighbor_hits=0`, so the failure was not graph-neighbor
expansion. Dense/BM25 fusion retrieved locally similar chunks, and the missing
boundary was candidate-to-evidence admission.

## Implementation

Three commits implement and harden the seam:

- `e4bcc3f3` — adds opt-in `subject_local` admission before semantic judging;
- `c57ad73a` — injects it only for `valuation_current_anchor` Episodes and
  reuses the TaskFrame-owned subject anchor;
- `4cd36122` — closes two self-review findings: tool-query entities cannot
  replace the task subject, and bare `数字+倍` no longer counts as a valuation
  assertion.

Admission is tri-state and typed:

| Decision | Meaning | Model/Judge visibility |
|---|---|---|
| `direct` | subject source, or subject identity plus explicit valuation assertion | yes |
| `relation_clue` | explicit comparable/supply-chain relation without valuation assertion | inspector clue only |
| `rejected` | bare entity list, unrelated/similarly named page, or no subject-local claim | no |

The policy default is `open`; causal, theme, stock-deep-dive, and other existing
callers remain compatible.

## Review findings and fixes

The two-axis self-review used fixed point `d6827606` and the committed design as
the spec source.

Standards reported no hard repository violation. It flagged three judgment-call
smells:

- primitive strings for admission decisions — fixed with
  `AnchorHitAdmission: Literal[...]`;
- repeated valuation-profile switches — fixed with one `evidence_profile`
  semantic variable;
- duplicated test fixtures across two public seams — deliberately retained
  because moving two short, seam-specific samples into shared test infrastructure
  would add coupling without changing production quality.

Spec review initially found two real defects:

1. query `方邦股份 PB` could switch a 瑞华泰 valuation Episode to the 方邦 anchor;
2. `瑞华泰产能增长3倍` could pass the generic numeric-multiple cue.

Both received failing regressions, code fixes, and a second spec review. The
second review returned PASS with `47/47` focused tests.

## Final true-Hybrid replay

Final runtime revision: `4cd36122`.

```text
finance Python: /Users/a77/finance-workspace-private/.venv-workbench/bin/python
KB_RAG_PYTHON: /Users/a77/knowledge-base-private/.rag_venv/bin/python3
KB Python: 3.12.13
RAG_BGE_MODEL: /Users/a77/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181
RAG_INDEX_DIR: /Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/.rag_index
HF_HUB_OFFLINE=1
RAG_WORKER_ENABLED=1
cutoff=2026-07-24
semantic judge=capture-only ordering probe
```

The worker loaded the model once. Prewarm took 29.763 seconds; the three
apertures took 12.862 seconds.

```text
narrow  requested/effective = hybrid/hybrid, degraded=false
broad   requested/effective = hybrid/hybrid, degraded=false
counter requested/effective = hybrid/hybrid, degraded=false

anchor_admission=direct:7,relation_clue:2,rejected:4
conclusion=4; counter=3; clue=5; discarded=4
evidence_count=7; status=success
```

All seven projected evidence atoms came from:

- `wiki/entities/瑞华泰.md`;
- `wiki/sources/688323_瑞华泰_最新逻辑卡.md`;
- `wiki/sources/瑞华泰 2025年年度报告 baseline 2026-04-28.md`.

`天奈科技=false` and `方邦股份=false` in both final model evidence and the
capture judge candidate list. The explicit 方邦 relation remains in clue
coverage and cannot masquerade as valuation evidence.

## Semantic judge status

The deterministic capture judge proves admission happens before semantic
judging. A configured live judge was checked without accessing Keychain or
requesting a credential:

```text
provider_count=0
should_judge=false
live_semantic_judge=blocked_external
reason=no environment-configured provider
```

This is an external availability gap, not a deterministic admission failure.
The live judge was not called and no key was requested or persisted.

## Tests

Final proportional gate:

```text
246 passed in 1.88s
Ruff passed
git diff --check passed
```

It covers KB RAG, closed-loop retrieval, EvidenceSearch, Episode tools, semantic
verifier, and benchmark contract.

The full `intelligence/tests` run used a fresh temporary userspace directory:

```text
2958 passed, 24 failed, 2 skipped in 82.66s
```

The 24 failures reproduce the known local-environment baseline:

- 14 loopback HTTP tests cannot bind a socket in this sandbox;
- 10 userspace/subconscious tests intentionally conflict with the required
  `FORESIGHT_USERS_DIR` override.

No failure touches the changed admission, Episode, RAG, causal, or benchmark
surfaces.

## Isolation

- Isolated KB clone clean at `9053b0c4` after removing four final replay log
  lines with a targeted patch.
- Original KB unchanged at `main@883815c9`; five indexed page directories have
  zero dirty paths.
- Index hashes remain those recorded in the causal verification receipt.
- No index rebuild, model download, API call, secret, database, runtime port,
  `main` merge, or 8792/8799 promotion occurred.
