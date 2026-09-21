## 这个分支做什么
修 8792 题设计算 / 跨轮状态 / 恢复 / 行情证据 / 公开交付；本轮把「判官拒句→公开稿」从一刀切改成理由码分流。不开发 Arena。

## 决策与被否方案
- 判官报告加可选 `reason_codes`（四码），按码路由：fact_beyond_evidence 删；unsupported_ranking 改写优先级格「N（研判）」；internal_process_leak 「调用工具」→「检索」；其余与无码走原槽位规则（必答槽内降级、槽外删）。否了 1d9e717d2「引了 E 且被拒→删」：账本 39 条里 25 条 L4、7 条判官背书数字。
- 优先级格只标注不清空：清空触发 `missing_contract_elements` 契约重写循环。
- 否了模型改写窗：多一次调用叠判官方差，等吐码率再议。
- live 用 K3：候选写死发 `temperature` 而 K3 网关拒它，用传输层 shim 剥键（否了改代码/换模型）。
展开：`docs/handoffs/2026-09-21-judge-reason-codes.md`。

## 当前状态
候选 `285c719728`（代码尖 `a97b27057`，其后只有 docs）；工作树 clean。对 gitea/main 的 merge-tree 有三处冲突（`docs/agent-product-door.md` / `turn_control_core.py` / `user_task.py`），全来自本分支早先题设计算提交撞 #819，与理由码无关；`episode_semantic_verifier.py` 自动合并干净。ahead/behind 现跑 `git rev-list --left-right --count gitea/main...HEAD`。未合 main、未 push、生产未被本轮改动（生产 12:47 被他人切到 `945c04bd7fdd`）。

## 未验证 / 已知边界
- live（K3 自审，n=2 拒句）只证「判官会吐码、路由按设计走」：1 句 causal 码→降级、1 句无码→降级。**删与两条改写 live 零覆盖**：排序题 K3 自审两发撞 75 s 帽（145 卡）→ 判官不可用带披露放行（既有路径）。
- K3 自审 35k 字符请求 71.8 s 贴帽；重题量不了排序改写，先解判官窗（不在本分支）。
- E2E 未在候选重跑（无结论叶子）；v20 fixture 是 glm 措辞，对 K3 只中核心数字。

## 下一步
1. 合 main 前解三处冲突 + 补 E2E；合并等用户确认。
2. 排序改写要 live 覆盖：判官窗已立工单 #57（`2026-09-21-judge-window-k3-latency-workorder.md`，先量后改），不在本分支做。
3. 吐码率用 `offline_judge_verdict_census.py` 的 `judge_stage.coded_share` 累积；低→修判官接法，不动无码缺省。

## 踩过的坑
别把「引了 E 且被拒→删」加回来；别清空优先级格；别把 `reason_codes` 放进 tool schema `required`；K3 经 Sub2API 拒 `temperature`；shim SSE 客户端先断那次不进日志；zsh 用 `$pipestatus`。

## 已验证
全仓 pytest @a97b27057：12061 passed / 85 skipped / 2 xfailed（收据 `20260921T042331Z-a97b2705`，可采信）；前端 lint/typecheck/110 单测/build 全绿；11 道 pre-commit 过；生产账本普查 113 run：39 条全 demoted、零 deleted；live 5 run 全 completed，原件 `~/.finance-runtime/8792-premise-market-evidence/v21-live/` + manifest。
