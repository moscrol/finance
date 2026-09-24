# 2026-09-05 接手单 C：knowhow recipe 线——合 PR #588（round 2）→ round 3：赚钱效应四簇规则进生产（翻 `live`）、MA5 (a′) 交叉表、题材周期文档定位

可独立分发。执行方无需读聊天记录，本单自带现状核实、证据路径、步骤、验收与红线。
接的是 2026-09-04 深夜中断的 Cursor session（用户最后一句口令：「你来命名，没有异议。9.3和9.4的数据后面我会补跑」——上一轮 agent 据此完成了 round 2 并开出 PR #588，之后 Cursor 模型不可用中断；转录里没有 PR #588 之后的动作，下面「现状」全部以 git / Gitea / 收据 / 实验目录重新核实）。

> **派单口令（贴给新 agent）**：你是仓库 `/Users/a77/finance-workspace-private` 的执行 agent。读 `/Users/a77/fwp-wt-resume-specs-0905/docs/superpowers/specs/2026-09-05-resume-knowhow-recipes-round3.md` 全文并逐条执行；用户不在线，判断写进交接「决策与被否方案」；**合并 `main` 要用户一句话**（本口令含「合并」即视为确认 PR #588；round 3 新开的 PR 另行确认）。用户自留的两件事（Chrome 登录 fupanhui、补跑 09-03 / 09-04 数据）**不要替他做**。

## 1. 这条线是什么、停在哪

`market_feature_store/consumption_registry.yaml` 的 `recipes` 段登记「怎么联立数据、何时主动报」的 knowhow。三条 2026-09-04 从 `pending-grilling` 编译成 `note`（PR #586 已合）：`theme_logic_cycle` / `ma5_rotation_cycle` / `money_effect_clustering`。同日 PR #583（分档同步 `REVIEW_SYNC_PLAN=auto` 落进 plist 仓内源）也已合。交接：`docs/handoffs/inflight/feat-registry-knowhow-recipes.md`（主线）、`docs/handoffs/inflight/data-source-tiered-sync.md`（同步链路，含用户登录步骤）。

**round 2 已做完、PR 已开、门禁绿、等合并**：

| 项 | 值（2026-09-05 00:40 核实） |
|---|---|
| PR | [#588](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/588) `feat/knowhow-round2-naming-rules` @ `bf7a8f4a`（已 push；标题「knowhow round 2——赚钱效应四簇命名 + 规则草案回写；MA5 逐周期交替假设未获支持」） |
| 树 | `/Users/a77/fwp-wt-tiered-sync`（干净；这棵树历史上跑过 #578 / #583 / #586 / #588 四条分支，名字与内容早已不对应，用完可删） |
| 改动 | 只两个文件：`market_feature_store/consumption_registry.yaml`（+10/−4）、`docs/handoffs/inflight/feat-registry-knowhow-recipes.md`（+51）；零代码 |
| 门禁 | `~/.finance-runtime/test-receipts/20260904T153528Z-bf7a8f4a.json`：**7710P / 0F / 15S**，exit 0，`dirty=false` |
| 冲突 | `gitea_pr.py conflict-check --head feat/knowhow-round2-naming-rules --base gitea/main` → clean（基座 `ba0393d1`，落后 `gitea/main@c6e702a6` 14 个纯文档提交） |
| 记忆库 | `/Users/a77/agent-memory/20_projects/finance-workspace-private.md` 已有「knowhow round 2（PR #588 待确认）」一条——合入后把「待确认」改掉 |
| 实验产物（不入仓） | `~/.finance-runtime/experiments/money-effect-20260904/`：`money_effect_kmeans.py`（第一段：5 日 trailing 窗口 k-means++，SEED 固定可复现）、`money_effect_rules.py`（第二段：命名校验交叉表 + numpy 浅决策树 + 回放一致率 + 去抖切换统计）、三份 `*.md` 输出；`~/.finance-runtime/experiments/ma5-cycle-20260904/`：`ma5_cycle_cases.py` + `ma5_cycle_cases_2026-09-04.md` |

round 2 的结论（PR #588 正文与交接「Round 2」节，合入前以它们为准）：

- **赚钱效应四簇**（5 日 trailing 均值、k=4、281 个全维可用交易日 2025-01-07 ~ 2026-09-02，剔 `sh_deviation_pct`）命名为 **缩量普涨 / 主线引领 / 放量分化 / 巨量轮动**，经 簇×fupanhui `market_stage` 六段、簇×月份 两张交叉表校验（巨量轮动 = 2026-06/07 的 36 天、主升 0 天；主线引领 = 2025-01/02、主升 14 天、连板 7.1）。
- **规则草案 4 条决策表**（5 日均值、按序命中）：① 成交额₅ > 26196 亿 且 新高₅ ≤ 464 家 → 巨量轮动；② 成交额₅ > 22114 亿 → 放量分化；③ 第一题材涨停份额₅ > 29% 且 最高连板₅ > 6 → 主线引领；④ 其余 → 缩量普涨。与簇标签 in-sample 一致率 **81%**（depth-2 树 79%、depth-3 86% 但有脏叶）；2 日去抖后 277 窗口切换 29 → 21 次 ≈ 每 13 个交易日一次。**成交额阈值 ≈ 样本第 59 / 78 百分位，绝对亿元随市值漂，生产版要改滚动 250 日分位再重测。**
- **MA5 假设 (a)「领涨群体逐周期交替」不成立**（72 段 / 36 上升段）：两榜确是两群人（J(R,W) 中位 0.2；W 榜个头 25×、R 榜 4.5×），但每段换人（与上一同向段 J≈0），下一段无延续亦无反转，相邻上升段 R 榜个头大/小翻转率 34% < 随机 50% → 是多周期 regime 不是逐周期交替 → 新假设 **(a′)「领涨个头的大小是 regime 变量」**，待与四簇交叉。
- round 2 默认值已生效：k=4、去抖 2 日；MA5 Top N=20、Jaccard、先独立脚本；题材退潮 N=3、等权。

用户自留项（**不是本单的活**）：Chrome for Testing 登录 fupanhui.com（用户定「周六再登」，周一 18:30 首个 cheap 日之前即可；步骤在 `data-source-tiered-sync.md`「接手复核」）；补跑 09-03 / 09-04 两个交易日（用户说自己补）。库内 `fact_market_daily` 现 `max(trade_date)=2026-09-02`——**round 3 的样本外验证窗口要等这两天以及之后的数据进来，本单只把机制搭好**。

## 2. 目标（可验收）

1. PR #588 合入；主树 ff；两份交接顶部与记忆库回写「已合入」。
2. **round 3-A 赚钱效应进生产**：把 4 条决策表实现成仓内可测的 D 档纯派生模块（0 请求、只读主库），阈值**不再写死亿元**——改为对「过去 250 个交易日的 5 日均值」取分位（成交额两档 = 第 59 / 78 百分位、新高家数 = 与 464 对应的分位、第一题材份额 / 最高连板同理，分位数从 round 2 的绝对阈值反推一次并写进 `decisions`），每日重算；2 日去抖；输出「今日簇名 / 昨日簇名 / 是否切换 / 各轴当前值与阈值」。**先在 281 天回放上重测**：分位阈值版规则标签 vs 簇标签一致率、切换次数，与 81% / 21 次对照，写进 `decisions`；一致率掉到 < 70% 就停下写原因，不硬上。`proactive`（「状态切换日主动报，附切换方向与该簇历史上之后 5/10 日的事实走法」）接进现有的一个消费者（候选见 §4；只接一个，写清为什么选它）。`status: note → live`，`joins` 写实施路径。
3. **round 3-B MA5 (a′)**：实验脚本（不入仓）把 72 段的 R 榜「个头」（榜内中位成交额 / 全市场中位）与当日 / 段内主导簇做交叉表；测 `MA5_MIN_SWING` 敏感性（现有 2–3 天碎段 #53 / #56 / #61 / #71 是 zig-zag 阈值偏小的产物）。结论回写 `ma5_rotation_cycle.decisions / open`。**假设未成立前不建 `feature_` 表、不翻 live。**
4. **round 3-C 题材周期第一步**：只做「定位」——用 `rg --files` / frontmatter 精确命中在 KB 仓 `wiki/` 找题材周期类文档清单（原骨架写「知识库 36 篇文档」[未实测]），列出路径与一句话，写进 `theme_logic_cycle.joins` 或 `open`；**不读正文、不建题材级向量**（那是下一单）。
5. 交接 `feat-registry-knowhow-recipes.md` 加「Round 3」节；记忆库加一条；INDEX 不涉及（本线没有 INDEX 号）。

## 3. 非目标（写死认领）

- ❌ 替用户登录 fupanhui、替用户补跑 09-03 / 09-04、动 `REVIEW_SYNC_PLAN` / plist / launchd（同步链路这一轮不动；周六 18:30 那趟 sync 只会记「周末跳过」，看一眼 `logs/daily-full-review.out.log` 可以，不要手动触发）。
- ❌ 把聚类结果（簇标签）写进任何 `fact_` / `feature_` 表——registry 的两段式写死「生产只跑规则」；规则标签是否落表见 §5 步骤 3 的选型，默认不落表。
- ❌ 改 k、改窗口、重跑 k-means 换命名（用户已拍「你来命名，没有异议」）。
- ❌ 题材级向量、题材阶段判据回放（round 3-C 只定位文档）。
- ❌ MA5 案例表进夜跑 `features` 步。
- ❌ 归一 `market_stage` 两套写法。
- ❌ 碰方法论回测（#21 第四刀）、RAG 瘦身（#22）、BP 线（#23–#25）的任何文件。

## 4. 证据路径表（先读这些，禁止臆测）

| 文件 / 命令 | 看什么 |
|---|---|
| `git -C /Users/a77/fwp-wt-tiered-sync diff gitea/main...HEAD` | PR #588 全部改动（两个文件） |
| `docs/handoffs/inflight/feat-registry-knowhow-recipes.md`（分支上）「探索结论」「Round 2」「下一步」「踩过的坑」 | round 3 的输入；坑：从 worktree 起 `connect(read_only=True)` 会解析到 worktree 自己的 `db/`（不存在）→ 探索脚本显式 `MARKET_FEATURE_STORE_DB=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb`；venv 没有 sklearn，numpy 手写够用 |
| `market_feature_store/consumption_registry.yaml` `recipes` 段（`rg -n "^  - key:" ` 定位；`money_effect_clustering` 在 447 行附近，`ma5_rotation_cycle` 431，`theme_logic_cycle` 417） | `joins / proactive / status / decisions / open` 五个字段的写法；`shuanghong_scan`（`status: live`）是「阈值只有一份、棘轮测试守着」的范本 |
| `market_feature_store/consumption_registry.py` `RECIPE_STATUSES`、`:190–235` 校验与 `registry-check` 输出；`tests/test_consumption_registry.py` `test_recipe_status_matches_placeholder_state` | 翻 `live` 的机器判据：`status` ⇔ 占位文本一致、`proactive` 非空 |
| `~/.finance-runtime/experiments/money-effect-20260904/money_effect_kmeans.py`、`money_effect_rules.py` | 第一 / 二段实验代码：特征取法（`load_market_regime_vectors` + `standardize_vectors`，`DROP=("sh_deviation_pct",)`，5 日 trailing 均值，SEED）、决策表回放一致率与去抖统计的算法——生产模块**照它的口径**实现，回放用它对照 |
| `intelligence/services/market_regime_analogs.py` `FEATURES`（:46）、`load_market_regime_vectors`（:333）、`standardize_vectors`（:145） | D10 十维向量的唯一来源（`total_amount / advancers / limit_up / limit_down / sh_deviation_pct / sh_index_pct_chg / max_boards / double_red_theme_count / top1_theme_share / new_high_count`）；生产模块复用它取数，不另写 SQL |
| `market_feature_store/signals.py` `DOUBLE_RED_SQL` + `tests/test_theme_fermentation_semantics.py` 里守它的棘轮测试 | 「阈值单一真本源 + 测试守着别处不得抄数字」的写法，分位阈值同样只能有一份 |
| `market_feature_store/sync/sync_daily_full.py::_run_compute_features`、`market_feature_store/schema.sql` `feature_market_window`（:872） | D-derived 派生步在哪、若将来要落表长什么样（本单默认不落表） |
| `market_feature_store/reports/daily_review.py`、`intelligence/services/market_watch_pack.py`、`intelligence/services/market_timeseries.py::latest_double_red_snapshot_block_for_llm`、`intelligence/services/market_regime_analogs.py` 的 D10 辅助查询 | `proactive` 可接的消费者候选：盘后复盘报告 / 市场观察包 / LLM 上下文块 / D10 问答。选**一个**，标准：已经每日跑、已经读 `fact_market_daily`、有测试 |
| `scripts/detect_turning_points.py`、`market_feature_store/signals.py`（MA5 峰谷、`MA5_MIN_SWING`） | round 3-B 的切周期入口；`~/.finance-runtime/experiments/ma5-cycle-20260904/ma5_cycle_cases.py` 已经调通 |
| `docs/handoffs/inflight/data-source-tiered-sync.md` | 用户自留项的步骤（只读，不做） |
| KB 仓 `/Users/a77/knowledge-base-private/wiki/`：`rg --files wiki \| rg -i "周期\|cycle\|生命周期\|发酵\|退潮"`、`rg -l "^tags:.*题材" wiki/concepts` 之类 | round 3-C 定位清单；**禁止批量读正文**（AGENTS.md「低 Token 工作约束」） |
| `/Users/a77/agent-memory/20_projects/finance-workspace-private.md` `rg -n "knowhow"` | 记忆体例与待改的「待确认」 |

## 5. 步骤 + 验收

### 步骤

1. 开工三连 `cd /Users/a77/finance-workspace-private && git status --short && git branch --show-current && git worktree list`；主树不动手。
2. 合 #588（派单口令含「合并」）：`git fetch gitea --quiet && python3 scripts/gitea_pr.py conflict-check --head feat/knowhow-round2-naming-rules --base gitea/main`（clean）→ `python3 scripts/gitea_pr.py merge 588 --yes` → 主树 `git pull --ff-only gitea main` → `python3 -m market_feature_store.cli registry-check`（`pending-grilling: -`）→ 交接 `feat-registry-knowhow-recipes.md`「当前状态」加「PR #588 已合入（`gitea/main@<sha>`）」、记忆库那条「待确认」改「已合入」——小文档修补，直接主树 `main` pathspec 提交推送（#583 / #586 回写就是这么做的）。
3. round 3-A 新树：`git worktree add /Users/a77/fwp-wt-money-effect-regime -b feat/money-effect-regime-rules gitea/main`。**选型（写死，除非证据推翻）**：新模块 `market_feature_store/money_effect_regime.py`，纯函数 + 一个 CLI 子命令（`python3 -m market_feature_store.cli money-effect-regime [--as-of YYYY-MM-DD] [--json] [--replay-since 2025-01-07]`），输入用 `market_regime_analogs.load_market_regime_vectors`（同一 `con`，`read_only=True`），5 日 trailing 均值（只用当日及之前）、分位阈值（滚动 250 日、对每个轴各算、分位数常量集中在模块顶部一处且带「由 round 2 绝对阈值反推」注释）、4 条决策表按序命中、2 日去抖（连续 2 日落新簇才算切换）。**不落表**（理由：阈值仍在校准期、不加 schema；被弃：`feature_market_regime_daily` 派生表——等样本外验证过了再考虑）。`--replay-since` 输出 281 天回放：与簇标签一致率、切换次数、混淆矩阵（簇标签从 `money_effect_kmeans.py` 同 SEED 重出，脚本留实验目录）。
4. `proactive` 接入：从 §4 候选里选一个消费者加一段「赚钱效应状态」（今日簇 / 昨日簇 / 是否切换 / 各轴值 vs 阈值 / 该簇历史上之后 5 / 10 日大盘涨跌的事实分布——只列事实不给概率），切换日才输出「⚠ 切换」；不切换只一行。写清为什么选它。
5. 测试：`tests/test_money_effect_regime.py`——合成 `fact_market_daily` 小库精确断言四簇各一例、去抖（第 1 日新簇不切、第 2 日切）、分位阈值随窗口变化、`as_of` 之后的行不参与（无前视）；registry `status: live` 后 `test_consumption_registry.py` 仍绿；`registry-check` 通过。变异测试一条：把去抖天数 2 改 1 → 切换次数断言必须变红。
6. round 3-A 真库回放：`MARKET_FEATURE_STORE_DB=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb` 只读跑 `--replay-since 2025-01-07`，把一致率 / 切换次数 / 混淆矩阵写进 `money_effect_clustering.decisions`（带日期与 [探索] 标注）与交接；一致率 < 70% → 不翻 live，写原因停在 note。今日（`max(trade_date)`）的簇名与各轴读数也写进交接。
7. round 3-B：复制 `ma5_cycle_cases.py` 到 `~/.finance-runtime/experiments/ma5-cycle-20260905/`，加两件事：每段 R 榜个头 × 段内主导簇（用步骤 3 的模块算每日簇）交叉表；`MA5_MIN_SWING` 取 3 档重跑段数 / 段长中位 / 翻转率。结论回写 `ma5_rotation_cycle.decisions / open`；不进仓、不落表。
8. round 3-C：KB 仓只用 `rg --files` + frontmatter 精确命中列题材周期文档清单（路径 + 标题 + 一句话来自 frontmatter / 首行标题），写进 `theme_logic_cycle.joins`（替掉「36 篇 [未实测]」）；找不到就写「未定位到，清单为空」。
9. 提交（pathspec、每步一个）、`ruff check .`、定向测试、等无其他 pytest 后 `bash scripts/run_main_gate.sh`（收据 `<stamp>-<rev8>.json` + `check_test_receipt.py --expect-revision`）；push、`gitea_pr.py open`（标题含「knowhow round 3」）、**不合**。交接加「Round 3」节；记忆库加一条。

### 验收

- [ ] PR #588 已合；主树 == `gitea/main`；`registry-check` 通过；两处「待确认」已改。
- [ ] `python3 -m market_feature_store.cli money-effect-regime --json` 在真库上输出今日簇名、昨日簇名、`switched`、四轴当前值与当日分位阈值；全程只读（主库 mtime / 体积不变）。
- [ ] 281 天回放：一致率与切换次数写进 registry `decisions` 与交接，并与 round 2 的 81% / 21 次并排；混淆矩阵在交接。
- [ ] `status: live` 且 `joins` 含模块路径与 CLI；`test_consumption_registry.py` 绿；`registry-check` 无 pending。
- [ ] `proactive` 已接进一个消费者，其既有测试绿，新增一条「切换日出 ⚠、非切换日一行」的测试。
- [ ] 分位阈值只有一份定义；变异测试记录在交接。
- [ ] round 3-B 交叉表与敏感性三档读数在实验目录与 registry `decisions`；`feature_` 表未新增。
- [ ] round 3-C 清单在 `theme_logic_cycle.joins`（或明确写空）。
- [ ] 全量门禁 `counts.failed==0`、收据与分支尖一致、`check_test_receipt.py` 退出码 0；PR 已开未合。

## 6. 红线（抄 AGENTS.md，不新发明）

- 开工先 `git status --short && git branch --show-current && git worktree list`；主树只做 `--ff-only` 与小文档 pathspec 提交。
- 🚫 禁 `git add -A` / `git add .`；一律 `git commit -- <明确文件列表>`；不强推；**合并 `main` 等用户确认**。
- 🚫 禁提交 `*.duckdb` / 实验脚本与输出（留 `~/.finance-runtime/experiments/`）/ `.env*` / `.DS_Store`。
- 解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；主库全程 `read_only=True`；不装新依赖（没有 sklearn 就 numpy 手写）。
- 门禁纪律：任何 pytest 前先确认本机无其他 pytest（`ps -eo command | rg -c 'python -m pytest|Python -m pytest'`）；全量只在最后跑一次；不用 `-n auto`；不看 `latest.json`。
- 跑马策略纪律：这些是假设不是定律——实验台账记输入窗口 / 候选池 / 后验；单次观察不写成规则；一致率、切换次数都带成立条件（窗口、维度、样本区间）。
- 不动同步链路（plist / launchd / `run_review_sync.py`）；不替用户登录或补数。
- 用户纠偏必落 correction（`python3 -m intelligence.cli record-correction ...`）。

## 7. 成立条件

- 现状读于 2026-09-05 00:30–00:45（`gitea/main@c6e702a6`，库内 `max(trade_date)=2026-09-02`）。
- round 2 的 81% 是 in-sample 乐观值；round 3 分位版重测同样是 in-sample；真正的样本外要等 2026-09 起的新窗口（用户补完 09-03 / 09-04 后才连续）。
- 一致率 ≤ 0.22 的轮廓系数背景下，「簇」是软区域——规则一致率 70–85% 是预期区间，不要为追高一致率加轴加叶。

## 8. 最终回复给派单人（简明，中文）

PR #588 合入结果与 `gitea/main` SHA；round 3-A 分支 / PR URL / 尖 SHA、模块与 CLI 路径、分位阈值反推表、281 天回放一致率与切换次数（对照 81% / 21）、今日簇名、接入的消费者与理由、是否翻 live；round 3-B 交叉表主结论与敏感性三档；round 3-C 清单条数；变异测试结果；定向与全量门禁读数（收据路径、`check_test_receipt.py` 退出码）；交接与记忆回写提交号；未做与原因。

## 9. 可迁移知识点（教学备注）

- **状态类特征先窗口化再聚类 / 再判规则**：单日向量天天换簇（71%），5 日窗口才有持续性（10%）。用户活跃状态、服务健康状态的聚类同理——状态是多日性质，单日是噪声。
- **绝对阈值会随量纲漂**：2.2 万亿的成交额门槛在牛熊之间含义不同；改成滚动分位是把阈值定义在「相对当下的历史」上——监控告警里的动态基线（dynamic baseline）就是这个。代价是分位本身要有窗口（250 日）与最小样本，这两个数也要写进成立条件。
- **聚类找边界、规则守生产**：k-means 的簇不可测试、不可解释，只拿它当「这几条轴有区分力」的探针；生产只跑可解释规则并用回放一致率把两者钉在一起。轮廓 < 0.25 时更不能照抄簇边界。
- **假设不成立也是产出**：MA5 (a) 被 72 段数据否掉，换成 (a′)。把「不成立」连同样本与窗口写进 `decisions`，比删掉它值钱——下一个人不会再跑一遍。
