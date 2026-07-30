# Session Handoff — 2026-07-30

Workspace: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
Branch: `codex/agent-runtime-root-repair` (clean)
Session range: `2bb14e80` → `c7cc3447`, 28 commits, 44 files, +6,579 / −704
Suite: 3,582 passed / 3 skipped / 11 pre-existing environment failures. Ruff clean.

## 1. The Goal, Restated

The product goal is not "the data layer is correct". It is: **a finance research
workbench the user opens every day**, matching the experience they get from
Codex reading the same knowledge base. The user's own diagnosis was
"输出质量不达标", and they had stopped using the workbench entirely — the last
real query before this session was 2026-07-22.

Everything below should be read against that goal, not against task counts.

## 2. Where The Progress Actually Is

**Product usability: materially improved and measured.** The failure mode that
made the tool unusable is gone, verified by re-running the exact question that
produced it.

**Data foundation: Tasks 1–8 complete, Task 9 not started.** Task 9 is three
consecutive unattended trading nights; it can only be earned by elapsed time.

**Serving runtime: unchanged.** Port 8792 still runs `a0b8e8c1` from 07-20.
**None of this session's work is serving the user yet.** This is the single
largest gap between "implemented" and "the goal".

**Self-use ledger: 0/10 days, but now actually usable.** It was structurally
incapable of recording anything before this session (see §3).

## 3. What Was Fixed, And Why Each Mattered

### 3.1 The template-degradation failure (the usability blocker)

6 of 29 real runs (21%) returned a template with zero tokens generated. Root
cause was not credentials or the network: owner skills drew from
`remaining_seconds`, which includes the synthesis reserve, so a slow or failed
skill starved final synthesis. Measured on the failing run: a 34s failed
`news-impact` skill plus 57s of retrieval left synthesis with
`remaining_budget_ms: 0`.

Fixed in `c5db0df1` by adding `stage_remaining_seconds`. Outcome measured on an
8-question batch: **0 of 8 template degradations**.

### 3.2 The vector layer had been silently dead for a day

The dominant blocker was not in this repository. The knowledge base's RAG index
freshness guard had been fail-closing every query since 2026-07-29 23:34,
surfaced only as "wiki-rag 检索失败（退出码 3）". Four 0729 sellside documents
were never committed, so the KB `post-commit` reindex hook never fired.
`rag update` alone does not clear it — the guard also requires committed source.

While it held, the one retrieval layer measured as accurate was unavailable and
the workbench ran on the noisy structured layer alone. Committing the four files
(`e775f701` in `knowledge-base-private`) restored it.

Same question, three runs:

| run | theme | wiki-rag | synthesis |
| --- | --- | --- | --- |
| 07-20 original | miss | — | template, 0 tokens |
| 07-30 before index fix | 固态电池 | `命中0·error` | timeout, degraded |
| 07-30 after index fix | 固态电池 | `命中6·ok` | LLM organic synthesis |

`6ab7646c` makes that guard's reason and remedy visible instead of an exit code,
and adds `scripts/check_rag_readiness.py` as a preflight.

### 3.3 The market layer was absent from every answer

All 8 batch questions reported "本轮没有连接本地市场数据". 18 call sites across
6 modules resolved the DuckDB relative to the **code** root, while
`DEFAULT_EXPORTS_DIR` correctly used the **data** root — the double-root design
was half implemented, and the two halves disagreeing was the symptom.

`75b6e46e` gave `intelligence.paths` a single resolver. Effect on the
highest-frequency workflow: `daily_market` went from refusing to answer to a
usable read with concrete numbers (半导体/AI算力分歧检验, 消费零售局部修复,
conditional upgrade criteria).

`c7cc3447` closed the last instance of the same bug: the self-use gate's trading
calendar, which had made the ledger report `trading_calendar_unavailable`
unconditionally.

### 3.4 The self-use ledger could not have recorded a single event

`verify_run_binding` required `zhipu/glm-5.2` exactly. The Keychain record
actually stored is `openai/gpt-5.6-sol` at `http://localhost:57244/v1`. Every
run made with the real provider was rejected on model binding mismatch, and the
three-backend comparison was blocked too.

`78f8ceae` makes provider/model recorded evidence rather than admission
criteria. All other admission rules are untouched.

### 3.5 Retrieval noise

Concept scoring counted substring hits inside a 2,000-character JSON dump of
each concept payload — a truncation artifact, not a semantic relation. It
supplied 80–90% of hits on mainline themes (固态电池 returned MOF材料/全球锂矿/
化工). Restricted to concept-name tiers in `7f1ac960`; semantic recall stays with
the vector layer, which measurement showed is the accurate one.

`9b13ab01` found that the workbench had been sending `--evidence-layer`,
`--fact-hardness` and `--source-type` to a KB CLI that accepts none of them, so
every layered evidence retrieval failed with exit 2 and returned an empty set.

### 3.6 Data foundation (Tasks 5–8)

- **Task 5** — durable member receipts, fair non-starving work selection. Also
  repaired a break Task 4 left behind: `fact_sector_stock_daily` had become a
  view while the member writer still issued `DELETE`/`INSERT` against it, so
  that sync could not run at all.
- **Task 6** — `completion_audit` as the single completion formula. The old
  nightly loop compared `count(distinct sector_ts_code)` against
  `count(*) from dim_sector`; those are different populations, so a coincidental
  match reported `ok` over a real gap.
- **Task 7** — item-by-item reconciliation plus an enforced static access guard.
  The guard immediately caught two violations introduced by Task 5's own code;
  both were routed through new store methods rather than relaxing the rule.
- **Task 8** — migration and one complete live sync on production, backed up
  first. Results in §4.

## 4. The Live Run, And The Spec Amendment It Forced

Production migration through `cli init`: 51s, 95,813 and 10,599,868 rows
preserved exactly against the backup. Universe published for 2026-07-30:
403 sectors, 52,734 declared relationships, snapshot `962a50be…`.
`dim_sector_active` fell **630 → 403**, retiring 227 stale identities.

The ledger's long-open `1,204/1,202` item is resolved. Two hypotheses were
tested and disproven first — the detail endpoint reports no count of its own,
and sector newness does not predict the shortfall. Measuring the full universe
found the cause:

- 130 missing relationships out of 52,734 = **0.2465%**;
- distribution −1×82, −2×15, −4×2, −5×2;
- success rate falls monotonically with sector size (88% under 50 members, 33%
  at 400+), fitting a ~0.25% independent per-member absence rate closely
  (0.9975^27 = 93% vs 88% observed; 0.9975^400 = 37% vs 33%);
- `990220.FP` read 1205/1203 — same sector, same −2 as the recorded 1,204/1,202,
  so the shortfall is stable. Every failure reproduced identically on retry.

Requiring `delivered == declared` turned that 0.25% deficit into a **47% data
loss**: 101 sectors wrote zero rows, discarding 24,772 correct relationships,
concentrated in 机器人概念, 人工智能, 新能源车, 芯片, 储能 — the mainline themes.

Exactness was therefore **moved, not relaxed**:
`delivered + recorded shortfall == declared`. The shortfall is stored per sector
and summed by `completion_audit.declared_shortfall`; an *unrecorded* gap still
fails the audit; surplus members are still refused; a shortfall beyond
`max(5, 5% × declared)` still fails closed. This is recorded as a dated
amendment in the design document, not a silent loosening.

Final state: **403/403 success receipts, zero pending, zero error**,
52,604 delivered + 130 recorded shortfall = 52,734 declared, reconciling exactly.
The 130 figure was reached twice independently and the two agree.

## 5. Judgment Errors Made This Session

Recorded because the reasoning matters more than the outcome.

1. **Assumed the relations-JSON cache was the main latency lever.** Measured
   parse cost was 0.38s, not the 100s. Redirected to the real time ledger.
2. **Called theme matching the top defect (6/8 misses).** It mostly is not a
   defect: `命中主题` measures whether the question hits an *active market
   sector* that day, and the knowledge-graph path was working separately via
   entity anchoring. Corrected after the user pointed at the two data sources.
3. **Reported 136s median latency and permanently skipped retrieval apertures as
   product defects.** Both were harness artifacts: `RAG_WORKER_ENABLED` defaults
   to `0` and prewarm only runs at API startup. With the serving configuration
   the same question retrieves in 8.0s with zero apertures skipped. §6b of the
   canonical ledger now mandates the serving configuration for acceptance runs.
4. **Concluded the shortfall was stable from two observations.** The user asked
   whether the local DuckDB had been consulted; it had 380 trading days, and
   checking properly killed the newness hypothesis too. The correct answer came
   from measuring all 403 sectors, not from a third hypothesis.
5. **First shortfall bound used a ratio only**, which refused seven small
   sectors for a single absent member (14 × 5% = 0.7). Added an absolute floor.

## 6. What Is Left, In Priority Order

1. **Promote the runtime.** Everything above is on the branch; 8792 serves
   07-20 code. Until this happens the user experiences none of it. Requires
   explicit approval and the blue/green procedure in
   `docs/workbench/canonical-8792-cutover.md`.
2. **Ten trading days of self-use.** The gate is finally functional. Record
   honestly, including `--outcome degraded`; the ledger's value is its honesty.
3. **Task 9** — three consecutive unattended trading nights. Only time earns it.
   `data_foundation_cutover_eligible` stays false until then.
4. **Flaky `test_continuous_episode_citations_survive_run_context_reload`**
   (task #14). Two hypotheses already disproven and recorded; not reproducible
   on demand. Worth attention because if it is a product-side race, real
   sessions can render answers with no citations.
5. **Surface both theme sources in the header.** The user's point stands: the
   market-sector match and the knowledge-graph anchor are two different things
   and the header shows only the first. A product improvement, not a defect.

## 7. Safety Boundaries

Production was backed up to
`/Users/a77/db-backups/market_feature_store.pre-sector-universe-<ts>.duckdb`
before any write, with row counts verified. No DuckDB file, provider payload,
credential or log is committed. No DuckDB was hand-edited — `--max-attempts` was
added to the CLI specifically so exhausted receipts could be re-driven through
the normal entry point. `main` was not merged and 8792 was not switched.
