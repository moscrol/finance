# fix/duckdb-backfill-qa-gate

## 这个分支做什么
把「历史日回补」的抓取标准和验收标准落成 skill，并让 skill 真能被 agent 读到。起因是 2026-09-07 的 09-03/09-04
断档回补：agent 照 CLAUDE.md 工作流 #1 跑了 `cli daily-full --trade-date 2026-09-03`，个股写成东财盘中快照、申万写成
realtime、`sync-sector-daily` 29 秒 403 次请求触发 fupanhui 429（`retry-after=251318s`）、二次重跑把 `fact_market_daily`
09-03 整行覆写成 NULL 仍报 ok，而验收只数了行数（报告里标 ✅）。查下来 `skills/duckdb-backfill` 早写了「快照仅当天、历史用
mootdx」，但它 `disable-model-invocation: true` 且不在 `.claude/skills/`——回补任务从来读不到它。

改动（4 文件 + 2 新增 + 1 软链）：
- `skills/duckdb-backfill/SKILL.md`：重写。去掉 `disable-model-invocation`；描述改成模型可触发的分支词；五条红线前置
  （历史日只用日期参数化源 / fupanhui 配额单写者单探针 / 日历行最后写 / 写完回读值 / 写锁）；八步标准流程带完成判据；
  **验收四件缺一不收**；删掉 `/Users/lbq/...` 过期路径与重复段。
- `skills/duckdb-backfill/references/backfill-runbook.md`：新增「历史日回补：模块清单与顺序」（16 行表，含 limit-advance、
  请求量、源语义）与「已知语义坑」①–⑥（sw realtime 覆盖 end 日 / market-overview 空壳 / mootdx 裸前收+NUL 名 /
  check-daily 日历连坐 / 快照仅当天 / 429 突发触发）；前置清单加写锁与单发探针。
- `skills/duckdb-backfill/scripts/qa_backfill_align.py`（新）：验收第 3 件。目标日 vs 最近 N 个完整日基线逐项对齐：行数
  （恒定宇宙 ≥98% / 波动表 / 派生层）、空壳市场行、日历连坐、「取最新」源写历史日、来源分布、`pre_close`/`pct_chg`
  链、申万 31 行链、上证链、金额量纲比、字段空值漂移、板块覆盖与 payload 对账、双红名单。只读零网络，撞锁 rc=3，
  `--db` 可验 staging，`--json` 贴交接。复用 `scripts/check_daily_review_data.py` 的表/字段清单与 `quality.py` 的
  GAP/ROW_ANOMALY 清单，不另抄。
- `tests/test_qa_backfill_align.py`（新）：钉住四条规则（空壳 FAIL、日历连坐 FAIL、快照非当天写 FAIL、NUL 名 FAIL）。
- `.claude/skills/duckdb-backfill -> ../../skills/duckdb-backfill`（新软链）；`skills.registry.json` 重扫（描述/哈希/
  view；顺带修正 `perspective-distill` 在 main 上已漂移的哈希）。
- `CLAUDE.md`：工作流 #1 标明「只对当天」并把历史日路由到 duckdb-backfill；技能计数表 24→25 / 14→13 并记录为什么。

## 当前状态
- 分支基于 `gitea/main@696b7b75`，干净 worktree `/Users/a77/fwp-wt-backfill-qa-gate`。
- `qa_backfill_align.py` 实跑（生产库只读）：09-01 / 09-02 → PASS（09-01 一条 WARN：成分表 sw_l1/市值列空值率漂移）；
  09-03 / 09-04 → FAIL 50 项，逐条对应人工 QC 结论（空壳、日历连坐、249/403 板块、0 成分、832 行 NUL 名、除息未调 WARN）。
- 定向测试 125 passed（registry 解析 / workbench skill / gate 锁重试 / feature family / sw_l1 / 新增 5 条）；
  `build_registry.py check` 一致、`check-parseability` 59/59。全量 ruff+pytest 见 PR 评论或 `~/.finance-runtime/test-receipts/`。
- 注意：`scripts/build_registry.py scan` 按目录名 `finance-workspace-private` 定位 ws 仓，在 worktree 里跑会扫**主树**；本分支
  是在 `/tmp` 沙盒里把该名字映射到本 worktree 后扫的。后续在 worktree 里改 SKILL.md 的人会踩同一坑（可做成 `--repo-root`）。

## 验收标准（验收方独立复算）
1. `.venv-workbench/bin/python skills/duckdb-backfill/scripts/qa_backfill_align.py 2026-09-02` → `RESULT: PASS`；
   `… 2026-09-03` → `RESULT: FAIL` 且含 `market-hollow`、`calendar`、`stock-names` 三类（只要 09-03 仍未补齐）。
2. `python3 scripts/build_registry.py check` → 「注册表与源一致」（需在主树或名字映射到本分支的树里跑，见上）。
3. `ls -la .claude/skills/duckdb-backfill` 是相对软链；`rg disable-model-invocation skills/duckdb-backfill/SKILL.md` 无命中。
4. `pytest tests/test_qa_backfill_align.py` 5 passed；ruff 绿。
5. CLAUDE.md 工作流 #1 读起来能让一个没读过 skill 的 agent 在「补上周三」时不跑 `daily-full`。

## 待办（不在本单，已在 runbook 标注）
- 代码缺陷（skill 挡不住，要改源）：`sync_fupanhui_market_daily.sync_fupanhui_market_overview` 空响应守卫 + COALESCE；
  `sync_akshare_sw_l1_daily.py:277` realtime 分支对非当天日期拒写；`sync_mootdx_stock_daily.py` `stock_name.rstrip('\x00')`
  与除息日 `pre_close` 语义（或 source 标注）。历史 29.9 万行 NUL 名的一次性 UPDATE 需用户拍板。
- 北交所历史 K 线补数（东财 `push2his` kline）仓内无 CLI，09-07 用的临时脚本；收进 `market_feature_store/sync/`。
- `daily-full-review` 同样不在 `.claude/skills/`；是否暴露由用户决定（它是夜跑入口，暴露后 agent 可能手跑）。
- 09-03/09-04 回补本身仍在 fupanhui 429 静默期，由 `/tmp/fph_probe_scheduler.py` 开窗自动跑；跑完按本 skill 四件验收。
