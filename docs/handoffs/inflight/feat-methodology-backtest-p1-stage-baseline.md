# feat/methodology-backtest-p1-stage-baseline

**状态：已合入（2026-09-05）。** PR #591 → `gitea/main@87d731f7`，在 #589（→ `gitea/main@9bd0efd7`）之后合。
「下一步 1」预设的「本树先 merge 再开 PR」没有发生也不需要：#589 一合，#591 的 diff 自动从 16 文件缩到
**8 文件 +591/−68**（只剩第五刀），gitea 对合并后的 main 直接判 mergeable、无冲突，故按原分支尖 `10beb788` 合入。

合并后在**主 clone**（`/Users/a77/finance-workspace-private`，干净树）跑全量门禁：**7740P / 1F / 8skip / 1xfail，ruff 0，419 s**，
收据 `20260905T015418Z-87d731f7.json`。唯一那条红是存量、与本两刀零交集，判据三条都成立：①合并前 `8af84269` 检出
同一棵环境复现同样红；②同版代码在没有 `db/` 的 worktree（本树）里隔离重跑绿；③主 clone 的收据史 08-27 `a178595a`、
08-30 `52710ee8` 已经是同一条红。**这也暴露了门禁本身的盲区**：分支门禁都在没有 `db/` 的 worktree 里跑，而
`market_watch_pack` 只有在真库存在时才前置「## 指定日盘面组件包」，于是
`test_completed_stream_persists_human_readable_answer` 的等值断言在 worktree 里恒绿、在主 clone 里恒红——
「干净环境里验过了」在这里等于「没验到」。修它不属本工单。

树 `/Users/a77/fwp-wt-methodology-backtest-p1e`，**叠在第四刀分支尖 `feat/methodology-backtest-p1-refuted@8cc32c98`（PR #589，未合）之上**，
不是从 `gitea/main` 开的——理由见「决策与被否方案」第一条。#589 合入后在本树 `git merge gitea/main` 一次即可，diff 不变。
设计稿 `2026-09-04-methodology-backtest-structured-history-design.md` §3.2「同 universe」延伸；接手单 D
`2026-09-05-resume-methodology-backtest-p1-fourth-cut-closeout.md` §5 步骤 9；上一刀交接 `feat-methodology-backtest-p1-refuted.md`。
解释器 `.venv-workbench/bin/python`。

## 这个分支做什么
P1 第五刀，**加法、不改既有运行时行为、规则级读数逐位不变**。第四刀把事件按大盘阶段拆了桶但只给 n / k / p，因为 p0 是整体的、
「这个阶段这招不灵」只是描述；这一刀给每个阶段桶**自己的基准率**，让它升为四态。

1. **阶段基准率**（`compiler.baseline_by_stage_for`）：与规则声明的 `baseline.kind` 同 universe、同窗口、同 success 定义，
   多一个按当日 `market_stage` 的 LEFT JOIN + GROUP BY；两种 kind（all_days / event_days）都支持；大盘标签的
   entity_type / entity_id / label 全走绑定参数，SQL 文本里零常量。NULL 阶段归 `(无大盘阶段)` 桶，命名在 Python 侧。
2. **阶段级四态**（`stats.stage_readouts`）：每桶用现成的 `readout()` → p / p0 / lift / Wilson / 前后半段 / p 值 / 四态，
   **同一套四态定义，不另造**；n < `min_n` 一律 `insufficient_n`。一条规则的 m 个阶段当一个族做 **Benjamini–Hochberg**
   （`insufficient_n` 不进族也不被改写），BH 没拒绝的 supported / refuted 降为 not_distinguishable。收据每桶带
   `verdict_single`（单次）与 `verdict`（BH 后）、`adjusted_p`、`rejected`。
3. **第三列对照** `baseline_stage_matched`（kind `same_stage_days`，`stats.stage_matched_p0`）：p0 = Σ n_stage·p0_stage / N，
   即「每个事件拿它当天所处阶段的基准率来比，整体应命中多少」；形状照 `baseline_alt`，只对照不定结论，
   回答「控制住大盘阶段后规则还有没有提升」。
4. 收据 md 阶段表加 p0（阶段）/ lift / Wilson / adj p / 结论；`report --refuted` 加 p0（阶段）/ 阶段结论两列（老条目无字段显示 —）；
   CLI `run / scan` 打印只报有结论的阶段桶；`run_rule / scan_rules / execute_compiled` 透传 `q`（默认 0.05）；
   收据 `sql.baseline_by_stage` 留查询原文。

## 真库读数（旁路库 v2 / 2026-09-02，只读 `--no-write`；`393fe9ee`）
四条种子规则**规则级读数与 #585 / #589 逐位相同**（均 not_distinguishable；`baseline_alt` 也不变）。阶段级换成各自基准率后：

| 规则 | 第四刀的「拉高 / 拖后腿」读数 | 换成阶段自身基准率后 | 阶段级四态（规则内 BH） |
|---|---|---|---|
| diff_ratio_turn_up_5d | 主升阶段 71.7% ↑ / 顶部横盘 22.1% ↓ / 下跌阶段 36.8% ↓ | 主升阶段 p0 **74.3%** → lift −2.5%；顶部横盘 p0 **21.2%** → lift +0.8%；下跌阶段 p0 42.1% → lift −5.3% | **下跌阶段 n=2,291 → `refuted`**（adj p ≈ 0，两半都低于 p0）；主升 / 主升阶段 / 反弹 adj p 0.040 但方向为负、未过四态；探底 n=536 +14.8% 单次 p≈0 但前后半段不稳 → not_distinguishable |
| dual_red_streak3_continuation | 主升阶段 80.3% / 主升 42.3% | 主升阶段 p0 74.3% → +6.1%（p 0.31）；主升 p0 64.9% → **−22.6%**（adj p 0.045，n=26 只到 min_n 边上） | 全 not_distinguishable；**stage_matched p0 = 71.4%，lift −3.2%**——+10.1% 的整体 lift 在阶段配对下为负，与事件日基准（−1.0%）同向 |
| first_board_new_high_1y_5d | 主升阶段 55.3% ↑ / 下跌阶段 33.7% ↓ | 主升阶段 p0 52.2% → +3.1%；下跌阶段 p0 35.2% → −1.5%（「三次输两次」是那段时期强势股本来就输两次） | **顶部横盘（短写法）n=182 57.7% vs 42.7% → `supported`**（adj p 0.0008）；同名长写法「顶部横盘阶段」n=1,354 是 −1.7%——只在一个时期成立 |
| limit_heat_rank_jump_3d | 主升阶段 72.3% ↑ / 顶部横盘 39.8% ↓ | 主升阶段 p0 70.0% → +2.4%；顶部横盘 p0 34.7% → +5.1%；下跌阶段 p0 47.7% → +5.4%（单次 p 0.0007） | 全 not_distinguishable（下跌阶段 adj p 0.008 但前后半段不稳） |

三句话：① 第四刀「拉高的阶段」表全是**时期效应**——主升期什么都涨七成，规则在里面反而略输；② 「顶部横盘 22.1%」不是规则失灵，
是那段万物皆跌；③ 全表唯一的证伪是「下跌期边际量转正 5 日仍跌得比同期更多」，唯一的支持是「某个顶部横盘期新高首板跑赢
15 个点」——两条都要等 `market_stage` 两套写法归一、或第二个同阶段时期出现后再看。
`(无大盘阶段)` 桶（日历前 8 日 NULL）p0 1.2%，与第四刀一致。主库 mtime `09-03 15:10:52`、1,798,320,128 B 不变；旁路库未写。

## 决策与被否方案
- **叠在 #589 之上开分支** / 否等 #589 合入再从 `gitea/main` 开（接手单原话） / 派单口令不含「合入」，#589 停在 PR 态；
  第五刀代码依赖第四刀的 `by_market_stage`，从 main 开根本编译不过；stacked 分支合入时 git 会认出同一批提交，diff 只剩本刀。
  代价：#589 若被要求改动，本树要 rebase 一次
- **阶段级四态复用 `readout()` 同一套定义（含前后半段稳定性）** / 否只比 Wilson 对 p0_stage / 一个系统里两种「supported」
  会让读者不知道哪个更硬；前后半段守门在真库上真起了作用（探底 +14.8%、下跌阶段 +5.4% 都被它拦下）
- **阶段族在规则内 BH，不并进规则级的族** / 否并成一个大族（4 规则 × 12 阶段 = 48） / 并进去会让规则级结论变严、改既有读数，
  违反「加法不改行为」；否不校正 / 12 个阶段不校正时「至少一个假显著」≈ 1 − 0.95¹² ≈ 46%，正是设计稿要防的
- **`same_stage_days` 只作第三列对照，不进 `BASELINE_KINDS` 白名单** / 否让规则可声明它为定结论的基准 / 声明成基准要动 rules
  白名单、编译分支、runner 的「另一种口径」选择逻辑，且阶段加权 p0 依赖事件的阶段分布（不是 universe 的固定量）——
  留给要它定结论的那一刀，先用对照列看它有没有信息量（有：双红三连 +10.1% → −3.2%）
- **阶段值仍按原文分桶不归一** / 沿第四刀决策；两套写法各成桶让「同名不同期」可见（顶部横盘 supported vs 顶部横盘阶段 −1.7%）
- **纯计算放 `stats.py`、SQL 放 `compiler.py`、runner 只接线** / 否全塞 runner / BH 降级路径在 mini 库里测不到
  （两个桶都 < min_n），纯函数才能构造「单次 supported 被 BH 降级」的夹具

## 已验证（本树）
- selftest 19 → **20/20**：新增「各阶段 p0 ≠ 整体 p0、n / baseline_n / baseline_k 之和守恒、n ≥ min_n 的阶段 supported 且过 BH、
  第三列 same_stage_days 亦 supported」（合成库五阶段 p0 0.427–0.620，整体 0.518，加权 0.522）
- pytest `test_methodology_backtest.py` 61 → **67** 绿；`test_experience_cards.py` 19 绿。新增：mini 库精确断言
  （主升阶段 12/14 → 6/7、下跌阶段 6/9 → 2/3、整体 18/23、加权 17/21、lift 7/8 − 17/21、Σbaseline_n=23）；
  独立 SQL 逐桶对账；BH 降级纯函数（15/20 单独 supported、加一个 12/20 后 adj p 0.083 降级；<min_n 不进族）；
  加权 p0；两种 kind 的阶段 SQL `?` 数 = 参数数、无 `'market'` 字面量、不认识的 kind 抛 ValueError；
  合成库阳性对照阶段级按 n 分成 supported / insufficient_n、翻转后 refuted / insufficient_n、证伪库条目与 report 带新列、老条目兼容
- **变异测试**：`stage_baseline_counts` 把各阶段计数换成整体计数（= 去掉阶段过滤）→ 3 条 pytest
  （精确断言 / 独立 SQL / 合成库）+ 1 项 selftest 变红，全部阶段 p0 塌成 0.518；已还原，`rg MUTANT` 为空
- ruff 0；pre-commit 10 道全过（layer-audit / unread-fields / path-literals / dataset-registration / tool-reachability 基线不变）
- 真库：上表；规则级四条与 #585 逐位相同
- 全量主门禁 `run_main_gate.sh` @ `41148217`（干净树 `dirty=False`）：**7729 passed / 0 failed / 15 skipped / 1 xfailed**，306 s，
  ruff 0；较 #589 收据 7723P 多 6 例 = 本刀新增测试，红集为空。收据 `~/.finance-runtime/test-receipts/20260904T183147Z-41148217.json`，
  `check_test_receipt.py --expect-revision` 退出码 0。**如实记录**：门禁期间 02:27–02:31 本机有另一 agent 的定向 pytest
  （9 条，含两条看门狗 / 超时时序测试）并行约 3 分钟（监视器 `pgrep` 每 10 s 一采），本刀门禁仍 0F——并行只会制造假红、
  不会制造假绿，绿收据成立；若对方那 9 条红了，先怀疑是撞上了本门禁。前端零改动，未跑 `pnpm build`
- 已 push 到 gitea，`gitea_pr.py conflict-check` 对 `gitea/main@094f67c9` 与对 #589 head 都 clean；
  PR #591 `http://127.0.0.1:3300/a77/finance-workspace-private/pulls/591`（head `94d774a1`），**未合 main、请先合 #589**。
  INDEX #21 行已直接在 main 回写两张 PR 的在途状态（`gitea/main@b603bea4`）

## 未验证 / 已知边界
- 阶段级结论**每个都只对应一个时期**（两套写法 = 两段时间），「支持 / 证伪」是「在那段时期内」的结论，不是「在那类阶段」的结论；
  要说后者得先归一写法（升 `LABEL_VERSION`，P0 决策未动）或等同类阶段再出现一次
- 规则内 BH 的 q 与 scan 的 `--q` 共用；`run` 单条没有 `--q` 旗标，用默认 0.05
- `same_stage_days` 加权 p0 的「n / k」列填的是各阶段基准率 n / k 之和（= 整体基准率的 n / k），p0 本身是加权值不是 k/n——
  md 里那一行不显示 k/n 以免误读
- 证伪库条目多了 `baseline_stage_matched` 与桶内新键，schema 版本仍 `methodology-backtest-refuted/v0`（加法、老读者不受影响）；
  真库证伪库仍为空（规则级无 refuted），阶段级 `refuted` 不落证伪库——证伪库只收规则级结论，阶段级只随收据进条目
- 经验卡统计门（`experience_cards.gate_promotion`）不读阶段级结论，沿第四刀「先记不改」

## 下一步
1. #589 合入后：本树 `git fetch gitea && git merge --no-edit gitea/main` → 全量门禁绿 → 开 PR、不合，等确认
2. `market_stage` 两套写法归一（升 `LABEL_VERSION` v3，老收据按版本判不可比）——归一后「顶部横盘 supported」与「顶部横盘阶段 −1.7%」
   会并成一桶，届时再看 first_board 在顶部横盘到底有没有超额
3. 若要让阶段配对基准定结论：`same_stage_days` 进 `BASELINE_KINDS`，编译分支 + runner「另一种口径」逻辑改成对照列列表
4. `lifecycle_stage` 仍卡人工标注集（#585 交接「下一步 2」）；渲染层硬门 P2

## 踩过的坑
- `pgrep -f 'python -m pytest'` 会匹配到**别的 agent 的 shell 命令行**（他们也在用 `ps | rg 'python -m pytest'` 查）——
  锚定到解释器路径：`pgrep -f '^(/[^ ]+/)?[Pp]ython[0-9.]* -m pytest'`；本机 09-05 01:30–02:10 至少三个 agent 在排队跑门禁
- pytest 的 `synthetic` 夹具是 120 日 / 12 板块的小库，五个阶段里有一个 n=18 < min_n；断言要按 n 分 supported / insufficient_n，
  别假设「阳性对照每个阶段都够样本」
- 新 worktree 没有 `db/`，真库要显式 `--labels-db /Users/a77/finance-workspace-private/db/history_labels.duckdb`（同 #585 坑）
