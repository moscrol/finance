# feat/historical-replay-engine（INDEX #25 历史重放引擎）

树 `/Users/a77/fwp-wt-replay-engine`，基座 `gitea/main`=`c6e702a6`（派单时）；2026-09-06 收尾时合入 `gitea/main@3f6a3ce5`
（合并提交 `08ac5232`，无冲突；第四刀 #589 / 第五刀 #591 已在里面）。工单
`docs/superpowers/specs/2026-09-04-historical-replay-engine-workorder.md`；设计稿 §10.2 第二 / 四条、§10.3 第 2 步。
解释器 `.venv-workbench/bin/python`。**PR #597** `http://127.0.0.1:3300/a77/finance-workspace-private/pulls/597`（`feat/historical-replay-engine → main`）。**未合 main，等用户确认。**

## 这个分支做什么

把仓内三块零件（`fidelity_replay` 冻结快照 / 双盲 `hypotheses[]` 格式 + `dual_blind_auto_verdict` 机判 /
`methodology_backtest` 编译器 + `history_outcomes` + `checkpoints.calibrate`）接成一条链：站 D0 → 两臂提示词 → LLM →
自动判分 → 分格读数 → 报表。**只量、只出收据，不改任何规则 / 卡 / 画像 / 提示词。**

1. `intelligence/eval/replay_engine.py`（入口层）+ `scripts/replay_engine.py`（`run / report / nodes`）：
   - `select_nodes`：复用 `select_pilot_dates`（月 × market_stage）但两档分开抽（`only_dates`）；`pit_grade=strict` 当且仅当
     manifest 存在、`validate_frozen_snapshot` 过、且引擎要读的表不在 `required_failures`；对账日期在 strict 档先占位；
     默认 `end` = 主库最后交易日往前 5 个交易日（T+5 可判）。
   - `build_replay_input`：strict 从 `.snapshot.json.gz` 取（再校 `compressed_sha256`），trade_date_only 走
     `build_input_snapshot(strict_updated_at=False)`；两档都追加 D0 当日 sector / theme / market 标签、规则视图（去 notes /
     provenance）、20 日历；`max_embedded_date > D0` 抛错不落盘。**strict 档标签表与车道 A 对照集只取 D0 可见实体**（见决策）。
   - `render_prompt` 两臂同模板：`anonymized` 把代码 / 名字 → `S001…` / `TH01…`、绝对日期 → `T-0…T-19`，数值与
     `market_stage` 文本保留；渲染后零绝对日期断言（fail closed）；`anon_map.json` 随节点落盘，判分前反解。
   - `validate_replay_answer`：字段名照抄双盲 `hypotheses[]`；只允许 `market / direction`；拒 `target` / 个股代码 /
     `evidence_as_of > D0` / `picks` 非空 / 未知实体 / `@h` 与 `horizon` 不一致 / market 抽不出数值条件。
   - 车道 A：`compile_rule` 以 `[D0, D0]` 编译取事件集（与 `execute_compiled` 第一句同一 SQL；它只回 12 行样例，所以
     引擎自己执行同一 `events` 查询取全集），微平均 P / R + 集合完全一致率，按 `pit_grade × arm × rule_id`。
   - 车道 B：direction 查 `history_outcomes`（`WINDOW_START_OFFSET=1`，`status != ok` / 无行 → unverifiable），market 用
     `market_actuals` + 条件口径；整形成 checkpoints / verdicts 直接调 `calibrate`（`CategoryStat` 不重写），格子
     `pit_grade × memory_bucket × arm × category × horizon`，N<10 只给 N，N≥10 给 Wilson 95%。
   - `memory_bucket` 按 `intelligence/eval/model_cutoffs.json` 分三桶，`pre_cutoff / unknown` 标 `memory_contaminated`，
     报表结构上不与 `post_cutoff` 相加；臂间差（named − anonymized）标 `memory_signal` = 记忆成分上界。
   - 对账段：同时有快照与真答卷的日期，台账文件复制到 run 目录子集再调 `dual_blind_forecast.aggregate`（台账目录一字不写）。
   - LLM 只走 `llm_refine.complete`，整个 run 包在 `call_ledger_scope(max_calls)`（默认 200，CLI 不允许超过），
     预算闸拒发即停不重试；temperature 0.2 / timeout 180 s 本单内冻结；失败率 >20%（≥10 次后）自动停。
   - market 类机判纯函数（`extract_conditions / eval_conditions / any_clause_true / all_t1_conditions_true / market_actuals`）
     从 `scripts/dual_blind_auto_verdict.py` 下沉到引擎，脚本 import 回去——单一实现。
2. `fidelity_replay.py`：`_pit_where / build_input_snapshot` 加 `strict_updated_at=True`（缺省产物逐字节不变，测试比
   `snapshot_sha256`）；`select_pilot_dates` 加 `only_dates`。
3. `intelligence/eval/model_cutoffs.json`：`grok-4.6` → 2026-02-01（xAI 官方模型页原文）；`glm-5.2` → `null`（docs.z.ai /
   docs.bigmodel.cn / HF 模型卡 / GitHub README 均未披露），note 写明。
4. 规则 schema 两加法（`rules.py / runner.py / receipts.py`，**在第四 / 五刀合入后做**）：`PROVENANCE_KINDS` 加 `discovered`
   （仓内无写入点，`propose` 仍只产 correction）；可选顶层 `windows{discovery, validation}`（`validation.start > discovery.end`，
   错误带路径 `windows.validation[0]`），`run_rule` 两窗各跑一次，返回 validation 的 `RunResult` 并把 discovery 挂在
   `.discovery`，收据加 `windows` 两块 + `verdict_discovery / verdict_validation`，顶层 `verdict == verdict_validation`；
   无 `windows` 的收据键集逐键不变。`_TOP_KEYS` 只追加 `windows`。
5. `scripts/replay_engine_selftest.py`（14 项，零凭证）、`intelligence/tests/test_replay_engine.py`（34 例）、
   `docs/learning/ledger-map.md` 新行、INDEX #25 行、本交接。

## PIT 现实（2026-09-05 01:36 在实施基线上只读重出，主库 max(trade_date)=2026-09-02，413 个交易日）

| 表 | 严格口径 `updated_at < trade_date + 1 day`（`fidelity_replay._pit_where` 的纪律） | 宽口径 `updated_at::DATE <= trade_date + 1`（工单 §1 的数字） |
|---|---|---|
| `fact_market_daily` | **13 / 413** 日，最早 2026-08-17 | 17 / 413，最早 08-11 |
| `fact_sector_daily_generation` | 806 / 107,097 行（只 2 个交易日），最早 08-25 | 1,839 行，最早 07-24 |
| `fact_theme_limit_heat_daily` | 7,222 / 46,877 行（45 日），最早 06-03 | 10,039 行，最早 06-02 |

数据没变，是口径差；工单写的是宽口径。`fact_market_daily.updated_at` 最小值 2026-08-12 20:22（整表那天重写过）。

快照：33 份 manifest，2026-07-10 → 09-02，同区间 39 个交易日缺 6 份（07-21、07-28、08-04、08-06、08-25、08-31）。**但 33 份
里只有 27 份能当 strict 输入**：07-10（manifest payload checksum mismatch）、07-15 / 07-24（wiki input material link mismatch）
三份过不了 `validate_frozen_snapshot`；07-31 / 08-13 / 08-14 三份 checksum 过但 `required_failures` 含全部基线表（当晚捕获到的是
空表）。33 份全部 `replay_eligible=false`（08-17 起只差 `fact_sw_l1_daily`）。`python scripts/pit_snapshot_inventory.py validate`
对前三份会报同样的错——引擎复用的就是那个函数。

另一条实施中才看清的 PIT 现实：**旁路库是从当前主库重建的，不是 PIT。** 2026-07-27 `dim_sector` 从 224 个板块扩到 630 个
并回填了 07-10 → 07-24 的历史行（`updated_at` 07-25 → 08-25），07-27 起 published 名单又变成 403 个。于是 07-22 的
`history_labels` 有 630 个板块实体，而当晚快照只有 224 个——多出来的 406 个在 D0 根本不存在（其中含后来才建的概念板块，
存在本身就是未来信息）。同时 224 个旧板块的价格序列在 07-24 之后断了，所以 07-13 → 07-24 strict 节点的 direction 假设几乎
全部 `outcome status=missing → unverifiable`（真跑里 07-20 / 22 / 23 / 24 共 23 条）。

## 真跑（glm-5.2，`.env.workbench` 的 `LLM_API_KEY` 通用出口 `custom` provider）

- 起止：pilot 2026-09-04 18:32:53Z → 18:33:41Z（1 节点 07-22，4 次调用，只验格式）；主跑 **2026-09-04 18:42:03Z →
  19:18:43Z**（本地 09-05 02:42 → 03:18），`run_id = replay-20260904T184203Z-514d2369`，树 `514d2369` dirty=false。
  真跑前 pytest 解释器进程数 = 0（等到 02:32 才清零）。
- 预算：dry-run 估算 160 次 / 1,471,412 输入 token（estimated，len/1.6）；实跑 **160 次调用 / 0 失败 / 9 份答卷无效**；
  加 pilot 合计 **164 / 200**。未触预算闸，未重试，未补跑。
- 产物：`~/.finance-runtime/replay/replay-20260904T184203Z-514d2369/`（`run.json`、40 个节点目录各有
  `input.json / anon_map.json / prompt.{A,B}.{named,anonymized}.txt / answer.named.json / answer.anonymized.json / verdict.json`、
  `ledger-subset/`、`report.{json,md}`）；dry-run 与 pilot 目录同级。
- 9 份无效答卷：车道 B 7 份（6 份 market claim 抽不出数值条件——上证收盘 / 上证涨跌% / 「涨停家数 > 跌停家数」/「不超过」
  这些不在 `METRIC_ALIASES` 白名单里；1 份缺 `falsify_when`），车道 A 2 份（named 臂漏掉 `limit_heat_rank_jump_3d` 键，
  按「预测为空」计入召回率）。整份拒绝是刻意的：提示词已声明「不满足会被整条拒绝」，机判白名单是尺子的一部分。
- 报表两版都在 git：`ba4a7752` 是 40 节点原样（strict 20 含 3 份空快照）；`934552ca` 是 `report --run-dir` 按收紧后的分档
  重出（strict 17，3 份空快照整节点剔除，其 12 次调用记在 `calls_in_run_dir=160`），文件名沿用真跑本地日 `replay-2026-09-05`。

### 读数（`intelligence/eval/measurements/replay-2026-09-05.md`，重出版）

车道 A（无泄漏；微平均精确率 / 召回率 / 集合完全一致率）：

| pit_grade | arm | diff_ratio_turn_up_5d | limit_heat_rank_jump_3d | dual_red_streak3_continuation |
|---|---|---|---|---|
| strict (17) | named | 95.4% / 94.1% / 64.7% | 86.9% / 76.3% / 35.3% | 零事件（两臂空集相等，100%） |
| strict (17) | anonymized | 99.6% / 87.3% / 58.8% | 99.7% / 97.0% / 41.2% | 同上 |
| trade_date_only (20) | named | 99.9% / 97.8% / 25.0% | 99.5% / 95.9% / 45.0% | 同上 |
| trade_date_only (20) | anonymized | 99.7% / 98.4% / 25.0% | 100.0% / 98.7% / 70.0% | 同上 |

读法：精确率普遍 ≥95%（模型很少把不触发的实体报成触发），召回率 76%–99%；完全一致率低是因为 20 个节点里漏一个实体就算
不一致（期望实体 1,281 / 799 / 1,633 / 679 个）。匿名臂车道 A 不比命名臂差，说明规则复现靠的是读表，不靠名字。

车道 B（`memory_bucket` 全 `unknown` → 全部 memory_contaminated；N≥10 才有率；终态 498 条 / unverifiable 23 条）：

| pit_grade | arm | direction T+3 | direction T+5 | market T+1 | market T+3 | market T+5 |
|---|---|---|---|---|---|---|
| strict | named | 46.9% N=32 | 33.3% N=30 | 70.8% N=24 | 58.3% N=18 | 84.4% N=16 |
| strict | anonymized | 41.9% N=31 | 59.3% N=27 | 62.0% N=25 | 61.1% N=18 | 86.7% N=15 |
| trade_date_only | named | 56.4% N=39 | 53.7% N=41 | 56.2% N=24 | 79.0% N=19 | 86.7% N=15 |
| trade_date_only | anonymized | 38.2% N=34 | 45.0% N=40 | 52.6% N=19 | 64.7% N=17 | 78.6% N=14 |

（命中率为分制：partial 算 0.5；Wilson 区间见报表。）臂间差（同档同桶合并类别 × 窗口）：**strict −4.0%**（named 55.0% N=120
vs anonymized 59.1% N=116）、**trade_date_only +11.2%**（62.0% N=138 vs 50.8% N=124）。trade_date_only 的 +11.2% 是记忆成分
的上界（那 20 个节点横跨 2024-12 → 2026-08，模型很可能见过），strict 档的 −4% 说明 2026-07/08 这两个月的行情没有给命名臂带来
优势——但 glm-5.2 截止日未知，两档都不能从 `unknown` 桶往 `post_cutoff` 解读。

`memory_bucket` 分布（每条假设一票）：strict unknown named 131 / anonymized 126；trade_date_only unknown named 139 /
anonymized 125；`post_cutoff` / `pre_cutoff` 均为 0。截止日表：`glm-5.2` null（官方未披露，四处来源列在 note）、`grok-4.6`
2026-02-01（https://docs.x.ai/docs/models 原文），本次真跑只用了 glm-5.2。

对账（同期 6 日 07-13/14/16/17/20/22，market 类 T+1，命中率 = hit/(hit+miss+partial)）：真人合计 40.0%（N=5：claude 2/2、
codex 0/3）vs 重放 named 62.5%（N=8）/ anonymized 44.4%（N=9），差 +22.5 / +4.4 个百分点。**N 都很小，差值只记录不做结论。**
07-10 / 07-15 / 07-24 不在 strict 集（快照校验不过），09-01 / 09-02 超出 judgeable end。

## 决策与被否方案

- strict 档标签表只取 D0 可见实体（快照里出现过的代码）/ 否照工单字面「全部标签」/ 旁路库从当前主库重建，07-22 会给出 406 个
  D0 不存在的板块（含后建概念）——存在与名字都是未来信息；「后补数据不冒充 PIT」优先于字面。差额写进 `pit_caveats`
  与报表节点表；车道 A 对照集同样过滤，否则模型看不到的实体会被算成漏召回。
- 空快照不算 strict（`required_failures ∩ {fact_market_daily, fact_sector_daily} ≠ ∅` → trade_date_only）/ 否维持工单定义
  「manifest 存在 + checksum 过」/ `pit-snapshot-inventory.md` 把这类快照定义为诊断产物；按旧定义 07-31 / 08-13 / 08-14
  的标签表为空、车道 A 在空集上「完全一致」、车道 B 在没有行情表的提示词上作答。真跑之后才看清，所以两版报表都留在 git，
  重出版整节点剔除并把花掉的 12 次调用记在 `calls_in_run_dir`。不要求 `replay_eligible=true`——33 份全 false（都缺
  `fact_sw_l1_daily`），那会让 strict 档空掉。
- 对账日期只在 strict 档占位 / 否两档都占 / 掉到 trade_date_only 的对账日没有对账价值，白占抽样名额。
- 默认 `end` = 最后交易日往前 5 个交易日 / 否跑到最后一天 / 再往后 T+5 一定 pending，白花调用；`--end` 可显式覆盖。
- 无效答卷整份拒绝、不重试 / 否只丢掉坏的那条或补一次调用 / 工单红线「不要循环重试」；机判白名单是尺子的一部分，
  放宽白名单就是为让数字好看改尺子。
- 车道 A 一次调用回三条规则 / 否每规则一次 / 160 次预算是按「节点 × 臂 × 车道」算的；三条规则共用同一张标签表。
- 一次一致率用微平均 P/R + 集合完全一致率 / 否宏平均 / 期望集为空的节点宏平均 precision/recall 无定义；微平均把它们自然
  归零，完全一致率单独报。
- 前视对照的「基准」= 同夹具 50% 硬币 stub 的命中率，对照假设用 `fwd_return@1` 并只挑噪声日实体 / 否用 @5 / 相邻 5 日窗
  重叠 4/5，前移后命中率只掉到 ~0.67，那是重叠不是没泄漏；@1 前移后读到的 D0+2 与背的 D0+1 独立才回到基准（实测 0.49 vs
  0.45）。
- 报表文件名用真跑开始的本地日（`run_local_date`）/ 否重出那天的日期 / 同一 run 重出不该产生第二个日期的文件。
- `glm-5.2` 截止日填 null / 否用二手转述或按发布日推 / 工单红线只认官方文档或模型卡。

## 已验证（本树，收据带路径）

- 全量门禁 `bash scripts/run_main_gate.sh` @ `934552ca` dirty=0：ruff 0，**pytest 7769 passed / 0 failed / 0 error /
  15 skipped / 1 xfailed（6:33）**，收据 `~/.finance-runtime/test-receipts/20260906T030501Z-934552ca.json`，
  `check_test_receipt.py --expect-revision $(git rev-parse HEAD)` 退出码 0（✓ 可采信）。跑前 pytest 解释器进程数 0。
- 定向：`test_replay_engine.py`（34）+ `test_methodology_backtest.py` + `test_fidelity_replay.py`（+1）+ `test_dual_blind_forecast.py`
  + `test_checkpoints.py` = **173 passed**；合并 main 后先跑过一遍 167 passed（schema 加法前）。
- `scripts/replay_engine_selftest.py` **14/14 PASS**（车道 A 阳性 exact=1.0、阴性最高 exact 0.325；车道 B 背答案 1.0、硬币 0.445；
  记忆对照 named 1.0 vs anonymized 0.503 → gap 0.50；前视对照前移后 0.49，在基准 ±0.1 内）；`methodology_backtest_selftest.py` 20/20。
- 变异测试（最终代码 `934552ca` 上复跑）：① `outcomes.WINDOW_START_OFFSET=0` → `test_eval_date_uses_next_trading_day` /
  `test_judge_direction_reads_window_after_d0` / `test_selftest_passes_end_to_end` **3 红**，恢复后 34 绿；② `build_anon_map` 漏 dates
  映射 → `test_two_arms_differ_only_at_mapped_positions[A/B]` / `test_rebuild_report_regrades_and_excludes_changed_nodes` /
  `test_selftest_passes_end_to_end` **4 红**，selftest 在 `render_prompt` 处 fail-closed（`anonymized prompt leaks absolute dates`）
  退出码 1，恢复后 34 绿 + 14/14。
- `scripts/layer_audit.py` ERROR 0（== 基线）；`scripts/check_unread_fields.py` 无新增（39 文件 / 96 字段，基线 40 / 100）；
  pre-commit 全部钩子每次提交都过（path-literals 曾拦下写死的快照目录，改为 `PIT_SNAPSHOT_DIR` / `Path.home()`）。
- 真跑期间 80 份匿名臂提示词 `rg -c '20[0-9]{2}-[01][0-9]-[0-3][0-9]'` 全部为 0；两臂提示词经 `anon_map` 替换后逐字相同（测试 + selftest）。
- 只读红线：`docs/learning/forecast-review-ledger/` 在 `git status` 里始终无改动；主库 33 张 `fact_*` 行数与 `max(updated_at)`
  跑前快照在 `~/.finance-runtime/replay/main-db-invariant-before.json`，旁路库 `history_build_meta` 在 `labels-meta-before.json`
  （labels 1,456,438 行 / outcomes 1,657,368 行，v2，2026-09-04 14:21）；报表成立条件块里的 `source_max_trade_date=2026-09-02`
  与 `label_version` 与之一致。
- `git status` 台账目录：无改动（对账用的是 run 目录里的 `ledger-subset/` 副本）。

## 未验证 / 已知边界

- **memory_bucket 分栏没有真正分开**：glm-5.2 官方无截止日 → 全 `unknown`。工单验收「给定 cutoff → D0 前后分两桶」只在
  单测与 grok-4.6 表项上成立，真跑没有 `post_cutoff` 一格。换 grok-4.6 跑一次能立起这一栏，但要另单（换模型 = 改尺子）。
- **strict 档的严格性只覆盖行情表**：标签值来自旁路库，两档同源、不可证明 PIT（`fact_sector_daily_generation` 严格口径只有
  806 行能证明）。报表 `pit_caveat` 已写明。
- 07-13 → 07-24 strict 节点的 direction 假设基本 unverifiable（旧板块序列 07-24 断档），所以 strict × direction 格子实际来自
  07-27 之后的 12 个节点。
- direction 只能用 `@3 / @5`：旁路库 outcomes 只建 [3, 5, 7, 10]，`T+1` direction 会 unverifiable；提示词已引导到 3 / 5。
- 对账段 N 极小（真人 5 条、重放 8 / 9 条）；台账里只有 07-10 → 07-17 有 verdict 文件。
- market 机判白名单只认涨家数 / 涨停 / 跌停 / 成交额 / 量比 / 历史新高，模型爱写「上证收盘」，6 份答卷因此整份无效——这是
  尺子的已知窄度，不是引擎 bug；要放宽须另单（会同时改双盲脚本的口径）。
- `dual_red_streak3_continuation` 在 40 个节点上零事件（要求 streak≥3 且主升 / 反弹阶段），车道 A 对它只证明了「两臂都没乱报」。
- 工单验收「两档各 ≥1 个 market_stage 类别以上」满足（strict 5 类、trade_date_only 13 类），但 strict 档只覆盖 2026-07/08。
- 没有跑前端命令（前端零改动）。
- 3 份空快照与 3 份校验不过的快照为什么会这样，本单只记录不修（`pit_snapshot_inventory.py` 是非目标）。

## 下一步

1. 用户确认后合 PR；合入后删分支；INDEX #25 行补 PR 号已写。
2. 想立起 `memory_bucket` 分栏：另开工单用 `grok-4.6`（截止日 2026-02-01 已录）跑同一节点集——2025 年节点会落 `pre_cutoff`、
   2026-02 以后落 `post_cutoff`，两栏并排才有「记忆 vs 能力」的读数。
3. 快照侧：查 07-31 / 08-13 / 08-14 为何捕获到空表、07-15 / 07-24 的 wiki delta 链为何断（launchd 作业侧，另单）。
4. 旁路库若要做 PIT 版（按快照重建标签）是另一条路，先看 P2 需不需要。

## 踩过的坑

- **同一棵树有别的 agent 在动**（2026-09-06 10:31–10:33）：我 `git merge gitea/main` 期间，`gitea/main` 又前进了一格且树上多出
  一个不是我做的合并提交和一个提交 `2d673aa0`（把两份报表提交了）；我按「重做一次干净合并」`reset --hard 514d2369` 时把它连
  同报表文件一起退掉了——`reset --hard` 会删掉**已被别人提交**的文件。靠 reflog 找回（`git checkout 2d673aa0 -- <两文件>`，
  与 run 目录 `report.*` 逐字节相同），重提为 `ba4a7752`。教训：reset 之前先 `git reflog -3` 看有没有不是自己的动作。
- `ps -eo command | rg -c 'python -m pytest'` 会把 rg 自己和 zsh 包装计进去，基线不是 0；要数解释器进程用
  `rg -c '^\S*[Pp]ython\S* -m pytest'`。
- `nohup … &` 放在子 shell 里会随工具调用结束被杀（真跑第一次启动 5 秒后就没了、日志为空）；改为前台命令交给工具后台化。
- Python 输出重定向到文件是块缓冲，长跑要 `python -u` 才能看进度。
- zsh 双引号里的反引号是命令替换，提交信息含反引号要走 `-F 文件`。
- `git commit` 的 pre-commit `path-literals` 钩子扫全树含未跟踪文件——写死 `/Users/a77/fidelity-replay/...` 会拦住别的提交。
- `dual_blind_auto_verdict.py` 的纯函数下沉到 eval 层后，脚本本身要 `sys.path` 里有仓根（它已经有），且引擎里的重放 /
  对账不能在 import 期加载脚本模块（按文件 `importlib` 延迟加载，避免循环）。
- 冻结快照早期（07-22）`fact_sector_daily.strength` 全空，按 strength 排序会退回源表的文本序（`100, 1012, 103…`），
  加了 amount 作次序键。

## 当前状态（2026-09-06）

分支 `feat/historical-replay-engine`，提交序列：`d730a29c`（fidelity_replay 两参数）→ `48e49305`（引擎 + CLI + 下沉）→
`3116d650`（截止日表）→ `950cb20f`（selftest）→ `514d2369`（测试）→ `08ac5232`（合 main@3f6a3ce5）→ `ba4a7752`（报表原样）→
`ac2082ab`（schema 两加法）→ `7bc358e0`（空快照不算 strict + report 重判）→ `934552ca`（报表重出）→ 本文 + ledger-map + INDEX。
`2dac32e0`（文档三件）→ 本提交（补 PR 号）。PR #597 已开（`gitea_pr.py` 在主树运行，conflict-check clean）。**不合 main，等用户确认。**
