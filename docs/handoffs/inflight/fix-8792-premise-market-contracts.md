## 这个分支做什么
修 8792 题设计算 / 跨轮状态 / 恢复 / 行情证据 / 公开交付；本轮把「判官拒句→公开稿」从一刀切改成理由码分流。不开发 Arena。

## 决策与被否方案
- 判官报告加可选 `reason_codes`（四码），按码路由：fact_beyond_evidence 删；unsupported_ranking 改写优先级格「N（研判）」；internal_process_leak 「调用工具」→「检索」；其余与无码走原槽位规则（必答槽内降级、槽外删）。否了 1d9e717d2「引了 E 且被拒→删」：账本 39 条里 25 条 L4、7 条判官背书数字。
- 优先级格只标注不清空：清空触发 `missing_contract_elements` 契约重写循环。
- 否了模型改写窗：多一次调用叠判官方差，等吐码率再议。
- 排序题送判载荷加 `ranking_contract`（优先级列=model_reasoning）；股票代码探测器只分区不预检。
展开：`docs/handoffs/2026-09-21-judge-reason-codes.md`。

## 当前状态
候选 `a97b27057`；工作树 clean。main 今天在快速前进，ahead/behind 别抄本文，跑 `git fetch gitea && git rev-list --left-right --count gitea/main...HEAD`。对 `gitea/main@945c04bd7` 的 merge-tree 干跑：**三处冲突** `docs/agent-product-door.md` / `intelligence/runtime/turn_control_core.py` / `intelligence/services/user_task.py`，全部来自本分支早先的题设计算提交（37526350c…41ca2165d）撞上 main 的 #819 研究求证意识合入，与本轮两个提交无关；main 对 `episode_semantic_verifier.py` 只加了 `_mask_bound_short_date_heading`（2cfa9d0d7），与理由码区域无交叠、自动合并干净。未合 main、未 push、生产未改。

## 未验证 / 已知边界
- **生产判官（K3 自审链）是否回 `reason_codes` 零实测**：没起 sidecar 跑过一题。不吐码时 v19 P3 那句以降级保留出门，不是删。
- E2E 未在 a97b27057 重跑（无结论叶子）；v20 live/E2E 收据不移签。
- 判官放过的编造股票代码抓不到；正文标注仅矩阵行「（研判）」一处，句级标注仍只在 issues。

## 下一步
1. sidecar @a97b27057 跑三题，看 `sentence_verdicts[].judge_reason_code`；`offline_judge_verdict_census.py --since 2026-09-21` 读 `judge_stage.coded_share`。低→修判官接法，不动无码缺省。
2. 吐码率够再议：收紧无码缺省 / 开改写窗。
3. 合 main 前补 E2E；合并等用户确认。

## 踩过的坑
别把「引了 E 且被拒→删」加回来（加表格豁免也不行）；别清空优先级格；别把 `reason_codes` 放进 tool schema `required`（老判官整份作废）；zsh 里 `${PIPESTATUS}` 为空，用 `$pipestatus`。

## 已验证
全仓 pytest @a97b27057：12061 passed / 85 skipped / 2 xfailed（收据 `20260921T042331Z-a97b2705`，可采信）；前端 lint/typecheck/110 单测/build 全绿；11 道 pre-commit 过；生产账本普查 113 run：39 条全 demoted、零 deleted，coded_share 基线 0.0%。
