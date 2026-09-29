# 2026-09-29 夜跑接入当晚报价封存 + 桥缺口两源补行（Claude Code 云端会话，经 exec 隧道操作 Mac）

写完不改；更正走 `record-correction`。分支 `feat/nightly-bridge-gapfill-0929`（Gitea）。

## 背景

- 桥 `bridge-stock-daily` 对复牌 / 送转 / 新股首日按合同拒算、不报错，覆盖率分母也不含它们，所以每天 3~10 只**静默缺行**。
  09-29 夜跑丢了 6 只，其中有广汽集团。见 `2026-09-29-evening-qa.md` §10。
- 19:20 用户接受两源仲裁方案（`docs/superpowers/specs/2026-09-29-bridge-silent-gap-decision-request.md`），
  19:54 人工候选库补 11 行后发布（`2026-09-29-bridge-gapfill-publish.md`）。**夜跑还没接**，明天起照样缺行。
- 同一份记录的待办 2：封存报价的范围不含当日复牌股。原因是 15:00 手工采集时，同花顺表的最新一日还是昨天。
- 用户在本会话说「推进」，授权范围是开发、演练和开 PR。合入 main、切夜跑代码根要另行逐字确认。

## 做了什么（按发现顺序）

1. 复核 #975。发现 `backfill_bridge_gaps.py` 按「代码目录/db」判断生产库，而夜跑从冻结代码根（另一棵 worktree）执行，这样认不出真生产库。改用 `write_path.is_canonical_production`。
2. 读 `run_review_sync.main` 时发现：非关键步骤记 `fail`/`timeout` 会进**收尾重试**，而收尾重试在下游全部算完之后才跑。补行如果在那时成功，canonical 就与涨停统计、板块成分、特征对不上。因此三个可选步骤一律把失败降为 `skip`（`_never_fail`）。
3. 补进去的行如果没有合法名，`limit-stats-local` 会按 `InvalidStockName` 拒跑，整晚发布失败。于是在 `plan_gap_fill` 加名字闸：没有合法名就不补这一行，裁决记 `no-valid-name`。#975 原测试里 688808 的证据没带名，已补上名字。
4. 读 `capture_dated_quotes.load_universe`：它取 `fact_stock_daily` 和 `fact_stock_daily_hithink` 各自最新一日的代码。**不需要改采集件**，只要把采集放到夜跑里、同花顺日线入 staging 之后再跑，复牌股和新股首日自然在范围内。
5. 新增 `capture-dated-quotes`、`bridge-gap-fill` 两步，registry 同位对齐；补行脚本新增 `--eastmoney-fetch-dir`（逐只抓东财日 K，上游拒服务即停）和捕获审计；拒绝路径也落收据。

## 决策

| 决策 | 选了 | 否了 | 为什么 |
|---|---|---|---|
| 何时采报价 | 夜跑桥接后 | 15:00 定时任务；按停牌名单补范围 | 15:00 时同花顺表还停在昨天，正是 09-29 漏复牌股的原因；另开定时任务还要装、要监控；停牌名单没有可信来源 |
| 可选步骤失败 | 降为 skip | 记 fail；设为关键步骤 | fail 会在下游算完后重试插行，派生表对不上；关键步骤会让一次证据抓取失败拖垮整晚发布 |
| 无名行 | 不补 | 插 NULL；猜名 | NULL 会让 limit-stats 拒跑；合同 1 只接受封存报价和库内历史名 |
| 东财证据 | 尽力而为，拒服务即停 | 强制；完全不用 | 东财时好时坏，强制就会常败；新股首日需要两个外部来源，只有封存报价一个不够 |
| 分支形状 | 合并 #970、#975 后再加提交 | cherry-pick；建在 0e7f 上 | 用合并的话，两张 PR 先合后本 PR 的 diff 自动缩小；0e7f 落后 main 645 个提交，切到 main 基的代码根也能顺带消除分叉 |

## 验证

- 云端临时虚拟环境（依赖只有 duckdb 和 pytest，不是 `.venv-workbench`）：相关 5 个测试文件 63 条通过，ruff 通过。
  这只算定点读数。
- 变异自检 `scripts/mutation_check.py`：8 个变异全部被抓住（8/8 KILLED），跑完树与 HEAD 一致。
- **Mac 沙箱演练**（`~/.finance-runtime/reviews/nightly-gapfill-0929/`，生产库 APFS 克隆，生产只读）：
  - 在克隆里删掉 09-29 的 6 行补数，模拟桥刚丢完行的状态；
  - 用分支代码原样调用 `capture_dated_quotes_step` 和 `bridge_gap_fill_step`；
  - 采集 5558 只，审计通过，3 只复牌股全部在范围内；
  - 东财 6/6 抓到；6 个缺口全部 `two-source-agree`，补回后 09-29 为 5559/5559；
  - 和人工发布的行逐列比较：只有 300211.SZ 的名字不同。夜跑取的是封存报价名「亿通科技」，人工那次取的是库内历史名「*ST亿通」。
- 全量门禁：见 inflight 交接（写本文时还在跑）。

## 没验证

- 真实 18:30 launchd 环境下的整晚运行（staging 路径、环境变量、换库都没走过）。
- 恢复链 `recover_local_review` 回放历史日时，这一步会联网抓东财、按两源规则补行。行为与决策一致，但没实跑过。
- 东财拒服务、15:00 前运行这两条路径只有单元测试，没有现场验证。

## 后续

- **要用户确认**：合入 main；切夜跑代码根（新锁定 worktree、两个 plist、s7 缺省值、`check_daily_plan_local.py`、
  `tests/test_eval_launchd_wiring.py::SYNC_CODE_ROOT`，走 PR，不直推），然后 `launchctl` 重载。回滚锚是 `finance-sync-0e7f77025409`。
- 生产 09-29 的 300211.SZ 名：封存报价显示「亿通科技」，生产里是「*ST亿通」。要不要改、怎么改由用户决定（需要再走一次候选库发布）。
- 同日验收补一条规则：原始表代码减去 canonical 代码必须为空，或逐条列出原因（evening-qa §1）。本分支只在收据里列出，没有接进门禁。

## 不要做

- 不要把可选步骤改回 `fail`，理由见上面「可选步骤失败」那一行。
- 不要在 15:00 前或回放时强行采集：捕获只能描述采集当天，拿今天的报价冒充过去的名字和前收，就是「取最新」那条红线。
