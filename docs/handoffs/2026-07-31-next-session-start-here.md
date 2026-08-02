# Start Here — next session (2026-07-31)

Written for a cold start. Read §1–§3 before touching anything; §4 is the task to
pick up; §7 is what not to redo.

## 1. The goal

**A finance research workbench the user opens every day**, matching what they get
from Codex reading the same knowledge base. Their own diagnosis was 输出质量不达标.
Judge work against that, not against task counts.

Three gates, current state:

1. **Can it answer?** 每日复盘 ✅ · 个股 ✅ · 公告 ✅ · 题材研究 ✅ (fixed last
   session) · **明日前瞻 ❌ — this is §4.**
2. **Is the answer good?** Mixed, with concrete open items (§5). Longest road.
3. **Is it in front of the user?** ✅ Closed. Port 8792 serves current code.

## 2. Environment

```
Code (work here)  /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
Branch            main   (merged + user-approved; NOT pushed to origin)
Data root         /Users/a77/finance-workspace-private
Knowledge base    /Users/a77/knowledge-base-private
Python            /Users/a77/finance-workspace-private/.venv-workbench/bin/python
Serving runtime   port 8792 → /Users/a77/finance-workspace-runtime → snapshot 028bab57
```

**Run the suite in BOTH configs, every time:**

```bash
cd /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
FINANCE_WS=/Users/a77/finance-workspace-private $PY -m pytest -q -p no:randomly
$PY -m pytest -q -p no:randomly
```

Baseline: **3,726 passed / 3 skipped / 11 pre-existing environment failures**
(`test_subconscious` ×8, `test_userspace` ×3 — failing before this work, ignore).
Both configs must give identical results.

An entire session was verified without `FINANCE_WS` last time, hiding two real
failures and letting a fallback reach the production DuckDB. Do not repeat it.

## 3. Two facts that will otherwise cost you an hour each

**LLM quota is a rolling 5-hour cap.** Error body is explicit:
`{"code":"1308","message":"已达到 5 小时的使用上限。您的限额将在 <time> 重置。"}`
About fifteen canary runs exhaust it. Budget end-to-end runs; prefer local
reproduction.

**User-visible text is humanised at display time.** Internal ids are rewritten in
the UI — `scenario_tree` shows as `情景树`, the word `registry` shows as `工具目录`.
When the user pastes an error, translate back before believing an id is wrong.
Last session I nearly chased a phantom "Chinese output id" because of this.

## 4. Pick this up first: 明日前瞻 returns a non-answer

User asked **「你觉得a股明天会怎么走」** → fail-closed stub. Diagnosis is complete;
no investigation needed, only the fix.

Run: `/Users/a77/.local/share/finance-workbench/users/default/runs/run_20260731_024144_312047`

```
direct_assessment    fulfilled     rebound_case  fulfilled
supporting_evidence  fulfilled     decline_case  fulfilled
invalidation         missing  ← 已绑定，但正文缺少该输出的措辞标记
evidence_boundary    missing  ← registry 里没有该输出对应的 claim
scenario_tree        missing  ← registry 里没有该输出对应的 claim
```

**The composed answer was good and was thrown away.** From `raw_answer` (1,934
chars): 核心矛盾：放量下跌与外部利好的博弈 / 指数下跌0.62%、成交放量至23425.75亿、
仅1768家上涨、跌停74家 / 盘后近20家公司披露回购增持、费城半导体涨9% / 若次日跌停家数
收缩、上涨家数扩大且成交未萎缩，则技术性修复更可信.

Three distinct causes:

1. **`evidence_boundary` and `scenario_tree` have no producer.** Same class as
   `chain_mapping` was for the theme path. Every claim in that answer sits in the
   `generic:` namespace, so `_claim_candidates` in
   `intelligence/services/task_fulfillment.py` returns nothing. Namespace mapping
   will not work here — key on **claim_type** instead (gap-ish types for
   `evidence_boundary`; scenario-bound claims for `scenario_tree`).
2. **`invalidation` fails on wording only.** Claims bound fine; `_MARKERS` looks
   for 失效/证伪/失效条件 and the prose says 若…则…, 风险. Content correct, vocabulary
   mismatched.
3. **`scenario_tree` duplicates `rebound_case` + `decline_case`**, both already
   fulfilled. Consider whether it should be required at all rather than inventing
   a producer for it.

Reference implementation: the identical fix for `chain_mapping` is commits
`8b0d818b` → `30d6471a`. Follow that shape.

## 5. Other open items, by user impact

| # | Item | Note |
|---|---|---|
| 24 | Repair drops sentences without checking coherence | Answer opened with a dangling 但 and never answered 「什么阶段」. Judge reported index 2, its prose described sentence 3, sentences 1 and 3 were dropped, 2 survived. Three candidate paths listed in the task. Seen twice. |
| — | Synthesis degrades ~1 run in 2–3 | `judge_output_invalid`, `insufficient_grounded_body`, `deterministic_repair_failed`, `decision_brief_quality_gate_rejected` each seen. Data stays correct; wording becomes templated. |
| 18 | Knowledge layer absent from daily-review prose | Block reaches the contract and the citation shows, but prose carries only the caveat sentence. |
| 23 | Boilerplate risk/verification sections | 「最强证据」was verbatim identical to「直接定性」in one run. |
| 14 | Flaky episode-citations test | Two hypotheses disproven; needs a reproduction harness. |
| — | 288 of 630 sectors have no `sw_l1` | Data-ops. Placeholder no longer narrated as a direction (`028bab57`), but 46% of the mapping is still empty. |

## 6. Operational

**Cutover has no script.** Full procedure in agent memory `workbench-runtime-cutover`.
Short form:

```bash
cd /Users/a77/finance-workspace-private
SHA=$(cd <worktree> && git rev-parse HEAD)
git fetch <worktree> main:refs/runtime/promote-<date> --force
git worktree add --detach /Users/a77/.finance-runtime/finance-workspace-$SHA $SHA
pkill -f "port 8792"; sleep 4
ln -sfn /Users/a77/.finance-runtime/finance-workspace-$SHA /Users/a77/finance-workspace-runtime
cd /Users/a77/finance-workspace-runtime
set -a; . /Users/a77/finance-workspace-private/.env.workbench; set +a   # ← LLM creds
while IFS= read -r l; do export "$l"; done < /tmp/runtime-8792-env.txt
nohup <python> -m uvicorn intelligence.api.app:app --host 127.0.0.1 --port 8792 &
# ~115s to healthy (RAG prewarm)
```

Omitting `.env.workbench` starts fine and degrades **every** answer to a template.
`/api/health`'s `source_revision` reports the **data** repo, not the code root —
check the symlink and `git log` instead. Rollback target in
`/tmp/runtime-rollback-target.txt`; old snapshots are kept.

## 7. Do not redo these

- **The US-market date is not a bug.** User asked for 7-30 US data and got 7-29.
  Correct: US summer session runs 21:30 → 04:00 Beijing, so at 02:41 on 7-31 the
  7-30 session was still open and 7-29 was the last completed one. The only defect
  is that the answer states 「目标交易日 2026-07-29」without explaining why. Fix the
  wording if anything; do not touch the date resolution.
- Relations JSON is large — query via `knowledge-base-private/scripts/query_relations.py`,
  never `cat`.
- Never weaken a gate to get a green receipt. Every fix last session either
  applied the gate's own stated criterion or fixed a category error in it; none
  lowered a bar.

## 8. Two lessons worth carrying

**Prompt instructions do not deliver required outputs; deterministic closure does.**
Everything driven by wording failed last session — the owner's `output_contract`
never reaches the composer's prompt at all, an explicit "list every candidate"
clause was ignored, the brief was told to use `company:` ids and used `data:D4:*`.
Everything closed in code worked — fact-line budget round-robin, claim-family
selection, chain-mapping rendering, claim-id canonicalisation.

**Instrument before iterating.** Seven diagnosis rounds on the theme path each
cost a restart and a slice of quota. Adding one line of explanation to the gate
(`66e60dc3`) made the eighth round land in a single run. That diagnostic is what
made §4 above a five-minute read instead of another seven rounds — use it.

Related: assert tests against what the **producer** writes, not what the UI
displays. Two of my tests last session encoded the same wrong assumption as the
bug they were meant to cover, so they passed while production stayed broken.
