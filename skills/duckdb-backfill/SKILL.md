---
name: duckdb-backfill
description: DuckDB market_feature_store full/backfill workflow for the finance workspace. Use when the user asks to 回补 duckdb、全量回补、补缺口、补 market_feature_store 数据、修复 fact_* 覆盖、同步 stock_high/sector_stock/limit_heat/limit_advance/sw_l1, or when a sync command hangs and the workflow needs short-command retries, coverage audits, timeout handling, and iterative skill optimization.
---

# DuckDB Backfill

## Overview

Use this skill to backfill `/Users/lbq/Desktop/c c/金融/db/market_feature_store.duckdb` safely and incrementally. Prefer small observable commands, read-only audits first, and script improvements whenever a sync path hangs or becomes fragile.

## Mandatory start

Run and report:

```bash
git status --short
git branch --show-current
```

Do not stage DB files or generated exports. DuckDB writes are local state changes; keep source edits separate from data sync.

## Core rules

- **Audit first**: Run `python3 skills/duckdb-backfill/scripts/audit_coverage.py` before writing.
- **Use short units**: Prefer one table, one quarter/month, or 5 trading days. Avoid long SQL heredocs and silent range jobs.
- **Stop silent hangs**: If a command has no output and CPU is 0 for about 2 minutes, terminate it and improve the skill/script instead of retrying blindly.
- **Prefer idempotent CLI commands**: Use existing `python3 -m market_feature_store.cli ...` commands before adding new data logic.
- **Separate facts from sparse tables**: `fact_limit_advance_presence` is the daily coverage table; `fact_limit_advance_daily` is sparse by design.
- **Record blockers**: Keep a list of skipped dates/sectors and explain why they were skipped.

## Backfill runbook（顺序 / 常用命令 / 已知覆盖状态）

回补 runbook（按表顺序：日历/基础 fact → 轻表 → stock_high 中表 → limit_heat/sector_stock 重表；常用 CLI 命令清单；以及 2026-06-15 起的已知覆盖状态、卡死/超时/CDP 500 日期与 skip 文件）见 `references/backfill-runbook.md`。回补前加载，按顺序小批执行。

## Iteration rule

Whenever a backfill path hangs, returns misleading success, or needs manual rescue, update this skill or its scripts immediately before continuing large-scale backfill.
