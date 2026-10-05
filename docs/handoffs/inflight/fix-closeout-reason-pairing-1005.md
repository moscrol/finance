## 这个分支做什么

修 `scripts/worktree_closeout.py`：`--reason` 改 append、按位置配 `--tree`；条数配不上、dry-run 里 `--plan` 混 `--tree`/`--reason` 都退 5。PR https://github.com/moscrol/finance/pull/43 （未合，合入须用户确认）。

## 决策与被否方案

| 采用 | 未采用 | 理由 |
|---|---|---|
| 第 i 条配第 i 棵 | 自定义 Action 按相邻配 | 用户指定按位置；argparse 不记两种参数先后 |
| 一条理由用于全部，不论位置 | 一条夹在两棵之间也拒 | 用户规则「一条=全部」；残余形状写进 PR 待定 |
| 规则只在 `pair_reasons()`，`main` 里 `parser.error` 退 5 | `_load_items` 抛 ValueError | 会被报成「plan 读不了」，前缀错、无 usage |
| 拒 `--plan` 混 `--tree`/`--reason` | 保留合并 | 旧行为静默丢 `--reason`、静默合并两路点名 |

## 当前状态

代码、测试、lessons_learned、本交接均已提交推送，无未提交改动；提交列表与 CI 看 PR。

## 已验证

- 先红后绿：新测试打 `bd2c58b37` 为 5F/5P，改后 10P（明细在 PR 描述）。
- 变异 6 门（spec 在 `~/.finance-runtime/reviews/closeout-reason-pairing-1005/`）：首轮 M4「0 条理由不补空串」SURVIVED，已补 `test_tree_without_reason_is_sampled_and_blocked`。
- 提交时 13 道 pre-commit 过；终轮变异与本机门禁读数按最终 head 取，见 PR 评论。
- 同族：34 个含 `action="append"` 的非测试文件全看过，只此一处。

## 未验证 / 已知边界

- `--tree A --reason RA --tree B` 仍让 B 静默拿到 RA（按约定接受）。
- 端到端只压到 dry-run 收据；apply 读收据逐条 `reason`，代码未改、未新测。
- 全量 `pytest -q` 本机没跑，靠 CI python 叶子。

## 下一步

CI 四叶绿 + 用户确认后合入；合入后本文件转日期快照或删。要拦「一条夹在中间」就另开单做记顺序的 Action。

## 踩过的坑

- 同族扫描用 `head -30` 截了文件清单（输出恰好 30 行），险些漏看 5 个文件就断言「没有第二处」：先数清分母。
- 旧测试从没走过 CLI 的「`--tree` 不带 `--reason`」：0 条那档是变异才露出的，红绿对比看不出（旧代码那里本来就对）。
- 沉淀：原则进 `.claude/lessons_learned.md`；不做门禁——哪些参数成对要语义判断，全仓只此一例。
