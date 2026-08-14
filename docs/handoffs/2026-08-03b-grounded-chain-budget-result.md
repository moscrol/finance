# Handoff — Grounded 合成链预算实验与架构决策门（2026-08-03b，更正版）

## 0. 一句话现状

`fix/grounded-chain-critical-path` 证明 child cap 与 allocator 能在 runtime enforcement point 生效，但它不是可合并的产品修复：全部 phase artifact 已有 brief `ok 69.740s` 与 composer `>20.261s` 下界，115秒 child + judge reserve 无法容纳现有三次串行 LLM；继续调 cap 是死路，下一步只能在 root/deep-mode 扩容与确定性 DecisionBrief（E）之间做架构选择。

## 1. Git 与运行时

| 项 | 状态 |
|---|---|
| 分支 | `fix/grounded-chain-critical-path` |
| 起点 | `main/origin-main@e785f833` |
| 计划 | `1bce5b5f` |
| 代码实验 | `9c6add5e` — child 115 + carry-forward/tail-reserve allocator |
| 初版 M2 | `ee98cf95` — 结论已被本更正 supersede |
| 初版 handoff | `a7ca3c96` — 结论已被本更正 supersede |
| main | 未合并；当前代码不要直接合并 |
| 8801 | PID 42180，加载行为 revision `9c6add5e` |
| runtime flags | `ASK_CONTINUOUS_RUNTIME` 未设置；`WORKBENCH_SHADOW_GROUNDED_TIMEOUT` 未设置 |
| health/readiness | healthy / ready，模型 `gpt-5.6-sol` |

代码 commit 后的提交均为文档，因此运行中代码与分支代码一致，但 health revision 仍显示 `9c6add5e`。在新架构 revision 形成前不要再烧 live A4。

## 2. 代码实验做了什么、没做到什么

实验只改预算可达性：

```text
child default: 90s → 115s
brief cap:     0.25T
judge reserve: 0.25T
composer:      remaining - judge reserve
judge:         all remaining
```

它正确解决了两个机制问题：

1. child 能触达 root 原本给得起的时间；
2. 不再按“当时剩余 × 固定 share”递归切片，前段未用时间可以回吐。

但它没有增加总预算，也没有删除三次串行 LLM 中的任何一次。实测工作量与预算不相容时，allocator 只能决定哪一段先失败。

## 3. 全部 phase artifact 与三段 telemetry 语义

| artifact | revision / epoch | phase 记录 | 正确语义 |
|---|---|---|---|
| `smoke-phase-check.json` | `6c16b73a` / E0 | brief `ok 69740/22`；composer `failed 20261/10` | phase grant 尚未执行；69.740s 是 brief 完成样本，20.261s 是 composer child 截断下界 |
| `smoke-after-fix.json` | `cd175a0e` / E1 | brief `failed 44560/22 provider_unavailable` | 每次 retry 各拿22s，phase 可达约2×grant |
| `smoke-budget-300.json` | `8ed66020` / E2 | brief `failed 29009/29` | retry 共享 phase deadline，elapsed≈grant 是硬截断 |
| `smoke-brief-fixed.json` | `bd845320` / E2 | brief `failed 22009/22` | grant-censored |
| `a4-pre` | `e785f833` / E2 | brief `failed 22010/22` | grant-censored |
| `a4-post` | `9c6add5e` / E2 | brief `failed 28010/28` | grant-censored |

semantic epoch 的两个边界：

- `cd175a0e`：单次网络调用开始读取 timeout；
- `8ed66020`：所有 retry 开始共享同一个 phase deadline。

跨这两个 revision 不能对同名 `elapsed_ms` 使用同一分类器。E0 的 `69740/22` 不是“超 grant 失败”，而是 timeout 没执行时留下的自然完成值；E2 的 `28010/28` 只是 `>28s` 下界。

## 4. A4 M2 与扩展证据

### 干净 A/B

| 指标 | a4-pre | a4-post |
|---|---:|---:|
| child 入口 | 89,999ms | 114,999ms |
| brief grant | 22s | 28s |
| brief elapsed | 22.010s | 28.010s |
| root 退出余量 | 96,569ms | 90,693ms |
| 终态 | brief timeout + fallback | brief timeout + fallback |

两侧 AnswerSpec / daily-review / answer SHA256 分别同为 `d106e6… / e2499a… / f1b6e1…`，task-frame 与 route 也一致。A/B 证明 allocator 生效并排除 H3/H4，但仅看这两份会漏掉已有自然完成值。

### 预算可行性

同日同日期、同为17/17 claim与2条 prepared message的 A1：

```text
brief completed = 69.740s
composer lower bound > 20.261s
T = 115s
judge reserve = 28.75s
```

给 brief 69.740s 后只剩45.260s；减 judge reserve 后 composer grant≤16.510s，低于其已观测下界。故在当前 contract 下，提高 brief cap 只会把失败后移到 composer。

`composer max_tokens=2400` 是 brief 1200 的两倍，但它只是上限，不能用于声称 composer 精确等于 brief 两倍；约250秒 root 只能作为 deep-mode 初始 sizing，不是直接测量。

## 5. 更正后的归因

- PRIMARY：`HARNESS → synthesize → execution-error-category-timeout`
- root_location：三次串行 LLM 拓扑与115秒 child/120秒 root contract 不相容
- confidence：medium（架构结论）；当前 A4 brief grant timeout 本身为 high
- SECONDARY：25% brief cap 在 E2 epoch 先触发硬截断
- TERTIARY：composer/judge 未启动，最终 fallback；`completed` 只表示可交付

H5 从 `INCONCLUSIVE` 更正为 `CONFIRMED`（medium）：确认的是**现有115秒 + judge reserve 的结构不可行**，不是精确三段 p95 或 A4 自然总耗时。

完整报告：`docs/verification/2026-08-03-a4-grounded-budget-m2-triage.md`。

## 6. 已取消的动作

- 不再做 brief-only 115秒 replay：69.740秒完成值已经存在。
- 不再逐级试 35/40/45 秒 brief cap：给足 brief 会直接饿死 composer。
- 不跑 A组：单题架构门未过。
- 不把当前 allocator commit 当产品修复合入 main。
- 不混入 `fix/kb-rag-worker-attribution`。

## 7. 下一步架构二选一

### 路线一：产品接受 deep mode / 扩 root

- root/child 初始 sizing 可按约250秒讨论，但必须重新做 uncensored phase profile；
- A4 的120秒 SLA 与 canary 要显式重定义；
- 必须作为独立 profile，不静默扩大所有用户请求；
- 优点：保留三次 LLM 的表达自由度；缺点：等待时间和成本显著增加。

### 路线二：确定性 DecisionBrief（E，默认工程建议）

- 用 AnswerSpec 确定性投影6个字段；
- `core_tension` 与 upgrade/downgrade 条件作为2个真实生成/派生风险；
- validator fail-closed，删除一次主链 LLM 往返；
- 先对冻结 artifact 做离线 golden + mutation，不调用 provider；
- 新拓扑形成后只跑一次 A4，再决定是否跑 A组。

如果产品目标仍是120秒内交付，E 是合理默认；root 扩容是产品体验选择，不是预算参数修补。

## 8. 测试与工作区

代码实验验证仍成立：

- 目标三套：74 passed；
- deadline/ask/conversation：107 passed；
- `intelligence/tests`：3648 passed / 13个既有失败 / 2 skipped；
- 正典仓库路径：4121 passed / 13个既有失败 / 3 skipped；
- Ruff：通过。

这些测试证明 allocator 实现正确，不证明架构能在120秒内交付。

用户既有脏文件全部保留。裸 `pytest -q` 会误收集 `tmp/*` 工作克隆，必须限定正典测试路径；不要删除用户工作树来换全绿。

## 9. 持久材料

- 设计（已标负实验）：`docs/superpowers/specs/2026-08-03-grounded-chain-budget-allocation-design.md`
- 实施计划（已写 outcome）：`docs/superpowers/plans/2026-08-03-grounded-chain-budget-allocation.md`
- M1（已标范围更正）：`docs/verification/2026-08-03-a4-grounded-budget-m1-triage.md`
- M2（更正版）：`docs/verification/2026-08-03-a4-grounded-budget-m2-triage.md`
- trace profile（三 semantic epoch）：`docs/trace-profile.md`
- eval artifacts：本地保留，不提交

两条 correction 已写入用户私有 corrections：

1. 声明“证据缺失”前必须扫描同目录相邻 artifact 与代码内实测；
2. telemetry 同名字段跨 runtime 修复点必须按 semantic epoch 解释。
