# docs/orphan-workorders-0923 · 无人接手工作的工单化 + #77 合并批代跑

## 这个分支做什么
把 09-23 盘点出的无 owner PR / 分支写成工单 #81–#87 + INDEX 续表；盘点、判据与当日动作全文在 `docs/handoffs/2026-09-23-orphan-inventory.md`。同一会话顺手代跑 #77 合并批，脚本在树外（见下一步）。

## 决策与被否方案
- 被接替 PR 关闭留指针，判据是「新增代码行在 main 可见比例」94–99%；否了 `is-ancestor`（squash 前向不成祖先，会误判成未落地）。
- 合并批只拼一棵 main+8 PR 预览树跑一次四叶；否了逐张各跑（7×40 分钟，机器扛不住）。
- 前端 / e2e 另开同 commit 的树跑；否了排在 python 后（build 产物可能弄脏门禁树）。
- #807 的 lessons 冲突取 union；#838 退回不关（#863 正文明写留 open）；#874 有活会话持有，不动。

## 当前状态
- 已提交推送 `785d67736`，PR #889 open（docs-only）。
- 预览树 `/Users/a77/fwp-preview-batch-0923@53c51cfdc` = main@`b59d6eed0` + #853 #857 #804 #840 #849 #836 #807 #889：registry 五项 0、前端 lint/typecheck 0、vitest 120P、build 0、e2e 34P/2S 已绿；python 全量 19:00 准入在跑（pid 79683），日志 `~/.finance-runtime/reviews/orphan-batch-0923/python-gate.log` 看 `GATE_EXIT=`，收据 `…/receipts/gate-SFFAGzfL/pytest.json`。
- **尚未合入任何 PR。**

## 已验证
上面三叶；7 张旧 PR 关闭成功（评论 6297–6325）；主干 `f47d464eb` 对预览基座非文档漂移 0；8 个 head 对现 main 的 merge-tree 只有 #807 的 lessons 冲突（预期）。

## 未验证 / 已知边界
python 全量结论；合后 main 文件集 == PR 文件集；#807 前向 union 与预览是否逐字节同（脚本打印差异行数）；#889 若再追加收据提交，只多 docs、不重跑。

## 下一步
1. `GATE_EXIT=0` 且 failed=0 → `bash ~/.finance-runtime/reviews/orphan-batch-0923/run-merge-batch.sh main6`（逐张 fetch / 漂移 / head 钉 / merge-tree / `merge --record` / 文件集核对）→ `… 807`（前向 union 推分支再合）→ 补盘点文档 §五并提交 → `… one 889 docs/orphan-workorders-0923 <head>` → `… verify`。
2. `bash …/run-cleanup.sh`：只删干净且 cherry+0 的 QC 树与已并入分支。
3. 红了：按 failed_ids 归属（#853 / #857 自带测试 vs 主干既有），不合、贴评论、写回本文件。

## 踩过的坑
- e2e 必须成对设 `RE06_E2E_PORT` + `RE06_E2E_URL`，只设一个就是 1 红假装产品故障（memory 已存粘贴行）。
- zsh 不分词，多字段循环用 `bash <<'EOF'`；主树 `gitea_pr.py` 旧版没有 `close`。
- 准入 pytest ≤ 2 时别人常驻 3–5 个，等待器等了 20 分钟才起跑。
- 工具沉淀：三个脚本（准入等待器 / 合并执行器 / 清理器）在上述目录，PR 号与路径硬编码，未进 `scripts/`；泛化要参数化清单与 record 路径，留给 #77 收口。
