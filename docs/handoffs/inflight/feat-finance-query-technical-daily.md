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

## 第二步：棘轮门禁（已做）

`scripts/audit_dataset_registration.py` + pre-commit hook `dataset-registration`（第 10 道）。

- **规则 1（硬拦，不需要库）**：`schema.sql` 每张 `fact_*`/`feature_*` 表，要么在
  `_DATASETS` 注册，要么在 `_UNREGISTERED_TABLES` 写明理由。存量 25 张已带理由免检。
- **规则 2（有库才跑）**：注册了但 `COUNT(*)=0` 的表必须列进 `_EMPTY_BY_DESIGN`。
  worktree 里 `db/` 是 gitignore 的，故 pre-commit 自动跳过；pytest 侧用 monkeypatch 复挂。
- **判据取自 `schema.sql`，不取自 `_DATASETS`**——否则「没注册的表」按定义是空集，
  审计变成照镜子（`audit_tool_reachability` 初版就栽在这，报过一次假绿）。
- 豁免名单**与 `_DATASETS` 同文件**，不另建清单：2026-08-12 那轮的理由只写在
  asset-inventory 文档正文里，不是机器可读的，08-25 复查时被读成「漏了」。

实测读数：schema.sql 40 张 = 15 注册 + 25 豁免；另 2 个注册的 VIEW（`CREATE VIEW`
不在 `CREATE TABLE` 里，单列以免总数对不上账）。

**证伪已跑**（一个不会红的门禁等于没装）：
- 往 schema.sql 注入 `fact_ratchet_probe_daily` → exit 1，提示二选一；schema 已还原。
- pytest 四条证伪：新增未认领表红 / 注册空表红 / `_EMPTY_BY_DESIGN` 不红 / 无库时跳过。

## 第三步：注册 sw_l1_daily（已做）

`fact_sw_l1_daily` → dataset `sw_l1_daily`。门禁读数 15 注册 + 25 豁免 → **16 + 24**。

**关键设计：`population="subset"` 而不是 `full`。** 实测该表完整度分两段——
`2026-06-05` 起每日 31/31，**此前 344 天每日只有 3~10 个行业**（平均 7.7，部分回填的残段）。
标成 `full` 会重演 `mainline_sector_daily` 那道疤：模型在残缺分母里取 top-N，
结构上得不到对的答案，而字段校验一声不吭。分界日已写进 `coverage`，模型下单前就看得见。

实证：查 `2026-03-10` 返回整齐的 5 行（通信/电子/机械设备/电力设备/计算机），
**不带 coverage 警告的模型会把它当成合法 top5**。

**⚠️ `fact_sw_l1_daily.amount` 的单位不是「亿」。** 全量 pytest 用
`test_amount_metric_labels_carry_unit`（§1.3-C「八处成交额口径一致」）把这条抓了出来。
查证：写入侧 `sync_akshare_sw_l1_daily.py` **原样存 AKShare 值、无任何换算**；
2026-08-24 全 31 行业合计 `1,982,328` 对当日大盘 `20,072` 亿，**比值 ≈ 100 → 百万元口径**。

处置：**不开放 `amount` 指标**，理由写进 coverage。不去放宽那条不变量——
为了多一个指标改门禁迁就代码是反模式。要行业成交额，走 `sector_daily` 的 `sw_l1` 维度聚合；
要真正暴露本表的 amount，得先在写入侧统一单位，那是另一个单子（会动
`adapters/market.py` / `structured_reports.py` 两个现有消费方，别顺手做）。

另两条口径也写进了 coverage：
- 与 `sector_daily` 不同层——那是 224 个概念板块，这是 31 个申万一级行业。
- `fupanhui_ratio`（27% 有值）、`amount_ma120*`（2%）**未开放为指标**，不是漏了。
  一个几乎恒空的 metric 与空 dataset 是同一种病。

⚠️ 该表的降级路径（`structured_reports.py:133` 那个「复盘会聚合代理」正则）在**当前数据里
没有出现**——`source` 全是 `akshare:index_hist_sw:*` / `index_realtime_sw:*` 两族。
代码里有这条路，库里没有这类行，别把它写成已发生的事实。

## 第四步：注册 auction_stock_daily（已做，推翻了 08-12 豁免）

`fact_auction_stock_daily` → dataset `auction_stock_daily`。门禁 16+24 → **17 注册 + 23 豁免**。

**推翻 08-12「稀疏/半结构，保持工具面收敛」的依据**（先量后判，不是拍脑袋）：
实测 145 个交易日、每日 50~99 行、13 个字段可用率近 100%——**并不稀疏**。
「半结构」指的是 `panel_key` 分面板，而 `population`/`coverage` 这套机制正是为表达子集
而存在的，08-12 那时还没有。

**最大的坑已写进 coverage：每面板每日只收 top 10。**
实测 2026-08-18 `zt` 面板 10 行，而前一日真实涨停 **106 只**——差一个数量级。
模型拿本表回答「昨天多少只涨停」会错得离谱，而字段校验一声不吭（`limit_seq`/`pct_chg`
都是这张表的合法列）。coverage 里明写了**该问谁**：`market_daily.limit_up` 或
`theme_limit_heat_daily`。

其余已核口径：
- 七面板：`zt` 昨日涨停 / `lb` 昨日连板 / `db`~`db5` 1~5 日前断板。
- **时间语义**：`trade_date` 是竞价发生日，面板名描述此前发生的事。
- 金额单位是**亿**——`day_amount` 与 `fact_stock_daily.amount` 逐位对账相等
  （66.09 == 66.09），与 sw_l1 那张不同，可放心开放。
- `limit_seq` 是**连板数不是排名**：`lb` 面板最小值为 2（连板按定义 ≥2），`zt` 为 1。

端到端实证：按面板聚合当日平均竞价涨幅得到情绪梯度——
昨日涨停 5.17% > 昨日连板 2.68% > 3日前断板 0.81% > … > 2日前断板 −0.72%。
这类结构 agent 此前完全算不出来。

## 下一步（未做，按价值排）

1. `fact_regulation_pool_daily` / `fact_regulation_event_daily` / `fact_historical_mapping`：
   2026-08-12 那轮**有意豁免**（见 asset-inventory §9 Ln351）。前两张与 mapping 都
   **没有 `trade_date` 列**（`effective_date` / `source_date`+`similar_date`），不是 drop-in；
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
