# fix/report-reads-single-snapshot

## 这个分支做什么

把 PR #851 修的那一处（换池预览跨快照拼接）当成**一类**来扫。DuckDB 自动提交下每条
SELECT 各取一次快照，十来条 SELECT 拼出来的报告可以由「从未同时成立」的数字组成。

## 决策与被否方案

- **只修演示得出错误结论的两处**（`query.health`、`collect_daily_review`）；
  否「把 54 个无保护函数全包上」——包了也证明不了修的是什么。
- **`completion_audit` 不改**。它首条读出 `snapshot_id`，其后每条都按它过滤，代际内行不
  改写 → 内部不会打架。绑快照治「内部不自洽」，治不了「结论陈旧」。**编不出错误结论就不动。**
- **审计器退出码恒 0，是辅助不是门禁**；否做成闸——判该不该绑快照要语义，AST 判不了，
  做成闸必然误报连篇或靠白名单养蛆，两种都把人逼去 `--no-verify`。
- **死代码只记录不删**（`_start_day_confirmation` 全仓零引用）；删代码是另一个决定。

## 当前状态

已提交 `e78c9eb5b`，已 push，**PR #857 开着未合并**（合并权在用户）。树干净。
注：开 PR 时 API 超时但 PR 已建成——POST 非幂等，回读确认过再没重试。

## 已验证

- 5 条新用例先红后绿，红在**真缺陷**上：`assert 3 <= 2`（体检单称有成分股的板块比维表里
  存在的还多）、`during != before`（日报拼了旧市场 + 新板块）。
- **保护性变异 3/3 见红**：拆 health 红 3、拆日报红 2、两处都拆红 5；还原后逐字节相同。
- 干净树收据 `20260922T135535Z-e78c9eb5.json`，`--expect-revision` 判可采信，54 passed。
- 回归 `-k "review or query or health or generation or report"` → **473 passed / 9 skipped**。

## 未验证 / 已知边界

- **未跑全仓 pytest**。上面是目标收据，不是全量收据。
- 剩余 **52 个候选未逐一裁定**，`scripts/audit_unsnapshotted_reads.py` 可复跑。
- 审计器**看不出助手已被上层快照覆盖**（`_sw_l1_double_red_matrix` 仍被列出，实际已在
  `collect_daily_review` 的快照内）——AST 固有局限，写在 docstring 里，没靠白名单掩盖。
- 只证了「同一进程内第二连接提交」，未测多进程 / 夜跑真实并发。

## 下一步

1. PR #857 等用户点头。
2. 若合入，按判据继续裁剩下 52 个候选，优先**产出对外结论**的读者。
3. `_start_day_confirmation` 是否删，单独提。

## 踩过的坑

`health()` 在 `finally` 里 `con.close()`。直接把夹具连接交给它，第二次调用就
`Connection already closed`——那是**脚手架**坏了不是被测行为坏了。不隔开会把它误读成实现
bug。解法：统一套一层 `Passthrough`（转发 execute、close 空转），连接生命周期只归夹具管。
