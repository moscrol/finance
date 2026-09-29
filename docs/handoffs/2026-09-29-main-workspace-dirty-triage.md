# 2026-09-29 · 主工作区 302 脏文件分诊表

> 执笔: Arena agent (exec-a77)。逐文件对照 gitea/main(e8605ca04d) 与本地工作区。
> 全量原件: checkpoint/main-workspace-20260929(已推 gitea,任何处置都不丢数据)。

## 分诊结论

| 类别 | 数量 | 建议 |
|---|---|---|
| M 分叉→取远端 | 33 | 工具/会话配置或本地版本更旧,主区同步时直接被远端覆盖 |
| M 分叉→人工评审 | 34 | 本地比远端新,可能是未入库的真实工作 |
| ?? 远端有但内容不同 | 13 | 全部人工评审(同名演化) |
| D 远端还在→建议恢复 | 12 | 疑似 .code-review-graph 系统性误删的同类事件 |
| ?? 已随 port 分支入库 | 119 | 见 port/main-workspace-incremental-20260929 |
| ?? 假脏(与远端一致) | 28 | 同步后自动消失 |
| M/D 假脏 | 6 | 同步后自动消失 |

## M→取远端(33)
```
.claude/hooks/load-memory.sh  本地2026-09-14 vs 远端2026-09-13
.claude/lessons_learned.md  本地2026-09-14 vs 远端2026-09-29
.code-review-graph/.gitignore  本地2026-09-22 vs 远端2026-08-20
.codex/hooks/load-memory.sh  本地2026-09-14 vs 远端2026-09-13
.devin/config.json  本地2026-09-14 vs 远端2026-09-13
AGENTS.md  本地2026-09-14 vs 远端2026-09-28
CLAUDE.md  本地2026-09-14 vs 远端2026-09-13
UBIQUITOUS_LANGUAGE.md  本地2026-09-14 vs 远端2026-09-24
docs/bp/2026-09-finance-agent-bp.md  本地2026-09-14 vs 远端2026-09-16
docs/bp/2026-09-finance-agent-deck.md  本地2026-09-14 vs 远端2026-09-16
docs/bp/2026-09-opc-application-form-answers.md  本地2026-09-14 vs 远端2026-09-16
docs/superpowers/specs/2026-09-01-workorders-INDEX.md  本地2026-09-14 vs 远端2026-09-29
docs/superpowers/specs/2026-09-05-time-river-gap-roadmap.md  本地2026-09-14 vs 远端2026-09-16
intelligence/services/river_query.py  本地2026-09-14 vs 远端2026-09-16
intelligence/services/river_window.py  本地2026-09-14 vs 远端2026-09-16
intelligence/workflows/daily_review.py  本地2026-09-17 vs 远端2026-09-27
market_feature_store/cli.py  本地2026-09-14 vs 远端2026-09-25
market_feature_store/consumption_registry.yaml  本地2026-09-14 vs 远端2026-09-25
market_feature_store/schema.sql  本地2026-09-14 vs 远端2026-09-21
market_feature_store/trading_days.py  本地2026-09-14 vs 远端2026-09-15
scripts/check_daily_review_data.py  本地2026-09-17 vs 远端2026-09-20
scripts/moneyflow/README.md  本地2026-09-14 vs 远端2026-09-27
scripts/moneyflow/run_l2_pipeline.sh  本地2026-09-14 vs 远端2026-09-16
scripts/moneyflow/write_to_duckdb.py  本地2026-09-14 vs 远端2026-09-27
skills.registry.json  本地2026-09-14 vs 远端2026-09-27
skills/daily-full-review/SKILL.md  本地2026-09-14 vs 远端2026-09-17
skills/daily-full-review/references/ops-pitfalls.md  本地2026-09-14 vs 远端2026-09-17
skills/daily-full-review/scripts/nightly_full_review.sh  本地2026-09-14 vs 远端2026-09-27
skills/dispatcher/SKILL.md  本地2026-09-14 vs 远端2026-09-16
skills/duckdb-backfill/SKILL.md  本地2026-09-14 vs 远端2026-09-27
tests/test_build_bp_public.py  本地2026-09-14 vs 远端2026-09-16
tests/test_code_map.py  本地2026-09-14 vs 远端2026-09-24
tests/test_river_recorded_at.py  本地2026-09-14 vs 远端2026-09-16
```

## M→人工评审(34)
```
docs/data-sources/fupanhui-workspace-asset-inventory-2026-08-12.md  本地2026-09-14 vs 远端2026-08-13
docs/learning/ledger-map.md  本地2026-09-29 vs 远端2026-09-27
docs/workflows/daily-review-workflow.md  本地2026-09-14 vs 远端2026-08-02
docs/workflows/theme-radar-workflow.md  本地2026-09-14 vs 远端2026-06-17
intelligence/api/app.py  本地2026-09-29 vs 远端2026-09-27
intelligence/api/static/index.html  本地2026-09-29 vs 远端2026-09-27
intelligence/services/river.py  本地2026-09-29 vs 远端2026-09-16
intelligence/services/run_store.py  本地2026-09-28 vs 远端2026-09-22
intelligence/services/workbench_overview.py  本地2026-09-29 vs 远端2026-09-22
intelligence/webapp/src/App.tsx  本地2026-09-29 vs 远端2026-09-23
intelligence/webapp/src/components/ConversationList.tsx  本地2026-09-28 vs 远端2026-09-03
intelligence/webapp/src/components/OutputWorkbench.tsx  本地2026-09-29 vs 远端2026-07-16
intelligence/webapp/src/components/components.test.tsx  本地2026-09-29 vs 远端2026-09-23
intelligence/webapp/src/main.tsx  本地2026-09-28 vs 远端2026-07-10
intelligence/webapp/src/styles.css  本地2026-09-29 vs 远端2026-09-16
intelligence/webapp/src/types.ts  本地2026-09-29 vs 远端2026-09-22
scripts/build_registry.py  本地2026-09-14 vs 远端2026-09-13
scripts/check_path_literals.py  本地2026-09-14 vs 远端2026-08-11
scripts/deploy_workbench_runtime.sh  本地2026-09-29 vs 远端2026-09-23
scripts/moneyflow/moneyflow.py  本地2026-09-14 vs 远端2026-09-13
skills/daily-full-review/state/runlog.md  本地2026-09-17 vs 远端2026-09-11
skills/divergence-distill/SKILL.md  本地2026-09-14 vs 远端2026-08-22
skills/finance-degraded-fallback/SKILL.md  本地2026-09-14 vs 远端2026-08-16
skills/finance-longtail-baseline/SKILL.md  本地2026-09-14 vs 远端2026-08-16
skills/handoff/SKILL.md  本地2026-09-14 vs 远端2026-08-27
skills/ifind/SKILL.md  本地2026-09-14 vs 远端2026-06-17
skills/limit-advance/SKILL.md  本地2026-09-14 vs 远端2026-09-11
skills/sector-data/SKILL.md  本地2026-09-14 vs 远端2026-09-11
skills/stock-deep-dive/SKILL.md  本地2026-09-14 vs 远端2026-07-10
skills/theme-radar/SKILL.md  本地2026-09-14 vs 远端2026-08-18
复盘/matrices/strategy-review-workbench.html  本地2026-09-18 vs 远端2026-08-26
复盘/matrices/strategy1-priority-stock-matrix.html  本地2026-09-18 vs 远端2026-08-26
复盘/matrices/strategy3-touch-up-rebound-matrix.html  本地2026-09-18 vs 远端2026-08-26
复盘/matrices/strategy4-dual-engine-matrix.html  本地2026-09-18 vs 远端2026-08-26
```

## ??→人工评审(13)
```
docs/bp/2026-09-finance-agent-bp-对外版.md  本地2026-09-06 vs 远端2026-09-16
docs/data-sources/runtime-and-pitfalls.md  本地2026-09-11 vs 远端2026-09-27
docs/handoffs/2026-09-13-8792-integrate-deploy-recheck.md  本地2026-09-13 vs 远端2026-09-13
docs/learning/teaching-framework/00-concept-label-skeleton.md  本地2026-09-08 vs 远端2026-09-16
docs/superpowers/specs/2026-09-07-teaching-framework-slice1-index-stage-leader-succession-design.md  本地2026-09-08 vs 远端2026-09-09
docs/superpowers/specs/2026-09-09-broad-index-coverage-delta.md  本地2026-09-09 vs 远端2026-09-09
docs/superpowers/specs/2026-09-14-extraction-first-p0-workorder.md  本地2026-09-13 vs 远端2026-09-15
market_feature_store/sync/sync_eastmoney_fund_flow.py  本地2026-09-12 vs 远端2026-09-22
scripts/moneyflow/process_l2_archive.py  本地2026-09-13 vs 远端2026-09-27
scripts/moneyflow/run_l2_from_share.py  本地2026-09-09 vs 远端2026-09-16
skills/l2-moneyflow/SKILL.md  本地2026-09-09 vs 远端2026-09-27
tests/test_l2_file_pipeline.py  本地2026-09-09 vs 远端2026-09-16
tests/test_theme_capital_from_baskets.py  本地2026-09-11 vs 远端2026-09-16
```

## D→建议恢复(12)
```
.claude/skills/公司画像页  (远端在,本地删——疑似系统性误删)
.claude/skills/潜意识模式  (远端在,本地删——疑似系统性误删)
.claude/skills/行业概览  (远端在,本地删——疑似系统性误删)
.code-review-graph/wiki-steering.json  (远端在,本地删——疑似系统性误删)
skills/公司画像页/references/charts.md  (远端在,本地删——疑似系统性误删)
skills/公司画像页/references/financial-data-formatting.md  (远端在,本地删——疑似系统性误删)
skills/公司画像页/references/first-page-layout.md  (远端在,本地删——疑似系统性误删)
skills/公司画像页/references/quality-checklist.md  (远端在,本地删——疑似系统性误删)
skills/公司画像页/references/slide-format-requirements.md  (远端在,本地删——疑似系统性误删)
skills/潜意识模式/SKILL.md  (远端在,本地删——疑似系统性误删)
skills/行业概览/SKILL.md  (远端在,本地删——疑似系统性误删)
skills/行业概览/references/workflow.md  (远端在,本地删——疑似系统性误删)
```

## 处置顺序建议
1. 本 PR(119 增量)评审合入
2. 人工评审上表三节(本地新于远端的条目有真价值概率最高)
3. 主区同步 gitea/main(脏数归零)→ 重建 RAG 索引
4. 同步 = checkpoint 兜底之上的安全操作
