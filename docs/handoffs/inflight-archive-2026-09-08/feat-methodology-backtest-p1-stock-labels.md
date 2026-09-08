# feat/methodology-backtest-p1-stock-labels

> **2026-09-04 已合入**：PR #585 → `gitea/main=443fe3d5`（分支尖 `42d94692`，主门禁 7708P/0F/15S/1x，ruff 0，前端零改动）。
> 纯加法，无运行时行为变化，无需切 8792；旁路库已按 v2 重建（213 MB）。下一刀见 `feat-methodology-backtest-p1-refuted.md`。
> 下文为合入前原状，供溯源。

树 `/Users/a77/fwp-wt-methodology-backtest-p1c`，基座 `gitea/main`=`5c7fe2eb`（#581 已合入后的 main，干净树）。
设计稿 `2026-09-04-methodology-backtest-structured-history-design.md` §3.1 表「stock（P1）」行 + §6 P1 第一条；
P1 第二刀交接 `feat-methodology-backtest-p1-propose.md`「下一步 2」。解释器 `.venv-workbench/bin/python`。

## 这个分支做什么
P1 第三刀，**加法、不改既有运行时行为**：给标签层加 `stock` 实体（`limit_up / first_board / new_high_1y`），
给 outcomes 加个股价格序列，规则 / 登记入口 / CLI 认 `stock`，一条种子规则。板块 / 题材 / 大盘 12 个标签的口径
与读数一字未动（真库三条老种子规则收据逐位复现）。

- `labels.py`：universe `limit_high_union` = `fact_theme_limit_stock_daily ∪ fact_stock_high_daily` 的 (日, 股) 并集，
  并集内三标签稠密 1/0，只在源表**整日缺失**时置 NULL；`LABEL_VERSION` v1 → v2；成立条件多一块 `stock_coverage`
  （并集大小 / 两表覆盖日数 / 涨停表缺哪些日）。
- `outcomes.py`：`_ret` 加 `series` 键（sector / stock），`_base` 按 `SERIES_BY_ENTITY_TYPE` 映射，join 走
  `(series, entity_id)`——板块 `.TI/.FP` 与个股 `.SZ/.SH/.BJ` 代码不撞车是巧合，不拿巧合当契约。
- `rules.py`：`ENTITY_TYPES` / `SCOPE_ENTITY_TYPES` / `UNIVERSES` / `LABEL_KINDS` 加 stock；`propose.build_rule_doc`
  的 universe 改从白名单取（原来写死两项）；CLI `propose --entity-type` choices 从白名单生成。
- 种子规则 `methodology/rules/first_board_new_high_1y_5d.v1.json`：首板 ∧ 一年新高 → 5 日上涨。

## 真库读数（旁路库 2026-09-02，只读；`a890f48d` 干净树，收据 `dirty=false`）
| 项 | 值 |
|---|---:|
| 标签行 | 671,440 → **1,456,438**（stock 3 × 261,666；其余 12 标签行数不变） |
| outcomes 行 | 610,704 → **1,657,368**（stock 261,666 × 4 窗口；ok 980,090 / pending 19,793 / missing 46,781） |
| 旁路库体积 | 98 MB → **213 MB** |
| build-labels / outcomes 耗时 | 2.4 s / 5.2 s |
| 主库 | mtime `09-03 15:10:52`、1,798,320,128 B 跑前跑后不变，无 WAL |

| 规则 | N | p | p0 全日期 | lift | p0 事件日 | lift | 结论 |
|---|---:|---:|---:|---:|---:|---:|---|
| **first_board_new_high_1y_5d**（新） | 4,790 | 47.8% | 47.0% | +0.7% | 46.8% | +1.0% | not_distinguishable（BH adj p 0.311） |
| dual_red_streak3_continuation | 88 | 68.2% | 58.0% | +10.1% | 69.2% | −1.0% | not_distinguishable（与 #581 交接逐位相同） |
| diff_ratio_turn_up_5d | 27,186 | 54.1% | 55.1% | −1.0% | 54.9% | −0.8% | 同上 |
| limit_heat_rank_jump_3d | 13,006 | 57.6% | 57.0% | +0.6% | 56.8% | +0.8% | 同上 |

新高首板 5,084 个事件（与只读核数 `first_board ∧ new_high_1y` 完全一致）里 4,790 已到期、12 pending、282 missing。
多窗口：T+3 胜率 51.6% 均值 +2.26%；T+5 47.8% +1.86%；T+10 44.3% 均值 +1.77%，但均值**最高**收益 +13.06%、
峰值日 4.6、峰后回撤 −10.05%——「新高首板」在强势股池子里没有选择超额，走势形状是先冲高再吐回来。
池子基准 p0=47.0% < 50%：强势股 5 日后为正的概率本身低于一半（均值回归），这是拿个股全市场当基准看不见的读数。

## 决策与被否方案
- **涨停 / 首板取 `fact_theme_limit_stock_daily`** / 否设计稿写的 `fact_limit_advance_daily` / 后者由
  `sync_fupanhui_limit_advance` 固定 `min_boards=2` 写入，4,907 行 boards 全 ≥ 2，**根本没有首板行**；`first_limit_date`
  取自接口日期列表，真库有 −9 ～ −337 个交易日的负 gap，56 个交易日缺覆盖。前者 `limit_status` 全 'U'、`limit_times`
  即连板数（首板 21,108 个股日占 79.5%），逐日只数与 `fact_market_daily.limit_up` 在 336/395 日完全相等，
  与连板梯队重叠的 4,671 行 `boards == limit_times` 全一致；同一 (日, 股) 跨板块重复但 `limit_times` 零冲突，按 (日, 股) 折叠
- **universe = 涨停表 ∪ 新高表并集（261,666 个股日）** / 否全市场 `fact_stock_daily`（2.1M 个股日） / 全市场要 ~8M 行、
  旁路库膨胀十倍；而问题是「强势股池子里首板 / 新高这层选择有没有超额」，基准率取同池子才是 §3.2「同 universe」本意，
  择时由事件日对照列剥离。代价：p0 是「强势股」基准，不是「随便买一只」基准——收据 `scope.universe` 写明，读者不会混
- 并集内稠密 1/0、源表整日缺失才 NULL / 否「不在表里就是 0」 / 涨停表 405 日缺 10 日，主库 `limit_up` 显示那些天有 40–92 只涨停，
  是同步缺口；置 0 会把缺口算成「没涨停」的阴性样本。缺哪些日记进 `stock_coverage.limit_list_missing_days`
- `new_high_1y = primary_high_period ∈ {1y,2y,3y,history}` / 否解析 `high_periods_json` / 真库核数 primary 恒为 json 最长周期、
  周期嵌套，两种判法 61,635 行完全相等；`is_new`（当日新进榜 / 周期升级）不做标签，留候选
- outcomes 显式 `series` 键 / 否靠 `entity_id` 唯一 / 测试里故意造了一只代码为 `S1.TI` 的「个股」，板块与个股各走各的序列
- `LABEL_VERSION` 升 v2 / 否只加标签不升版本 / 目录变了（12 → 15）、outcomes 内容变了，老收据按版本判「不可比」是版本存在的意义；
  sector / theme 读数逐位相同已另行核过，写在本文
- 只做设计稿点名的三个标签 / 否顺手加 `limit_boards`（连板数数值标签）/ `first_board` 已能表达首板，连板数规则等有人要再加

## 已验证（本树）
- selftest 12 → **18/18**：个股阳性对照 N=192 p=1.0 p0=0.546 → supported；`limit_up` N=240 p=0.8（二连板窗口为负，比首板宽且命中低）；
  outcomes 前移一交易日 → 个股阳性 refuted（p=0），重建恢复；universe 行数 = 植入并集 2,016
- pytest `test_methodology_backtest.py` 39 → **48** 绿；`test_experience_cards.py` 19 绿。新增：手工小库个股语义
  （跨板块重复折叠 / 二连板非首板 / 涨停表缺日 NULL / 连板数缺失 NULL / 炸板 Z 不算涨停 / 3y ⊃ 1y、120d 不算 / 只在涨停表的股
  新高 0 且缺日 NULL）、个股 outcomes 手算一致 + `S1.TI` 同码不串线 + 停牌 missing、白名单三向拒绝、stock 规则可引大盘标签、
  种子规则文件可加载、合成库个股阳性 + 并集基准 `N < baseline_n <= 并集 < 全市场`、CLI `propose --entity-type stock` 端到端
- 真库：3 个抽样事件 fwd / max / peak / dd 手算一致；**248,626 个 h=3 个股 ok 行 SQL 重算零不匹配**；missing 集中在 D0 =
  06-16 ～ 06-23（`fact_stock_daily` 2026-06-24 只有 2,169 行，正常日 ~5,144）
- ruff 0；pre-commit 10 道全过（path-literals / unread-fields / layer-audit / dataset-registration 基线不变）
- 全量主门禁 `run_main_gate.sh` @ `a890f48d`（干净树，`dirty=False`）：**7708 passed / 0 failed / 15 skipped / 1 xfailed**，
  377 s，ruff 0；较 #581 基线 7699P 多 9 例即本单新增测试，红集为空。收据
  `~/.finance-runtime/test-receipts/20260904T143232Z-a890f48d.json`
- 已 push 到 gitea，`merge-tree` 对 `gitea/main@5c7fe2eb` 无冲突；PR #585
  `http://127.0.0.1:3300/a77/finance-workspace-private/pulls/585`，**未合 main，等用户确认**

## 未验证 / 已知边界
- 涨停表比主库 `limit_up` 少数：395 日里 336 日完全相等、380 日差 ≤ 3，个别日少 8–20 只（2026-05 上旬），推测是无板块归属的涨停股
  不进题材表。这些股当天不进 universe，也不会被算成阴性；量级 ~2–3%，未修
- 个股 universe 里 2.9% 的个股日在 `fact_stock_daily` 没有同日行（新高表 97.1% / 涨停表 98.6% 有价），落 missing
- `fact_stock_daily.pct_chg` 极值 −95.78 / +858.85（IPO 首日、复牌），未剔（只剔 ≤ −100），个股窗口均值会被拉，胜率不受影响
- 个股收据 `events.sample` 含个股代码：设计稿 §6「共享层的合规硬门」要求个股粒度不对外呈现——本单收据只在分析师侧
  （`methodology/receipts/` gitignore），种子规则 `notes` 与台账地图行都写了这一句；渲染层硬门本身是 P2
- `fact_limit_advance_daily` 一条 `pct_chg = -100`（2026-04-28 603272.SH），本单不用这张表，仅记录
- 阴性对照仍只有板块那组随机标签；个股没有独立的随机标签阴性对照（`is_new` 可作候选，但它与收益未必独立）

## 下一步
1. 主门禁绿后开 PR、合入（加法，无运行时行为变化，无需切 8792）；合入后本文顶部回写
2. **`lifecycle_stage`（启动 / 发酵 / 高潮 / 分歧 / 退潮）——本单未做，卡在标注集，不是代码。** 理由与解法：
   - 前 15 个标签每一个都引用既有口径（双红 / 拐点 / 排名 / 涨停 / 新高），阶段标签没有——「高潮」和「分歧」的边界是人眼定的，
     先写规则再看真库等于用规则定义正确答案，回测就成了自证。设计稿 §3.1 也写死了「需先设计规则并用
     `theme-fermentation-tracer` 的历史链路做**人工标注对照**」
   - 需要用户给的东西：30–50 条 `(题材 sector_ts_code, trade_date, stage)` 标注，覆盖 5 个阶段各 ≥ 6 条、跨 ≥ 3 个题材、
     含 2–3 条「分歧 vs 高潮」难例。落 `methodology/annotations/lifecycle_stage.v1.jsonl`（进 git，一行一条，带 `annotated_by / ts`），
     台账地图先登记
   - 有了标注集，规则设计变成「在 `limit_heat_rank / limit_heat_rank_jump / mainline_flag / dual_red_streak / amount_rank_top10`
     上找一组阈值，对标注集的一致率 ≥ 某个门槛」，一致率与混淆矩阵进收据成立条件；没达门槛就不进白名单
   - 代码侧零脚手架：`ENTITY_TYPES / LABEL_KINDS` 现成，届时加一个 `("theme", "text")` 标签 + 一段 SQL 即可；提前占位的空标签
     会让 `count(distinct label)` 与 unread-fields 门禁都难看
3. 题材消息面标签 `news_event`（KB `evidence_index / theme_signals` 按日对齐）——跨仓，另单
4. P2：`finance_query` 暴露 `methodology_verdicts`；Beta 后验对照列；相似历史日

## 踩过的坑
- CLI 默认 `--db-path` 跟 `market_feature_store.db.DB_PATH` 走，在 worktree 里解析到 `<worktree>/db/`（空）；真库要显式
  `--db-path /Users/a77/finance-workspace-private/db/market_feature_store.duckdb`（旁路库随之落同目录）。P0 交接写了旁路库路径没写这一句
- 没有价格行的个股，日历够不到 T+h 的窗口按既有规矩记 `pending` 而不是 `missing`（status CASE 里 pending 先于 missing）；
  测试起初断言「全 missing」踩到，现在断言「早期 missing、末尾 pending、绝无 ok」
- `ruff format --check` 在本包**未改过的**文件上也报 would reformat——本仓门禁只跑 `ruff check`，不要顺手 format，会把无关 diff 混进来
