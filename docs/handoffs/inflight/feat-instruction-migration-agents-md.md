# feat/instruction-migration-agents-md · 冻结迁移的依赖指针

## 这个分支做什么
指令正文迁到 AGENTS.md；CLAUDE.md 保留导入和 Claude Code 备注；技能源/软链视图归位，同步注册表与工具钩子的仓根绑定。

## 决策与被否方案
- 原候选 b2d40776e80eb3743626e3231d1f367385428244 保持冻结。本文件的订正只存在于清障集成分支，不 amend 原候选。
- 不带基于旧底 b4a35fa2 的另一批技能正文改动，以免回退 main 已有红线。
- 清障分别使用 fix/codex-isolation-interpreter@6d709cfd、docs/hybrid-ledger-dependency@7d193f1c；不重新领历史编号，不放松检查器，不扩大沙箱权限。

## 当前状态
原候选门禁仍红，不可将后续结果追认给它。集成工作和后续状态由 [fix-instruction-gate-clearance.md](fix-instruction-gate-clearance.md) 承接。未推送、未开 PR、未合入。

## 已验证
历史候选正式全量两轮：9407P/2F、9408P/1F，均 exit 1、dirty=false。前端四项及 E2E 已跑绿。完整订正与收据索引：`~/.finance-runtime/gate-matrix-b2d40776-corrected.md`。

## 未验证 / 已知边界
旧 13b0be98 的 9405P/1F 与候选相差三个文件，不能当候选读数。历史 watchdog 间歇失败缺完整断言，原因未定论。原候选 crosswalk 缺历史依赖、沙箱在 venv 优先 PATH 下失败，均不豁免。

## 下一步
读取集成交接及其仓外门禁矩阵，按新候选的完整结果判断；合并仍需用户确认。

## 踩过的坑
主 pytest 解释器相同不代表子解释器相同；PATH 改变足以触发旧沙箱失败。`--showlocals --tb=long -vv` 可在不改候选的情况下取失败子字段。零计数收据不作全量证据。
