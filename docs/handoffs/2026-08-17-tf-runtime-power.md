# T-F 主检验功效：Runtime 质量块（**不开 900**）

- 日期：2026-08-17
- 指令：`2026-08-17-dispatch-f-addendum-3-decision.md` §3
- 前序：845 是护栏当主检验问错了的正确答案，**不重算、不沿用配 n**
- 数据：`~/.finance-runtime/evals/arm-a-cal-20260816/`，45 条，九题旧 pin，离线
- 事件路径：`arms[].diagnostics.events`（不在 `arm.events`）
- 5a 已落 spec；5d 并行不挡窗；领域护栏降级见 §6

## 0. 一句话

用户预期「Runtime 率基率高、方差和 citations 不同，n 可能远小于 450」。
#68 只部分支持这句话：

- **延迟**是连续量，450/臂**很宽裕**（均值差半宽约 8s；20s 效应约需 n=69）。
- **repair 恢复**有题内方差，但基率是 8/21=**38%**，不是「高」。10pp 约需总 n=385，450 够；5pp 不够。
- **首轮超时 / tool 失败**看起来有 3 题方差，**几乎全是 `runner_exception` 空事件被算成 0**。剔 infra 后变回题级恒 0/恒 1，和 citations 同一类结构常数。
- **cancel/resume/restart** 这 45 条是 **0**，基率高估不出来。
- **Trace 条数对账**有事件的臂 35/35，是门禁不是功效题。

效应量我提议、你拍：率 **10pp**（「明确改善」），延迟均值/P50 **20s**，P95 **20s**。
**仍不开 900。**

## 1. 从 45 条里实际抽到的

| 指标 | 口径（本页采用） | 基率 / 分布 | 题级形状 |
|---|---|---|---|
| 墙钟延迟 | `latency_seconds` | 全 45：均值 89.5s，P50 91.9，P95 187.7，sd 64.7 | fast-path 5 条约 0.3s；5 条 `runner_exception` 把 P95 抬到 188–241s |
| 首轮超时 | 第一条 `finish.stop_reason==deadline_exhausted` | 21/45=47%；有事件则 21/35=60% | 见 §2：剔 infra 后只剩 1 题有方差 |
| tool 失败 | 该臂是否出现 `tool_error`（`tool_result.ok=false` 为 **0**） | 6/45=13%；`tool_error` 事件 8 条 | 见 §2：剔 infra 后只剩 1 题有方差 |
| repair 恢复 | 进入 `repair_goal` 的 21 条里，末条 finish ∈ {`repair_model_finish`,`repair_model_stop`,`model_finish`} | **8/21=38%** | 进入率 21/45=47%；这 21 条首条 finish **全是** `deadline_exhausted` |
| 另一口径（并列，不主用） | 进入 repair 且臂 `stop≠repair_model_unavailable` | 15/21=71% | 含「修完又撞诚实闸」：末条 finish 与臂 `stop` 不一致 14/21 |
| cancel / resume / restart | 事件 kind 含这些词 | **0 / 45** | #68 没做 §9.2 失败注入 |
| Trace 条数对账 | `tool_request` 条数 = `tool_result`+`tool_error` | 有事件 35/35；空日志 10（5 fast-path + 5 exception） | 按 `call_id` 对不齐 19/45，是记录缝 |
| 投影在场 | `blind_projection` + sha | 45 / 45 | 恒 1 |
| provider_traces | `diagnostics.provider_traces` | 73 条：success 52 + fallback_success 8；其余 13（`request_error` 8 等） | 5 臂至少一条非 success |

`provider_traces` 的非 success 和 `tool_error` 事件不是同一集合，功效表不混用。

同日另一页（`docs/verification/2026-08-17-evidence-bound-output-rate-correction.md` §4）
按**顶层字段**把首轮超时 / Trace 对账 / tool denied·invalid 标成「无字段」。
那是「没有现成列」，不是「事件里抽不出来」：

- 首轮超时：本页用 `diagnostics.events` 里**第一条** `finish.stop_reason`，21/45 能数。
- Trace 对账：没有预计算布尔，但 `tool_request` vs `tool_result`+`tool_error` 条数 35/35 能对。
- repair：不能只看臂级 `stop_reason`（那页的 1/6）。进入 `repair_goal` 的是 21 条；
  14 条修完后臂 `stop` 被诚实闸改成 `numeric_lineage_gap`，用终态会把恢复率算没。
- tool denied/invalid：事件里只有 `tool_error`，**没有** denied/invalid 细分。同意要补记录才分得开。
- cancel/resume/restart：同意，事件里就是 0。

空事件 10 条：`index-rebound-space`×5（fast-path）+ `ruihuatai-valuation`×2 / `theme-comparison`×3（`runner_exception`）。
`0=0+0` 的条数对账算通过，**不能**据此说崩溃臂「对账完整」。

## 2. 超时 / tool 失败：方差是崩溃编码，不是 Bernoulli

若把空事件算成「未超时 / 未失败」，会得到「3 题有方差、v≈0.267、10pp 需 205」——
**和 #69 把恒 0 格池进去撑出 0.1375 是同一类假刚够。**

逐格（`[r1..r5]`，1=发生）：

| 题 | 首轮超时 | tool_error | 空事件是哪几发 |
|---|---|---|---|
| `rebound-duration` | 5/5 | 0/5 | — |
| `weekly-market-cause` | 5/5 | 1/5 | — |
| `current-mainline` | 5/5 | 0/5 | — |
| `ruihuatai-valuation` | 3/5（另 2 空） | 3/5（另 2 空） | r2、r4 = `runner_exception` |
| `theme-comparison` | 2/5（另 3 空） | 2/5（另 3 空） | r2、r3、r4 = `runner_exception` |
| `unfamiliar-methodology` | 1/5 | 0/5 | — |
| `contextual-follow-up` / `counterfactual-mainline` / `index-rebound-space` | 0/5 | 0/5 | fast-path 只有最后一题 |

剔 5 条 infra 之后：

- 超时：**恒 1** = rebound / weekly / current / ruihuatai(3/3) / theme(2/2)；**恒 0** = 其余除 unfamiliar；**有方差** = 只有 `unfamiliar-methodology` 1/5。
- tool 失败：**恒 1** = ruihuatai(3/3) / theme(2/2)；**有方差** = 只有 `weekly-market-cause` 1/5；其余恒 0。

九题池化 v≈0.089（超时）是常数格 + 崩溃 0 撑出来的，**不用**。
冻结 30 没有 live，扩不出去；**不跑去补**。

读法：这两项在 #68 上是**题型结构**（数据题几乎必首轮超时；部分题一跑就 `tool_error`），
不是「多重复就能分辨 5–10pp」的率。15 重复能看见的是「某题从恒超时变成经常不超时」这种大跳，
不是 5pp。

## 3. 提议的效应量（待拍）

护栏侧 5pp 已经降级，不再为它扩样本。主检验要的是「明确改善」：

| 量 | 提议 δ | 理由 |
|---|---|---|
| 率（repair 恢复；以及若你仍想看超时/tool 失败） | **10pp** | 5pp 是护栏语言；主检验用 10pp 才配「明确」 |
| 延迟均值或 P50 | **20s** | 约剔 fast 后 P50（113s）的 18% |
| P95 | **20s** | spec 点名 P95；#68 剔 fast 后 P95≈188s，再剔 exception 后 ≈152s |

不采纳就改 δ 再套 §4 的公式，不必重抽 45 条。

公式与 #69 同形：率 `required_nr = 2v / (δ/1.96)²`；延迟把 v 换成 `σ²`。
分层纪律与领域侧相同：**恒 0 / 恒 1 / 崩溃编码的 0 不进池化 v**。

## 4. 450/臂 能不能判

延迟 σ 主用剔 `index-rebound-space` 的 40 条：均值 100.7s，sd 59.8s。
敏感度：再剔 5 条 `runner_exception` → n=35，均值 88.6s，sd 49.2s，P95 152s。
P95 用 2000 次 bootstrap 外推（粗；n=40 时 CI 被崩溃尾巴拉宽）。

| 指标 | v 或 σ | δ | required_nr | 450 够？ |
|---|---|---|---|---|
| 延迟均值/P50（σ=59.8） | 59.8s | 20s | **69** | **够，很宽裕**（450 时两臂差半宽 ≈8s） |
| 延迟均值/P50 | 同上 | 15s / 10s | 122 / 275 | 够 |
| 延迟均值/P50（再剔 exception，σ=49.2） | 49.2s | 20s | 46 | 更宽裕（半宽 ≈6s） |
| P95（n=40 含崩溃尾巴） | bootstrap | 20s | — | **刚够**：450 时两臂 P95 差半宽 ≈19s |
| P95（n=35 剔崩溃） | bootstrap | 20s | — | **够**：半宽 ≈7s |
| P95（含崩溃） | bootstrap | 10s | — | **不够** |
| repair 恢复 8/21（进入率 47%，v=p(1−p)=0.236） | 0.236 | 10pp | 进入 181 → 总 n≈**385** | **够** |
| repair 恢复（3 题题级样本方差均 0.267） | 0.267 | 10pp | 进入 205 → 总 n≈436 | **够**（贴着） |
| repair 恢复 | 0.236 | 5pp | 进入 725 → 总 n≈1540 | 不够（也不该为 5pp 扩） |
| 首轮超时 / tool 失败（剔 infra 后） | 题级近恒 | 5–10pp | — | **不可按率功效判**；只能看某题是否大跳 |
| 首轮超时 / tool 失败（把崩溃当 0，v=0.267） | 0.267 | 10pp | 205 | **作废**，见 §2 |
| cancel/resume/restart | 无 | — | — | **不可判**，#68 没注入 |
| Trace 条数对账 | 有事件则恒 1 | — | — | **不当功效题**。有事件却对不上 → 该臂不可发布（spec 已有） |

## 5. 读法

- **450 不是为 citations 护栏服务的。** 它碰巧盖住：延迟主检验、P95≈20s、repair 10pp。
- 用户「n 远小于 450」只对**延迟均值**成立（约 70）。对 repair 10pp 是「450 刚好」。
  对超时/tool 失败/lifecycle，问题不是 n，是**没方差或没样本**。
- **不够的项**不靠加样本硬凑：率类 5pp、lifecycle 注入、把结构常数当 Bernoulli。
  lifecycle 要等 §9.2 失败注入，另开一小段，不并进 900。
- 维护成本是工程账，45 条 live 算不出功效。
- #68 是旧 pin，**不能当新 pin 的 Arm A 基线**；本页只借方差结构。

## 6. 领域护栏（降级，不配 n）

「发布面带 citations 的记录率」只报分层点估计和区间，**>5pp 回退才停**。
分不出 5pp 可以接受，不扩样本。845 封存，不再当开窗门槛。

#68 数据题·有方差 4 题的该率：均值 0.20 / 0.40 / 0.40 / 0.40（见 `2026-08-17-tf-stratified-power.md`）。
开窗后按新 pin 再报，不把旧 pin 当基线。
输出级 `diagnostics.bindings` 的 ebo 是阶跃函数、23/45 未定义
（见 `2026-08-17-evidence-bound-output-rate-correction.md`）；报护栏必须写明未定义是计 0 还是排除。

## 7. 没做

- 没开 900。没切 8792。没动绊线参数。没改题集。
- 没跑失败注入，所以 lifecycle 三项空白。
- 5d 未做（不挡窗）。
- 没把 450 写成「那就开跑」。δ 你还没拍。
