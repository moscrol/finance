# Teaching Framework Slice 1 验收记录

本批在隔离分支 `feat/teaching-framework-slice1` 完成，主库只读，教学产物写入旁路 DuckDB。

## 定向检查

```text
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_teaching_framework_store.py \
  intelligence/tests/test_teaching_framework_flags.py \
  intelligence/tests/test_teaching_framework_stage.py \
  intelligence/tests/test_teaching_framework_succession.py \
  intelligence/tests/test_teaching_framework_readouts.py \
  intelligence/tests/test_teaching_framework_cli.py
21 passed

.venv-workbench/bin/python -m ruff check \
  intelligence/services/methodology_backtest/store.py \
  intelligence/services/teaching_framework \
  intelligence/services/river_query.py \
  intelligence/tests/test_teaching_framework_store.py \
  intelligence/tests/test_teaching_framework_readouts.py \
  intelligence/tests/test_teaching_framework_cli.py \
  scripts/teaching_framework.py
All checks passed
```

## 真实数据回放

输入为主库 `db/market_feature_store.duckdb`，输出为 `/tmp/teaching-slice1-run2.duckdb`；固定 `--computed-at 2026-09-07T00:00:00Z`，避免构建时间进入行哈希。

```text
build-labels
  rows=11658, gaps=11
  framework_version=tf-v0.1+b4aab238
  canonical_hash=81e78fcf52b9e8729dbbeebb51b7c1348ad3c5e76bf7fb86fdeb8149b169a72c

build-succession
  nodes=150, overtaken=0
  status: ok=90, unverifiable=60
  handoff: n=90, k=8, baseline_n=98, baseline_k=43
  verdict=refuted
  canonical_hash=dcadc3f61908fd1a42600d031b53cd92ed93cc8da8fbdf71568f791f7de987b4
```

旁路标签行同时保存供应商 `label_version` 与教学框架 `framework_version`；接力节点保存 `context_break`、`forward`、`context_birth`，旧收据保留且版本或参数改变时标为 `incomparable`。

本记录只证明本批输入上的可复现构建和口径闭环，不把真实数据读数当作交易结论；C 类板块角色仍留在下一刀。

## 全量检查

```text
.venv-workbench/bin/python -m ruff check .
All checks passed

.venv-workbench/bin/python -m pytest -q
7934 passed, 76 skipped, 1 xfailed, 8 warnings
```
