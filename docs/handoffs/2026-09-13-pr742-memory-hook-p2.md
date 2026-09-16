# 2026-09-13 PR #742 第三轮质检：记忆钩子项目身份 P2 收尾

## 背景

PR #742（b54fdf6a）质检确认前两项 P2 关闭、原全量收据可信、变基忠实，但新增一项
P2：`.claude/hooks/load-memory.sh` 按 git common-dir 父目录名选项目笔记。隔离实测：
金融仓独立 clone 改名 `finhot`、origin 仍指 `finance-workspace-private.git`、vault 里
两份项目笔记都在时——基线选对金融笔记，候选注入 finhot 笔记并提示回写到
`20_projects/finhot.md`；Claude 直跑与 Codex 委托入口同错，退出码都是 0。
报告与可复跑探针：`~/.finance-runtime/reviews/pr742-b54fdf6a-20260913/review.md`。

## 这个回归的来历（同一原则的第三次撞见）

1. 2026-09-08 前：按 origin URL basename 猜。真机 origin 指
   `github.com/moscrol/finance.git` → 推出 "finance" → 笔记静默缺席。
2. 本分支迁移提交 `10db26b5`：改按 common-dir 父目录名猜 → 真机修好，
   改名独立 clone 破（父目录名 = 新目录名）。
3. 本轮：两种猜法都把「位置」当「身份」。与 `build_registry` 的 ws 绑定同一条原则：
   **脚本 checked in 在哪个仓，身份就固定是哪个仓**，位置信息一律不参与。

## 决策对比

| 方案 | 评价 | 结果 |
|---|---|---|
| 保留 common-dir 推断 | 改名 clone 即失配；父目录名从来不是业务身份 | 否 |
| 恢复 origin URL 推断 | 真机 origin 指 moscrop/finance → 静默缺席（2026-09-08 事故原样复还） | 否 |
| 按 vault 内容反查匹配 | vault 里 finhot.md 真实存在（别的项目），内容比对不可靠且引入读扩散 | 否 |
| 常量绑定 `finance-workspace-private` | 钩子随仓分发，没有第二个候选；与 registry 修法同构 | 选 |

## 验证

- 新行为测试 `test_memory_hook_binds_finance_project_in_renamed_clone`：改名 clone＋
  双笔记假 vault＋正确 origin，覆盖 Claude 直跑与 Codex wrapper 两个入口，断言注入
  内容与回写路径。在 b54fdf6a 上先红（注入 `WRONG_FINHOT_NOTE`），修复后绿；
  钩子文件 5 passed。真树实跑行为不变（仍注入金融笔记、回写路径正确）。
- 修复提交 `23019bbd`；Codex wrapper 注释里会漂的行号引用顺带改成按机制描述。
- 最终整仓门禁在冻结 SHA 上重跑，逐叶证据与收据索引：
  `~/.finance-runtime/gates/instruction-clearance-r5-20260913/matrix.md`。
  本快照不是通过证明，不在运行后 amend 写入读数。

## 后续 / 不要做

- 不顺带扩大到 watchdog、views 缺链、bash 3.2、收据目录变量（质检明确列为边界外）。
- 真机 vault 存在 `finhot.md` 是别的项目的正常笔记，不因为本仓钩子曾经误选就动它。
- 合并 PR #742 仍等用户明确确认；确认后按批次规程在实际 main tip 复跑。
