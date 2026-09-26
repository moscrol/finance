# fix/instruction-gate-clearance —— 已合并（PR #742）

已合入 main：merge `bed89634`（2026-09-13，用户明确确认后合并）。本分支使命完成，
别再基于它开工；接手相关问题从 main 另开分支。

三轮质检 P2 全部「先红后绿」关闭：registry 仓根绑定（ws 恒绑 REPO_ROOT）、
交接压缩 ≤3K、记忆钩子项目身份恒绑 finance-workspace-private。同一原则：
目录名 / common-dir / origin URL 都是位置不是身份，脚本随哪个仓分发就绑哪个仓。

批次门禁在 main tip `bed89634` 全绿：9475 passed / 0 failed / 77 skipped
（收据 20260912T174111Z-bed89634.json，过 check_test_receipt.py --expect-revision
精确校验）；registry ①–⑤ exit 0；frontend 76 passed；e2e 15 passed。
merge 树与候选 3d9c3102 树哈希逐字节相同（f6802a89…）。

逐叶证据：~/.finance-runtime/gates/post-merge-742-20260913/（main tip 批次门禁）、
~/.finance-runtime/gates/instruction-clearance-r5-20260913/matrix.md（候选门禁）。
快照：docs/handoffs/2026-09-12-instruction-gate-clearance.md、
2026-09-12-instruction-gate-qc-p2-closeout.md、2026-09-13-pr742-memory-hook-p2.md。

未随本单关闭的已知边界：repos.present 跨机器可漂；generate-views --check 测不到
缺失软链；watchdog 间歇根因未定论；FWP_TEST_RECEIPT_DIR 与 run_main_gate.sh:82
bash 3.2 崩溃未修。
