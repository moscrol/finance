# feat/methodology-backtest-p1-refuted

树 `/Users/a77/fwp-wt-methodology-backtest-p1d`，基座 `gitea/main`=`47a4fcde`（#585 已合入 + 回写后的 main，干净树）；
2026-09-05 收口时合入 `gitea/main@c6e702a6`（合并提交 `32251769`，无冲突；这 21 个提交零个碰本刀文件）。
设计稿 `2026-09-04-methodology-backtest-structured-history-design.md` §6「以下三条是 2026-09-04 BP v0.4 壁垒重构后补入的
产品约束」前两条；上一刀交接 `feat-methodology-backtest-p1-stock-labels.md`。解释器 `.venv-workbench/bin/python`。

## 这个分支做什么
P1 第四刀，**加法、不改既有运行时行为**。P1 剩余项里 `lifecycle_stage` 卡人工标注集、`news_event` 跨仓，这两条产品约束是
唯一不被外部输入卡住的；而且设计稿写「P0 的规则文件与收据格式要为它们留字段」，P0 的 `_TOP_KEYS` 里其实没有，补上。

1. **规则归属层**：`sharing ∈ {shared, private}` + `owner` **必填**（不给默认值——渲染层硬门是「缺任一字段即不渲染」，
   规则层若默认 shared，一条漏写的私有规则就会被当共享规则渲染出去）。shared → `owner=system`，来源写 `source_perspective`；
   private → `owner` = 用户 id。四条种子规则显式标 `shared / system / 来源`。`propose` 登记的候选默认 **private**、owner 取
   `--user / FORESIGHT_USER / default`（纠偏是某人的纠偏）；`--sharing shared` 时 owner 恒 system，传别的 owner 直接拒。
2. **按大盘阶段拆分**：runner 把已到期事件按事件日当日 `market_stage` 拆桶（n / k / p），进收据 `by_market_stage` 与 md 表。
   只是读数拆分，**不参与四态**：p0 是整个 universe 的，各阶段 p 与它比只能看方向。
3. **证伪库**：结论为 `refuted` 的收据另落一条精简条目 `methodology/refuted/<rule_id>@v<version>/<date>.json`
   （`schema_version: methodology-backtest-refuted/v0`，字段 rule_id / rule_version / sharing / owner / N / p / p0 / Wilson /
   by_market_stage / refuted_at / 收据路径），**进 git**；scan 模式以 BH 校正后的结论为准。`report --refuted` 按大盘阶段展开
   「这个阶段这招不灵」。台账地图新行。

## 真库读数（旁路库 v2 / 2026-09-02，只读；`e520e31e` 干净树，收据 `dirty=false`）
四条种子规则整体读数与 #585 逐位相同（四条均 `not_distinguishable`，证伪库为空）。新增的按阶段拆分才是这一刀的信息量：

| 规则 | 整体 p / p0 | 拉高的阶段 | 拖后腿的阶段 |
|---|---|---|---|
| dual_red_streak3_continuation | 68.2% / 58.0% | 主升阶段 n=61 **80.3%** | 主升 n=26 **42.3%**——同一「主升」两种写法是两个时期，68% 是 80% 与 42% 的混合；前后半段 81.8%/54.5% 早就在说这件事 |
| first_board_new_high_1y_5d | 47.8% / 47.0% | 主升阶段 n=463 55.3% / 主升 n=467 54.4% | 下跌阶段 n=169 **33.7%** / 下跌 n=125 **32.8%**——新高首板在下跌期三次里输两次 |
| diff_ratio_turn_up_5d | 54.1% / 55.1% | 主升阶段 n=1,805 71.7% | 顶部横盘 n=1,056 **22.1%**、下跌阶段 n=2,291 36.8%；`(无大盘阶段)` n=298 k=2（日历前 8 日 market_stage 为 NULL） |
| limit_heat_rank_jump_3d | 57.6% / 57.0% | 主升阶段 n=933 72.3% | 顶部横盘 n=211 39.8%、下跌 n=380 46.3% |

`market_stage` 的「XX阶段 / XX」两套写法按设计「直接投影」未归一（P0 决策），这里也按原文分桶——两套写法各自成桶，
而且它们对应不同时期，所以桶间差既是阶段差也是时期差。归一与否是另一个决策（见下）。

## 决策与被否方案
- `sharing` / `owner` 必填、无默认 / 否缺省 shared+system / 缺省会让漏写的私有规则「升格」成共享；代价是所有测试夹具与种子文件补两行
- 字段放顶层 `sharing` / `owner` / 否塞进已有 `scope` 对象 / 设计稿原文写的是「scope ∈ {shared, private}」，但 `scope` 已被
  `{entity_type, universe}` 占用；归属与适用范围是两个轴，顶层更清楚；收据顶层再放一份供渲染层硬门直接判
- 证伪库**进 git** / 否随收据 gitignore / 设计稿原话「证伪库是资产，不是副产物」；收据是本机可重建物，条目要跨机器、
  跨旁路库重建留下来。代价：以后 `run` 打出 refuted 会在树里多一个待提交文件——这正是要的效果
- scan 模式以 BH 校正后结论落库 / 否单次 refuted 就落 / 「一次跑多条规则总有一条在 95% 下显著」对证伪同样成立，
  没过校正的证伪不是证伪
- 阶段拆分只作读数、不给按阶段的四态 / 否每阶段各算一次 Wilson 对 p0 / p0 是整体基准，按阶段下结论需要按阶段的基准率
  （universe 里同阶段日子的 success 比例），是另一条查询与另一个字段，留下一刀
- 阶段值按原文分桶、不归一 / 否合并「主升阶段 / 主升」 / P0 已决定 market_stage 直接投影，归一要升 label_version 且影响所有
  用 market_stage 的规则；本单只读不改标签层
- `propose` 默认 private / 否默认 shared / 设计稿「私有 → 共享的升格必须过统计门 supported 且由人拍板」，登记入口不能替人拍板

## 已验证（本树）
- selftest 18 → **19/19**：前视夹具打出的 refuted 落条目，schema / 字段齐、五个阶段 n 之和 = N=288、Wilson 上界 < p0
- pytest `test_methodology_backtest.py` 48 → **61** 绿；`test_experience_cards.py` 19 绿。新增：归属白名单 8 组拒绝
  （缺 sharing / 非法值 / 缺 owner / shared 非 system / private 是 system / owner 含 SQL 味 / source_perspective 空或超长）、
  收据带归属与来源、mini 库阶段拆分精确到 {主升阶段: 6/5, 下跌阶段: 2/2}、证伪条目只收 refuted（supported 抛 ValueError）、
  坏文件 / 别的 schema 跳过、CLI run/scan 只在 refuted 时落条目且 `--no-write` 不落、scan 条目带 BH、`report --refuted`
  两种输出、`propose` 默认 private / shared 自动 system / shared+别的 owner 退出码 2、种子规则全 shared/system/有来源
- ruff 0；pre-commit 10 道全过（path-literals / unread-fields / layer-audit 基线不变）
- 真库 `scan` 四条：整体读数与 #585 逐位相同；`report --refuted` 输出「证伪库为空」；`methodology/refuted/` 未被创建。
  2026-09-05 合 main 后在 `57cb9b3d` 重跑一遍：四条 N / p / p0 / lift / Wilson 与上表逐位相同，按阶段拆分各桶 n / k 逐位相同，
  收据 JSON 与 09-04 那张只差 `generated_at` / `conditions` 两个键；主库 mtime `09-03 15:10:52`、1,798,320,128 B 不变，无 WAL；
  `layer_audit.py` ERROR 0 == 基线，`check_unread_fields.py` 无新增
- 全量主门禁 `run_main_gate.sh` @ `57cb9b3d`（合 `gitea/main@c6e702a6` 后 + 交接文档提交，干净树 `dirty=False`）：
  **7723 passed / 0 failed / 15 skipped / 1 xfailed**，323 s，ruff 0；较 #585 基线 7708P 多 15 例 = 本刀 13 条新测试 + main 侧
  两条（`test_consumption_registry` / `test_eval_launchd_wiring`），红集为空。收据
  `~/.finance-runtime/test-receipts/20260904T173537Z-57cb9b3d.json`，`check_test_receipt.py --expect-revision` 退出码 0
  （revision / 解释器 / 依赖指纹 / 干净树全部 ✓）。前端零改动，未跑 `pnpm build`

## 未验证 / 已知边界
- 证伪库目前是空的：四条种子规则没有一条被证伪，`report --refuted` 的真库输出只有一行「为空」；条目格式只在合成库的前视夹具上验过
- 阶段拆分没有按阶段的基准率，桶间 p 差里混着时期差（两套写法）；「这个阶段这招不灵」现在是描述性读数，不是结论
- `(无大盘阶段)` 桶：日历前 8 日 `fact_market_daily.market_stage` 为 NULL，事件落在那几天就进这个桶
- 渲染层合规硬门（仅登录可见 / 必带 N 与区间 / 实体粒度到板块题材 / 不进营销 / KOL 匿名化）本单没做，只把 `sharing / owner / N /
  Wilson` 放到了收据顶层供它判；`entity_type=stock` 的共享规则渲染禁令也要在那一层落
- 经验卡 `invalidated` 前置条件读的是 `latest_receipt` 的 verdict（#576），不读证伪库；两者此刻一致，但证伪库是跨机器留存的，
  将来若旁路库重建后收据目录为空而证伪库有条目，两处会不一致——届时该让统计门也认证伪库

## 下一步
1. 主门禁绿后开 PR、合入（加法，无运行时行为变化，无需切 8792）；合入后本文顶部回写
2. 按阶段的基准率（`baseline.kind = same_stage_days` 或作为第三列对照）——有了它「这个阶段这招不灵」才能从描述升为四态
3. `lifecycle_stage`：仍卡标注集，需用户给 30–50 条 `(题材, 日期, 阶段)`，见上一刀交接「下一步 2」
4. P2：渲染层硬门；`finance_query` 暴露 `methodology_verdicts`；Beta 后验对照列

## 踩过的坑
- **三个全量门禁并行 → 时序测试假红**。09-04 23:24–23:37 本机同时跑 `e520e31e`（本刀）、`bf7a8f4a`、`892a6ec2` 三个全量
  pytest（16 GB、swap 20/21 GB），本刀那张收据 `20260904T153125Z-e520e31e.json` 7719P/**2F**，红的是
  `test_conversation_orchestrator.py::test_ask_watchdog_returns_partial_and_suppresses_late_progress` 与
  `test_workbench_conversation_integration.py::test_skill_timeout_degrades_one_module_and_continues`——看门狗 / 超时类，与本刀
  diff 零交集。09-05 01:25 机器安静时把这两条**单独重跑 3 次：3/3 绿**（每次 ~75 s），随后干净时段全量 0F。归因「环境红」的判据
  是三件同时成立：隔离重跑绿 + 干净时段全量绿 + 失败用例与 diff 零交集；缺任一条都不能拿「负载」当结论。跑全量前先
  `pgrep -fl '[P]ython -m pytest'`（括号技巧防 pgrep 匹配到自己）确认本机没有别的 pytest
- **交接文档别 stash**。09-04 中断时交接文档在 `git stash -u` 里；stash 是仓级不是树级，多 worktree 共享一个 `.git`，在别的树
  `git stash list` 也看得见、也能 pop 错分支。宁可先提交一个 `docs(handoff)` 再走
- `build_rule_doc` 默认 private 后，测试里不传 owner 会被白名单拒（owner 必填）——这是设计好的行为，测试要显式给 `owner="tester"`
- 同日重跑覆盖同名条目：CLI 测试里先 `run` 再 `scan`，最后留下的条目 `test_mode=scan`，断言要按最后一次写
