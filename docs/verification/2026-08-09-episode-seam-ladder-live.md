# P7 live smoke 实跑 — 消融实验阶梯的首份真实 provider 证据（2026-08-09）

> **口径**：三次 live 实跑，worktree `/Users/a77/finance-workspace-private`，
> 分支 `fix/seam-ladder-receipt-diagnostics`，解释器 `.venv-workbench/bin/python`，
> provider `openai / gpt-5.6-terra / https://x.ailzd.com/v1`（从
> `~/.local/bin/start-finance-workbench` 提取的生产 env，**不是** `.env.workbench`）。
> 收据在 `/Users/a77/.finance-runtime/seam-ladder/`（设计上不进 git）。
> 每条读数只对其 `source_revision` 成立。

---

## 0. 一句话

P7 从 2026-08-09 起**不再被环境卡住**，三次实跑跑通。它立刻暴露了两个
**离线 44 条断言永远看不到**的缺陷（收据丢判据、live judge 根本没接线），
两个都已修；还证明了 **S3 那道题本身出错了**——它的前提与数据相反。

---

## 1. 先推翻交接文档的一条前提

`docs/handoffs/2026-08-09-market-routing-handoff.md` §4 写 P7「三项 preflight 均不满足
（环境事实，非代码回归）」。**2026-08-09 复核：三项全部满足** [实测]

| preflight 项 | handoff 当时 | 复核 |
|---|---|---|
| 市场快照 ≥ fixture as_of | ❌ 无 2026-08-07 | ✅ `latest_market_date()` = `2026-08-07`，与三条 case 的 `as_of` 齐平 |
| continuous mode | ❌ 未开 | ✅ `start-finance-workbench:102` 即 `export ASK_CONTINUOUS_RUNTIME="on"` |
| LLM provider 解析 | ❌ 解析不到 | ✅ `detect_providers()` → `openai / gpt-5.6-terra`；中转 `GET /v1/models` 200/1.3s |

```
live_preflight(...) → ready = True, failures = ()
```

**"阻塞"的真实形状不是环境缺东西，是跑 ladder 的 shell 没有生产 env。**
裸 shell 里 `providers=0`、`ASK_CONTINUOUS_RUNTIME=None`；带上生产 export 段三项立刻全绿。

> ⚠ **`.env.workbench` 是陷阱**：它仍写着 `LLM_MODEL=glm-5.2` /
> `open.bigmodel.cn`，而 GLM 是 2026-08-05 已退役那条线。`source .env.workbench`
> 是最顺手的动作，preflight 会**照样 ready=True**——它只检查"有没有解析到 provider"，
> 不检查"解析到的是不是产品线"。产出的收据会挂着 `glm-5.2` 的戳而看起来完全正常。
> 跑完第一件事是核收据里的 `preflight.model`。

---

## 2. 三次实跑读数

| 收据 | revision | 时刻(UTC) | 说明 |
|---|---|---|---|
| `2026-08-09-live.json` | `8640d2c7-dirty` | 11:35:31 | 基线，收据未插桩 |
| `2026-08-09-live-instrumented.json` | `0f789b65-dirty` | 12:16:41 | 收据已插桩，judge 未接 |
| `2026-08-09-live-judge-wired.json` | `0f789b65-dirty` | 12:22:14 | judge 已接线 |

### S1 `next-session-index`（能力面只有 `market_data`）

| | run A | run B | run C |
|---|---|---|---|
| `stop_reason` | `repair_model_unavailable` | `deadline_exhausted` | `repair_model_unavailable` |
| `tool_calls` | 1 | 0 | 1 |
| `structural_status` | partial | **failed** | partial |
| `latency_seconds` | 111.015 | 70.527 | 111.149 |
| `gaps` | （未记录） | 研究截止时间已到 | **`LLM 调用失败（TimeoutError）`** |

**三次跑出两种失败形态，都是预算/超时族。** run C 拿到了错误原文：**TimeoutError** [实测]。
run B 的 `tool_calls=0` 意味着 episode 连 `market_data` 都没调到就耗尽了截止时间——
即 handoff §2.2 记的"首轮饿死"形态。

> ⚠ **三次采样不足以给 S1 定一个根因。** 形态在 run 间会跳，这个量是高方差的。
> 要定性必须提高采样，不要用 2-3 次的排序下结论。

### S3 `weekly-market-cause`（四个能力全开）

| | run A | run B | run C |
|---|---|---|---|
| `structural_status` | completed | completed | completed |
| `structural_issues` | [] | [] | [] |
| `tool_calls` | 3 | 4 | 3 |
| `draft_chars` | （未记录） | 409 | 398 |
| `semantic_issues` | （未记录） | `semantic judge unavailable` | `semantic judge transient provider error` |

S3 的**结构层三次全部闭合**：required outputs 无缺、evidence 齐、零重复查询。

### 按设计规格 §7.2 的三条完成判据

| 判据 | 结果 |
|---|---|
| S1 schema 不出现 `mainline_context`/`news_search`/`evidence_search` | ✅ `tool_schema_names = ["market_data"]` |
| S3 tool calls 与 evidence hashes 确有已开放能力 | ✅ 4 能力在 schema、3-4 次调用、17 个 evidence hash |
| semantic verifier 为 `passed` 或 `repaired` | ❌ 三次都是 `unavailable` |

**2 过 1 不过。过的那两条正是阶梯要证明的东西**——阶段隔离在真 provider 下成立，
S1 确实只看得见 `market_data`。不过的那条，根因见 §3.2。

---

## 3. 两个只有 live 才看得见的缺陷（均已修）

### 3.1 收据只记状态不记判据 → `0f789b65`

`unavailable` 在 `episode_semantic_verifier` 有**六个返回点**（contract 缺失 /
frame-contract hash 不匹配 / structural partial 不予放行 / 空 public draft /
judge 截止耗尽 / judge 瞬时故障），而 `continuous_turn_adapter` 在**验证器根本没产出
outcome** 时也记同一个词。**七种不同缺陷共用一个字**，收据只存这个字。

run A 因此只能靠读源码反推病因，而**反推错了**：我从代码推断 S3 是"空 public draft"，
插桩后实测 `draft_chars=409`——不是空的，真因是 judge 侧。

分辨它们所需的事实本来就在 `private_artifact` 里，只是收据丢了。新增四项
（offline / live 两条路径对称，两处 record 构造原本就是逐字复制）：

| 字段 | 分辨什么 |
|---|---|
| `semantic_verifier_ran` | 块缺失 = 验证器没跑，与它可能给出的任何裁决都是不同的失败 |
| `semantic_issues` | 验证器自己的 issues 元组 |
| `draft_chars` | 0 = 模型什么都没产出；>0 且带"空 draft" = 句子解析器不认。两个不同 bug 同一症状 |
| `gaps` | `_stopped_outcome` 把 `turn.error` 放这里，停机 episode 的 provider 错误原文唯一幸存处 |

> **可迁移**：门禁记了状态没记依据，等于把复核成本转嫁给下一个人。
> 收据的价值不在结论，在**结论可被独立重算**。

### 3.2 live judge 根本没接线 → `0648c086`

收据把 live 路径标为 `"production_llm_judge"`，但 `run_live_stage_case` 构造的是
**无参数的** `SemanticEpisodeVerifier()`——没有 `primary_judge`、没有 `finalizer`。
验证器没有任何东西可调，judge 循环耗尽重试后落到 `:1196` 的
`"semantic judge unavailable"`。**每条 rung、每次都是。**

于是第三条完成判据**在构造上就不可能满足**，与被测的接缝本身无关。

而离线路径用的是 `OfflineSemanticVerifier` 桩，硬编 `judge_status="passed"`——
它的 docstring 明写「**must not be read as evidence that the production LLM judge
works**」。所以离线 44 条全绿，从来没暴露这一点。

改为与 `intelligence/api/app.py:267/274/345` 同构（`EpisodeFinalizer` 建一次、
runtime 与 verifier 共用，verifier 拿 `primary_judge=client`）。前后对照 [实测]：

```
S3 semantic_issues   改前  "semantic judge unavailable"          ← 根本没被调用
                     改后  "semantic judge transient provider error"  ← 被调用了、provider 侧失败
```

**第三条判据由不可达变为可达。** judge 现在真的在跑，剩下的是 provider 侧稳定性。

> **可迁移**：**桩的存在本身不是问题，桩被当成证据才是。** 这个仓的桩把
> "别拿我当证据"写进了 docstring，做得对；出问题的是 live 路径**声称**接了真的、
> 实际没接。**标签写的是意图，不是生效值——验收要断言生效值。**

---

## 4. S3 那道题本身是坏的（未修，待定）

run B/C 的 `gaps` 里，模型自己说了：

> 「用户问题的**"本周下跌"前提与截至 2026-08-07 的结构化周度收盘数据相反**。」

查库核对 [实测]，`fact_market_daily`：

| trade_date | sh_index_close | advancers | limit_up |
|---|---|---|---|
| 2026-07-31 | 3832.262 | 4691 | 99 |
| 2026-08-03 | 3809.663 | 4005 | 75 |
| 2026-08-04 | 3822.285 | 3642 | 138 |
| 2026-08-05 | 3878.430 | 3725 | 103 |
| 2026-08-06 | 3900.352 | 2789 | 79 |
| 2026-08-07 | 3940.037 | 2856 | 74 |

**那一周涨了 +2.81%，且 08-03 起逐日单调上行。** 题面问"本周行情下跌的主要原因"，
前提为假。

所以 S3 **不适配它自己的用途**：设计规格要它证明"可达 public answer"，但一个行为
正确的模型**必须拒绝**为一次没发生的下跌归因。这道题永远落在 gap 区，**不是运行时缺陷**。

两点值得单独记：

1. **这是产品的好消息，不是坏消息。** 模型没有顺着假前提编一套下跌归因，
   而是查了数据、指出前提与数据相反。这正是我们想要的行为。
2. **离线 S3 报 `semantic=passed status=completed`。** 脚本模型不管前提真假，
   照常返回一份格式正确的 draft。**离线门禁在一道真实系统会正确拒答的题上发绿光**——
   这是本轮最能说明"为什么必须跑 live"的一条。

### 4.1 已修：「下跌」→「上涨」，改前重跑了 floor 表

设计规格 §3.1 明写 stage floor 由 `ResearchTaskContract.__post_init__` 的
`mandatory ⊆ allowed` 不变量推导，**换题必须重跑 floor 表，不要只改字符串**。
照做了，而结果推翻了直觉 [实测]：

| 候选题面 | question_type | 推导 floor | required_outputs | mandatory |
|---|---|---|---|---|
| 原「本周行情**下跌**的主要原因」 | `market_cause` | S3 | 5 项 | `market_data, news_search` |
| 「本周行情**上涨**的主要原因」 | `market_cause` | **S3** ✅ | 5 项 | 同上 |
| 「本周行情**走强**的主要原因」 | `market_cause` | **S3** ✅ | 5 项 | 同上 |
| 「本周行情的**主要驱动因素**」 | `general_finance_qa` | **S2** ❌ | **2 项** | `market_data, mainline_context` |
| 「本周行情**变化**的主要原因」 | `general_finance_qa` | **S2** ❌ | **2 项** | 同上 |

**中性措辞会把这道题静默降级到 S2，并把 required_outputs 从 5 项砍到 2 项
（`causal_chain` / `cause_attribution` / `counterpoint` 全部消失）——等于抽掉整个因果测试，
而 fixture 里的 `expected_stage_floor` 字段还写着 S3。**
方向词正是路由到 `market_cause` 的信号。"换个不带前提的中性说法更稳健"这个直觉是错的。

采用「上涨」（与原题最小差分、且事实为真）。fixture 里留了 `note` 字段记录本次推导；
`load_cases` 忽略未知键，已实测不影响加载。

### 4.2 换题后实测：前提异议消失，但暴露了下一层

`2026-08-09-live-fixture-fixed.json`（`910c03f0-dirty`）：

| | 换题前(run C) | 换题后 |
|---|---|---|
| S3 `gaps` 含"前提与数据相反" | **是** | **否** ✅ |
| S3 `tool_calls` | 3 | **6** |
| S3 `stop_reason` | `model_finish` | `repair_deadline_exhausted` |
| S3 `structural_status` | completed | partial |
| S3 `latency_seconds` | 68.9 | 111.2 |

前提问题解决了。而题面变真之后模型**干得更多**（工具调用 3 → 6，真去找因果证据了），
然后**在修复阶段耗尽截止时间**。

**至此三轮排查的混淆项都被移除，只剩一个假设**：S1 与 S3 现在都是纯粹的
deadline/预算失败（S1 `deadline_exhausted` 70.5s / `tool_calls=0`；
S3 `repair_deadline_exhausted` 111.2s / `tool_calls=6`）。
是 provider 慢，还是预算算术给的时间本来就不够——见 §5。

---

## 5. provider 稳定性实测 — 超时不是 provider 的错，是预算算术

### 5.0 先撤回本文上一版的一个断言

上一版写「**这条中转在 episode 量级的 prompt 下不稳**」。**这句话是错的，已实测推翻。**
它是从两次 episode 超时反推出来的，没有独立测过 provider。真实读数见下。

### 5.1 我的第一版探针测的是它自己的 bug（24/24 假失败）

第一版探针用裸 `urllib` 直连中转，**24 次调用全部 HTTP 502
`Upstream access forbidden`**，两个模型无一幸免。看起来像"上游全挂"。

实际原因：`urllib` 默认发 `User-Agent: Python-urllib/3.12`，中转把它当脚本流量拦掉。
只改 UA 就从 502 变 200 [实测]：

```
UA=Python-urllib(默认)  → HTTP 502  3.3s
UA=curl/8.7.1           → 200      26.7s   # 同一把 key、同一个 URL、同一份 body
```

**这个坑本仓已经写在 `intelligence/services/llm_refine.py:52-59`**，连症状描述都一样：
「症状极具误导性：错误码是 502（看起来像上游挂了），而 curl 手测恒通，于是很容易
误判成"网关不稳定"」。生产走 `_LLM_USER_AGENT = "finance-workbench/1.0"`，**不受影响**。

> **教训**：造新探针之前先搜有没有、以及生产是怎么发请求的。我绕开了生产客户端
> 自己写 HTTP，于是把一个已被记录并已被修复的坑重新踩了一遍，还差点把它写成
> "provider 挂了"的结论。**测量工具本身也是被测系统的一部分。**

### 5.2 修正 UA 后的真实读数

15K 字符 prompt、**短输出**（问一句话能答完的问题），每模型 10 次 [实测]：

| model | ok/total | p50 | p90 | max | min |
|---|---|---|---|---|---|
| `gpt-5.6-terra` | 9/10 | **4.3s** | 21.8s | 21.8s | 3.5s |
| `gpt-5.6-sol` | 10/10 | **5.3s** | 6.1s | 6.1s | 3.5s |

（terra 那 1 次失败是 502 `Upstream service temporarily unavailable`，与 5.1 的 UA 502 不同因。）

**大 prompt 根本不慢。** p50 4-5 秒，离 S1 的 111s 差两个数量级。
所以"prompt 大 → 超时"这条因果不成立。

### 5.3 真正的自变量是**输出 token**，不是输入

同一个 15K prompt，把提问换成"写一份尽可能详尽的市场结构分析"，每档 3 次 [实测]：

| model | 耗时 | 出参 tokens | 约合速率 |
|---|---|---|---|
| `gpt-5.6-terra` | 26.1 / 28.9 / 34.8 / 37.8 / 50.4 / 75.9 s | 1168–3967 | **≈ 45–52 tok/s** |
| `gpt-5.6-sol` | 50.7 / 53.9 / 70.6 / 74.0 / 75.7 / 91.4 s | 1907–3110 | **≈ 34–43 tok/s** |

延迟基本就是"出参 token ÷ 速率"。**terra 比 sol 快约 30%**——
08-08 那次 sol→terra 的方向在这条轴上站得住，而这次是 6 样本且按 token 归一，
比当初 2-3 次裸延迟读数硬得多。（仍只是延迟轴，**不含质量**。）

### 5.4 中转**不认** `max_tokens`，也不认 `max_completion_tokens`

[实测] 请求 10，实得 416 / 351，且 `finish_reason=stop` 而非 `length`——
**限制根本没被应用，模型跑到自然结束**：

```
max_tokens=10            → finish_reason=stop  completion_tokens=416
max_completion_tokens=10 → finish_reason=stop  completion_tokens=351
```

§5.3 里 `max_tokens=60` 的三次实得 1849 / 3967 / 2562，也是同一回事。

**这是硬约束：不能靠调 token 上限来给生成时间设天花板。** 出参长度由 prompt
的指令决定，不由参数决定。

### 5.5 结论：首轮窗口落在 provider 延迟分布的中间，且借用机制在阶梯里空转

> ⚠ **本节上一版的 "首轮 ≈25s" 是错的，此处更正。** 那个 25s 是
> `start-finance-workbench` 注释里**生产 8792 修复前**的读数（26.67s），
> 我把它套到了阶梯上——既不是阶梯的配置，也不是修复后的值。实际算出来见下。

#### 阶梯的真实首轮窗口 = 69.77s，而 S1 卡在 70.5s

按 `_opening_planning_timeout` 的算法对阶梯 S1 的 context 实算 [实测]：

```
case.timeout      = 180.0
synthesis_reserve = 20.00s
常规首轮切片 base  = 69.77s
可借余量           = 0.00s        ← 借用机制在这里完全空转
借入后首轮窗口     = 69.77s       (上界 llm_timeout=75.0)
```

对照 S1 的实测 `latency_seconds`：**70.478 / 70.527s**（两次 `deadline_exhausted`，
`tool_calls=0`），以及 111.0 / 111.1s（首轮 69.77 + 修复阶段）。
**S1 就是卡在这个窗口上，一秒不差。**

#### 为什么借用会空转：阶梯没接生产的 reserve 分配

`_opening_planning_timeout` 借的是 `synthesis_reserve` **超出地板的部分**，
而 `MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS = 20.0`：

| 路径 | 传 `synthesis_reserve_for_task` | 实得 reserve | 可借 |
|---|---|---|---|
| 生产 `intelligence/api/app.py:366` | ✅ `GLMAgentRuntime.synthesis_reserve_for_task` | standard 60s（`market_cause`/`market_watch` 75s） | 40~55s |
| 阶梯 `run_episode_seam_ladder.py` | ❌ **一个字都没传** | tier 默认 **20.0**（`research_contract.py:393`） | **0** |

`borrowable = max(0, 20.0 − 20.0) = 0`。**对 standard 档，只要没人显式传更大的
reserve，这个修复就是死代码。**

这与 §3.2 的 judge 未接线是**同一类缺陷**：阶梯号称复刻生产，却漏掉了生产的接线参数。
两处都不是算法错，是**装配错**。

#### 真正的成因：窗口落在分布中间，不是"远远不够"

把 §5.3 摆进来：terra 长输出实测 **26.1 / 28.9 / 34.8 / 37.8 / 50.4 / 75.9s**，
另有一次冒烟 6795 token / **135s**。

**69.77s 的窗口不是"远远不够"，是正好卡在这条分布的中间。** 分布左半边能过、
右半边过不去——这才是 S1 三次跑出两种失败形态（`deadline_exhausted` vs
`repair_model_unavailable`）的原因。上一版把它归因为"预算切片本来就不够"，
方向对但量级判断错了。

而 §5.4 说明**堵不住出参**，所以可行方向：

1. **先让阶梯接上生产的 reserve 分配**（补 `synthesis_reserve_for_task`）——
   在此之前，阶梯量到的任何预算行为都不代表生产
2. 让 finish 阶段产出更短的 draft（**收窄结构，不是写"请简短"**——
   handoff §2.2 已记录过祈使句无效、结构收窄有效）
3. 抬 `llm_timeout` 上界（现 75s，已低于实测长输出的尾部）
4. 换更快的模型/端点

**不要先怀疑模型能力，也不要靠加重试**：重试只会把同一个窗口重踩一遍。

### 5.6 已修：按生产的方式分配 reserve（对表控制面不变量第 1 条）

对照 `agent-memory/10_knowledge/agent-control-plane-five-invariants.md` 第 1 条
**「预算单一权威」**——同一个 standard 档，生产算出 60s、阶梯算出 20s，
两处各算一遍算出两个答案，正是该不变量要防的形状。

改动只有一处：`stage_derivation` 在 `build_episode_context` 时补上
`GLMAgentRuntime.synthesis_reserve_for_task(...)`。前后实测：

| | 改前 | 改后 |
|---|---|---|
| `synthesis_reserve` | 20.00s | **60.00s** |
| 可借余量 | 0.00s | **40.00s** |
| 首轮窗口 | 69.77s | 69.75s（借用把它补回来了） |

**首轮几乎没变，变的是合成侧从 20s 变 60s。** 而 §5.3 实测一次研究型回答要
26–91s——原来那 20s 从一开始就写不完一个答案。

live 前后对照（同一 fixture、同一 provider）[实测]：

| | 未接生产预算 | 接上后 |
|---|---|---|
| S1 `structural_status` | `failed` | **`completed`** |
| S1 `missing_outputs` | 5 项 | **`[]`** |
| S1 `draft_chars` | 0 | **471** |
| S1 `stop_reason` | `deadline_exhausted` | **`model_finish`** |
| S1 `tool_calls` | 0 | 1 |
| S3 `missing_outputs` | 5 项 | **1 项**（仅 `cause_attribution`） |
| S3 `draft_chars` | 0 | **382** |
| S3 `stop_reason` | `repair_deadline_exhausted` | **`repair_model_stop`** |

**一处装配修复把 S1 从整体失败推到结构完成。**

> 🔁 **§5.7 的结论已被 §5.11 的直接证据推翻——先读 §5.11 再读本节。**
> 本节保留原文，因为出错的方式本身值得留档：我把「remedy 无效」错读成了
> 「diagnosis 不成立」。

### 5.7 一个 refuted：judge 的窗口不是它失败的原因

`refuted` 按控制面文档的纪律记下来——它比一条侥幸成功的补丁有价值。

**动手前写下的预测**：judge 三次尝试窗口实算为 `(15.0, 7.5, 7.5)`s，
而 §5.2 实测 terra 短输出 p90 = 21.8s > 15s。若 judge 失败源于窗口过小，
把 `MAX_SEMANTIC_JUDGE_WINDOW_SECONDS` 由 30 抬到 90（窗口变
`(25, 25, 25)`）后，`semantic_status` 应转为 `passed` 或 `repaired`。

**实测结果：预测不成立。** semantic 仍是 `unavailable`，而且**整体更差**——
两条 rung 的 `draft_chars` 都回到 **0**，`semantic_issues` 退回
「missing required output …」，即 episode 连草稿都没产出。

**原因**：judge 窗口与草稿生成**抽的是同一笔 synthesis reserve**。
`total_window = deadline.synthesis_timeout(min(90, 25×3))` 把最多 75s 划给 judge，
finish 阶段就没得写了。**这两者是零和的，不是各自独立的旋钮。**

改动已还原（`MAX_SEMANTIC_JUDGE_WINDOW_SECONDS = 30.0`），未提交。

> ⚠ 仅 1 次采样，且本系统已多次表现出 run 间方差。
> 能确证的只有**「窗口过小」这个假设不成立**，不能据此反推"30 就是最优值"。

另一条支持它不是超时的证据：判定接线修好后共 6 次 judge 调用（3 次 live × 2 rung）
**全部失败**。若真是 p90 尾部超时，按 §5.2 的分布应有约 8 成成功，6/6 全败的
概率约 0.6%。**系统性失败，不是尾部。**

### 5.8 装配缺口第三处：绝对截止（已修）与随后的稳定性采样

补上 `deadline_expires_at`（对表控制面不变量第 5 条）后，**judge 第一次给出裁决**：
S3 `semantic_status = repaired`，且它抓到的是真东西——草稿把「成长主线获得增量资金
推动」写成可核验主因，而已绑定证据只支持指数/成交额/板块量价。

**但那一次不可复现。** 同一 revision 连跑取样：

| run | S1 结构 | S1 判卷 | S3 结构 | S3 判卷 |
|---|---|---|---|---|
| 1 | completed | unavailable | partial | **repaired** |
| 2 | partial | unavailable | completed | unavailable |
| 3 | completed | unavailable | partial | unavailable |
| 4 | — | preflight blocked | — | — |
| 5 | — | preflight blocked | — | — |

**judge 成功率 1/6 个 rung-attempt。** 上一版据单次 `repaired` 写下的乐观口径按此更正：
三处装配修复把系统从**「必然失败」推到「偶尔成功」，但没有一项是稳定的**。
结构层同样不稳（S1 completed 2/3、S3 completed 1/3）。

> ⚠ 一个**未解释**的模式：三次里**每次都恰好只有一条 rung completed**，从未两条都成、
> 也从未两条都败。已排除最像的机制——root budget 按 rung 隔离（`episode_id` 唯一，
> `stage_derivation` 的 `finally` 里 `release_root_budget`）。n=3 时「恰好一条」在独立
> 假设下约 12.5%，**不足以断言相关性**。记录待观察，不作为结论。

### 5.9 run 4/5 是被一条误导性错误吃掉的

两次 preflight 报 `market_data_freshness: no market snapshot date available`，
读起来像「数据没了」。**实际数据一直在**——事后立刻复查
`latest_market_date()` 仍返回 `'2026-08-07'`。

根因：`ask_blocks._market_data_asof` 对**三种不同情况返回同一个 `None`**——
库文件不存在 / `try_connect_readonly` 不可用（并发占用）/ 表里查不到行。
23:03 那一刻大概率是 DuckDB 被别的进程占着。

preflight **拦住是对的**（fail closed，没伪造收据），错的是它把「此刻读不到库」
说成「没有快照」。**这是本文第四次遇到同一族缺陷**：§3.1 的 `unavailable` 一词七义、
§5.8 的 `_classify` 丢弃原始错误、§5.1 我自己的探针把 UA 问题报成上游故障，
现在是这条。**一个信号承载多种成因，诊断就得靠猜。**

代价具体：采样从 5 次掉到 3 次，而且是在我明确要"多采样再下结论"的那一步上。

### 5.11 judge 的原始错误终于拿到了：确实是超时，而 §5.7 的结论是错的

不再改生产代码，改为在阶梯里**包一层注入给验证器的 judge client**
（`_RecordingJudgeClient`）。验证器的 `_stable_semantic_judge_error` 只拿
**异常类型名**去分类、把消息丢掉，所以包一层就能把原文留下。

第一版包错了地方——它 patch 了 `llm_refine.complete`，**一条记录都没抓到**。
原因：验证器有两条 judge 路径，`llm_refine.judge_provider()` 那条在
`LLM_JUDGE_*` 未配置时整个跳过（`:1107`），我们正是这种情况，真正走的是
`primary.complete(...)`（`:1244`）。**instrumentation 也会装错地方，空记录本身
就是"我插错了"的信号，不是"没有失败"。**

包对之后，S3 的三次 judge 调用 [实测]：

```
turn_error  15.63s  asked=15.0  attempts=1  LLM 调用失败（TimeoutError）
turn_error   8.31s  asked= 7.5  attempts=1  LLM 调用失败（TimeoutError）
turn_error   8.19s  asked= 7.5  attempts=1  LLM 调用失败（TimeoutError）
```

**三次都恰好烧满自己的窗口然后超时**，窗口值与 §5.7 算出的 `(15.0, 7.5, 7.5)` 完全吻合。

#### 所以 §5.7 错在哪

| | §5.7 当时写的 | 现在的证据 |
|---|---|---|
| 诊断「judge 因窗口过小而超时」 | **判为不成立** | **成立**，有原始错误 |
| 疗法「抬 `MAX_SEMANTIC_JUDGE_WINDOW_SECONDS`」 | 实测更差 | 仍然更差 |

我当时把**「疗法无效」读成了「诊断不成立」**。实际两件事都真：judge 确实死于超时，
而单纯抬窗口也确实会把草稿饿死——因为 §5.7 已经发现的那条**零和关系**：
judge 窗口与草稿生成抽的是同一笔 synthesis reserve。

**疗法被证伪不等于病因被证伪。** 当一个改动同时动了两个耦合量，它的失败无法区分
「病因判错」和「代价没算」。这是本轮方法论上最值得留的一条。

#### 真正的结构性问题

把三个实测数摆在一起：

| 量 | 值 |
|---|---|
| synthesis reserve 总额 | **60s**（§5.6 修好后） |
| 草稿生成实测成本 | **26–91s**（§5.3，另有一次 135s） |
| judge 首次尝试所需 | **> 15s**（本节，且 §5.2 短输出 p90 已是 21.8s） |

**60 秒要同时装下这两样，而只草稿一项的中位数就逼近上限。** 这不是调哪个常数的问题，
是这笔预算对当前 provider 速率**总量不足**。

可行方向（互斥性递减）：
1. 让草稿更短——**收窄输出结构**，不是写"请简短"（§5.4：`max_tokens` 中转不认）
2. 抬总额（`tier` 的 `total_seconds` / `_MAX_SYNTHESIS_BUDGET_FRACTION`），代价是端到端延迟
3. judge 换更快的独立端点（`LLM_JUDGE_*` 那条路径现在是空的，配上就能与主模型解耦，
   顺带满足 §5.2 提到的"judge 与 composer 不该相关"）

⚠ 本节 1 次采样，且 S1 那次 `structural=failed / tools=0`、根本没走到 judge。

### 5.12 仍然开着的

| 项 | 现状 |
|---|---|
| judge 系统性失败 | **下一步**。已排除窗口过小（§5.7）。诊断被卡在收据只存分类标签、不存 provider 原始错误——`_classify` 把 raw 丢了。要定位得先把 raw 传出来 |
| S3 的 `cause_attribution` 缺口 | 从 5 项收敛到 1 项，剩这一项 |
| terra 的 502 偶发 | 20 次里 1 次，样本不足以定率 |
| `llm_timeout` 上界 75s | 已低于 §5.3 实测长输出尾部（75.9s / 135s），未动 |

> ⚠ 本节所有数字是**延迟/稳定性**轴，**不含答案质量**。要下"哪个模型更好"的结论
> 必须另做质量评测。另：10 与 6 的样本量足以看方向，不足以定小差异。

---

## 6. 验收

| 项 | 结果 |
|---|---|
| `ruff check --config=ruff.toml`（与 pre-commit 同一条命令） | 通过 |
| 离线阶梯 `test_episode_seam_ladder.py` | 44 passed |
| pre-commit 全钩子（含层级审计） | 通过，ERROR 0 |
| 主树 37 个他人未提交改动 | 未受影响（全程 pathspec 提交，无 `git add -A`） |

本仓无 `ruff-format` 钩子（`.pre-commit-config.yaml` 只有 `ruff-check`），
故未做格式化——`ruff format` 会改动多处与本轮无关的既有代码。
