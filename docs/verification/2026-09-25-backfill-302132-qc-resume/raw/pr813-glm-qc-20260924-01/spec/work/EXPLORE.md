# C2/C3 探索计划（PR #813, rev 3c5b3c9a, base 4cc15e70）

范围：仅 C2（源护栏上界 / adjusted 过滤 / 无效或部分态拒绝）与 C3（源-oracle 一致性，次级）。
C1/C4/C5/C6/C7 不在范围内，不整体批准候选。

已读源区域（candidate 绝对路径）：
- market_feature_store/sync/repair_backfill_stock_history.py: _guard 239-381, _accept 593-722
  （BackfillSpec 87-107、_fail/_finite/_oracle_* 亦相关，按 source-map 定位）
- 未读全 CLI（_apply_main/_rebuild 仅按需后续查）。

C2 待证断言：
1. 并跑表上界：live_parallel 查询 BETWEEN window_start AND max(gap_parallel)（274-281 行），
   且 src_a 截止 seg_a_end=max(gap_parallel)（341-346 行）→ 上界之外的合法后继历史
   既不触发误拒，也不进入授权源（LAG 前驱链不受污染）。
2. adjusted 过滤：live_parallel 与 src_a 均限定 h.adjusted='none'；若目标缺口日只有
   adjusted='hfq' 行，应视为缺日 → 部分态拒绝 / 源集合≠市场历拒绝。
3. 无效输入：源行 close=NaN/inf（_finite 失败）→ 写前拒绝。
4. 部分态：删除一个 gap_parallel 日或将其改成 hfq → live_parallel≠spec 且非空 →
   "_fail 部分态"（写前拒绝，不得发布）。

C3 待证断言（次级）：
- _accept 611-647 行以 bf_src/bf_pq 独立重算 oracle（pre_close=前市场日 close 量化 0.01，
  pct/amount/volume 独立公式），并对保留行（含 updated_at 全列）与 09-11 钉值做写前后快照
  逐列相等；回填行 turnover 必须为 None。探针在合成库上做一次 apply 后调用 _accept 复核
  通过，再做 amount 突变复核被拒（mutation 检测非仅行数）。

探针：work/probe_c2_guard.py（本阶段只写不执行）。
合成 DuckDB + 合成 parquet 均落在 work/ 下；不触碰生产/网络/git/候选目录。

执行命令（下一阶段，单条 bash）：
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260924-01/spec/work/probe_c2_guard.py \
  --confcutdir=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260924-01/spec/work \
  -p no:cacheprovider \
  --basetemp=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260924-01/spec/work/tmp/pytest -q

限额：explore/execute 各 <=17 请求；本阶段 3 次读 + 2 次写；仅 1 个探针文件。
