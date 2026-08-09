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

## 5. 仍然开着的

| 项 | 现状 |
|---|---|
| S1 的 TimeoutError | [实测] run C 拿到错误原文。三次采样看到两种形态，**采样不足以定根因** |
| S3 judge 的 transient provider error | judge 已在跑，provider 侧瞬时失败 |
| S3 题面假前提 | 见 §4，换题需重跑 floor 表 |

两条挂掉的都指向同一处：**这条中转在 episode 量级的 prompt 下不稳**。
旁证 [实测]：一个 6 个词的请求打过去 `prompt_tokens=4689`（中转注入约 4.7K token
系统提示）、2.6s 返回；而真实 episode 是 17K+ token 量级，S1 在 111s 上 TimeoutError。

> ⚠ **不要用 2-3 次采样去排模型/延迟的序。** 模型轴 08-08 从 `gpt-5.6-sol` 切到
> `gpt-5.6-terra` 依据的就是每档 2-3 次的延迟读数——那个采样量在延迟这种高方差量上
> 排不出可信序。本文所有 latency 同样是低采样，**只可用作"存在超时"的存在性证据，
> 不可用作模型间比较**。要比较必须先把采样量提上去。

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
