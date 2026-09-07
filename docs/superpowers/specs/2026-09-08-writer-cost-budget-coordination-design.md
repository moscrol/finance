# 设计：写作成本进预算——把「模型写一次结论要多久」接进三处按 sol 标定的数

日期：2026-09-08
状态：**设计稿，未实施。** 判官窗那一处已单独修好并开 PR（#656，`R-20260908-01`，旁支 live 11/11 判官过）；本稿只管剩下互相咬合的三处。分支 `spec/writer-cost-budget-coordination`，基线 `gitea/main@2542f0ad`。
收据：`~/.finance-runtime/glm-ceiling-20260907/RECEIPT.md`（§1–§7，含逐轮读数与 `synthesis-reserve-floor.patch`）；`summary.json` / `readings.json` 为机器可读版。
父稿：

- 2026-09-06 用户决策「先找能力 max，再按超限的部分设约束」（生产启动器注释在案；PR #608 max 档）
- 2026-09-07 PR #646 `LLM_REASONING_EFFORT`（GLM-5.3 强制思考、只认 max/high/low）
- PR #656 判官窗跟合同档位走（本稿的先例：档位表放产品值、实测表放模型值、取大者）
- `intelligence/services/provider_latency.py` 模块 docstring（「那个地板是 provider 的属性，不是全局常数」；新增条目必须附实测）

用户立场（2026-09-07 口述，本稿立稿前提）：

> 「我希望先探究能力 max，而不是因为限制给不出完整的答案输出。」

---

## 0. 一句话

**一个模型侧的量——写一次结论要多少秒——被三处按 sol 标定的预算各自消费，且三处互相咬合；单独改任何一处，失败只是换个地方出现。** 三处一起改，验收判据是同题三发 completed ≥ 5/6、零 `repair_deadline_exhausted`。

三处：合成保留（`synthesis_reserve`，60s）、根账本把写作轮的模型时间记在研究额度里（`root_budget_for_policy` / `_consume_root_seconds`）、修复授予帽（`repair_seconds_cap_for("zhipu")` = 40s，按 glm-5.2 **不思考** p90 标的）。

**本稿不动 600s 档位表，不让 LLM 自选预算，不动出口硬层。** 放开的是「写结论」这一段的时间账，不是正确性。

---

## 1. 为什么现在做

### 1.1 GLM 思考臂在 max 档：研究预算没咬，写作预算咬了 [实测 2026-09-07，n=3/格]

同题三发（Q1 = 固态 vs 钠电近月对比，D5 = 冻结题「2026-06-11 可控核聚变」），GLM-5.3-flash，`LLM_REASONING_EFFORT` 三档，`ASK_EPISODE_BUDGET_STATUS=off`：

| 臂×题 | completed | 判官过 | 模型自停 | 用时 p50 / max | 失败形状 |
|---|---|---|---|---|---|
| max×Q1 | **3/3** | 3/3 | 3/3 | 550s / 660s | — |
| high×Q1 | 1/3 | 2/3 | 1/3 | 454s / 811s | r2 首块前停摆 75s 无重试 → failed；**r3 写作轮到点 → partial** |
| low×Q1 | 2/3 | 3/3 | 2/3 | 185s / 194s | 6 工具自报 partial |
| max×D5 | **3/3** | 3/3 | 3/3 | 437s / 440s | — |
| high×D5 | 3/3 | 2/3 | 3/3 | 485s / 543s | 修复前那发判官 unavailable |
| low×D5 | 2/3 | 3/3 | 3/3 | 115s / 190s | **零工具**只靠预取交 partial |

18 发里 `tool_budget_exhausted` 与工具超时几乎为零，全部由模型自停或写作/修复阶段收场。**研究预算不是天花板。** sol 同题参照：Q1 286s completed，D5 347s completed。

### 1.2 被切的那发：切在写作轮 [实测，high×Q1-r3]

研究轮每轮 ~115s（当时 zhipu 慢、三 sidecar 并发），模型剩 161s 才开始写；写作轮 7.3K token（≈5.5K 隐藏推理）要 200s+ → `deadline_exhausted` → 修复轮也没写完 → partial（判官仍过）。**60s 合成保留是按 sol 写 1.4–1.7K token 标的**；GLM 思考臂一次写作 3.3K–7.7K token。

### 1.3 写作成本本身 [实测，n=11 思考 run]

| 量 | 读数 |
|---|---|
| 单个写作轮输出 token | 3.3K–7.7K，p50 4.9K（含隐藏推理） |
| 解码速度 | 27.5–40.6 tok/s，p50 32.8 |
| 写作轮墙钟（估） | p50 ≈150s，p90 ≈210s；有下一轮可直接观测的三发：126 / 131 / 249s |
| 修复轮输出 token | 1.9K–6.8K（Q1 上 3/6 思考 run 需要修复） |
| sol 参照 | 规划轮 0.03–0.25K、写作 1.4–1.7K，无隐藏推理 |

### 1.4 单独抬合成保留：4/4 partial，更糟 [实测 2026-09-08 00:50–01:17]

把合成保留按模型地板抬到 240s（写作 p90，或写作 p50 + 修复 p50），其余不动，同臂同题 Q1/D5 各一发（high / max）：**4/4 `repair_deadline_exhausted` / partial**，而同臂无地板时 5/6 completed。地板确实生效（工具批帽 540 → 360），模型也确实更早开始写（剩 285–348s，之前 161s），但：

- max×Q1：写作轮 181s 完成时墙钟还剩 167s，却报 `deadline_exhausted`——**根账本溢出**（§2 第二行）。
- high×Q1：第一次 finish **completed**，判官要求修复，修复轮 6.8K token 对着 40s 授予 → `repair_deadline_exhausted` → **已完成的稿被降成 partial**（§2 第三行）。

这就是「改一处失败换地方」的现场。代码保留在 `synthesis-reserve-floor.patch`（6 条测试、变异过、门禁过），本稿 P2 直接回放。

---

## 2. 机制：三本账怎么咬合

| # | 机制 | 代码 | 60s 保留下（现状） | 240s 保留下（§1.4） |
|---|---|---|---|---|
| 1 | deadline 数学：`planning_timeout = min(llm_timeout, remaining − reserve)`，< 8s 强制收笔；写作轮拿 `synthesis_timeout = min(llm_timeout, remaining)` | `ResearchDeadline.stage_timeout / synthesis_timeout`；`agent_episode` 主循环 | 模型可研究到剩 68s 才被叫停；GLM 写作 150–200s 装不下 | 剩 248s 收笔，写作装得下 ✅ |
| 2 | 根账本 `initial_seconds = total − reserve`，**所有模型轮（含写作轮）的耗时都 `consume_seconds` 到这本账**，溢出 → `deadline_exhausted`（有 `_carry_just_written_finish` 补救，但补救出来的是 partial） | `root_budget_for_policy`、`_consume_root_seconds`、`agent_episode` 第 920 行附近 | 540：GLM 累计模型时间 400–570，偶尔溢出 | **360：研究 251 + 写作 181 = 432 必溢出** ❌ |
| 3 | 修复授予 = `min(repair_seconds_cap_for(provider.name), 余量)`；余量 = `hard_seconds_cap − allocated` = reserve；`"zhipu"` 帽 40s 按 glm-5.2 不思考 p90 34.4 标 | `provider_latency._REPAIR_SECONDS_BY_PROVIDER`、`repair_budget`、`InMemoryRootBudgetLedger.grant` | 帽 40 / 余量 60：GLM 思考臂修复 60–210s，短的偶尔挤过 | 帽 40 / 余量 240：帽仍是 40，**修复必败，且会把 completed 降成 partial** ❌ |

一句话：reserve 在第 1 本账里**保护**写作，在第 2 本账里却把研究额度**让出去而写作照样从研究额度扣**，第 3 本账的帽根本没看模型。抬 reserve = 同时缩账本 = 写作轮在账本上溢出得更早。

另外两处相关但本稿**不改**的事实（记录，避免再查一遍）：

- 75s 单次调用超时在流式路径下是**字节间隔**超时，300s 的轮次照样跑完；它只在 provider 首块前停摆时咬（high×Q1-r2），而单 provider 链的瞬态重试复用同一个 `timeout=remaining` 窗，超时型失败结构上不可能重试（`_complete_provider_chain`）。另案。
- `provider.name` 不能当模型键：生产链首 `name="zhipu"` 实际是 sol@cockpit（启动器注释在案）。所以 P1 的键必须是（配置模型名前缀，effort），与 P2 同一把尺。

---

## 3. 原则

1. **产品侧数字与模型侧数字分开。** 档位表（30 / 90 / 240 / 600，工具次数，保险丝）回答「用户愿意等多久」，与模型无关，本稿不动。模型侧数字（写一次结论几秒、修一次几秒、判官一次几秒）只从实测表来，键是（模型名前缀，effort），**不是 provider 名**。这与 PR #656 的做法同构：`derive_stage_caps` 放档位值，`provider_latency` 放实测值，取大者。
2. **「不由模型自选预算」的红线不动。** 地板是部署侧按实测填的表，不是 LLM 说的；`GLMAgentRuntime.synthesis_reserve_for_task` 的 docstring「never by model choice」指的是 LLM 不能给自己加预算，与部署侧模型档案不冲突。
3. **三刀一起上，或一刀都不上。** §1.4 已证明单独上 P2 更糟；单独上 P0 无害但不解决被切；单独上 P1 在余量 60 下无事可做。验收判据只对三刀合体成立。
4. **sol 逐字节同前。** 未命中实测表的模型（sol、未开思考的 GLM）三处数字与请求体不变；这是每条测试的第一条断言。

---

## 4. 三刀

### 4.1 P0：账本——写作轮的时间从余量扣，不从研究额度扣

现状：`initial_seconds = total − reserve` 是研究额度；余量 `hard − initial = reserve` 只给修复铸窗；而 finalization 之后的写作轮照样 `consume_seconds` 研究额度，溢出走补救。

改法（两个候选，取 a）：

- **(a) 写作轮按实际耗时事后铸窗。** finalization 之后的模型轮返回后，先向账本 `grant` 一笔 `seconds_granted = min(实际耗时 E, 余量)`（复用 `repair_budget` 的 grant 对象，`grant_id` 用 `f"{episode_id}:finalization:{llm_calls}"` 保证幂等），再 `consume_seconds(E)`；修复从**剩下的**余量铸。**不能在收笔时一次性把整段 reserve 铸出去**——那会把修复余量吃光（reserve 240 全给写作 → allocated 600 = hard cap → 修复一秒也铸不出）。按实际耗时铸，写作 p50 150 之后还剩 90 给修复，正好是 P2 取 240 的算术。语义与「reserve 就是写结论的钱」一致，`initial_seconds` 公式不动；sol 路径下写作轮 15–40s → 多一笔 15–40s 的 grant，累计模型时间 100s 量级的 sol 永远碰不到溢出，请求体逐字节不变（收据 `allocated_seconds` 多一笔 grant 是唯一可见变化，写进验收）。
- (b) 写作轮改 `settle_seconds`（只扣不抛）。一行改动，但绕开了账本作为唯一预算权威的设计，且让 `_carry_just_written_finish` 那条补救路失去存在理由。不取。

P0 的成立条件：写作轮拿到的额度 = reserve，所以 **P0 的效果上限由 P2 决定**；P0 单独上时 reserve 仍是 60，只是把「溢出 → 补救出 partial」变成「有 60s 额度 → 仍可能溢出」，无害无益。

### 4.2 P1：修复帽按模型，且与余量一起定

现状：`repair_seconds_cap_for(provider.name)`：openai 30 / zhipu 40 / 默认 30，全部是不思考模型的实测。

改法：`provider_latency` 加 `repair_seconds_floor_for(model_name, reasoning_effort)`，(glm-5.3*, max/high) → **200s**（修复轮 1.9K–6.8K token @ 33 tok/s ≈ 60–210s，取 p90 量级；n=6 修复轮，小样本，上线后按收据回调）。组合根 `app.py` 在 `repair_seconds_cap=` 处取 `max(provider 帽, 模型地板)`，与 P2 的装配点同一段代码。

修复能铸的余量上限是 reserve（§2 第三行）：**P1 的 200 只有在 P2 把 reserve 抬到 ≥ 写作 + 修复之后才有意义**——这就是 P2 取 240 而不是 210 的原因（写作 p50 150 + 修复 p50 90）。若要修复 p90 也装下，reserve 要到 ~360（600 的 60%），研究只剩 240s，低于实测研究阶段 270–300s——**不取**；修复 p90 的单子接受 partial，记进 §5 的预期失败率。

### 4.3 P2：合成保留按模型地板——回放 `synthesis-reserve-floor.patch`

`provider_latency.synthesis_reserve_floor_for(model, effort)`：(glm-5.3*, max/high) → 240s；`app.py` 装配 `continuous_glm` 时对 `GLMAgentRuntime.synthesis_reserve_for_task` 取地板；sol / low / 未设 effort 返回 None 逐字节同前；`ASK_SYNTHESIS_RESERVE_FLOOR` 为实验逃生阀。6 条测试、变异（清空表 3 红）已在补丁里。

P2 单独上的后果已在 §1.4：4/4 partial。**只能与 P0、P1 同批。**

### 4.4 顺序与切流

一个 PR 三刀（或三个 PR 同批合、同次切流），预注册三行（`claim_ledger_id.py` 取号），每行的失败形状写死为「另两刀未上时的形状」以便归因。切流走既有五步（bootout → 软链 → 账本 switch → bootstrap），回滚锚照常。

---

## 5. 验收（缺一条不算）

旁支 sidecar（修复分支，GLM-5.3-flash，`LLM_REASONING_EFFORT=max` 与 `high` 各一条，`ASK_EPISODE_BUDGET_STATUS=off`，users 目录按端口独立），同题 Q1 / D5 各 **3 发**：

1. completed ≥ 5/6（每 effort），`repair_deadline_exhausted` = 0，`deadline_exhausted` = 0。
2. 判官 passed/repaired 6/6（PR #656 已保证，此处只防回归）。
3. 收据可见地板生效：`batch_grant_asked = 360`（= 600 − 240）；`allocated_seconds` 含一笔 `finalization` grant，数值 = 写作轮实际耗时；修复轮 `granted_seconds = min(200, 240 − 写作实际耗时)`，写作 ≤ 150s 的单子 ≥ 90（不再是 40）。
4. 写作轮 `remaining_seconds_at_entry ≥ 240`（收笔不再拖到剩 161s）。
5. **sol 回归**：生产 8792 同题 Q1 一发，`synthesis_reserve` 仍 60、`batch_grant_asked` 仍 540、修复帽仍 40、请求体首轮字节稳定（`finance-base-ab` ±3 硬门）。
6. 预期失败率写明：修复 p90 单子（修复轮 > 90s 且写作已用满 150s）接受 partial；六发里出现 ≤ 1 发属预期，≥ 2 发 refuted。

---

## 6. 非目标 / 红线

- 不改 `PRODUCT_MAX_SECONDS = 600`、工具次数、LLM 调用保险丝——用户愿意等多久是产品决策，不随模型变。
- 不给 LLM 自选预算：地板来自部署侧实测表；`runtime_budget` 注入的提示词本稿不动（`ASK_EPISODE_BUDGET_STATUS=off` 是 GLM 出口的启动器配置，非代码）。
- 不动出口硬层（`admit_finish` / 判官 / 来源分档）。
- 不动 75s 单次超时与单 provider 重试（另案，§2 末）。
- 不把 GLM 切回生产：本稿只让 GLM 思考臂在 max 档能稳定交完整答案，供「模型是第一刀」的对照实验用；生产出口仍是 sol@cockpit。

---

## 7. 已知反对意见与回应

- **「直接开预算提示词就不会被切了。」** 会。19:49 那发就是：模型看到「剩 33%」按提示收敛，3 轮 partial；关掉提示同题 7 轮 completed。提示词按 sol 每轮 10s 标的 0.3 阈值，对 90s/轮的模型等于提前两轮喊停。两种失败都是同一个数在 GLM 上的两个方向，正解是把写作成本接进预算，不是让模型自己猜。
- **「换 low 就快了。」** low 研究量掉 60%（Q1 首发 6 工具 53 条证据 vs max 122–139），D5 一发零工具直接写。快但不稳，不适合当正经研究档（§1.1）。
- **「high ≈ max，用 high 省 17%。」** 形状相近，但 high 三发 Q1 只 1 发干净完成，max 三发全完成；n=3 分不清是 effort 还是当晚 zhipu 并发延迟。本稿对 max / high 同一套数。
- **「为什么不把 reserve 从写作 token 自适应算。」** 运行时估写作 token 需要先写；且方差大（3.3K–7.7K）。先用实测表钉住，收据攒够再谈自适应（与 `provider_latency` 拒绝自适应的理由同）。

---

## 8. 成立条件

- 实测全部来自 2026-09-07 22:26–01:17，zhipu coding 端点，三 sidecar 并发；解码速度 27.5–40.6 tok/s 含并发影响，单发时可能更快（第一轮 43 tok/s）。
- 每格 n=3（写作成本 n=11，修复轮 n=6）。240 / 200 两个数上线后按收据回调，回调走 `provider_latency` 表 + 台账 outcome，不走感觉。
- `LLM_REASONING_EFFORT` 语义按 PR #646：设了就 `thinking=enabled + reasoning_effort=值`，GLM-5.3 系列只认 max/high/low；未设时 GLM-5.3 是否思考取决于端点（09-05 glm-5.3 标准档收据 22–265 token/轮、不思考），本稿的地板只在 max/high 生效。
- 判官侧的数（PR #656）独立于本稿；本稿验收第 2 条只防回归。
