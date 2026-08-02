# App Server Ceiling Fixture Verification

Date: 2026-07-29
Status: sealed and consumer-validated

## Identity

- Fixture source revision: `01e3d36aa734e31f8bb761a7eb17b9ac077aca43`
- Fixture input SHA-256: `b0edcbcc07b05ac04e8e1a80c21bea951e6115a79f7cbee19de03fb360aed03c`
- Component: `b0edcbcc07b05ac0`
- Fixture manifest SHA-256: `1db1c2d6c21a3e463deba4372fdd122df1ee5b8be3e19a5f037ce219b230aa81`
- Active pointer self hash: `63f36a2d1eb292f95d6f443bdb4297b48db52e80036aef3bcade3645ecb318ec`
- Information cutoff: `2026-07-24T23:59:59+08:00`

The benchmark consumer reloaded the active pointer, revalidated the manifest and
every sealed file, and resolved the same component and hashes.

## Instruction And Leak Gates

- Instruction manifest: `0eb1b74f08906d72505064cd298e88cf6b643b2b38c1ba14630e624d8c22ae42`
- Deterministic scan: `bb52f85c18b206b768cd03220ca8c5e246dff95365b97bf0920ce2c4b0537c98`
- Files scanned: 23
- Semantic candidates: 2 generic workflow headings
- Semantic request: `d937d0a62af0352df236554c86236a57dd6d14f8c52d78bf601d67a00eef6a93`
- Independent receipt: `29458715cdee5e141fb140a701fe768fb266d8ae289572ba214f45fd07ede28a`
- Reviewer/model/verdict: `codex:/root/spec_audit_2` / `gpt-5.6-sol` / `pass`

The reviewer saw only the hash-bound request and candidate snippets. No prior
PASS was reused after the source revision or instruction manifest changed.

## Physical PIT Finance Data

- DuckDB SHA-256: `8bfdc0af83e15df604cd87a6f53ecab9af0fa29cbabc94577161aed8f0f004fb`
- Source rows: 22,420,448
- Target rows: 22,307,437
- Latest `fact_market_daily.trade_date`: 2026-07-24

The 2026-07-24 market row is derived only from cutoff-safe components. It
withholds the late-written market-stage label, retains field-timestamped index
data, derives breadth and turnover from cutoff-safe stock/window data, and
counts limit-up stocks from `limit_status` with stock-level deduplication.
`limit_down` remains null because no equivalent point-in-time source exists.
The derivation receipt names `fact_stock_daily`, `feature_market_window`, and
`fact_theme_limit_stock_daily`.

## Wiki And True Hybrid

- Wiki Git revision: `883815c9b43658339b6308a6494536d2e71b9ad7`
- Wiki manifest: `dc111a1335be75e31124a527d40ad8e2c3e05b3aed077509c8e29e3c0c7e79ef`
- Exported Wiki files: 19,864
- RAG code revision: `9053b0c4137428e9ad9d8b4be3ba475b7377b435`
- Hybrid manifest: `470ffd64ae27f63766a9f373b3d177542ecf92b233ddc15dc86be582d7ca02f8`
- Model/mode: `bge-m3` / `hybrid`
- Chunks/source files: 104,611 / 9,753
- Source revision: `manifest:v1:51ddfe839f262d718b3da6635be711b884f8f0d310f3aa16f5807fa07d294a08`
- Fresh probe: query `瑞华泰`, five fresh Hybrid hits

The prebuilt index was adopted only after byte identity, dense shape, BM25,
chunk fingerprint, source manifest, and fresh-query validation. The original
finance and knowledge repositories were not written by the builder.

## Verification

- PIT/fixture/benchmark focused regression: `50 passed`
- Sealed runtime regression: `25 passed, 1 skipped`
- Fixture/sealed-runtime/binding regression before the final PIT derivation:
  `58 passed, 1 skipped`
- `git diff --check`: pass

This receipt proves fixture integrity. It does not claim five-case answer
quality, App Server eligibility, or product release readiness.
