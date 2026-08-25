# feat/finance-query-technical-daily

## 这个分支做什么

把 `feature_stock_technical_daily`（UP 线/偏离度，203 万行、日更）注册进
`finance_query._DATASETS`，让 agent 能答「这只票偏离多少 / 谁站上 UP 线」。

顺带修一个隐蔽坑：已注册的 `stock_technical_snapshot` 指向 **0 行空表**，而它的两个指标
（`up_value`/`deviation_pct`）正是本表字段——问「偏离度」的模型会选中它、拿到 0 行、
如实回「该口径暂无数据」，数据其实在隔壁。那张空表是运行时诚实闸
（`honesty_gates._EMPTY_CALIBER_TABLE`）的锚点，**不能删也不能改指向**，故只在
`coverage` 里加一句重定向。

## 当前状态

- 树 `/Users/a77/fwp-wt-technical-daily` @ `897ffa15`，基线 `gitea/main@67f246bb`。
- **已提交，未 push、未开 PR、未合 main**（等用户确认）。
- `_PUBLIC_DATASETS`：16 → 17。

## 已验证

- 全量 `intelligence/tests`：**5859 passed / 11 skipped / 0 failed**（966s，exit 0）。
  注意这是在 `gitea/main@67f246bb` 上跑的，**不是** handoff 里那个「main 已红 4 条」的旧基线。
- ruff 全仓绿；pre-commit 9 道全过（层级/路径字面量/字段契约/工具可达性均无新增）。
- 真实库端到端两问跑通（`db/market_feature_store.duckdb`）：偏离 >20% 榜、单票轨迹。

## 口径（实测 2026-08-25，写进 coverage 的依据）

- `UP = MA26 + 0.764 × STD26`（布林带变体 N=26/P=20），`偏离度 = (close/UP − 1) × 100`。
  出处 `skills/up-line/SKILL.md:14`、`market_feature_store/query.py:890`。
- **满 26 个交易日才算得出** → 新上市/长期停牌股当日缺行；2026-08-24 实测 5519/5540 = 99.6%。
  故 coverage 明写「**缺行 ≠ 没偏离，是算不出**」。
- 键唯一：2,036,732 行 == distinct(trade_date, stock_ts_code)。
- 代码格式 `.SH/.SZ`，与 `fact_stock_daily` 一致，08-24 join 命中 5519 行。

## 下一步（未做，按价值排）

1. **棘轮门禁**：新增 `fact_*`/`feature_*` 必须「注册 / 显式豁免」二选一，
   **外加 `COUNT(*)=0` 的表不许注册**（本轮差点把空表 `fact_top_gainers` 注册进去）。
2. `fact_sw_l1_daily`（4,383 行、日更）：不是 0 引用（`adapters/market.py`、
   `api/structured_reports.py`、`eval/pit_snapshot.py` 各有引用），但**不在语义层**，
   adapter 也无查询方法 —— 属「有通路、无语义面」，可评估注册。
3. `fact_auction_stock_daily` / `fact_regulation_pool_daily` / `fact_historical_mapping`：
   2026-08-12 那轮**有意豁免**（「保持工具面收敛」，见 asset-inventory §9 Ln351），
   要注册得先推翻那个理由。且后两张**没有 `trade_date` 列**
   （`effective_date` / `source_date`+`similar_date`），不是 drop-in；
   ⚠️ `fact_historical_mapping.source_date` 与 registry `filter_future_dated` 的
   `source_date` 约定同名不同义，注册前必须确认，否则整批被判成「晚于问句日」。

## 踩过的坑

- **`fact_top_gainers` / `fact_high_volume_gainers` 是 0 行空表**（只有 schema、无写入链，
  涨幅排行本就是「只展示不入库」的设计）。数表名不查行数会把它推荐进语义层，
  得到一个永远空的 dataset。
- **基线要认树**：本轮先在已弃用脏树 `feat/reading-rules-baseline-batch1` 上量得
  `_DATASETS = 13`，而 `gitea/main` 真实基线是 **16**。增量类结论先确认量的是哪个 checkout。
- **grep 作用域要写进结论**：`grep -rl ... intelligence/services intelligence/runtime` 只扫两个
  子目录，却把结论写成「`intelligence/` 全层 0 引用」，漏掉 `adapters/`、`api/`、`eval/`。
  完整教训已沉淀进 `.claude/lessons_learned.md`「能力盘点 / 负面断言的举证」。
