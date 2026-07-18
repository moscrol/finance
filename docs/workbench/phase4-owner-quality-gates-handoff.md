# Phase 4 Owner Quality Gates Handoff

## Branch state

- Branch: `fix/owner-quality-gates`
- Base branch: `refactor/owner-stage-executors`
- Base PR: https://github.com/linxiaoqi5111-del/finance-workspace-private/pull/239
- Local implementation commit: `18c29c5 refactor: enforce owner quality gates`
- Remote implementation commit: `03613e4513c487567787bd21982af6a698e1c7b1`
- Phase 4 PR has not been created.

The local and remote implementation SHAs differ because direct push through
`git-manager.devin.ai` returned 403. The remote commit was rebuilt with the
GitHub Git Data API and has the same tree.

## Implemented

1. Added owner-level `SkillOutput.status`:
   - `completed`
   - `partial`
   - `degraded`
   - `failed`
2. Kept stage-level `StageStatus` unchanged.
3. Added centralized owner status adjudication from required stage results,
   evidence thresholds, answer contract availability, warnings, and
   `AnswerSpec.quality`.
4. Moved weak-evidence certainty handling into claim policy:
   - weak claims soften `必然 / 肯定 / 确定 / 已证实`;
   - one L3 claim no longer exempts unrelated weak claims;
   - `不确定` is preserved.
5. CORE company promotion now requires:
   - company-bound verified claim;
   - hard evidence tier;
   - evidence ID resolving to `AnswerSpec.sources`;
   - resolved `EvidenceRef` also carrying a hard tier.
6. `ask.py` propagates claim evidence tiers into citation `EvidenceRef` values.
7. Unresolved CORE companies are downgraded to CANDIDATE during finalization.
8. Renderer separates `核心公司` from `候选与外围公司`.
9. Added `weak_evidence_hard_certainty` quality validation.
10. Conversation orchestration emits the owner-level status instead of
    inferring status only from warnings.

## Files changed

- `intelligence/services/answer_model.py`
- `intelligence/services/ask.py`
- `intelligence/services/conversation_orchestrator.py`
- `intelligence/workbench_skills/contracts.py`
- `intelligence/workbench_skills/research_owner.py`
- `intelligence/tests/test_answer_model.py`
- `intelligence/tests/test_workbench_research_owner_skills.py`
- `intelligence/tests/test_workbench_skill_router.py`

## Validation completed

- Python: `1752 passed, 1 skipped, 1 warning`
- Ruff: passed
- Frontend lint: passed
- Frontend typecheck: passed
- Frontend unit: `56 passed`
- Frontend build: passed
- Workbench E2E: `15 passed`
- a77 targeted tests: `79 passed`

## a77 validation

- Worktree: `/Users/a77/workbench-theme-vertical`
- Detached HEAD: `03613e4513c487567787bd21982af6a698e1c7b1`
- Python:
  `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`
- Canonical data:
  - `/Users/a77/知识库/wiki`
  - `/Users/a77/知识库/.rag_index`
  - `/Users/a77/finance-workspace-private/db/market_feature_store.duckdb`
  - `/Users/a77/finance-workspace-private/market_snapshot`

Golden questions:

1. `请个股深挖英维克的液冷业务：公司本体、客户证据、收入传导、市场选择和风险都要覆盖。`
2. `分析英维克最新财报：收入、利润率、现金流和同比变化。`
3. `英维克最新液冷公告会产生什么一阶和二阶影响？`

All three preserved required headings, passed AnswerSpec quality, produced no
invalid EvidenceAtom IDs, no unsupported probability, and no invalid CORE
promotion. Their first required retrieval stage timed out and later typed
stages remained partial.

## Known issue to fix first

The current owner status adjudicator is too strict:

```python
if not required or not completed or contract is None:
    return "failed"
```

The a77 golden cases have a renderable contract and partial typed artifacts,
so Phase 4 semantics require `partial`, not `failed`.

Recommended correction:

```python
if contract is None or not required:
    return "failed"
if all(
    artifact.status in {"failed", "timeout", "skipped"}
    for artifact in required
):
    return "failed"
if any(artifact.status != "completed" for artifact in required):
    return "partial"
```

Then:

1. Change the retrieval-failure owner test expectation from `failed` to
   `partial`.
2. Keep the direct test that all required stages failed means `failed`.
3. Run targeted tests, full Python tests, and Ruff.
4. Add a new commit; do not amend.
5. Update the remote branch through the GitHub Git Data API helper:
   `/home/ubuntu/github_git_data_push.py`.
6. Rerun `/home/ubuntu/phase4_a77_validate.py`; all three golden questions
   should report `partial`.
7. Fetch the PR template and create the Phase 4 PR with base
   `refactor/owner-stage-executors`.
8. Check CI, reviews, and deployments. Do not merge.

Do not print `GITHUB_PAT_LINXIAOQI5111_DEL`.
