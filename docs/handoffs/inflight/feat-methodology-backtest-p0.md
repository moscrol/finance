# feat/methodology-backtest-p0

> **2026-09-04 19:50 已合入**：PR #573 → `gitea/main=313b09c9`（分支尖 `7ebdbd7c`，主门禁 7653P/0F/15S/1x，ruff 0，前端零改动）。
> 合入的是 CLI / services 侧能力，不进 Workbench 合同，无需切 8792。后续 P1 见 `feat-methodology-backtest-p1-gate.md`。
> 下文为合入前原状，供溯源。

树 `/Users/a77/fwp-wt-methodology-backtest-p0`，基座 `gitea/main`=`2d8eaea5`（干净树）。工单
`docs/superpowers/specs/2026-09-04-methodology-backtest-p0-workorder.md`（INDEX #21，登记在
`docs/finance-agent-bp` 分支，尚未合 main），设计稿 `…-structured-history-design.md`。解释器
`.venv-workbench/bin/python`。**已合 main（见顶部），未强推。**

## 这个分支做什么
把「人眼看图」编译成可查询的结构语言，给「纠偏 → 经验」设统计门：
① 旁路库 `db/history_labels.duckdb`：12 个逐日逐实体、确认日语义、版本化标签 + `data_gap` + 交易日历，从主库只读重建；
② 前瞻结果表 3/5/7/10 日（fwd / max / days_to_peak / drawdown，窗口不含 D0）；
③ 规则 JSON v0 → 白名单校验 → 参数化 SQL；④ Wilson 95% + 同期基准率 + 前后半段 + 精确二项 p + BH → 四态；
⑤ CLI `scripts/methodology_backtest.py build-labels|outcomes|run|scan|report`，收据 JSON+md 带成立条件块；
⑥ 三条种子规则、零凭证自测（阳性 / 阴性 / 前视）、pytest 32 例、台账地图新行。
逻辑全在 `intelligence/services/methodology_backtest/`（不 import runtime，layer_audit ERROR 0）。

## 决策与被否方案
- 标签 / outcomes 全在 DuckDB 里用 SQL 生成（`ATTACH` 主库只读，先例 `evolution/strategy3`）/ 否 Python 逐行 + `executemany` / 实测 20 万行 24s；否 pandas / intelligence 下无人用它
- `data_gap` 单独落 `history_data_gaps` 表，不占标签名额 / 否作第 13 个标签 / 工单验收写死 `count(distinct label) = 12`，同时要能列出被打标日期
- 题材实体 `entity_id` 沿用 `sector_ts_code`（热度表 623 码全在 `fact_sector_daily`，99.3% 热度行有同日 `pct_chg`）；`mainline_flag` 取 `fact_mainline_sector_daily` / 否设计稿写的 `fact_mainline_theme_daily` / 其 `theme_code`（TH000xx.FP）与题材实体 ID（990xxx.FP）不同空间无法 join，且覆盖 53 日 vs 106 日
- 热度档位写死 `dimension=sector / scope=all / data_stage=final / is_realtime=false` 并进 `LABEL_VERSION` / 否按日择档 / 另一档 `proxy` 只有 2026-07-17 一天 81 行
- 基准率窗口 = [首个事件日, 末个事件日] 内同 universe 全部 (实体, 日) / 否全日历 / 设计稿 §3.2「同日期范围」；日期精确配对（只取事件日）留 P1 作对照列
- 谓词值 / 日期 / horizon 全 `?` 绑定，label / op / metric / baseline.kind 走白名单映射进 SQL 文本；文本值限字母数字中文 `·/-` / 否转义 / 转义防注入，白名单防「规则说了什么」失控（08-20 决策）
- `volume_surge` 用列 `amount_vs_yesterday_pct > VOLUME_SURGE_PCT`（设计表口径），真库上与 `SignalDetector` 的 total_amount 算法 74 日完全一致；MA5 峰谷直接调 `SignalDetector`
- 种子规则 1 的 `market_stage` 用真库实际值 `主升阶段/主升/反弹阶段/反弹` / 否照抄设计稿示例「扩张/高潮」/ 数据里不存在，N 必为 0
- min_n 消融只读 `checkpoints.load_calibration`，写进收据附录，不改 `DEFAULT_CALIBRATION_MIN_N`（P1）
- `rules.py` 与 `compiler.py` 合一提交 / 否逐步 / `unread-fields` 门禁要求 `Rule.predicates / baseline_kind` 当场有读取点

## 当前状态
10 个提交（`f41d17c1`…`9ebf04d1` + 本文档与台账行）。新增：`intelligence/services/methodology_backtest/{__init__,store,labels,outcomes,rules,compiler,stats,runner,receipts}.py`、
`scripts/methodology_backtest.py`、`scripts/methodology_backtest_selftest.py`、`intelligence/tests/test_methodology_backtest.py`、
`methodology/rules/*.v1.json` ×3；改：`.gitignore`（`methodology/receipts/`）、`docs/learning/ledger-map.md`（新行）。
收据在本树 `methodology/receipts/`（gitignore，不提交）；旁路库 `/Users/a77/finance-workspace-private/db/history_labels.duckdb` 98MB。

## 已验证（本树、`.venv-workbench`，主库只读、`max(trade_date)`=2026-09-02）
- `build-labels` 1.4s：671,440 行，`count(distinct label)`=12，`max(trade_date)`=2026-09-02=主库；删库重建行数一致；`data_gap`=2026-03-30（223 行零占比 98.65%）
- `outcomes` 2.1s：610,704 行（ok 585,245 / pending 15,610 / missing 9,849）；一行手算 fwd/max/peak/dd 完全吻合；theme 与 sector 同 (实体,日,窗口) 值相等
- 三条种子收据均 `not_distinguishable`：`dual_red_streak3_continuation` N=88 p=68.2% p0=58.0% Wilson[57.9%,77.0%] 前后半段 81.8%/54.5%；`diff_ratio_turn_up_5d` N=27,186 lift −1.0%；`limit_heat_rank_jump_3d` N=13,006 lift +0.6%。scan BH adj p 0.002/0.099/0.190，全部 `exploratory=true`
- 收据成立条件块齐：源库 max 日 / label_version / rule_id@version / N / data_gap 日数 / 树 / 解释器 / revision `9ebf04d1` / dirty false；附录 min_n ∈ {2,10,20} 有标签类别数 = {2, 1, 1}（83 可证伪点、69 已判定、仅 2 个类别：生命周期推演 n=67、duckdb_flow/市场路径 n=2——后者就是 `min_n=2` 给标签的病灶实例）
- 主库 33 张 `fact_*` 行数与 `max(updated_at)` 跑前跑后一致，文件 mtime 未变（09-03 15:10），无 WAL
- selftest 12/12 PASS 4s：阳性 N=288 p=1.0 p0≈0.52 lo=0.987 → supported；阴性 → not_distinguishable（12 个 seed 0 假阳性，lift 均值 −0.5%）；outcomes 前移一交易日 → refuted，重建后恢复
- pytest 32 绿 5s；**变异**：`outcomes.WINDOW_START_OFFSET` 1→0 时 4 例变红（含 `test_outcomes_window_excludes_label_day`、`test_lookahead_shift_flips_positive_control`），selftest 前视对照同步变红；还原后 32 绿
- Wilson (0,20)/(20,20)/(10,20) 与公开表值一致到三位小数；二项 p(7,20,.5)=0.263176 与 scipy 一致；BH 手算例一致
- 编译器拒绝夹具三组各带字段路径（`condition.all[0].label` / `.op` / `.value[0]`），不触库；ruff 0；pre-commit 10 道每次提交全过
- 全量 `pytest intelligence/tests` @ `adb62c66`：**6910 passed / 14 skipped / 1 xfailed / 0 failed**，376s（收据 `~/.finance-runtime/test-receipts/20260904T113136Z-adb62c66.json`）
- 已 push 到 gitea，PR #573 `http://127.0.0.1:3300/a77/finance-workspace-private/pulls/573`，未合 main

## 未验证 / 已知边界
- 只有 413 个交易日；很多规则会落 `insufficient_n`，是正确输出。回补 2019–2024 是 D8 另单
- `.TI`→`.FP` 代码换代：`.TI` 到 2026-07-24、`.FP` 自 2025-10-09，124 天两套并存（同名 125 对）。`entity_id` 按代码，streak 在换代处截断、并存期同一板块可能双计；未去重，收据 `source_row_counts.sector_code_suffixes` 记有分布（finding，未修）
- `market_stage` 原值有「主升阶段/主升」等两种写法，按设计「直接投影」未归一；规则里两种都列
- `multi_period_resonance` 源列只有 1,910 非空 / 139 真；`mainline_flag` 只从 2026-04-01 起有值
- 基准率与事件同 universe 但只匹配日期范围，不匹配具体日期；牛市集中的规则仍可能被高估 p0（方向偏保守）
- 阴性对照是固定 seed 的确定性夹具，不是统计保证（任何 95% 区间 ~5% 假阳性）
- 主库若被夜跑写锁占用，`ATTACH` 抛 `DatabaseLockedError`→退出码 3；本次未遇到
- INDEX #21 的状态行在 `docs/finance-agent-bp` 分支，本分支未动它；两支合入后需把 #21 标「P0 已提交」

## 下一步
1. PR #573 等用户确认后合 main（`python3 scripts/gitea_pr.py merge` 或 Gitea 页面）；合入后把 INDEX #21 标「P0 已提交」
2. P1（设计稿 §3.4 / §6）：`calibrate` min_n 改默认值需分支 + 用户确认（读数已在收据附录）；经验卡 `rule_id` 映射 + promotion 统计门；个股标签；`lifecycle_stage` 人工对照集；日期精确配对基准率作对照列
3. 若要把种子规则立案进 `docs/prediction-ledger.md`，按 R-号流程 `claim_ledger_id.py claim` 另走，本单未取号

## 踩过的坑
- **阴性对照假偏差**：随机标签若用写死的独立 seed，标签模式与确定性的事件相位（idx=10+12j+s%4）的一次偶然相关会在所有 seed 下原样复现——12 个 seed lift 全 +1.6%～+2.9%，看起来像流水线有前视。逐层对比（从库里同一批 pct 用纯 Python 重算，3720 行 fwd 零不匹配）证明流水线干净，偏差在夹具；改为 label seed 派生自 seed 后 12 seed 0 假阳性
- `unread-fields` 棘轮门禁看不到「下一个提交会读」，dataclass 字段必须与读取点同提交；`CompiledRule` 因此去掉了给 runner 预留的冗余字段
- DuckDB `COUNT(*) FILTER (...) OVER (...)` 嵌在 CASE 里可用，gaps-and-islands 一段 SQL 解决「断档 / NULL 后重新计数」的 streak
- `executemany` 在 duckdb 1.5.4 上 20 万行 24s，不要用它灌标签；numpy dict / pandas `register` 是毫秒级，但本单最终全走 SQL 没用到
- `plan.get(i, (rng.gauss(), …))` 默认参数会被急切求值——生成器 RNG 消费每天恒定，反倒让相位对齐更容易出偶然相关
