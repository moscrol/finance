# fix/report-reads-single-snapshot

## 这个分支做什么
#851 的跨快照拼接当一类扫：审计器列候选，只修能演示错误结论的 `query.health` 与 `collect_daily_review`。#74 补齐：54 候选裁定表、跨进程边界断言、A 类占位单 #78。

## 决策与被否方案
- 只修两处；否 54 全包——证明不了修的是什么。
- 审计器只列不闸；否 pre-commit——AST 判不了语义。
- 「多进程阳性对照」改为三条边界断言；否硬凑——DuckDB 拒绝跨进程并发打开同一文件[实测]，生产写者 staging+os.replace，第二进程在两读间提交做不出来。
- A 类 7 处登记 #78 不在本 PR 修；否顺手修——不扩面；真实暴露面（同进程多线程写者）grep 未见，≤P2。
- `completion_audit` 不改、`_start_day_confirmation` 不删（沿用）。

## 当前状态
已提交：修复 `e78c9eb5b`、交接 `086d99962`、本提交（裁定表 `docs/verification/2026-09-22-unsnapshotted-reads-triage.md`、`tests/test_report_reads_cross_process_boundary.py`、#78 占位单、本文）。PR #857 开着，零漂移于 main@f24a61a8a，合并权在用户。INDEX #74 行只在 PR #858 分支上，#858 未合前本枝不动 INDEX（文件尾会冲突），合后补 #74/#78 两行。

## 已验证
- 5 条用例先红后绿；拆 `collect_daily_review` 绑定 2 红、还原 sha 同 5 绿（#74 复验）。
- 边界 5 passed：三种锁组合 REFUSED；持有连接跨 os.replace 读旧代际；多次 connect 读者 [1,2] vs 单连接 [1,1]。
- 四叶在本 head 跑，收据按 revision 取（counts>0 那份），读数贴 PR #857 评论。

## 未验证 / 已知边界
- 线程内写库只 grep 到 pool.map 目标名，未追到 DuckDB 调用。
- B 类「fail-closed 方向」是读码推断。
- 全量 pytest 须 `--ignore=scripts/archive`（#58 未合前仓根收集 Interrupted）。

## 下一步
1. 用户点头 → `gitea_pr.py merge 857 --yes --expect-head <head> --record`；合后 main tip python 叶复跑。
2. #858 合入后补 INDEX 行。
3. #78 首做 `strong_subtheme_trace`（唯一跨进程也混的形态）。

## 踩过的坑
`health()` 在 finally 里 close，夹具用 `Passthrough` 隔开。同进程再 connect 同路径拿到同一实例（旧代际），全部关掉才见新文件——「重开连接」不是刷新。
