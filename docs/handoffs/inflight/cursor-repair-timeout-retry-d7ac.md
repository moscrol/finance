# 在途交接 · cursor/repair-timeout-retry-d7ac

更新：2026-08-12 · Cursor Cloud（Mac 隧道已通，A1/A7 产物已判决）

## 这个分支做什么

修复轮 LLM 瞬态错误单次重试（熔断上限 1）。生产形状：repair 授予 16s，`timeout_configured=75`，第一发 TimeoutError 烧穿后一击终局。PR #296 ready for review。

## 当前状态

- 实现已推送：92599b00 首版 + 450933b2 审查修复（烧穿后从 root hard-cap 未分配余量再铸 ≤30s grant）。
- **卡在等用户审 #296**；合并 main 必须用户确认，未动。
- Mac 产物目录不在仓内 `intelligence/users/`，而在 `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`（8792 进程环境）。

## A1 31s vs 103s 判决（产物，不是猜）

三轮 `contract.research_tier` **全是 `standard`**，`question_type=market_watch`。**不是路由方差。**

| 轮 | elapsed | stop_reason | repair | 形状 |
|---|---|---|---|---|
| R1 | 103.4s | `model_finish` | 0 | 首跳直接 tool call，30s 内写完，其余是 judge |
| R2 | 31.0s | `deadline_exhausted` | **0** | PLAN→quick 裁决→第二跳 TimeoutError，0 证据，进不了 repair |
| R3 | 84.6s | `repair_model_finish` | 1 | 先拿到 4 条工具证据，主路径超时后 delivery repair 24s 写完 |

~30s 是 standard 的**检索分配段**：档位 90s，GLM `market_watch` 要 75s 合成保留，被 `_MAX_SYNTHESIS_BUDGET_FRACTION=2/3` 钳成 60s，分配段 = 90−60 = **30s**。R1 的 103s 是 30s agent + judge，不是换了 deep 档。

R2 本 PR **救不了**：0 证据 + `stage_timeout=0` → `tools_open=False` → `admit_repair` 拒。那是「主路径超时且没证据」另一条失败形状，别并进本 PR。

## 本 PR 对得上的生产收据

同一用户目录，repair 授予恒 16s（缺口×8），`timeout_asked≈16`，`timeout_configured=75`，第一发 TimeoutError 后无重试：

- A7-R1 / A10-R1 → `repair_deadline_exhausted`
- A9-R2 / A9-R3 / A10-R3 → `repair_model_unavailable`

第二版从 hard-cap 未分配余量（90−已分配）再铸 ≤30s，就是为这一击。

## 已验证 / 未验证

- 测试：烧时钟 4 条 + 受影响 7 文件 262 passed；全量 4074/26 与 main 基线逐条一致。收据条件：云端 `/usr/bin/python3` + `FWP_ALLOW_ANY_PYTHON=1`。
- 未在真实 provider 上验证。quick 档 30s 硬顶常铸不出，属预期 fail closed。
- 合并后重跑 A 组：看 A7/A9/A10 的 repair TimeoutError 是否变成 retry 后的 `repair_model_finish`；**不要用 A1-R2 当本 PR 验收题**。

## 下一步

1. 用户审 #296 → 确认后合并 → 部署 → 重跑 A 组。
2. A1-R2 形状另立案（主路径超时 + 零证据 + tools 已关）。
3. A5 日期错位仍待立案。
4. 工具沉淀（Mac `~/harness-reference`）：失败集合对基线 worktree diff；「重试放在能看见剩余预算的那一层」。

## 踩过的坑

- 找 run 目录先看 8792 的 `FORESIGHT_USERS_DIR`，别在仓内 `users/` 里 rglob。
- 远程 `python3 -c` 会被 `sh -c` 吃括号；复杂脚本用 stdin heredoc。
- 不要把隧道 token 写进交接或 commit。
