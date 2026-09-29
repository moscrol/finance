# 2026-09-29 09-28 候选库发布进生产（Arena 会话）

写完不改；更正走 `record-correction`。

## 授权

- 17:05 前用户在 Arena 会话里作答：①接受 920201.BJ 09-28 名「百瑞吉」（一次性例外，见
  `2026-09-29-name-inference-acceptance-920201-0928.md`）；②授权发布，条件是「验收四件」补齐且全绿。
- 执行方式：用户同意本次用 node 子进程启动 `.venv-workbench/bin/python`（桥的沙箱白名单里没有 python，remote_exec 没配 token）。

## 验收四件（在候选库的 APFS 克隆上独立复跑，原始输出在 `db/candidate-20260928/qa-0929/`）

1. `check_daily_review_data.py 2026-09-28 --phase data --plan local` → `RESULT: COMPLETE`（local 计划按 registry 裁到 19/20 张表，属设计）
2. `check-daily --plan local` → `RESULT: PASS`，gaps/row_anomalies/range_violations 均空
3. `qa_backfill_align.py --plan local` → `RESULT: PASS | FAIL 0 / WARN 2 / 检查项 14`
   - WARN `fact_stock_high_daily 196 < 基线中位 509×0.5`：可接受。新高名单随广度变化，09-28 涨 897 / 跌 4554，是窗口里最弱的一天
     （09-11 涨 643 家时是 161）。
   - WARN `turnover 空值率 67%→100%`：可接受，但属于既有缺口。同花顺来源 09-21 起一直 100% 空，基线 67% 是 09-17/18（东财，0%）和 09-21~24（100%）混出来的。
   - INFO sw-l1 来源 `akshare:index_realtime_sw`：是 09-28 夜跑当晚（staging mtime 09-28 18:43）写的，属当日盘后，
     不违反「历史日不用 realtime」红线；31 个行业的链式检查 PASS。
4. 双红：严格双红 0 个（基线 [10, 85, 13, 45, 0, 0]；09-23/24 也是 0）
- 独立 SQL：09-28 有 5556 行，空名 0、NUL 名 0；pct_chg 重算不符 0；pre_close 链不等 16（除权，和基线同量级）；
  45 张带 trade_date 的表在 09-28 之前的行数和生产逐表一致；生产有、候选缺的 ops 行 = 0。

## 发布

- 脚本 `db/candidate-20260928/qa-0929/publish_candidate_0928.py`，复用 `market_feature_store.db` 的原语：
  run mutex → 写者探针 → 候选 clonefile 成发布件 → 换库锁(SH) → 身份+版本复查（ino 285261140 / mtime_ns 1790601648018125333，
  和 QA 时一致）→ ops 补差复查=0 → `backup_before_swap` → `atomic_swap_into_place(expect_identity)`。
- 17:04:59 开始，17:05:01 完成。收据 `db/candidate-20260928/publish-receipt-cand0928-170459.json`。
- 备份：`db/market_feature_store.duckdb.bak-20260929T170459-cand0928-170459`，sha256 `10619a72…8b167c3d`，恢复步骤在它的 receipt.json 里。
- 换后生产：ino 309062893，sha256 `f7fff8cc…92003126`（和候选原件逐字相同）；没有 WAL；`check_db_lock` OK。
- 换后在生产上复跑了 1/2/3 件：COMPLETE / PASS / PASS（FAIL 0 WARN 2）。QA 克隆已删掉。

## 仍未做

- 09-28 没有走 `run_review_sync.main`，所以没发告警，也没导出 `market_feature_store/exports/2026-09-28-daily-review.json`。
- 09-21~24 那 11 个老缺口（4 只新股首日 + 7 只老股空名）没补，要另定名称来源。
- 这次发布用的加工代码是 `feat/dated-quote-capture-0929`@fa1933623（领先 main 2 个提交：只改了采集件、attach 接线和 registry 步骤名，没改加工模块），还没合入 main。
