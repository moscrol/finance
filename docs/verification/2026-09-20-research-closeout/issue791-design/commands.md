# 实际使用的主要命令与边界

工作目录均为 `/Users/a77/fwp-wt-history-market-anatomy`。shell 只读候选；产物写审查目录，探针数据库为 `duckdb.connect(':memory:')`。

```sh
git status --short
git branch --show-current
git rev-parse HEAD
git worktree list
bash scripts/session_facts.sh
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/code_map.py query '历史比较 相似度 similarity 涨停题材聚合 union 公开投影'
git diff --stat 4ace5ec2...HEAD
git log --oneline 4ace5ec2..HEAD
git show 40321402:docs/verification/2026-09-17-sector-history-comparison/README.md
git ls-tree -r --name-only 87c719f8 docs/verification/2026-09-18-react-components-comparison
git show 40321402:scripts/replay_sector_history_diagnostic.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/research-closeout-20260920/issue791-design/probe_existing.py > /Users/a77/.finance-runtime/reviews/research-closeout-20260920/issue791-design/probe.stdout.txt
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_historical_research_query.py::test_trigger_only_analogue_ranking_ignores_future_values_and_full_path_is_labelled tests/test_history_model_projection.py::test_analogue_projection_exposes_reference_vector_candidate_delta_and_cutoff intelligence/tests/test_market_regime_analogs.py > /Users/a77/.finance-runtime/reviews/research-closeout-20260920/issue791-design/targeted-tests.txt 2>&1
git status --short
git rev-parse HEAD
```

另用 `rg`/`sed` 精确读取 review.md 所列源码、测试、schema 与分支 handoff；未扫描 wiki 或审查根。缺失的 worktree `.agent-memory` 改读 `/Users/a77/agent-memory/` 精确偏好/项目/能力图文件。code-map 的 stale/unavailable 只作为地图状态，不据此断言能力不存在。全量 tests、模型、生产接口均未运行。
