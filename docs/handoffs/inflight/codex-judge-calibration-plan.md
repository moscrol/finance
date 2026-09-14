# codex/judge-calibration-plan

## 这个分支做什么
修正历史取回文档的执行依据，写出判官身份与校准失效方案；本轮不实施 runtime。

## 决策与被否方案
- 旧 #27 标为历史方案；#43、INDEX、roadmap 改指 #47。保留原 SQL 及撤销理由，避免删掉历史证据。
- C 复用 LLMCallLedger，在真实 judge 调用链采集；不把 SDK 的 ServedModelLog 当成已接线。
- pending 只补缺分；跨进程/封存后的补评分仅作诊断。恢复资格另建全臂重评批次，未知历史 writer 不能借重评补造身份。
- sealed 禁止追加，日后只读不按当前时间作废。产品失败导致配对缺失时 no_call，成功子集仅描述。
- 细节与取舍见 `docs/handoffs/2026-09-14-judge-calibration-plan.md`。

## 当前状态
方案与四处指针订正已提交 `64c8f90c`；基线 `gitea/main@1fef3d276d0e`。未合并。C 的代码与 17 项验收尚未实施。
共享记忆已有图谱及两篇 B 笔记，本轮补了范围/分母边界；已由 agent-memory 自动同步。

## 已验证
- 基线的 river recorded_at/frozen 定向测试 19 passed；收据 `~/.finance-runtime/test-receipts/20260914T080356Z-1fef3d27.json`。
- 方案 Python 反例实际执行，no_call 断言在未改代码上按预期失败，证明缺口仍在。
- git diff --check、文档提交 pre-commit 通过。graph_audit 60 行/106 条 exit 0，不能证明正文语义。
- vault_lint --strict：1 error/16 warns；错误为 TOOLKIT 镜像不一致，三份知识文档均未被点名。

## 未验证 / 已知边界
未重测生产库覆盖面；19 条不是全仓测试。未调真实判官，未给历史收据追认身份。新增方案只覆盖 legacy CLI ask，不代表 Workbench Episode。

## 下一步
从 `docs/superpowers/plans/2026-09-14-judge-calibration-validity.md` Task 1 开始实施；交付应包括实际调用收据与共同聚合门，不能只完成字段记账。合入仍待用户确认。

## 踩过的坑
共享主检出树是旧 detached HEAD 且脏；以本独立树和固定 revision 为准。agent-memory 自动同步会在编辑期间提交，遇到补丁上下文失配先重读。
