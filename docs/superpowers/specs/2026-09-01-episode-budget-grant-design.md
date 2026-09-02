# 设计：Episode 工具授权额与假超时（2026-09-01）

日期：2026-09-01
状态：P0 `6984d101` + P0.1 `f6b65188` 已提交。finalize 时长已离线量完。P1 仍挂起——20s 地板被证伪。
工单：`docs/superpowers/specs/2026-09-01-episode-budget-grant-workorder.md`
证据：`docs/verification/2026-09-01-finance-base-shape-alignment.md`（尝试 4 更正）+ `finance-base-ab/out/attempt-4-aligned/budget-chain.json`

## 0. 一句话

standard 档把启动器 300s 截成 90，再冻住 60s synthesis reserve，研究阶段只剩约 30s 给工具。授权额 ≤0 不进线程池，却回灌与真超时逐字相同的 `tool_timeout` + 空 `detail`。模型换工具再试。外壳没搬坏。

另一半失败是授权 >0 但仍短于工具自然时长（11.5s 派给要 17s 的 `kb_search`）。那半边 P0 之后模型看到的仍是空 `detail`。

## 1. 为什么不是「抬档 / 抬 T / 换题 / 借记 borrow」

| 候选 | 为何不取 |
|---|---|
| 抬 `ResearchPolicy.for_tier("standard")` 或 env 300 | `effective_timeout = min(tier_total, timeout)` 仍是 90。`R-20260816-07` / `-14` / `-21` 禁止只把数字调大。 |
| 换短题 | 短题一样烧 30s 窗口；`kb_search` 真跑也要 >17s。 |
| 按实耗借记 opening borrow | 对任意 `t ≥ baseline`，`stage ≡ 0`（恒等 no-op）。见 §4。 |
| 按授予借记 opening borrow | 有效，但会把工具阶段从 ~30s 拉到 ~74s、合成保护掉到 20s 地板。缺 finalize 时长 P95，触 `R-20260816-09`。 |
| 零授权就 fail-closed | 错。live 臂零授权之后 repair 从 root 未分配余量铸了两发 30s。 |

## 2. 选定切片

**P0（本提交，不改任何秒数）**  
零授权仍用时间闸词表 `error=tool_timeout`。`detail=not_dispatched: stage_timeout_granted=0`。真 `TimeoutError` 的 `detail` 经 allowlist 清空。集成测试：带 raw detail 的 timeout 结果过 accumulator，模型消息无异常原文。`R-20260816-13` 定位改符号，不再钉行号。

**P0.1（本刀，零 LLM、不动秒数）**  
`detail` 带实授值 `stage_timeout_granted=<granted>`（零就是 `=0`）。allowlist 为正则 `^stage_timeout_granted=\d+(\.\d+)?$`。consume 优先读 clock；`_result` 给所有 timeout 项盖同一字符串。覆盖「授权 11.5s 仍超时」那一半。

**P1（挂起）**  
不要补一行 `synthesis_reserve -=`。离线量完：生产成功写作 P95=26.9s（有时钟子集 24.7s），20s 地板不够。见 `docs/verification/2026-09-02-finalize-duration-offline.md`。该拍的仍是「reserve 不可侵犯 vs 工具有地板」，合成侧数字要用 25–35，不是 20。

## 3. 不改

8792 / 启动器 / 档位表 / `_BALANCED_SYNTHESIS_RESERVE` / `ASK_TOOL_BATCH_TIMEOUT` / 包装对照再烧 LLM / 零授权提前收工。

## 4. 借记按实耗是恒等（挂起理由）

`T=90`、`R=60`、`baseline=T−R=30`、首轮耗时 `t ≥ baseline`。按实耗扣：`R' = R − (t−30)`，`remaining = 90−t`，于是 `stage = (90−t) − (60−t+30) = T − R − baseline ≡ 0`，与 `t` 无关。写出这版、测试全绿、读数一分不变。
