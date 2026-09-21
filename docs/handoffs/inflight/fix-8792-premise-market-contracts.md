## 这个分支做什么
修 8792 题设计算 / 跨轮状态 / 恢复 / 行情证据 / 公开交付；本轮把「判官拒句→公开稿」从一刀切改成理由码分流。不开发 Arena。

## 决策与被否方案
- 判官报告加可选 `reason_codes`（四码），按码路由：fact_beyond_evidence 删；unsupported_ranking 改写优先级格「N（研判）」；internal_process_leak 「调用工具」→「检索」；其余与无码走原槽位规则（必答槽内降级、槽外删）。否了 1d9e717d2「引了 E 且被拒→删」：账本 39 条里 25 条 L4、7 条判官背书数字。
- 优先级格只标注不清空：清空触发 `missing_contract_elements` 契约重写循环。
- 否了模型改写窗：多一次调用叠判官方差，等吐码率再议。
- live 用 K3：候选写死发 `temperature` 而 K3 网关拒它，用传输层 shim 剥键（否了改代码/换模型）。
展开：`docs/handoffs/2026-09-21-judge-reason-codes.md`。

## 当前状态
**PR #825 已开，等用户确认合入**（head `4075ce8ac`，base main）。已推 gitea；工作树 clean。两次前向合并已完成：← `3c70af64d`（解 3 处）、← `c615adbd2`（#770 材料收口，解 6 处 + 补一条真缝）。对 `gitea/main@c615adbd2` conflict-check clean。生产 8792 未被本轮改动（他人 12:47/13:1x 两次切换）。

## 未验证 / 已知边界
- live（K3 自审，n=2 拒句）只证「判官会吐码、路由按设计走」：1 句 causal 码→降级、1 句无码→降级。**删与两条改写 live 零覆盖**：排序题 K3 自审两发撞 75 s 帽（145 卡）→ 判官不可用带披露放行（既有路径）。已立工单 #57。
- v20 public fixture 是 glm 措辞，对 K3 只中核心数字，不是回归判据；本轮未另冻 K3 fixture。
- `episode_protocol` 的「先 render_from_claims 再 admit」顺序只有单测，无 live。

## 下一步
1. 用户确认后合 #825（`gitea_pr.py merge 825 --yes --expect-head <当前> --record --authorized-by`）。合前重跑 conflict-check：main 在快速前进。
2. 判官窗 → 工单 #57（`2026-09-21-judge-window-k3-latency-workorder.md`，先量后改），不在本分支。
3. 吐码率用 census `judge_stage.coded_share` 累积；低→修判官接法，不动无码缺省。

## 踩过的坑
别把「引了 E 且被拒→删」加回来；别清空优先级格；别把 `reason_codes` 放进 tool schema `required`；K3 经 Sub2API 拒 `temperature`；**改判官报告字段要 grep 所有重建 payload 的地方**（#770 的 `reconcile_claim_checks` 会静默丢可选键）；对方说「没冲突」只对他那侧成立，自己 merge-tree。

## 已验证
四叶在 `4075ce8ac` 全绿：python `ruff` 0 + `pytest` 12440P/85S/2xf（收据 `20260921T062625Z-4075ce8a`，可采信）；frontend 110 单测 + build 后树干净；e2e 34P/2S；registry-check 五条 0。live 5 run 全 completed，原件 `~/.finance-runtime/8792-premise-market-evidence/v21-live/` + manifest。
