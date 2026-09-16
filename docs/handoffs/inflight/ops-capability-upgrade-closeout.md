# ops-capability-upgrade-closeout · 能力升级收尾（W5–W7 + 补验队列）
> 展开版 `docs/handoffs/2026-09-10-capability-upgrade-closeout.md`。本文件滚动覆写、未提交。**队列 1–4 项前置已于 09-11 00:0x 改判。**

## 当前状态（00:2x）
- **W5 定案不变**：clean 13 / recovered 10 / unavailable_final 5（material-01/02、calc-01、continue-01/02）/ engine_missing 2；旧包 HOLD。
- **队列第 1 项（五题 resume）改判 NO-GO，不是「等窗口」**：被测出口 Cockpit 57244 触到**账号周窗**上限（sol/terra 429 `model_cooldown`；quota-pool-state 自证周窗余 3%、**reset 09-16 00:38**）；判官 **grok Build 402 余额耗尽**（18:53 终件时尚好）。判官离线的读数不是生产形状（B5 已认过），硬跑只会产出第二种假干净件。两项须用户处置（充值/换出口），二选一见 `blocked/00.md` **B9**。第 2 项依赖第 1 项；第 4 项（after 臂）同前置，且一臂 ≈4.24M input tokens，**单个 Plus 账号周配额撑不住**，出口选型要先定。
- **第 3 项（01 统计批 09:47）与 5–8 项**：同批网关依赖，前置未解别排。
- **待合入清单更正**：「I1 合入 main 才能统一两臂口径」**不成立**——`gitea/main`（tip 已到 `3ed44703`）没有 `capability_benchmark.py`，harness 从未上 main（cherry-pick 得 `DU` 冲突）。口径统一靠两臂共用 I1 树这一棵量具、`--base` 各指自己的 sidecar；合车道分支是独立 PR，不在 after 臂前置链上。另两个待合入不变。

## 这一轮新增（00 车道，已提交 `baseline/capability-benchmark-00@6bea3197`）
- 只读闸 `~/.finance-runtime/capability-benchmark-00/preflight-00.sh`：出口/判官/sidecar 臂标签/续跑计划四查，NO-GO 退 1，编排每 attempt 必过。
- 拆两个哑雷（均已修）：① 编排探针探的是**生产 launcher 的网关**（13:07 已切 8080）而非 sidecar 固化的 57244——探活层与被保护层不是同一出口，正是「全 502 却落 28 completed 终件」的成因；② `baseline-chain.txt` 尾停在 09-09 旧件，重起编排会重放三道已跑干净的题。
- 离线验证（零配额）：resume 实重跑 **7 题**（5 隔离 + chain-01/02 的 B7，交接只提 5）；I1 `review-pack` 对终件如实拒收（新包出不来，旧包只能靠 HOLD 拦）；I1 harness 23 单测 + ruff 全绿。

## 没做（决策）
- 不硬跑五题；不换判官（`gpt-5.6-sol` 与写手同族，破坏异构性）；不擅自切出口 8080（臂内混合可接受，但要与判官充值一起由用户定）。
- 09-10 日报、theme_flow 回填、主检出推进：未做（理由见快照）。

## 下一步（前置解除后）
`preflight-00.sh` → GO → `run --resume` + `--case` 只点必需题 → 重出评审包（新目录）→ ≥20% 双评 → aggregate → 01 统计批 → after 臂（sidecar 起自 main tip 树，harness 用 I1 树）→ 04/I2/05/10。
