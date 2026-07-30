# Session Handoff — 2026-07-31

Workspace: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
Branch: `main` (merged this session, user-approved; not pushed to `origin`)
Session range: `9103bc5c` → `028bab57`, 22 commits, 34 files, +2,780 / −101
Suite: 3,726 passed / 3 skipped / 11 pre-existing environment failures. Ruff clean.
**Serving runtime: `028bab57` on port 8792.** Six cutovers this session.

## 1. The headline

**The workbench is in front of the user for the first time.** Port 8792 had been
running `a0b8e8c1` from 07-20; it now runs this session's code. That was the
single largest gap between "implemented" and the goal, and it is closed.

Second: **the knowledge base can reach an answer at all.** Every graph-sourced
claim was previously unbindable — its source descriptor is a path
(`wiki/relations/entity_exposures.json`), the claim is a Chinese sentence, and the
gate required token overlap between them. The intersection is empty by
construction. Fixing that (`501387ef`) is what let `chain_mapping` pass.

## 2. What now works, verified end to end

| Question class | Before | After |
|---|---|---|
| 每日复盘 | 136s, 主线空, 6 degrades | 18–24s, 0–1 degrades, data + date + knowledge line |
| 题材研究 | **structurally impossible** | 72s, 1,853 chars, 9 companies named in prose |
| 个股深挖 | worked (82s, 4 degrades) | unchanged |
| 公告/消息 | worked (78s, 7 degrades) | unchanged |

The theme answer now joins both legs in one sentence — it takes the knowledge
base's 固态电池 candidates and checks them against the day's mainline attribution:

> 近期资金主要选择的持续主线集中在半导体、AI算力、医药等方向，固态电池并未出现在
> 近期持续出现的主线板块行列中。

## 3. The theme path: nine sequential defects

Worth reading as one story, because each fix only exposed the next.

1. `8b0d818b` — gate's candidate test was `output_id in claim_id`, containment
   backwards. `"counterpoint" in "counter:1"` is false; all three required outputs
   drew zero candidates.
2. `ccb00d0f` — `DecisionBrief` had seven fields and no slot for a chain mapping,
   so twelve `company:` claims had nowhere to go and were dropped.
3. `ba8c6ddd` — given the slot, the model filled it with `data:D4:*` instead. A
   claim family is deterministically identifiable, so it is now selected in code.
4. `23c9d947` — composer still omitted the companies, so the section is rendered
   deterministically when the brief names claims the prose does not.
5. `501387ef` — the graph-source binding defect above.
6. `baf52c9e` — `counterpoint` required evidence ids, but a falsification
   condition ("若公司否认则逻辑弱化") has no source by nature.
7. `65439d5d` — composer wrote atom ids into `claim_ids`; every sentence was
   invalidated over a field slip. `parse_decision_brief` already normalised this
   for the brief; the rule now applies on the composer side.
8. `66e60dc3` — **the turning point.** The gate said "仍缺少 X" without saying why.
   Four very different situations looked identical. Now each missing item states
   which: no candidates / not written into the answer / evidence unbound / marker
   absent.
9. `30d6471a` — found in one run by #8. The exemption in #6 keyed on
   `claim_type in {"expectation","gap"}`, taken from what the rendered marker
   displays. That value comes from `_grounded_claim_type()`, derived from
   `ClaimStatus`. The real `claim_type` producers write is `counter_evidence`.
   My own test used the display value too, so it passed while production failed.

**Rounds 1–7 each cost a restart and a slice of LLM quota. Round 8 made round 9
take one run.** Instrument before iterating.

## 4. The reusable lesson

Across this session, every channel driven by prompt wording failed and every
channel closed deterministically worked.

Failed: the owner's `output_contract` never reaches the composer's prompt at all;
the composer's explicit "list every candidate" clause was ignored; the brief was
told to use `company:` ids and used `data:D4:*`.

Worked: fact-line budget round-robin (`f7646ad0`), claim-family selection
(`ba8c6ddd`), chain-mapping rendering (`23c9d947`), claim-id canonicalisation
(`65439d5d`).

**A required output should not depend on model compliance.**

## 5. Process failures worth not repeating

- **The whole session was verified in the wrong config.** Every suite run omitted
  `FINANCE_WS`, hiding two real failures. Found by code review, fixed in
  `b3a1af14`. Both configs are now run every time.
- **A silent fallback reached the production database.** The knowledge block fell
  back to `DEFAULT_MARKET_DB_PATH` when given no path, so tests and evals read the
  real DuckDB. Visible only with `FINANCE_WS` set.
- **Three call sites resolved the market DB from `context.repo_root`**, which the
  deployment contract defines as the *code* root. Silent no-op after promotion. A
  test now forbids the pattern.
- **Two of my own tests encoded the same wrong assumption as the bug** (display
  claim_type; source-text assertions). Assert behaviour, and assert against what
  the producer actually writes.

## 6. Open work, by user impact

| # | Item | Why it matters |
|---|---|---|
| 24 | Repair drops sentences without checking coherence | Answer opened with a dangling 但 and never answered "什么阶段" — half the question. Evidence captured: judge reported index 2, its prose described sentence 3, sentences 1 and 3 were dropped, 2 survived. Three candidate code paths listed in the task. Seen twice, not a one-off. |
| 18 | Knowledge layer absent from daily-review prose | The block reaches the contract and the citation shows, but the prose carries only the caveat sentence, not the per-direction substance. |
| 23 | Boilerplate risk/verification sections | 「最强证据」was verbatim identical to「直接定性」in one run; risk and verification lines are reusable on any day for any question. |
| 14 | Flaky episode-citations test | Two hypotheses disproven; needs a reproduction harness. |
| — | 288 of 630 sectors have no `sw_l1` | Data-ops. `028bab57` stops the placeholder being narrated as a direction, but the mapping itself is still 46% empty. |

Synthesis is also intermittently unavailable — `judge_output_invalid`,
`insufficient_grounded_body`, `deterministic_repair_failed`,
`decision_brief_quality_gate_rejected` each appeared once or twice. Roughly one
run in two or three degrades to the template answer. Data stays correct; wording
becomes templated.

## 7. Operational notes

**LLM quota is a rolling 5-hour cap**, not a daily one. Error body is explicit:
`{"code":"1308","message":"已达到 5 小时的使用上限。您的限额将在 <time> 重置。"}`.
About fifteen canary runs exhausted it. Normal daily use will not.

**Runtime cutover has no script**; the procedure is reverse-engineered and
recorded in the agent memory note `workbench-runtime-cutover`. Key points: the
snapshot is a detached worktree of the *data* repo, `.env.workbench` carries the
LLM credentials and omitting it degrades every answer to a template, and
`/api/health`'s `source_revision` reports the *data* repo, not the code root —
check the symlink and `git log` instead.

Rollback: previous snapshot retained, target in `/tmp/runtime-rollback-target.txt`.

## 8. Where this leaves the goal

Three gates:

1. **Can it answer?** Four of four classes now answer. Theme research went from
   structurally impossible to a real 1,853-character research output.
2. **Is the answer good?** First real evidence this session, and it is mixed. The
   theme answer is genuinely usable. The daily review produced one good analytical
   sentence (「指数弱势与结构性活跃之间存在明显张力」) and, in the same session, an
   answer that opened mid-thought and skipped half the question. Items 24, 18 and
   23 are this gate, and it remains the longest road.
3. **Is it in front of the user?** Closed today, for the first time.

The next most valuable input is not another fix — it is the user's own questions
against the promoted runtime. Gate 2 defects surface faster from real use than
from simulated queries, and three of the five open items were found that way in
the last hour of this session.
