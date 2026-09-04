# 2026-09-04 历史重放引擎（站在 D0 出结构化判断 → 自动判分 → AI 校准读数；模型截止日分栏；匿名化对照臂）工单（P1.5，中单）

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
INDEX #25。前置：无硬前置（方法论回测 P0 / P1 已在 `gitea/main`）。与 #24 互不依赖；#24 若先合，本单输出的判断记录沿用其 `rule_id` 字段名。预计三到五天。
设计稿：`docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md` §10.2 第二、四条、§10.3 第 2 步、§10.4。

## 1. 背景与动机

- 用户 2026-09-04 理念第六句：「站在相似的节点去推导，然后拿后续的走势来验证——这是让它学习的过程。」设计稿 §10.3 把它排为闭环的**第 2 步**：先用现有三条规则当 AI 的方法论，量 AI 复现规则判断的一致率和 AI 前瞻判断的按类别命中率，把尺子立起来；「发现新规律」（P2）在尺子之后。
- 仓内已有三块零件，缺的是把它们接成一条链的引擎：
  - **PIT 输入**：`intelligence/eval/fidelity_replay.py::build_input_snapshot`（`:952`）只取 `trade_date ≤ D0` 且 `updated_at < D0 + 1 day` 的行，绑定 D0 当时的 wiki commit；`/Users/a77/fidelity-replay/pit-snapshots/` 每日不可变快照（launchd `com.financeworkspace.pit-snapshot`）。
  - **结构化判断格式 + 自动判分**：双盲台账 `docs/learning/forecast-review-ledger/<date>.answer.<agent>.json` 的 `hypotheses[]`（`id / category / claim / horizon / confidence_probability / evidence_refs / evidence_as_of / falsify_when`），`scripts/dual_blind_auto_verdict.py` 从 DuckDB 自动裁定 market / direction 类假设；`scripts/dual_blind_forecast.py aggregate` 按 agent × category × confidence 分账。
  - **确定性对照与结果表**：`methodology_backtest` 的编译器（规则在 D0 触发了哪些实体）与 `history_outcomes`（每个 (实体, 日, 窗口) 的 `fwd_return / max_return / days_to_peak / drawdown_after_peak`）。
- **两个泄漏，第二个全仓无守门**（设计稿 §10.2 第四条）：
  - 数据泄漏：D0 之后的行进了输入。`fidelity_replay` 已守。
  - **模型记忆泄漏**：LLM 训练语料里可能就有 D0 之后的 A 股行情与新闻，「站在 2025-03 推导」可能是在背答案。仓内没有任何收据记录所用模型的训练截止日（`rg -i 'training cutoff|训练截止' intelligence/eval docs` = 0）；`ceiling_leakage.py` 的 `post_cutoff_result` 指**基准冻结日**之后的结果语句，是封印指令泄漏检查，与此无关，不要混用。
- **PIT 现实（2026-09-04 只读核数，主库 `max(trade_date)`=2026-09-02）**：
  - `fact_market_daily.updated_at` 最小值 **2026-08-12**（整表在那天重写过），`updated_at ≤ trade_date + 1 day` 只通过 **17 / 413** 个交易日（最早 2026-08-11）；`fact_sector_daily_generation` 1,839 / 107,097 行（最早 2026-07-24）；`fact_theme_limit_heat_daily` 10,039 / 46,877（最早 2026-06-02）。
  - 每日快照：**33 份** manifest，2026-07-10 → 2026-09-02，缺 6 个工作日（07-21、07-28、08-04、08-06、08-25、08-31）。
  - 结论：严格 PIT 只能站 33 个节点，且全在同一个两个月的行情区间里；要站到 413 个节点，只能接受 `trade_date ≤ D0` 边界（行值被 D0 之后回填改写的风险由执行方声明，不由引擎掩盖）。**因此 `pit_grade` 必须是每条读数的一等字段**，两档分开报，不出混合平均。
- **形态决策（写死）**：
  - 引擎落 `intelligence/eval/replay_engine.py`（入口层，可 import services；`layer_audit.py` docstring 第 8–9 行），CLI `scripts/replay_engine.py`。不进 runtime、不进 Workbench 合同。
  - 判断格式复用双盲答卷 `hypotheses[]` 的字段名，但类别只允许 `market` / `direction`（板块 / 题材 / 大盘层），**不允许 `target`（个股）**——BP §3.4 边界；`picks` 留空。`scripts/dual_blind_forecast.py::validate_answer`（`:226–228`）要求 `picks` 非空，**不改它**；重放答卷用引擎自己的 `validate_replay_answer`，hypotheses 部分口径照抄。
  - 判分不写 `docs/learning/forecast-review-ledger/`（那是真向前台账，写进去就污染地面真值）；所有产物落 `~/.finance-runtime/replay/<run_id>/` 与 `intelligence/eval/measurements/replay-<date>.{json,md}`。
  - LLM 调用只走 `intelligence/services/llm_refine.complete`（`:831`；受 `_budget_rejection` 预算闸）。实际模型名取返回的 `provider.model`，写进每条记录——不写「glm」这种族名。
  - 两条测量车道分开报：**车道 A 规则复现一致率**（零泄漏，因为不涉及未来）与**车道 B 前瞻判断命中率**（有两种泄漏，带三个标签）。
  - 「AI 学习」= 系统知识层增长。本单只量、只出收据，不改任何规则 / 卡 / 画像 / 提示词。

## 2. 目标（每条可验收）

1. **节点选择与 PIT 分档** `select_nodes(db, start, end, count_per_grade)`：复用 `fidelity_replay.select_pilot_dates`（`:667`，按 月 × market_stage 分层）；每个节点标 `pit_grade ∈ {strict, trade_date_only}`——`strict` 当且仅当 `/Users/a77/fidelity-replay/pit-snapshots/<D0>.manifest.json` 存在且 checksum 校验通过（用 `scripts/pit_snapshot_inventory.py` 的校验逻辑，不重写）；否则 `trade_date_only`。默认每档 20 个节点，`--count-per-grade` 可调。
2. **输入构建** `build_replay_input(node)`：`strict` 档从快照 `.snapshot.json.gz` 取；`trade_date_only` 档调 `build_input_snapshot` 的**新增参数** `strict_updated_at: bool = True`（默认值不变，既有调用方零行为变化），置 False 时 `_pit_where`（`:918`）不加 `updated_at` 条件。两档输入都追加：D0 当日 `history_labels` 的全部 sector / theme / market 标签（旁路库只读）、`methodology/rules/*.json` 全文、交易日历 D0 之前 20 日。输入 JSON 落盘并带 `input_sha256`、`pit_grade`、`max_embedded_date`（必须 ≤ D0，否则拒绝生成，照 `:1028–1030`）。
3. **两条臂的提示词** `render_prompt(input, arm)`：`arm=named` 用真名与绝对日期；`arm=anonymized` 把 `sector_ts_code` / 板块名 → `S01…`、题材名 → `TH01…`、绝对日期 → `T-0 … T-19`、`market_stage` 文本保留、所有数值保留；映射表随节点落盘（`anon_map.json`），判分前反解。两臂提示词除命名外**逐字相同**（用同一模板渲染，测试断言 diff 只落在映射位）。
4. **车道 A 规则复现一致率**：对每个节点、每条 `scope.entity_type ∈ {sector, theme}` 的规则（PR #585 后 `stock` 也是合法 scope，且已有一条个股种子规则 `first_board_new_high_1y_5d`——**本单不跑个股规则**，输入里也不放 `STOCK_LABELS`），提示词给出规则 JSON 与 D0 标签表，要求 AI 输出「该规则今日在哪些实体上触发」的实体列表；对照 `methodology_backtest.compiler` + `runner.execute_compiled` 以窗口 `[D0, D0]` 得到的事件集，算每节点的精确率 / 召回率 / 完全一致（集合相等）比例。**此车道不涉及任何 D0 之后的数据，是无泄漏读数。**
5. **车道 B 前瞻判断**：提示词要求 AI 以双盲 `hypotheses[]` 格式给出 ≥ 3 条、≤ 8 条可证伪假设，`category ∈ {market, direction}`，`horizon ∈ {T+1, T+3, T+5}`，`direction` 类 claim 必须落到一个 `sector_ts_code` 与一个 `history_outcomes` 度量（形如 `S07 fwd_return@5 > 0`，命名臂用真码），`market` 类 claim 用 `fact_market_daily` 列的数值条件（`dual_blind_auto_verdict.extract_conditions` 能解析的写法）；每条可选 `rule_id`（AI 认为自己在应用哪条规则）。`validate_replay_answer` 拒绝 `target` 类、拒绝个股代码、拒绝 `evidence_as_of > D0`。
6. **自动判分** `judge(node, answer)`：`direction` 类查 `history_outcomes`（`WINDOW_START_OFFSET=1`，窗口不含 D0；`status != ok` → `unverifiable`）；`market` 类复用 `dual_blind_auto_verdict.market_actuals` + `eval_conditions` 口径（下沉或 import，不复制两份实现——若脚本不能干净 import，把这两个纯函数搬到 `intelligence/eval/replay_engine.py` 并在原脚本处 import 回去，保证单一实现）。判分只读主库 / 旁路库。
7. **模型截止日表** `intelligence/eval/model_cutoffs.json`（进 git）：`[{model_pattern, training_cutoff: YYYY-MM-DD | null, source_url, checked_at, note}]`，首版录 `glm-5.2`（写手默认，`llm_refine.py:100–101, :207–208`）与 `grok-4.6`（`grok_cli_judge.py:37`）；**查不到官方截止日就填 null**，不猜。每条记录按实际 `provider.model` 匹配得 `memory_bucket ∈ {post_cutoff, pre_cutoff, unknown}`（D0 > cutoff → post；≤ cutoff → pre；cutoff 为 null → unknown）。报表把 `pre_cutoff` 与 `unknown` 都标 `memory_contaminated`，**不与 `post_cutoff` 合并出任何数字**。
8. **聚合与收据** `intelligence/eval/measurements/replay-<date>.{json,md}`：车道 A 按 `pit_grade × arm × rule_id` 出一致率；车道 B 把每条假设整形为 checkpoints 记录 + verdicts 记录后直接调 `checkpoints.calibrate`（复用 `CategoryStat`，不重写聚合），再按 `pit_grade × memory_bucket × arm × category × horizon` 分格出 N / 命中率 / Wilson 95%（`methodology_backtest.stats.wilson`）；**格子 N < 10 只显示 N，不显示命中率**（与 `DEFAULT_CALIBRATION_MIN_N` 同闸）。成立条件块：模型名 / 截止日来源与 `checked_at` / 节点数按档 / 快照 manifest sha 列表 / 旁路库 `label_version` 与 `source_max_trade_date` / 树 / 解释器 / revision / dirty / LLM 调用次数与失败次数。
9. **与双盲台账对账**：对 2026-07-10 → 2026-09-02 中同时有快照与台账答卷的日期（以 `<date>.answer.*.json` 存在为准），在 `strict` 档跑重放，把重放 `market` 类命中率与 `scripts/dual_blind_forecast.py aggregate` 里真人 agent 同类别同期命中率并排（两列 + 差值 + 各自 N），写进报表「对账」段。差值本身不做结论，只记录。
10. **规则 schema 两处加法**（`methodology_backtest/rules.py`，为设计稿 §10.2 第二条占位；编译器 SQL 不变）：
    - `PROVENANCE_KINDS` 增加 `"discovered"`（现为 `("correction", "manual")`，`:98`）。
    - 新可选顶层键 `windows: {"discovery": [start, end], "validation": [start, end]}`（`validation.start > discovery.end` 否则校验错误，带字段路径）；`runner.run_rule` 有 `windows` 时对两窗各跑一次（复用 `resolve_window`，`:134`），收据加 `verdict_discovery` / `verdict_validation`，顶层 `verdict` 取 **validation** 的。无 `windows` 行为不变。
    - **不做 `sharing / owner / source_perspective`**：这组字段由在途分支 `feat/methodology-backtest-p1-refuted`（P1 第四刀，`fwp-wt-methodology-backtest-p1d`，2026-09-04 23:06 已提交 `e520e31e`，含证伪库 `methodology/refuted/` 与 `report --refuted`）以**扁平顶层字段**实现（`rule.sharing` 字串 / `rule.owner` / `source_perspective`），四条种子规则文件同步加了字段。本单的 schema 加法**必须在第四刀合入后 rebase 再做**，`_TOP_KEYS` 只追加 `windows`，不碰它们的键名；派单时若第四刀尚未合，先做本单其他步骤，schema 步骤最后做。
11. **零凭证自测** `scripts/replay_engine_selftest.py`（LLM 用可注入的 stub callable，不联网）：
    - 阳性对照（车道 A）：stub 返回编译器事件集 → 一致率 100%。
    - 阴性对照（车道 A）：stub 返回随机实体子集 → 一致率显著低于 100%。
    - **记忆对照（车道 B，验证匿名化臂的检出力）**：stub「背答案」——当且仅当提示词里出现绝对日期字符串时，查 outcomes 表按真实结果作答；否则按 50% 随机。命名臂命中率必须显著高于匿名臂，报表必须把差值标出来。这是匿名化臂存在的理由：**臂间差就是记忆成分的上界**。
    - 前视对照：把 outcomes 整体前移一个交易日后，阳性 stub 的车道 B 命中率必须掉到基准附近。
    - 全部在 `methodology_backtest_selftest` 同款最小旁路库上跑，退出码 0 = PASS。
12. **测试** `intelligence/tests/test_replay_engine.py`：`pit_grade` 判定（有 / 无 manifest、checksum 坏）；`strict_updated_at=False` 只在显式传参时生效、既有 `build_input_snapshot` 调用路径行为不变；两臂提示词 diff 只在映射位；`validate_replay_answer` 拒绝 `target` / 个股 / 未来 `evidence_as_of`；`memory_bucket` 三分支；格子 N < 10 不出率；`windows` 校验与双窗收据；`discovered` 合法。`test_methodology_backtest.py` / `test_fidelity_replay.py` / `test_dual_blind_forecast.py` / `test_checkpoints.py` 全绿。
13. **真库读数**：`--count-per-grade 20 --arms named,anonymized --lanes A,B`（40 节点 × 2 臂 × 2 车道 ≈ 160 次 LLM 调用；先 `--dry-run` 打印调用数与估算 token，`--max-calls` 硬帽默认 200），报表写进交接：车道 A 两档两臂一致率；车道 B 分格表；对账段；`memory_bucket` 分布（若 `glm-5.2` 截止日查不到，整表 `unknown`——这就是当前真相，照写）。
14. `docs/learning/ledger-map.md` 追加一行：`历史重放读数 | intelligence/eval/measurements/replay-<date>.{json,md} | JSON/md | scripts/replay_engine.py run | 是 | 同名 .md`；节点级产物（`~/.finance-runtime/replay/`）不登记（可重建、不进仓）。
15. 在途交接 `docs/handoffs/inflight/feat-historical-replay-engine.md`。

## 3. 非目标（写死认领）

- ❌ LLM 提议者（从重放里提候选规则）→ 设计稿 P2；本单 `discovered` 只是 schema 合法值，没有任何代码会产生它。
- ❌ 个股层假设（`target` 类、`picks`）→ BP §3.4 产品边界；引擎校验直接拒绝。
- ❌ 写 `docs/learning/forecast-review-ledger/` 任何文件；改 `dual_blind_forecast.py` / `dual_blind_auto_verdict.py` 的现有行为（只允许把纯函数下沉后 import 回去）。
- ❌ 改 `fidelity_replay.build_input_snapshot` 的默认语义（新参数默认 True）；改快照冻结流程 `pit_snapshot_inventory.py`。
- ❌ 回填 2026-07-10 之前的严格快照——历史上没冻结的就是没有，`trade_date_only` 档如实标注。
- ❌ 改提示词模板以「提高命中率」、换模型、调温度——本单只量不调；调优另单，且要先有本单的尺子。
- ❌ 改 `checkpoints.calibrate` / `CategoryStat` / `DEFAULT_CALIBRATION_MIN_N`；改经验卡 / 纠偏 / 画像 / 规则文件内容。
- ❌ `lifecycle_stage` / 消息面标签 / 个股标签 → 设计稿 P1 其他单。
- ❌ 相似日（SAX / `fact_historical_mapping`）→ P2；本单节点选择只按 月 × market_stage 分层。
- ❌ 微调 / 蒸馏；Workbench / API / runtime 任何改动。
- ❌ 写 `docs/prediction-ledger.md` / 取 R-号。
- ❌ 把 `pre_cutoff` / `unknown` 与 `post_cutoff` 合并成一个「总命中率」——报表结构上不允许。

## 4. 证据路径表（先读这些，禁止臆测）

| 文件 | 看什么 |
|---|---|
| `docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md` §10 | 六句理念对照、四条守门、顺序、分期——本单实现的是 §10.3 第 2 步 |
| `intelligence/eval/fidelity_replay.py` `:1–10` docstring、`:667` `select_pilot_dates`、`:723` `find_kb_commit_as_of`、`:807` `build_pilot_plan`、`:918` `_pit_where`、`:952–1033` `build_input_snapshot`、`:1036–1077` `build_outcome_snapshot` | PIT 边界的实现；新参数加在 `_pit_where` / `build_input_snapshot`；`max_embedded_date > as_of` 即拒绝的写法照抄 |
| `docs/learning/fidelity-replay-evaluation.md`、`docs/learning/pit-snapshot-inventory.md` | 「`updated_at < as_of + 1 day` 才算 PIT」「后补数据不冒充 PIT」两条纪律；快照 manifest 字段 |
| `/Users/a77/fidelity-replay/pit-snapshots/`（不在仓）、`scripts/pit_snapshot_inventory.py`、`intelligence/eval/com.financeworkspace.pit-snapshot.plist` | 33 份快照 07-10 → 09-02；checksum 校验逻辑复用；launchd 已加载（`launchctl list` 有 `com.financeworkspace.pit-snapshot`） |
| `scripts/dual_blind_forecast.py` `:83` `ALLOWED_HYPOTHESIS_CATEGORIES`、`:146–190` `cmd_manifest`、`:193` `validate_answer`（`:226–228` picks 非空）、`:941` `aggregate` | 假设格式与类别；manifest 只是冻结清单不是 PIT 快照（`duckdb_cutoff` 取当前 max）；aggregate 的 agent × category 分账形状用于对账段 |
| `scripts/dual_blind_auto_verdict.py` `:71` `extract_conditions`、`:87` `eval_conditions`、`:133` `market_actuals`、`:215` `judge_direction`、`:259` `build_verdicts_for_date` | market 类自动裁定的口径，下沉复用 |
| `docs/learning/forecast-review-ledger/2026-09-03.answer.claude.json`、`2026-07-17.verdict.json` | 一份真答卷 / 真裁定的字段实例（`hypotheses[].{id,category,claim,horizon,confidence_probability,evidence_refs,evidence_as_of,falsify_when}`；`verdicts[].{id,agent,verdict,actual,stream,horizon,evidence_ref}`） |
| `intelligence/services/methodology_backtest/store.py` `:59–72` `history_outcomes` DDL、`:119` `open_labels_db(read_only=True)`；`outcomes.py` `:46` `OUTCOME_ENTITY_TYPES`（PR #585 后含 stock）、`:48` `WINDOW_START_OFFSET`；`labels.py` `:103–113` 标签名（`SECTOR / THEME / MARKET / STOCK_LABELS`，`LABEL_VERSION` 已升 v2） | direction 类判分的数据源；窗口不含 D0；输入只放 sector / theme / market 标签 |
| `intelligence/services/methodology_backtest/runner.py` `:134` `resolve_window`、`:189` `execute_compiled`、`:269` `run_rule`；`compiler.py` | 车道 A 的确定性对照；`windows` 双窗跑法 |
| `intelligence/services/methodology_backtest/rules.py` `:48–49` `ENTITY_TYPES / SCOPE_ENTITY_TYPES`（含 stock）、`:95` `_TOP_KEYS`、`:97–98` `_PROVENANCE_KEYS / PROVENANCE_KINDS`、`:266` `validate_rule`；`receipts.py` `:46` `build_receipt`、`:248` `latest_receipt`、`:278` `write_receipt` | 两处 schema 加法的落点；收据顶层加 `verdict_discovery / verdict_validation`。**第四刀合入后这些行号会再漂，以 `rg` 为准** |
| `feat/methodology-backtest-p1-refuted` 分支（`git log gitea/main..feat/methodology-backtest-p1-refuted`；树 `/Users/a77/fwp-wt-methodology-backtest-p1d`） | 第四刀改了 `rules.py / receipts.py / runner.py / propose.py / 四个种子规则文件`——本单 schema 步骤前先确认它合没合，合了就在它之上做 |
| `intelligence/services/methodology_backtest/stats.py` `:35` `wilson` | 分格区间 |
| `intelligence/services/checkpoints.py` `:341–424` `CategoryStat / calibrate`、`:63` `DEFAULT_CALIBRATION_MIN_N` | 车道 B 聚合直接复用；N < 10 不出率 |
| `intelligence/services/llm_refine.py` `:831–850` `complete` 签名与返回、`:100–101, :207–208` glm-5.2 默认、`_budget_rejection` | 唯一 LLM 入口；`provider.model` 是实际模型名；预算闸 |
| `intelligence/services/grok_cli_judge.py` `:37` `DEFAULT_MODEL = "grok-4.6"` | 截止日表第二行 |
| `intelligence/eval/tool_hunger.py`、`intelligence/eval/measurements/` | 报表脚本形状（`--since` / `--out-dir` / `write_*_report`） |
| `intelligence/eval/ceiling_leakage.py` `:24, :49, :757` `post_cutoff_result` | **确认它是基准冻结日语义，不要拿来当模型截止日守门** |
| `scripts/layer_audit.py` docstring `:6–9` | eval 是入口层，可 import services；services 不得 import runtime |
| `scripts/check_unread_fields.py` | 新 dataclass 字段与读取点同提交 |
| `docs/learning/ledger-map.md` | 台账登记表头 |
| `~/.finance-runtime/` 现有目录惯例（`live-probe-*`、`test-receipts/`） | 节点级产物落点 |

## 5. 步骤 + 验收

### 步骤

1. 开工三连；从 `gitea/main` 新开树与分支 `feat/historical-replay-engine`（`git worktree add /Users/a77/fwp-wt-replay-engine -b feat/historical-replay-engine gitea/main`）。解释器 `.venv-workbench/bin/python`；`python -c "import duckdb"`。
2. `python3 scripts/code_map.py query "历史重放 fidelity_replay 双盲 auto_verdict"` 确认没有现成引擎（2026-09-04 查过：只有三块零件，无链）。
3. 先跑一遍只读核数把 §1「PIT 现实」的数字在实施基线上重出（`updated_at` 分布、快照份数与缺日），写进交接；数字若变，以实施日为准。
4. 实现顺序（每步一个提交，pathspec）：`rules.py` 三处 schema + `runner` 双窗 + 收据字段（+ 测试）→ `fidelity_replay.build_input_snapshot(strict_updated_at)`（+ 测试既有路径不变）→ `replay_engine.py`：`select_nodes` → `build_replay_input` → `render_prompt` 两臂 → `validate_replay_answer` → 车道 A → `judge` 与 `market` 纯函数下沉 → 车道 B 聚合（复用 `calibrate`）→ `model_cutoffs.json` + `memory_bucket` → 报表 → 对账段 → CLI（`run / dry-run / report`，`--max-calls` 默认 200）→ selftest → pytest → ledger-map → 交接。
5. 查 `glm-5.2` 与 `grok-4.6` 的官方训练截止日：只接受官方文档 / 模型卡 URL；查不到填 `null` 并在 `note` 写「2026-09-04 未见官方披露」。**不要用媒体转述**。
6. 真库：先 `run --dry-run` 打印节点数 / 调用数 / 估算 token（输入按 `len(prompt)/1.6` 估，标 estimated），再 `run`。若 `_budget_rejection` 拒绝，等预算窗口，不要绕。产物在 `~/.finance-runtime/replay/<run_id>/`；报表 `intelligence/eval/measurements/replay-<date>.{json,md}` 提交。
7. 变异测试至少两条：① `judge` 的 `WINDOW_START_OFFSET` 改 0 → 前视对照与 `test_replay_engine` 至少一例变红；② 匿名化映射漏掉日期 → 「两臂提示词 diff 只在映射位」测试变红且记忆对照失效。恢复后绿。记进交接。
8. 门禁：`ruff`、`layer_audit.py`、`check_unread_fields.py`、`pytest -q intelligence/tests/test_replay_engine.py intelligence/tests/test_methodology_backtest.py intelligence/tests/test_fidelity_replay.py intelligence/tests/test_dual_blind_forecast.py intelligence/tests/test_checkpoints.py`，全量 `run_main_gate.sh`；push、开 PR、**不合 main**。

### 验收（机器可判或有明确观察面）

- [ ] `select_nodes` 在真库上：`strict` 档节点全部落在有 manifest 的 33 日内且 checksum 通过；`trade_date_only` 档节点的 D0 无 manifest；两档各 ≥ 1 个 `market_stage` 类别以上。
- [ ] `build_replay_input` 两档产物 `max_embedded_date ≤ D0`；人为把一行 `trade_date = D0 + 1` 塞进夹具 → 抛错不落盘。
- [ ] `strict_updated_at` 缺省时 `build_input_snapshot` 输出与改动前逐字节一致（对同一夹具库比 `snapshot_sha256`）。
- [ ] 两臂提示词：对同一节点，`named` 与 `anonymized` 的 diff 只出现在 `anon_map.json` 列出的位置；匿名臂提示词里 `rg -c '20[0-9]{2}-[01][0-9]-[0-3][0-9]'` = 0 且不含任何 `dim_sector` 名称。
- [ ] `validate_replay_answer`：`category=target` → 拒；claim 含 6 位个股代码 → 拒；`evidence_as_of > D0` → 拒；合法答卷通过且字段与双盲 `hypotheses[]` 同名。
- [ ] 车道 A 阳性 stub 一致率 = 1.0；阴性 stub < 0.8（夹具规模下）。
- [ ] 记忆对照：命名臂命中率 − 匿名臂命中率 > 0.2（夹具设计保证），报表「臂间差」字段非空且标 `memory_signal`。
- [ ] 前视对照：outcomes 前移一交易日后，阳性 stub 车道 B 命中率落到基准 ±0.1 内。
- [ ] `memory_bucket`：cutoff 为 null → 全部 `unknown`；给定 cutoff → D0 前后分两桶；报表任何一格都不把 `post_cutoff` 与其他桶相加。
- [ ] 分格表：N < 10 的格子只有 N，无命中率、无区间；N ≥ 10 有 Wilson 区间且不越界 [0, 1]。
- [ ] 对账段：至少 5 个日期同时有快照与真答卷，两列命中率与 N 并排；若不足 5 个，段落写「不足对账最小样本」而不是留空。
- [ ] `windows` 规则：`validation.start ≤ discovery.end` 校验错误带字段路径；合法双窗收据含 `verdict_discovery` / `verdict_validation`，顶层 `verdict == verdict_validation`；无 `windows` 的既有种子规则收据与改动前字段逐键一致（对同一旁路库比 `stats` / `verdict` / `events`）。
- [ ] `PROVENANCE_KINDS` 含 `discovered`；`propose` 仍只产 `correction`（`grep` 代码无 `"discovered"` 写入点）。
- [ ] 报表成立条件块含：模型名（实际 `provider.model`）、截止日与 `checked_at` 与来源、按档节点数、manifest sha 列表、`label_version`、`source_max_trade_date`、revision、dirty、LLM 调用 / 失败次数；`dirty=false`。
- [ ] 真库 `run` 完成：调用数 ≤ `--max-calls`；`~/.finance-runtime/replay/<run_id>/` 每节点有 `input.json / answer.named.json / answer.anonymized.json / verdict.json / anon_map.json`。
- [ ] `docs/learning/forecast-review-ledger/` 目录 `git status` 无任何改动；主库 `fact_*` 行数与 `max(updated_at)` 跑前跑后一致；旁路库 `history_build_meta` 不变。
- [ ] `ledger-map.md` 新行在；`layer_audit.py` ERROR 0；`check_unread_fields.py` 无新增；`ruff` 0；两条变异测试记录在交接；全量门禁绿。

## 6. 红线（抄 AGENTS.md，不新发明）

- 开工先 `git status --short && git branch --show-current && git worktree list`；主树有他人足迹**另开干净树**。
- 🚫 禁 `git add -A` / `git add .`；一律 `git commit -- <明确文件列表>`；不合 `main`、不强推、合并等用户确认。
- 🚫 禁提交 `.env*` / 密钥 / `*.duckdb` / `*.jsonl` 台账 / 节点级产物 / `.DS_Store` / 缓存与虚拟环境。`~/.finance-runtime/replay/` 不进仓；`model_cutoffs.json` 与 `measurements/replay-*.{json,md}` 进仓。
- 解释器 `.venv-workbench/bin/python`。
- `intelligence/services/` 不得 import `intelligence/runtime/`；纯函数下沉方向只能是 scripts → eval / services，不能反向。
- 主库、旁路库、快照目录全程只读；`docs/learning/forecast-review-ledger/` 一个字节都不写。
- LLM 只走 `llm_refine.complete`，尊重 `_budget_rejection`；`--max-calls` 不得默认超过 200；先 `--dry-run`。
- 提示词、温度、模型在本单内一经确定不得为「让数字好看」而改；要改另单。
- 任何读数必须带 `pit_grade / memory_bucket / arm` 三标签；报表结构上不提供混合平均。
- 截止日只认官方来源，查不到写 `null`；估算值全程带 `estimated`。
- 台账号只用 `python3 scripts/claim_ledger_id.py claim` 取（本单不取）。
- 用户纠偏必落 correction（`python3 -m intelligence.cli record-correction ...`）。

## 7. 成立条件

- 树：`/Users/a77/fwp-wt-finance-agent-bp` @ `docs/finance-agent-bp`（本单在此起草，已合 `gitea/main@5c7fe2eb`）；实施基线取派单时的 `gitea/main`。
- 数字：主库只读查询于 2026-09-04 22:38（`max(trade_date)`=2026-09-02）；快照目录 `ls` 于同刻（33 manifest，缺 6 工作日）；`launchctl list` 见 `com.financeworkspace.pit-snapshot` 已加载。
- 行号读自上述树；实施时以 `rg` 重定位。
- 本文零运行时改动。

## 8. 可迁移知识点（教学备注）

- **回测的三种泄漏**：数据泄漏（未来行进了输入）、模型泄漏（模型见过答案）、程序员泄漏（看了结果再改提示词）。前两种本单各给一道门（PIT 分档 / 截止日分栏 + 匿名臂），第三种靠「提示词在本单内冻结、调优另单」——同一原则在机器学习里叫 train / validation / test 三分，在临床试验里叫预注册。
- **对照臂不是为了好看，是为了定上界。** 匿名臂拿不到名字和日期，能力仍在、记忆没了；两臂之差就是「记忆最多贡献了多少」。这叫消融（ablation），比任何一段「我们相信模型没背答案」的声明都硬。
- **两档 PIT 分开报**，不是数据不够的妥协，是把「这个数能信到什么程度」写进数据结构里。可信度是读数的一个维度，不是脚注。
- **复用聚合而不是重写**：车道 B 把假设整形成 checkpoints 记录再喂 `calibrate`，AI 的校准读数和用户的校准读数因此**同一把尺子**——这正是 §10.1 第②行说的「可以并排比」。
- **先立尺子再调参**：本单只出读数；任何看到读数后想改提示词的冲动，都是「程序员泄漏」的开始。
