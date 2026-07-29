# Codex App Server Spec v3 Verification

Date: 2026-07-29
Status: first v3 review corrections applied; second independent v3 review pending

## Inputs

- Second independent review:
  `codex-app-server-spec-v2-independent-review-2026-07-29.md`.
- Exact binary:
  `/Applications/ChatGPT.app/Contents/Resources/codex`,
  `codex-cli 0.146.0-alpha.3.1`.
- Correct protocol generation:

  ```text
  codex app-server generate-json-schema --experimental --out <empty-dir>
  ```

- Generated JSON files: `347`.
- Deterministic length-prefixed path+content bundle SHA-256:
  `7c000f25d1b023c953dcdd31be4d81a6226329c1cab3b43e46a06be37ffd4a88`.
- `codex_app_server_protocol.v2.schemas.json` SHA-256:
  `0ffceedba04b90b5b97b6f2f2837ff9c81595038f31112849a682dd0cd9d0903`.
- Correct `ServerRequest.json` SHA-256:
  `5abe765ff9bd94b88f2f2fb417025ec011eac172925ffdfc74d7ccf2542bc114`.

## v2 review coverage

| Finding | v3 contract |
|---|---|
| Same-fixture control missing | §1, §4, §5 require a new five-case profile-D run on the final sealed view |
| Gold/eval/history leakage | §5.1 replaces Git checkout with a curated no-`.git` export plus deterministic and independent semantic leak scans |
| Effective capability/host radius open | §6 freezes item/tool allowlist and OS filesystem/network/IPC/Keychain/process negative controls |
| Five-case blind rule not executable | §4 and §12–13 freeze all five `published_answer` projections and missing/tie rules |
| Claim/source lineage incomplete | §9 adds span-bound claims and runner-owned content-addressed EvidenceLedger |
| Protocol receipt malformed | §3 pins correct `--out`, file count, bundle convention, and 64-digit hashes |
| Isolated auth ambiguous | §7 allows only environment-only `OPENAI_API_KEY` against a pinned direct endpoint |
| Quota ordering inconsistent | §11 reads after initialize and before/after every attempt |
| Actual model/tier unproven | §7–8 bind ThreadStart response, provider, tier, reroute absence, and `fast_mode=false` |
| Retry resets budget | §11 gives the case one absolute deadline shared by failure, backoff, retry, interrupt, and grace |

## First v3 review correction

The first v3 review found no remaining P0 and four narrower issues. They are now
mechanical contracts:

- §7 records exact request/resolved/provider-executed identity pointers and
  classifies the current binary `execution_identity_unobservable` because its
  generated protocol lacks provider-response model/tier fields. That blocks
  runner code/live turns but not reviewed fixture/export tooling.
- §11 derives a per-case hard token cap from the sealed headless control and
  requires worst-case quota admission before initial and retry attempts.
- §9 makes the private EvidenceLedger a write-once hash chain with an atomic
  final root seal bound into the public artifact.
- §5.1 fixes Unicode normalization, tokenization, n-gram/similarity thresholds,
  exception rules, and positive/negative leakage fixtures.

## Important scope correction

The completed v2 D artifact
`75a144399068843580b330e2899ebbbc3093cccbc0f5ac9d01e986c95053e898`
remains a valid budget-ablation receipt: it physically reached seven calls and
supports the wall-clock/call-cap diagnosis. It is not relabeled as the App Server
control because it used live roots and has only three cases.

The v3 experiment keeps the domain harness. Both arms access finance/Wiki data
only through the same typed `finance-tool` broker and PIT snapshot. The treatment
is native Codex ownership of context, repository instruction discovery, recovery,
and stopping—not future data, direct Wiki grep, external web, extra agents, or a
larger compute envelope.

## Remaining gates

1. Obtain an independent v3 spec `PASS` after the four corrections above.
2. Build and seal the curated instruction export and physical PIT fixture.
3. Prove all isolation positive/negative controls.
4. Run and seal the five-case same-fixture profile-D headless baseline.
5. Obtain a binary/protocol or separately reviewed provider receipt that exposes
   actual executed model/provider/service tier; only then write App Server runner
   code. The current binary must fail preflight before the first case.
6. Preregister five answer projections, quota radius, blind commitment, and
   output paths before the first App Server answer.

No part of this verification changes `main`, 8792/8799, KB merge boundaries,
credentials, databases, indexes, model weights, or existing benchmark artifacts.
