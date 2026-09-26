# docs/orphan-followup-0923-close · 批次 1 已合、批次 2 四叶绿等用户确认

## 这个分支做什么
收口 09-23 盘点遗留四件事的最后一段：删已合分支的 inflight，写收据快照 `docs/handoffs/2026-09-23-orphan-followup-batches.md`，INDEX #62/#66/#68 改「四叶绿，等确认」。决策与依据见 `2026-09-23-market-recovery-decisions.md`。

## 决策与被否方案
- 工单 PR（#844 #896 #897 #898 #899）只做到四叶绿、不代合；否了套用「顺手合并」常设授权——各工单原文都写「合入等用户确认」。
- 五张拼一棵预览树跑一次四叶；否了逐张（5×20 分钟且机器有别人 3–6 套全量）。
- 本枝是 docs-only 收口 PR，合入时走同一套漂移检查；否了直推 main（hook 拦，也不该）。

## 当前状态
- main `c9dd71dfd` 含批次 1 四张（#871 `a026544c5` / #861 `d3ff8219c` / #874 `09da2ae03` / #893）。
- 批次 2 预览 `d29d6f73f`（`~/fwp-preview-orphan3-0923`）四叶全绿：python 15123P/0F 可采信、registry 五项 0、前端 120P、e2e 34P/2S；读数已贴五张 PR。**等用户一句确认**。
- 本枝 PR 待开（docs-only）。

## 已验证
两批收据 `check_test_receipt.py --expect-revision --require-full-scope --base-drift-max 5` 均可采信；合后 `git diff <预览> gitea/main` 非文档 0。

## 未验证 / 已知边界
批次 2 未合入；`test_code_map` 低负载有图三次读数未取得（#899）；启动器补丁未应用；readiness 采样未做；#73 归协调者会话。

## 下一步
1. 用户确认后：`AUTH2="<原话>" SRC2="<出处>" bash ~/.finance-runtime/reviews/orphan-followup-0923/batch2/run-merge-batch2.sh batch`；合完 #845/#833 补指针评论 → #899，INDEX #62/#66/#68 改「已合 + SHA」，删预览树与四棵子代理树。
2. 用户授权后应用启动器补丁（`reviews/rag-readiness-0923/README.md` 步骤，备份、不重启 8792）。
3. QC 会话按 #861 评论 6463 口径推进 09-21 恢复；换库另取授权。

## 踩过的坑
Gitea POST 在 load>50 时 30s 超时但服务端已落，重试前先回读；新预览树前端叶先 `pnpm install --frozen-lockfile --prefer-offline`；hook 把命令里的「pushed」也当 push 拦。
