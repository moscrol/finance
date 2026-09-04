# 2026-09-04 方法论回测 P0（结构化历史标签层 + 规则编译器 + 统计四态）工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
无前置单；与 BP 分支 `docs/finance-agent-bp` 并行（各开各的分支，互不依赖）。设计稿：`docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md`（下称「设计稿」），形态决策已在设计稿写死，本单不重开。

## 1. 背景与动机

- 用户 2026-09-04 提出：决策频繁，但不是每次决策都能升级为纠偏 / 经验；要基于历史统计推论，不能一次错误否定一套方法；历史行情与题材要「代码可查」，把人眼看的形态编译成结构语言，用现在的方法论去算历史成功率。
- 病灶实证：`intelligence/services/checkpoints.py:56` `DEFAULT_CALIBRATION_MIN_N = 2`——两个样本就给可靠性标签。现有校准只有命中率点估计，没有基准率与区间。
- 已有资产（2026-09-04 只读核数）：主库 52 表，`fact_market_daily` 413 交易日（2024-12-20 → 2026-09-02），`fact_sector_daily` 105,880 行，`fact_theme_limit_heat_daily` 46,877 行。定义、回测引擎、多窗口前瞻收益、零凭证自测夹具都已存在（见 §5），本单是把它们接成一条可重复的链。
- **形态决策（写死）**：
  - 标签落**旁路 DuckDB** `db/history_labels.duckdb`，从主库只读重建；不改 `market_feature_store/schema.sql`。理由：规则未稳不冻进正典；`*.duckdb` 已 gitignore；先例 `fph2026` 旁路库。
  - 方法论是**声明式 JSON 规则 → 参数化 SQL**，谓词 / 算子走白名单；**禁止**自由 SQL 字符串。理由：`docs/superpowers/specs/2026-08-20-asof-prefetch-dual-red-design.md` §1 已拍。
  - 统计口径 = Wilson 95% 区间 + 同期基准率 + 前后半段 + 四态结论；`--scan` 走 Benjamini–Hochberg。理由：设计稿 §3.3。
  - 逻辑进 `intelligence/services/methodology_backtest/`（纯函数 + 只读 DuckDB 连接；**禁止 import `intelligence/runtime`**，`scripts/layer_audit.py` 会拦），CLI 在 `scripts/methodology_backtest.py`，规则文件在 `methodology/rules/`（进 git），收据在 `methodology/receipts/`（gitignore，可重建）。理由：与 `evolution/` + `scripts/evolve.py` 同形；P2 要给 agent 暴露时 services 层可直接复用。

## 2. 目标（每条可验收）

1. `build-labels`：生成设计稿 §3.1 表前 12 行标签（sector 5 / theme 3 / market 4），写入旁路库 `history_labels`，含 `label_version`、`computed_at`、`source_max_trade_date`；`diff_ratio` 全零日打 `data_gap`。
2. `outcomes`：前瞻结果表，按 sector / theme 两类实体、`horizons=[3,5,7,10]`，字段 `fwd_return / max_return / days_to_peak / drawdown_after_peak`；交易日历取 `fact_market_daily.trade_date`。
3. 规则 JSON schema v0（设计稿 §3.2 示例为准）+ 编译器 + 白名单校验（非法 `label` / `op` / 自由 SQL 片段一律拒绝并给出字段路径）。**2026-09-04 补充（设计稿 §6 P1 三条约束的占位字段，P0 只占位不实现逻辑）**：schema 增加 `scope ∈ {shared, private}`（缺省 `shared`）、`owner`（缺省 `system`）、`source_perspective`（可空）；收据顶层带 `scope` 与 `entity_type`；`refuted` 收据与 `supported` 收据同格式、同目录，文件名含 verdict 以便后续单独收集（例如 `<date>.refuted.json`）。不做任何权限、渲染或共享逻辑。
4. 统计模块：`wilson(k, n)`、基准率、lift、前后半段、BH 校正、四态结论；`min_n` 来自规则文件，缺省 20。
5. CLI：`scripts/methodology_backtest.py build-labels|outcomes|run|scan|report`；`run` 输出收据 JSON + md，收据含成立条件块（源库 `max(trade_date)`、`label_version`、`rule_id@version`、N、`data_gap` 日数、树 / 解释器 / revision / dirty）。
6. 三条种子规则进 `methodology/rules/`：`dual_red_streak3_continuation.v1.json`（设计稿示例）、`diff_ratio_turn_up_5d.v1.json`（边际量拐点后 5 日）、`limit_heat_rank_jump_3d.v1.json`（热度跃迁后 3 日）。
7. 零凭证自测 `scripts/methodology_backtest_selftest.py`（照 `skills/theme-fermentation-tracer/scripts/selftest.py` 的形状：临时目录按 `schema.sql` 造最小库）：阳性 / 阴性 / 前视三组对照，退出码 0 = PASS。
8. `intelligence/tests/test_methodology_backtest.py`：编译器白名单、Wilson 数值（对照已知表值）、四态边界、前视检测、旁路库重建幂等。
9. 真库跑三条种子规则出收据；`docs/learning/ledger-map.md` 登记新台账行。
10. 在途交接 `docs/handoffs/inflight/feat-methodology-backtest-p0.md`。

## 3. 非目标（写死认领）

- ❌ 个股标签（`limit_up / first_board / new_high_1y`）→ 设计稿 P1。
- ❌ 题材 `lifecycle_stage`、消息面标签 → 设计稿 P1（需人工对照集，先别写规则）。
- ❌ 改 `DEFAULT_CALIBRATION_MIN_N` 或任何 `checkpoints.py` / `experience_cards.py` 运行时代码 → 设计稿 P1；本单只允许在收据里附一段「min_n ∈ {2,10,20} 下 83 个可证伪点的类别数变化」读数（只读 `calibrate`，不改值）。
- ❌ 改 `market_feature_store/schema.sql`、写主库 → 设计稿 P2。
- ❌ `finance_query` 新 dataset、Episode 合同、判官 → 设计稿 P2。
- ❌ 缠论 / MACD / 图像识别 → 设计约束（设计稿 §3.1 路线 C 不做；`fph2026` 已有缠论旁路）。
- ❌ 回补 2019–2024 历史 → 项目 MOC 任务看板 D8 另单；N 不足是正确输出。
- ❌ 写 `docs/prediction-ledger.md` / 取 R-号 → 收据不是预注册假设；要立案另按 R-号流程。
- ❌ 自动改 `params.json` / 经验卡 / 画像 → `strategy-evolve` 原则。
- ❌ 顺手修 `feature_*_window` 无消费者表 → 登记 finding 即可。

## 4. 证据路径表（先读这些，禁止臆测）

| 文件 | 看什么 |
|---|---|
| `docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md` | §3 三层设计、§3.1 标签目录 v1、§3.2 规则 JSON 示例、§3.3 四态口径、§4 无前视与数据陷阱 |
| `docs/superpowers/specs/2026-08-20-asof-prefetch-dual-red-design.md` §1 | 为什么禁止自由 SQL；`finance_query` 是参数化查询构建器 |
| `market_feature_store/schema.sql` | `fact_sector_daily`（VIEW，:160）与 `fact_sector_daily_generation`（:136）列名与 published 语义；`fact_theme_limit_heat_daily`（:314）`dimension/scope/data_stage/is_realtime/rank`；`fact_mainline_theme_daily`（:384）；`fact_market_daily`（:31）`market_stage/amount_vs_yesterday_pct/advancers`；`dim_sector`（:16） |
| `skills/strategy1-matrix/SKILL.md` + `scripts/update_matrix.py` | 严格双红口径 `pct_chg>0 且 diff_ratio>10 且 amount>500`，**复用勿重定义** |
| `scripts/detect_turning_points.py::detect` | MA5 峰谷 / 放量 >10% 的确认日算法，**复用勿重写**；标签打在确认日 |
| `scripts/backtest_sector.py::SectorBacktestEngine` | 只读 canonical 表、`MARKET_FEATURE_STORE_DB` 覆盖、库不存在 fail closed 的写法 |
| `evolution/validate.py::trading_calendar / forward_returns / aggregate` | 多窗口前瞻收益与交易日历逻辑，移植到 outcomes |
| `skills/theme-fermentation-tracer/scripts/selftest.py` | 零凭证自测形状：临时目录按 `schema.sql` 造最小库 + 断言四段产出。**照抄形状** |
| `intelligence/services/checkpoints.py` `:56` 与 `calibrate / CategoryStat` | `DEFAULT_CALIBRATION_MIN_N = 2`；只读调用出 min_n 消融读数 |
| `scripts/layer_audit.py` docstring | services 不得 import runtime 的门禁口径 |
| `docs/learning/ledger-map.md` | 台账登记表头：台账 / canonical 路径 / 格式 / 唯一写入者 / 提交? / 渲染物 |
| `CLAUDE.md`「市场假设验证 / 跑马策略执行规则」「回填注意事项」 | outcome 多窗口口径；`.TI` 代码 vs 中文名；`diff_ratio` 全零日 |
| `~/.claude/skills/fph2026/SKILL.md` | 旁路库先例；确认缠论 / MACD 不在本单范围 |

## 5. 步骤 + 验收

### 步骤

1. 开工三连（在主检出树）：`git status --short`、`git branch --show-current`、`git worktree list`。主树有他人未提交足迹，**不要在主树动手**。
2. 新树：`cd /Users/a77/finance-workspace-private && git worktree add /Users/a77/fwp-wt-methodology-backtest-p0 -b feat/methodology-backtest-p0 gitea/main`。若 `git fetch` 卡住，直接用本地 `gitea/main` ref（2026-09-04 实测 fetch 曾挂起，本地 ref 可用）。
3. 解释器一律 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（venv 无 `.pth`，加载哪份代码由 cwd 决定，在新树 cwd 下调用即可）。先 `python -c "import duckdb"` 确认可用。
4. 读 §4 证据路径表；用 `python3 scripts/code_map.py query "方法论回测 历史标签 双红"` 确认无现成实现（2026-09-04 查过：只有 `backtest_sector` / `detect_turning_points` / 双红定义，无标签层）。
5. 实现顺序：`labels.py`（标签生成器 + data_gap）→ `outcomes.py` → `rules.py`（schema + 校验）→ `compiler.py` → `stats.py` → `receipts.py` → CLI → selftest → pytest。每步一个提交，pathspec。
6. 三条种子规则文件 + 真库 `build-labels` / `outcomes` / `run ×3` / `scan` 出收据（主库 `read_only=True`；若被夜跑写锁拒绝，等 21:00 后重试并在收据注明）。
7. 只读 `calibrate` 消融：`min_n ∈ {2,10,20}` 各跑一遍现有可证伪点，把「有标签类别数」三个数写进收据附录。
8. `docs/learning/ledger-map.md` 追加一行：`方法论回测收据 | methodology/receipts/<rule_id>@v<version>/<date>.json | JSON | scripts/methodology_backtest.py run/scan | 否（可重建） | 同名 .md`。
9. 在途交接 `docs/handoffs/inflight/feat-methodology-backtest-p0.md`（分支做什么 / 决策与被否方案 / 当前状态 / 未验证 / 下一步 / 踩过的坑 / 已验证）。
10. `ruff check .` 与 `pytest -q intelligence/tests/test_methodology_backtest.py` 绿；跑 `scripts/check_test_receipt.py` 确认收据条件；push 分支到 gitea，开 PR，**不合 main**。

### 验收（机器可判或有明确观察面）

- [ ] `build-labels` 在真库上完成；旁路库 `history_labels` 行数 > 0，`select count(distinct label)` = 12，`select max(trade_date)` = 主库 `fact_market_daily` 的 `max(trade_date)`。
- [ ] 删除旁路库后重跑 `build-labels`，`select count(*), max(computed_at)` 中行数与首跑一致（幂等 / 可重建）。
- [ ] `data_gap` 标签在真库上至少能列出被打标的日期（若为 0 天，收据注明「本窗口无全零日」）。
- [ ] 编译器拒绝夹具：`label` 不在白名单、`op` 为 `; DROP`、`value` 含 SQL 片段，三种输入各返回带字段路径的校验错误，且不触库。
- [ ] **阳性对照**：selftest 植入「标签 X 后 5 日收益必为正」的合成数据，`run` 结论 = `supported`，`lo > p0`。
- [ ] **阴性对照**：随机标签，结论 ∈ {`not_distinguishable`, `insufficient_n`}。
- [ ] **前视对照**：把 outcomes 整体前移一个交易日后，阳性对照结论不再是 `supported`（翻转或降级），证明编译器无前视泄漏。
- [ ] Wilson：`wilson(k=0,n=20)`、`wilson(k=20,n=20)`、`wilson(k=10,n=20)` 与公开表值一致到小数点后三位；区间不越界 [0,1]。
- [ ] 四态边界：N = min_n − 1 → `insufficient_n`；N = min_n 且 `lo > p0` 但后半段 `< p0` → `not_distinguishable`（不是 `supported`）。
- [ ] `scan` 对 ≥ 3 条规则输出 BH 校正后的结论列与 `exploratory=true`。
- [ ] 三条种子规则真库收据存在，每份含成立条件块（源库 max 日 / label_version / rule_id@version / N / data_gap 日数 / 树 / 解释器 / revision / dirty）。
- [ ] 收据附录含 `min_n ∈ {2,10,20}` 三个类别数读数。
- [ ] `ledger-map.md` 新行在；`layer_audit.py` ERROR 0；`ruff` 0；新增 pytest 全绿且**至少一条测试在故意注入前视 bug 时变红**（变异测试，记进交接）。
- [ ] 主库 `fact_*` 任何表行数与 `max(updated_at)` 跑前跑后一致（未写主库）。

## 6. 红线（抄 AGENTS.md，不新发明）

- 开工先 `git status --short && git branch --show-current && git worktree list`；主树有他人足迹**另开干净树**。
- 🚫 禁 `git add -A` / `git add .`；一律 `git commit -- <明确文件列表>`；不合 `main`、不强推、合并等用户确认。
- 🚫 禁提交 `.env*` / 密钥 / `*.duckdb` / `*.db` / `.DS_Store` / 缓存与虚拟环境；旁路库与 `methodology/receipts/` 加进 `.gitignore`（确认 `*.duckdb` 已覆盖）。
- 解释器 `.venv-workbench/bin/python`；宿主 `python3` 缺依赖会给偏高失败数。
- `intelligence/services/` 不得 import `intelligence/runtime/`（`layer_audit.py` 门禁）。
- 主库只读（`read_only=True`）；同一时间只有一个写入连接，不与夜跑抢锁。
- 不给 agent 开 Shell / 任意 SQL；规则文件里出现 SQL 片段即拒绝。
- 台账号只用 `python3 scripts/claim_ledger_id.py claim --branch <分支>` 取（本单默认不取号；若决定把种子规则立案进 `prediction-ledger`，才取）。
- 实验性收据默认不提交（可重建）；规则 JSON、代码、测试、台账地图行、交接文档提交。
- 用户纠偏必落 correction（`python3 -m intelligence.cli record-correction ...`），本单执行中若用户纠正判断同样适用。
