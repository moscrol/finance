# Handoff: 生产 8792 切中转 + 首轮预算修复 + 决证通过（均已完成）

> **日期**：2026-08-08，最后更新 17:4x
> **写给**：下一个 agent
> **前一份**：`2026-08-08-prior-recall-and-runtime-fixes.md`（读订正后的版本）
> **范围 revision**：`38c06356`（分支 `fix/first-turn-budget`；合并后见 main）
> **用户决策**：不再用 cockpit；出口切到中转 `https://x.ailzd.com/v1`

---

## 0. 状态一句话

**出口切换、首轮预算修复、生产线决证——三件都已完成并实测通过。**
生产 8792 现在能跑通完整 research run：`llm_calls=9 / tool_calls=9`、
3 个子 agent 分支真并行、4 个 binding、1378B 实答（不再是模板）。

⚠️ **但请先读 §2.5：原诊断是错的。** 这份 handoff 前几版把「重标定
`ResearchPolicy` 档位表」列为主线，**那条路已被探针证伪**——档位表从 90 调到
300，首轮预算一秒不变。真正的绞索在 `episode_factory.py:360` 的 reserve
计算。绕过这一节会让你重走一遍已经排除的路。

三个结构问题的现状（§2.4）：

- **(a)** BYOK 下静态秒数不可能正确。延迟**已经被测、也已落盘**
  （`llm_refine.py` 的 `LLMCallRecord.elapsed_ms` → orchestrator 的
  `llm_call_ledger`），但**预算侧从不读它**。缺的是消费端，不是观测。
  → **仍未做**，见任务 1。
- **(b)** reserve 的逻辑在第一步是反的——为一场还不存在的合成攒时间，
  饿死了唯一能启动这一切的那次调用。
  → ✅ **已修**（`38c06356`），见任务 2。
- **(c)** deadline 紧张时把并行**关掉**（`max_branches=0`）。provider 越慢
  越需要并行，这里恰好反着来。
  → **仍未做**，抬的是上限不是下限，优先级低于任务 1。

⚠️ **前人做过两次无效尝试**（换模型、加回合预算旋钮）。过程和数据留在 §3，
因为它们**排除了两个看起来最像的原因**，能省你重走一遍。

---

## 1. 已完成并已验证（不用重做）

| # | 事项 | 验证方式 |
|---|---|---|
| 1 | 出口从 cockpit 切到中转 | 启动器已改，备份 `start-finance-workbench.bak-20260808-relay-cutover` |
| 2 | BYOK 劫持解除 | `FORESIGHT_LLM_KEYCHAIN=0`；实测 `runtime_providers_for("linxiaoqi5111")` 落回 env，链长度 1、`name='openai'`、`base_url=https://x.ailzd.com/v1` |
| 3 | provider 链无污染 | 链长度实测 = 1（`_PROVIDERS` 的 7 个兄弟 key 在启动器与 plist 中零命中） |
| 4 | 凭证 | Keychain `finance-workbench-test-relay`/`a77`；启动器取不到就 `exit 1`，不带空 key 起服务 |
| 5 | 请求路径 | 用生产同款 `_llm_request_headers`（UA `finance-workbench/1.0`）实测 200 |
| 6 | 部署闸门 | `scripts/deploy_workbench_runtime.sh` 已提交（`2a56e3a6`），实测校验的确实是快照树 |
| 7 | health 报生效模型 | `edb2ea10` 修好「凭证那半 provider-neutral、model 那半还硬回落 glm-5.2」 |
| 8 | 生产台账 seed | `$FORESIGHT_USERS_DIR/tester/judgments.jsonl` 496 条（原生产 27 个 user 零台账） |
| 9 | 回合预算可配 | `0457e39e`，env `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS`，默认 120 不变 |

**当前 health**：`ready=True`、`credential_available=True`、`model=gpt-5.6-terra`、
`code_matches_repo=True`、`continuous mode=on`。

**全量测试**：`13 failed, 4391 passed, 3 skipped`（13 条为既有环境依赖失败），
`layer_audit` ERROR 0。

---

## 2. 唯一的阻塞：预算档位表按更快的 provider 标定

### 2.1 链路（每一层都在削减首轮可用时间）

```
回合预算 T (_continuous_turn_timeout_seconds, 默认 120)
  → verification_reserve = min(40, T/3)     runtime/continuous_turn_adapter.py:66,399-403
  → runtime_timeout      = T − verification_reserve
  → _generic_research_deadline 再与 ResearchPolicy 档位 min 封顶
      quick 30s / standard 90s / deep 240s        services/research_contract.py:392-394
  → 再扣 synthesis_reserve（standard 20s / deep 48s）
  → stage_timeout = min(llm_timeout=75, remaining − reserve)   services/research_contract.py:356
  → **这个值就是 HTTP 请求超时**        runtime/glm_agent_runtime.py:154,277 `timeout=remaining`
```

⚠️ **路径订正（`b6b8bd58` 及之前的版本写错了目录）**：`glm_agent_runtime.py` 与
`continuous_turn_adapter.py` 在 **`intelligence/runtime/`**，不在 `services/`。
只有 `research_contract.py` 在 `services/`。**行号都是准的**，别照旧路径去找——
`intelligence/services/` 下确实没有这两个文件，而 `tmp/` 下有 5 份 `services/`
时代的旧副本，容易误以为找到了。

`llm_timeout=75` 的来源：`runtime/glm_agent_runtime.py:40`
`DEFAULT_GLM_LLM_TIMEOUT = 75.0`，:393 作为默认参数传进
`ContinuousAgentEpisode`（:423）。全树无任何调用点覆盖它，所以生产路径确实是 75。

> ⚠️ 埋着的坑：`runtime/agent_episode.py:67` 另有 `DEFAULT_LLM_TIMEOUT = 20.0`，
> 是直接构造 episode 时的兜底。20s **低于实测 P50（28s）**——任何绕过
> `GLMAgentRuntime` 直接构造的路径会拿到一个必然超时的预算，且不会有任何提示。

最后一跳是关键：**stage 预算不是「软目标」，它直接当 socket timeout 用**。
provider 一慢就 `TimeoutError` → `model_unavailable`。

### 2.2 实测分布（这是本次最有价值的产出，别重测）

同一条中转、同一提示词规模、`_llm_request_headers` 同款请求头：

```
gpt-5.6-terra  N=8   21 22 24 25 31 39 40 50 (s)
               P50=28s   P95=50s   max=50s
               预算 25s → 3/8 完成 (38%)
               预算 50s → 8/8 完成 (100%)
               预算 70s → 8/8 完成 (100%)
```

其余三个模型（各 2-3 次采样，仅供排序，**样本不足以下结论**）：

```
gpt-5.6-sol    25 / 48 / 50 s      ← 原产品线模型，最慢
gpt-5.5        15 / 18 s
gpt-5.4        10 / 19 s
```

⚠️ **延迟与提示词大小不相关**：实测 9K token → 60.3s，17K → 21.2s，30K → 18.4s。
是中转本身抖动，不是 token 数驱动。**所以任何 2-3 次的采样都会被方差骗**——
我第一次就是这么被骗的（见 §3）。

### 2.3 需要多大预算

`stage_timeout` 被 `llm_timeout=75` 封顶，而 P95=50s < 75s，**所以只要让
`remaining − synthesis_reserve ≥ 75`，首轮就够用**。倒推：

- standard 档 90s − reserve 20s = 70s < 75 → 差一点
- deep 档 240s − reserve 48s = 192s → 够

多轮才是大头：standard 档 `max_steps=6`，按 P50=28s 算光模型调用就 168s，
**已经超过 standard 档 90s 的总预算**。所以不是「调大一点」，是这张表整体
偏小一个量级。

### 2.4 但「把数字调大」只是止血 —— 结构上有三个更根本的问题

这一节是用户在复盘时问出来的，比上面的数字更值得先读。

#### (a) BYOK 下，静态秒数不可能正确 —— 延迟测了、落盘了，但预算侧不读

provider 是用户插进来的：官方 API、中转、本地模型、限流的免费额度，
延迟能差一个数量级。**任何写死的秒数都只对标定它的那个 provider 成立。**

🔴 **这一节我写错过两版，第三版才是对的。请只信这一版。**

- v1「全树 `adaptive`/`latency`/`calibrat*` 零命中」→ **过头了**。排除 `eval/` 后
  `latency` 命中 6 个非测试文件（含 `services/research_policy.py`），`calibrat` 7 个，
  只有 `ewma` 真零命中。
- v2「`glm_agent_runtime.py` 与 `continuous_turn_adapter.py` 全是『还剩多少』，
  没有一处算『花了多少』」→ 这两个文件本身**描述准确**（:133/:146/:236/:262 与 :178
  确实只有 `expires_at - monotonic()`），但**我找错了层**：这两个文件里根本没有
  `urlopen`/`httpx`，它们不是发请求的那一层。

**发请求的那一层是 `services/llm_refine.py`（`urlopen` 在 :637/:672/:767/:1387），
而它一直在测延迟：**

```
llm_refine.py:340-348   class LLMCallRecord: caller / provider / model / status /
                        elapsed_ms / reason
llm_refine.py:558-576   _record_llm_call(...)
                        elapsed_ms = round((monotonic() - started) * 1000)
llm_refine.py:419       summary()["total_elapsed_ms"]
llm_refine.py:429-433   summary()["records"]  ← 每次调用的 provider/model/status/elapsed_ms
```

**而且它已经流到 artifacts 了**：`runtime/conversation_orchestrator.py:3089-3103`
把 ledger 作为 `llm_budget` / `llm_call_ledger` 落盘，带全量 per-record 明细。

所以"系统从来不测 provider 延迟"**是错的**。准确的说法是：

> **测了，也落盘了，但预算侧从不读它。**

［实测］在 `services/research_contract.py` + `services/mode_governor.py` 里搜
`elapsed` / `ledger` / 观测量的消费点：`research_contract.py` 只有自己 mint
root ledger（:622/:635/:645）和反序列化 `elapsed_ms`（:1006），
`mode_governor.py:242` 只校验"deep 提升需要一个 root budget ledger"的存在性。
**没有任何一处把观测到的延迟回读进档位或 stage 预算。**

这把缺口从"要建观测"缩小成"要接消费端"——**工程量小一个量级，见任务 1。**

所以现状准确的描述是**半动态**：

| 维度 | 状态 |
|---|---|
| 「还剩多少时间」 | ✅ 动态。`stage_timeout = min(llm_timeout, remaining − reserve)`，`remaining` 实时算 |
| 「provider 有多快」 | ⚠️ **测了、落盘了、但预算侧不读**。`llm_refine` 记 per-call `elapsed_ms`，orchestrator 落进 `llm_call_ledger`，而 `research_contract` / `mode_governor` 从不回读 |
| 「预算取值」 | ❌ 全部硬编码常量（档位总秒数、各 reserve、`llm_timeout=75`） |

所以卡住我们的不是"没有测量"，是**观测与决策之间断了一根线**。
这比"完全瞎"好修得多：数据已经在 artifacts 里，缺的是消费端。

> ⚠️ 别把这条写成"系统不会测延迟"——那是我 v1/v2 的错误说法，一查 `llm_refine.py:558`
> 就露。准确措辞是「测了但没人读」。

#### (b) reserve 的逻辑在第一步是反的

各种 reserve（`verification_reserve` 40s、`synthesis_reserve` 20/48s）的用途
是正当的：保证到点还有时间**把已查到的证据合成一个有依据的答案**，而不是
写到一半被砍。这条挡住过真实事故，不要拆掉。

**但在第一次模型调用时，它保护的东西还不存在。** 这时一条证据都没查到，
它却在为一场永远不会发生的合成攒时间，代价是让唯一能启动这一切的那次调用
饿死。而且失败是全损的：首轮超时，那 25 秒**照样全花掉了**，什么也没产出，
省下的 reserve 一秒都没用上。

正确的形状大概是 **reserve 随已产出的东西增长**：第一步没有东西要保护就该
给足，越往后证据越多 reserve 才越该收紧。现在是从一开始就按「要留着合成」
的姿态切分，方向反了。

> 这也解释了为什么「把回合预算从 120 调到 300」只把 `stop_reason` 从
> `model_unavailable` 变成 `deadline_exhausted`（§3②）：**首轮那一刀的
> 切法没变**，只是总盘子大了。

#### (c) deadline 紧张时把并行关掉 —— 方向也是反的

［实测］`services/mode_governor.py`：

```
:202  if not signals.deep_deadline_available:
:203      return _quick_decision(reason="deep_deadline_unavailable", ...)
:133          max_branches=0          ← 并行被关掉
:153  （对照：_deep_decision 是 max_branches=3）
```

连起来是：**provider 慢 → deadline 紧张 → 判定 deep 不可用 → 降级 → 子研究分支
归零**。而并行恰恰是**唯一能让墙钟不随步数线性增长**的杠杆（N 个分支并行，
墙钟≈最慢那个，不是 N 倍）。**provider 越慢，这个杠杆越值钱，而这里在它最值钱
的时候把它拿掉了。**

⚠️ **读代码时容易错一层**：`_quick_decision` 里 `research_tier="standard"`（:129），
**不是 `"quick"`**。所以"降级到 quick"降的是 `effective_mode`，档位仍落在
standard（90s / `tool_call_cap=8`），不是 quick 档 30s。按"降级 = 30s"去推 §2.3
会算错。

> 顺带一条值得肯定的设计：`ModeGovernor.decide(plan, signals)` 的形状是
> **模型提议、代码裁决**（docstring: "Approve model-requested depth from
> observable, code-owned signals"），信号是硬事实（`independent_entities >= 2`、
> `separable_branches >= 1`、`len(evidence_domains) >= 2` 等），且
> `ResearchPolicy` 明写"不允许由 LLM 提高上限"。**这一层不要动**——模型能给
> 自己批预算就会通胀。要改的只是「紧张时砍并行」这个方向。

### 2.5 🔴 根因订正：档位表根本不参与首轮 —— 原诊断已被证伪

**这一节推翻本文档 15:2x 版本的核心论断，也推翻我自己在 §2.2/§2.3 的推理框架。
先读这里，再读上面。**

我在动手改代码前先按代码算了一遍「首轮实际能拿到几秒」，结果和「档位表 90s
太小」对不上，于是没写代码，先去读盘上的真实 run。两件事都错了：

#### (1) 首轮预算不由档位表决定

`services/episode_factory.py:349-354`：

```python
effective_timeout = base_policy.total_seconds
if timeout is not None:
    effective_timeout = min(base_policy.total_seconds, max(0.0, float(timeout)))
```

`timeout` 是回合注入值（`turn − verification_reserve = 120 − 40 = 80`）。于是
`effective = min(tier_total, 80)`，而 **80 恒为较小者**。探针实测：

```
standard total_seconds = 90  → 首轮 26.67s
standard total_seconds = 180 → 首轮 26.67s
standard total_seconds = 300 → 首轮 26.67s      ← 一秒不变
```

**所以「重标定档位表」对首轮失败可证明无效。** 原任务 1（主线）建立在
一个不成立的因果上。这也解释了 §3② 为什么只把 `stop_reason` 换了个名字。

#### (2) 真正的绞索是 reserve 的二次收缩

`episode_factory.py:360-363` + `glm_agent_runtime.py:52`：

```
effective = min(90, 120 − 40)        = 80
reserve   = min(60, 80 × 2/3)        = 53.33      ← _MAX_SYNTHESIS_BUDGET_FRACTION
首轮 stage= min(75, 80 − 53.33)      = 26.67s
provider 实测 P50                     = 28s       ← 首轮连中位数都不到
```

`_BALANCED_SYNTHESIS_RESERVE = 60.0`（`glm_agent_runtime.py:52`）、
`_MAX_SYNTHESIS_BUDGET_FRACTION = 2/3`（`episode_factory.py:103`）。
两个常量各自都合理，**乘起来把首轮压到了 P50 以下**。

#### (3) 盘上证据（三个 run，`users/tester/runs/`）

```
run.json                 status: completed          ← 顶层「成功」
report.json              status: partial
continuous-episode.json  status: failed / deadline_exhausted
events[1] model_turn     error: "LLM 调用失败（TimeoutError）", provider_attempts: 1
trace context_growth     turn_count: 0, sub_agent_branch_count: 0
answer.md                235B，三个 run 的 sha256 **完全相同** → 模板降级
```

⚠️ **本文档此前记的症状 `model_unavailable` 与盘上不符**（实际是
`deadline_exhausted`，`model_unavailable` 只是 event 里那层 `TimeoutError`
的旧措辞）。以盘上为准。

⚠️ 另外注意 `run.json` 报 `status: completed` 而 episode 是 `failed`——
**顶层状态不能用来判断 research 成功**，它只表示「HTTP 任务跑完了」。

---

## 3. 我试过但没用的两条路（省你时间）

### ① 换模型 —— 无效，且我的推荐建立在坏数据上

我先按 2-3 次采样得出「terra 9-15s，能塞进 25s 预算」，据此建议用户从
`gpt-5.6-sol` 换到 `gpt-5.6-terra`，用户采纳了。**换完仍然失败，同样的
`model_unavailable`、同样 28s、同样 `provider_attempts=1`。**

补测到 N=8 才看清 terra 的 P50 是 28s——**P50 本身就超预算**，换模型从一开始
就救不了。**这个结论我收回**：低采样在一个高方差的量上得出的排序不可信。

> **当前生产仍是 `gpt-5.6-terra`。** 这翻掉了 08-05「模型轴已定 = sol」那个用户
> 决策，而支撑它的数据已被我自己推翻。terra 的 P50（28s）确实优于 sol（48s），
> 所以我没改回去；但**换型依据现在只剩延迟一个维度，质量侧零对照**。
> 预算修好之后应当补一次 sol vs terra 的同题盲评，再定模型轴。

### ② 把回合预算旋钮调大 —— 有效但不充分

`0457e39e` 把 `_CONTINUOUS_TURN_TIMEOUT_SECONDS` 做成可配，启动器设 300。
实测**确实生效**：`stop_reason` 从 `model_unavailable` 变为 `deadline_exhausted`，
run 从 28s 拉到 40s。但首轮仍超时——因为 `_generic_research_deadline` 会拿
`ResearchPolicy` 档位再 min 一次，**上层的 90s 才是当前的封顶**。

所以这个旋钮是必要的（provider 换了就得能调），但不是充分的。

---

## 4. 交给你的任务

> **顺序是有依据的，别跳。** 任务 1 是任务 3 的前置条件——没有延迟数据，
> 重标定就只能按我这次手工量的这一份静态数字来，换个 provider 又得重来一遍。

### 任务 1（前置，先做这个）：让它会测 —— **是接线，不是新建**

**这一条我最初列成「补可观测性」，当成事后能查的诊断增强。那是低估了——它是
自适应预算的前置条件。** 但我随后又把工程量**估大了两次**，第三版才对。

🔴 **不是「让它会测」，它已经在测。是「让预算侧去读」。**

发请求那一层 `services/llm_refine.py` 一直在测，而且已经落盘（详见 §2.4(a)）：

```
llm_refine.py:558-576    _record_llm_call() → elapsed_ms + provider + model + status + reason
llm_refine.py:419/429    summary(): total_elapsed_ms + 每次调用的 records 明细
conversation_orchestrator.py:3089-3103   已作为 llm_budget / llm_call_ledger 落盘
```

`StageArtifact` 那两个字段也早就并排放着，20+ 处在填：

```
services/research_contract.py:967   StageArtifact.elapsed_ms: int
services/research_contract.py:970   StageArtifact.timeout_seconds: float = 0.0
```

**所以任务 1 的真正内容是接消费端。** 按这个顺序做：

1. **先证实数据够用（半天以内，可能不用改代码）。** 从生产 8792 已有的 run
   artifacts 里把 `llm_call_ledger.records` 捞出来，看 `caller` 里
   `chat_tools` 那些的 `elapsed_ms` 分布——**如果它够，§2.2 那份手工 N=8 探针
   可以直接退役**，任务 3 用真实生产分布标定。这是本任务性价比最高的一步。
2. **补 ledger 里缺的那一半：那次调用分到多少预算。** 现在 `LLMCallRecord`
   有 `elapsed_ms` 但没有 granted budget。缺它就没法区分「超时」是 provider 慢
   还是预算小——这正是你提的「必须一起记」。加一个字段即可，形状照
   `llm_refine.py:340-348`。
3. **把预算侧接上。** ［实测］`services/research_contract.py` 与
   `services/mode_governor.py` **没有任何一处回读观测量**：前者只 mint root
   ledger（:622/:635/:645）和反序列化 `elapsed_ms`（:1006），后者 :242 只校验
   ledger 存在性。这是缺口的真身。
4. **顺手补两个已知洞**：`services/agent_research.py` 四处 `elapsed_ms=0` 硬编码
   （:827/:891/:918/:953）；`timeout_seconds` 默认 `0.0`，LLM 调用那一层是否真被填
   我没查实（已知填充点在 `workbench_skills/research_owner.py` 多处、
   `owner_dag.py:131,158,183,319`；`registry.py:107,122` 写死 30）。

⚠️ `runtime/glm_agent_runtime.py` 本身确实不报 elapsed（只有 `expires_at -
monotonic()`），但**别从这里下手加埋点**——下游 `llm_refine` 已经有了，
在这里再加一份会出现两个口径不一致的 elapsed。

另外**字段名别新造**：eval 侧已有 `RuntimeArm.latency_seconds`
（`eval/runtime_backend_benchmark.py:386`，:720 median 聚合，:246 非负校验）。
生产 trace 沿用同名，两侧数据才能直接对齐。

第二件事仍然缺，照原样做：**本次生效的档位与预算**。`report.json` / `trace.jsonl`
里 `research_tier`、`total_seconds`、`stage_timeout` 一个都查不到，事后无法判断
一个 run 跑在哪档、首轮拿到几秒。我这次全靠读代码倒推。
（`research_tier` 在 `services/research_contract.py:698,733,834` 是有字段的，
同样是没往 artifacts 里带。）

> 📌 **别拿 `runtime.source_revision` 当版本依据。** 生产 health 里它报
> `edb2ea10`，而 HEAD 是 `b6b8bd58`、`repo_tree_fingerprint` 却与 loaded 一致
> ——`0457e39e` 其实**在**运行的树里，只是这个标签停在快照构建时刻。
> 指纹是权威的，标签滞后。与 `45d51616` 同类问题，没修干净。

按路线图「一块」的四件（可达性/契约/观测/变异测试），**观测这件缺着**。
做完这条，后面所有预算类问题一眼可见，也不必再手工跑 N=8 的探针。

### 任务 2：把「每轮多久」与「总共几轮」解耦

> ## ✅ 第一步已实现并通过生产决证（`38c06356`，分支 `fix/first-turn-budget`）
>
> **做了什么**：首轮向 `synthesis_reserve` 借**超出「跑一次合成」地板的余量**，
> 不是整段不扣。实现在 `runtime/agent_episode.py`：
>
> ```
> :74    MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS = 20.0
> :453   is_opening_call = llm_calls == 0 and not accumulator.evidence
> :1273  _opening_planning_timeout()  # baseline + max(0, reserve − floor)
> ```
>
> **效果（探针实测，`floor=20`）**：
>
> | 场景 | 旧 | 新 |
> |---|---|---|
> | 生产 standard/theme (80, 53.33) | 26.67s | **60.00s** ≥P95 ✓ |
> | 生产 turn=300 (90, 60) | 30.00s | **70.00s** ≥P95 ✓ |
> | 护栏测试 (15, 4) | 11.00s | 11.00s 未变 |
> | 测试替身 reserve=0 | 20.00s | 20.00s 未变 |
> | quick 档 (30, 20) | 10.00s | 10.00s 未变 |
> | grounded deep (180, 100) | 75.00s | 75.00s 未变 |
>
> 借出后合成仍保底 20s，「到点还能交出有依据答案」的不变量成立。
>
> **验证**：全量 `13 failed, 4391 passed, 3 skipped`（与改前逐条一致，零新增）；
> 生产决证三条判据全中（见任务 4）。
>
> ### 🔴 两个坑，下一个人一定会踩
>
> **1. `context.deadline` 是鸭子类型注入点。** 我第一版在 `ResearchDeadline` 上
> 加了个 `opening_stage_timeout()`，三条测试立刻 `AttributeError` ——
> `test_agent_episode.py:593` 的 `_ScriptedDeadline` 和 `:615` 的
> `_LateRecoveryDeadline` 只实现 `stage_timeout` / `synthesis_timeout` /
> `remaining` / `expired` 四个方法。**动这条路径只能用替身已有的接口**，
> 现在 `synthesis_reserve` 走 `getattr(..., 0.0)` 兜底。
>
> **2. 有条护栏测试守着「首轮不许吃光 reserve」，别改它。**
> `test_planning_turn_cannot_spend_the_reserved_finalization_budget`（:2668）
> 断言 `calls[0]["timeout"] <= 11.0`（15−4）。我第一版正是改掉了这个语义，
> 它转红——**那是它在干正确的事**：首轮若吃光全部预算，合成就没了，照样吐模板。
> 改成「借余量」后它原封不动地绿了（reserve 4 < floor 20，借不到）。
> **不要通过改测试来迁就实现。**
>
> ### 下一步（本任务剩余部分，未做）
>
> 上面只解了「首轮饿死」。**旋钮解耦本身还没做**——HTTP 超时仍从研究预算推导。
> 下面原文照旧有效，判据 2/4 仍未满足。

> 原标题是「让第一次模型调用不吃 reserve」。**升级过，因为那只是症状。**
> 根本形状是：现在**一个数同时承担两件事**——它既是研究预算，又是 socket
> timeout（§2.1 最后一跳）。这两件事的正确依据完全不同：
> 「一次调用最多等多久」归 **provider 特性**，「总共能跑几轮」归 **产品预算**。
> 绑在一起，就必然出现「provider 慢 → 研究预算被吃光 → 首轮都开不了」。

拆成两个独立旋钮：

1. **HTTP 超时不再从研究预算推导。** 按实测 provider 延迟定（P99 + 余量，
   §2.2 的 max=50s → 取 75s 正好，`DEFAULT_GLM_LLM_TIMEOUT` 现值就是 75），
   它只负责**防挂死**，不负责控成本。
2. **研究预算改在「每轮返回之后」检查**：「还够开下一轮吗？」不够就带着
   已有证据去合成，而不是提前扣一笔 reserve 占着。

这样 §2.4(b) 的首轮饿死**自动消失**——首轮不再需要跟 reserve 抢时间；
而 `synthesis_reserve` 的大部分职责由「不开新轮」承担，不必靠提前预留。

⚠️ **但 reserve 不能整个删掉。** 合成本身也是一次 LLM 调用，也要时间；
「不开新轮」保护的是**还没开始**的轮次，保护不了**已经开始**的合成。所以
`synthesis_reserve` 应当收缩成「只覆盖一次合成调用」，而不是现在这样
按整个 turn 的比例切。判断依据可以用 `episode_finalizer.py:17`
`DEFAULT_FINALIZER_TIMEOUT = 20.0`——那才是合成真正需要的量级，
不是 `verification_reserve` 的 40s。

判据（不是「数字变大了」）：

1. **首轮 stage 预算 ≥ P95**（当前 50s）
2. **HTTP 超时与研究档位无关**：改档位表不应改变 socket timeout；
   变异测试——把档位总秒数改一半，HTTP 超时不应变化
3. 现有那些「到点还能交出有依据答案」的测试**全绿，一条都不能松**
4. 首轮超时后**不再是全损**：已完成的工具调用结果要能进合成

> 📌 顺带修 §2.4(c) 那条反向逻辑（`max_branches=0`），两者同源：都是
> 「时间紧 → 削减能力」，而正确方向是「时间紧 → 用并行换墙钟」。
> 建议同一个分支做完，但**分成两个 commit**，便于单独回滚。

### 任务 3：用实测分布重标定 ResearchPolicy 档位表

`intelligence/services/research_contract.py:390-396`：

```python
"quick":    cls("quick",    3,  30.0, 20.0),
"standard": cls("standard", 6,  90.0, 20.0),
"deep":     cls("deep",     12, 240.0, 48.0),
```

> ## 🔻 已从「主线」降级 —— 它救不了首轮（§2.5 探针证明）
>
> **原文把这条列为主线阻塞。那是错的。** 探针实测：standard 档从 90 调到
> 180、300，首轮预算恒为 26.67s，**一秒不变**。因为
> `effective_timeout = min(tier_total, turn − verification_reserve) = min(tier_total, 80)`,
> 那个 `80` 永远是较小者，档位总秒数根本不参与首轮。
>
> **所以先做任务 2，别先动这张表。** 决证已在**不改这张表**的前提下通过。
>
> 这张表仍然值得重标定，但理由变了：不是为了救首轮，而是为了**多轮**——
> standard 档 `max_steps=6`，按 P50 28s 算光模型调用就 168s，超过该档 90s 总预算
> （这条原判断依然成立）。降级后它的优先级在任务 1 之后。

任务 1 做完后**用 trace 里的真实分布**标定；在那之前可以先用 §2.2 那份
（N=8，只覆盖 terra 一个模型、一个时段）作为临时依据，但要在 commit message
里写明样本来源与局限。

> ✅ **照抄仓内已有的模板，别自己发明。** `services/research_policy.py` 里
> `GroundedBudgetProfile` 已经把「这个数怎么来的」做成**一等字段**而不是注释：
>
> ```python
> research_policy.py:25   measurement_basis: str
> research_policy.py:43   measurement_basis=(
>     "single preregistered A4 canary plus frozen replay: 146.55s observed "
>     "end-to-end need, 20% slack = 175.86s; engineering headroom only, "
>     "not p95 or another latency percentile")
> ```
>
> :13-15 的 docstring 写明用意：*"deliberately data, not only a comment, so
> tests and traces can keep the provenance honest"*。注意它**诚实标注了自己
> 不是 p95**——这正是我们现在需要的那种自我限定。
>
> **给 `ResearchPolicy` 也加 `measurement_basis`。** 这是本次最该沉淀的一条：
> 我这回全靠读代码倒推那三个数字的来历，花了很久；而隔壁文件早就把这件事
> 做对了。下次换 provider 时，下一个人能一眼看出这些数还成不成立。

> ⚠️ **三套预算系统，严谨程度差三档，互不对账**——这是本次的结构性发现：
>
> | 系统 | 位置 | 数字的依据 |
> |---|---|---|
> | `GroundedBudgetProfile` | `services/research_policy.py:10` | ✅ 有 `measurement_basis`，且诚实标注非 p95 |
> | `ResearchExecutionPolicy` | `services/research_policy.py:52` | ⚠️ `max_llm_calls=40`，注释写明「失控保险丝而不是常态限流」 |
> | `ResearchPolicy` 档位表 | `services/research_contract.py:392-394` | ❌ **零依据说明** |
>
> **杀死我们的是第三套——唯一没人写下推导过程的那套。** 三套各按各的口径
> 长起来、中间没有对账，这是「跨层口径对账」这个形状的又一次复发
> （前几次：health 报 `glm-5.2` 而实际跑别的、`source_revision` 滞后于指纹、
> 快照与仓库漂移）。重标定时至少要说明这三套的关系，不要再加第四套。

**这是策略变更不是配置**，请：

- 在**分支**上做（`fix/research-policy-recalibration`），按 CLAUDE.md 红线，
  合并 main 等用户确认
- 每档给出「按 P50 / P95 各需多少秒」的推导，写进 commit message，
  别只给结果数字
- 注意 `max_steps` 与总秒数要一起算：standard 档 6 步 × P50 28s = 168s，
  光模型调用就超过该档 90s 的总预算——**只调总秒数不看步数会再标错一次**
- 变异测试：把新数值改回旧值，应有测试转红（现在没有任何测试钉这张表）
- 跑完全量对齐基线 `13 failed, 4391 passed, 3 skipped`，并与 `--collect-only`
  对账（`13+4391+3` 应等于 collect 条数）

⚠️ **改完必须用真实 run 验，不能只看单测。** 判据见任务 4。

### 任务 4：跑通生产线决证 —— ✅ **已通过（`38c06356`，2026-08-08 17:25）**

> **三条判据全中，这条不用重做。** 下面的跑法与读法保留，因为**每次改预算或
> 换 provider 都应该重跑它**——它是唯一能证明整条链闭合的判据。

实测结果（`run_20260808_172521_718800`，user=`tester`）：

```
判据 1  memory_lookup 真调用   ✓  outcome/traces 2 条 episode:memory_lookup (success)
                                  + outcome/evidence 1 个 atom (tool=memory_lookup, 3bb2d0e9)
判据 2  prior_recall binding   ✓  basis=user_premise, evidence_hashes=['3bb2d0e9…']
判据 3  正文无台账路径泄漏      ✓

status=partial  stop_reason=repair_model_stop
llm_calls=9  tool_calls=9  input_tokens=43187  耗时 237s
bindings: direct_assessment / chain_mapping / counterpoint / prior_recall
```

**修复前后对比**（同一道题、同一条中转、同一个模型）：

| | 修复前（3 个 run） | 修复后 |
|---|---|---|
| llm_calls / tool_calls | 1 / 0 | **9 / 9** |
| 耗时 | 28-31s | **237s** |
| bindings | 0 | **4** |
| answer.md | 235B 模板（三次 sha256 **完全相同**） | 1378B 实答 |

⚠️ **判据 1 有个陷阱，我差点误判。** `memory_lookup` 在 `continuous-episode.json`
里出现 **28 次**，但绝大多数落在**声明位**而不是调用位：

```
4x  /contract/required_outputs[]/evidence_types[]     ← 只是"契约里要求它"
1x  /contract/allowed_capabilities[]                  ← 只是"这次授权了它"
2x  /outcome/traces[]/provider = episode:memory_lookup ← 这才是"真调了"
1x  /outcome/evidence[]/tool   = memory_lookup         ← 这才是"真产出了证据"
```

**判"真调用"只能看 `outcome/traces` + `outcome/evidence`**，不能 grep 计数——
那正是路线图区分的「定义了」vs「这次真够得着」。原文判据写"出现在工具序列里"
不够精确，而且 `payload.tool_calls` 在不同 event 里既可能是 list 也可能是 **int**
（计数），照原读法脚本会直接 `TypeError`（我踩了两次）。

意外收获：**子研究分支真的并行跑起来了**。events 里
`branch_started`×3 / `branch_completed`×2 / `branch_failed`×1，
分支目标分别是「市场交易状态与代表股分化」「产业链驱动与兑现证据」
「用户历史判断与反证核对」，`tool_calls` 4+2+3=9 与 usage 吻合。
这同时实证了 `runtime/sub_research.py:317-329` 那条 `ThreadPoolExecutor`
路径在生产上是活的（不是"实现了但没接线"）。

答案本身也不再是模板：给出基准判断，明确说"现有资料没有液冷题材自身的涨跌、
资金、涨停扩散数据，因此无法确认当下强弱与拥挤程度"，并把用户原来的
"二次侧卡脖子"升级为"能否拿到系统集成商认证、能否转化为订单与利润"。
**是有依据的克制，不是编。**

---

原始跑法（保留，用于复跑）。在 **8792** 上：

```bash
CID=$(curl -s -X POST localhost:8792/api/conversations -H 'Content-Type: application/json' \
  -d '{"user":"tester","title":"decisive"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["conversation_id"])')
curl -s -X POST "localhost:8792/api/conversations/$CID/messages" -H 'Content-Type: application/json' \
  -d '{"content":"液冷题材现在怎么看？我之前的判断还成立吗","skill_mode":"auto","user":"tester"}'
```

**必须用 `user=tester`**——只有它的台账里有 judgments（已 seed）。题目里必须有
指向用户自己历史看法的措辞（"我之前的判断"），否则 `_PRIOR_REFERENCE_RE` 不命中，
`prior_recall` 槽位根本不开，那时的"没召回"不是缺陷。

判据（三条全中）：
1. `memory_lookup` 出现在工具序列里
2. `prior_recall` binding 存在，`basis=user_premise`，有 `evidence_hashes`
3. 正文无台账路径泄漏

`status=partial` **不算失败**——8788 那次决证也是 partial，原因在数据源侧。
判的是那条链闭不闭合。

读法：
```bash
RUN=<从响应取>
python3 -c "
import json,pathlib
ep=json.loads(pathlib.Path('/Users/a77/.local/share/finance-workbench/users/tester/runs/$RUN/continuous-episode.json').read_text())
o=ep['outcome']
seq=[c.get('name') for e in ep.get('events',[]) for c in (e.get('payload') or {}).get('tool_calls',[]) if c.get('name')]
print('status:',o.get('status'),o.get('stop_reason')); print('tools:',seq)
print('prior_recall:',[b for b in o.get('bindings',[]) if b.get('output_id')=='prior_recall'])
"
```

### 任务 5（做完 1-3 后可选）：让档位按分布自动定

任务 1 落地后，`stage` 预算原则上可以由观测到的 P95 推出来，而不是人手标。
那才算真正解决 §2.4(a) 那个结构问题——**BYOK 下秒数不可能静态正确**。

⚠️ 这一条**别顺手做**。自适应预算会引入一类新的失败：预算随最近几次调用漂动，
同一个问题两次跑出不同结果，且难以复现。要做的话先设计好「用什么窗口、
多久重算一次、漂动上下界」，并且**默认关闭、显式开启**。
先把 1-4 做完拿到稳定基线，再谈这条。

### 任务 6：8788 去留（**解锁了，但仍需问用户**）

8788 仍在跑（pid 79613，rev `9380b3b9`，落后 main），且 health 里没有
`loaded_code_root` / `code_matches_repo`——**它自己不知道自己漂了**。

原来的阻塞条件是「8792 跑通前不要关」，因为 8788 曾是唯一跑通过完整
`memory_lookup → prior_recall` 链的线。**该条件已解除**：任务 4 已在 8792 上
通过（`38c06356`，三条判据全中），对照线不再唯一。

但**仍然先问用户再关**。两个理由：
1. 8792 这次是 `partial` / `repair_model_stop`，链闭合了但还没有一次
   `completed`。留着 8788 作为「已知能跑」的参照，成本只是一个进程。
2. 关它属于动生产。

⚠️ 关之前先确认端口归属，**别照 pid 记忆去 kill**：本机同时有 **5 个**
`intelligence.api.app` uvicorn 进程（另有 worktree 起的 8795 等）。
现查：`lsof -nP -iTCP:8788 -sTCP:LISTEN`。

---

## 5. 红线与坑

- 🚫 **key 不进仓库任何文件**。启动器里只有 `security find-generic-password` 读取命令。
- 🚫 **不擅自合并 main、不强推**。当前 main 有 **8 个未 push 的提交**，
  push 要用户确认。用 `git log --oneline origin/main..main | wc -l` 现查，别引用这个数。
- ⚠️ **不要手工 `cp` 补快照**，用 `scripts/deploy_workbench_runtime.sh`。
  逐文件补丁实测三次都起不来（`b93e4a00`）。
- ⚠️ **不要在服务启动路径抛异常**。launchd 是 `KeepAlive=true` +
  `ThrottleInterval=10`，会变成每 10 秒一次的无限崩溃循环。
- ⚠️ **解释器只认 `.venv-workbench/bin/python`**。
- ⚠️ **行号会漂**。本文档行号是 `0457e39e` 上的实测值，引用前先 grep 现查符号名。
- ⚠️ **别用 2-3 次采样给高方差的量下结论**（§3 ①就是这么错的）。中转延迟的
  min 与 max 差 5 倍以上。
- 🔴 **`/api/health` 的 `code_matches_repo` 不能用来判断「快照是不是新的」。**
  ［实测］`services/runtime_provenance.py:113-115` 的 docstring 明写：指纹
  *"called once per process (`create_app`) and the result is reused by every
  health response"* —— **启动时算一次，之后所有 health 复用**。
  我提交 `38c06356` 之后取 health，它仍报 `code_matches_repo: True` +
  指纹 `bd9322cb…`，而那时快照里根本没有我的改动。
  > 讽刺的是同一个文件 :100-111 的 docstring 正是在讲「版本号会在最可能出错的
  > 时刻前进」这个 bug 类。缓存让它换了个形式复发：仓库前进了，health 仍报 True。
  > **唯一可信的现算点**是 `deploy_workbench_runtime.sh` 第 [2/3] 步
  > （它 `cd` 到快照后重新 `build_runtime_provenance`）。部署后指纹应该**变**：
  > 这次从 `bd9322cb…` → `4e7d8323…`（471 模块）。指纹没变 = 没部署成。
- ⚠️ **本机有 5 个 `intelligence.api.app` uvicorn 进程**（8788 / 8792 / worktree
  起的 8795 等）。任何 kill / 重启前先 `lsof -nP -iTCP:<port> -sTCP:LISTEN`
  现查归属，**别照 pid 记忆动手**。8792=pid 18034、8788=pid 79613 是
  `2026-08-08 17:2x` 的读数，重启后就变。
- ⚠️ **`deploy_workbench_runtime.sh` 部署的是工作树当前内容，不是某个 commit**
  （脚本第 40 行自己写明了）。所以它会把**未合并的分支代码**送上生产。
  这次就是这么把 `fix/first-turn-budget` 部到 8792 的——有意为之，但要知道
  自己在做什么；它只 rsync `intelligence/`，`docs/`、`复盘/` 的改动不受影响。

---

## 6. 明确不在范围

- ❌ 改 `AGENT_RUNTIME_BACKEND`（壳轴 A/B 仍无数据）
- ❌ 改 `MAX_BATCH_TOOL_CALLS=4`
- ❌ Phase 1 #1 的压缩策略——它要 `max_turn_input_tokens` 分布，
  而那要先有能跑完的 run。**顺序不能反：先会测 → 修预算 → 拿分布 → 再谈压缩。**
  （任务 1 顺带解决它的一半：逐轮观测的管道建起来后，token 与延迟走同一条路。）
- ❌ 任务 5 的自适应预算——除非 1-4 已经跑出稳定基线。提前做会让「同题两次
  结果不同」变成常态，把后面所有对照实验的地基抽掉。
- ❌ 清 `tmp/` 下 4 个历史工作 clone（是 `test_pytest_collection_scope.py`
  变异测试的唯一冲突源）

---

## 7. 做完请回写

- `agent-memory/20_projects/finance-workspace-private.md` 交接记录；
  并更新「🚦 Agent Runtime 线路」那节——它还写着 cockpit 那条🔴阻塞，
  以及「模型轴已定 = gpt-5.6-sol」，两条都已过期
- `docs/layered-rebuild-roadmap.md` Phase 1 第 2 项的限定（"决证只在 8788 验过"）
- 能力变更回写能力图谱并跑 `graph_audit.py`（应 exit 0）
