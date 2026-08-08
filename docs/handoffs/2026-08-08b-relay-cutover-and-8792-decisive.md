# Handoff: 生产 8792 切中转（已完成）+ 预算档位重标定（未完成，交 agent A）

> **日期**：2026-08-08，最后更新 15:2x
> **写给**：agent A
> **前一份**：`2026-08-08-prior-recall-and-runtime-fixes.md`（读订正后的版本）
> **范围 revision**：`0457e39e`（main，未 push）
> **用户决策**：不再用 cockpit；出口切到中转 `https://x.ailzd.com/v1`

---

## 0. 状态一句话

**出口切换已完成并逐层验通。生产 research run 仍然跑不通**，卡在一个新暴露的
问题上：**这套预算档位表是按一个快 3-5 倍的 provider 标定的**，中转的延迟分布
落在预算之外，第一次模型调用就被掐断（一次调用、零个工具）。

剩下的活**不只是把数字调大**。复盘时定位到两个更根本的问题（§2.4）：
BYOK 下静态秒数不可能正确，而系统**从来不测 provider 延迟**（实测：全树零命中），
所以它没有自校准所需的输入；另外 reserve 的逻辑在第一步是反的——它为一场
不会发生的合成攒时间，饿死了唯一能启动这一切的那次调用。

**任务顺序按这个结论排过，别跳**（§4）：先让它会测 → 再修首轮那一刀的切法
→ 再用真实分布重标定 → 再验决证。

⚠️ **我做了两次尝试，都没解决**（换模型、加回合预算旋钮）。两次的过程和数据都
留在下面，因为它们**排除了两个看起来最像的原因**，能省下你重走一遍的时间。

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
  → verification_reserve = min(40, T/3)          continuous_turn_adapter.py:66,399
  → runtime_timeout      = T − verification_reserve
  → _generic_research_deadline 再与 ResearchPolicy 档位 min 封顶
      quick 30s / standard 90s / deep 240s        research_contract.py:392-394
  → 再扣 synthesis_reserve（standard 20s / deep 48s）
  → stage_timeout = min(llm_timeout=75, remaining − reserve)   research_contract.py:356
  → **这个值就是 HTTP 请求超时**              glm_agent_runtime.py:154/277 `timeout=remaining`
```

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

### 2.4 但「把数字调大」只是止血 —— 结构上有两个更根本的问题

这一节是用户在复盘时问出来的，比上面的数字更值得先读。

#### (a) BYOK 下，静态秒数不可能正确 —— 而系统从来不量延迟

provider 是用户插进来的：官方 API、中转、本地模型、限流的免费额度，
延迟能差一个数量级。**任何写死的秒数都只对标定它的那个 provider 成立。**

［实测 `0457e39e`］全树搜过 `adaptive` / `ewma` / `latency` / `elapsed` /
`observed_*` / `calibrat*`：`intelligence/` 里（`eval/` benchmark 除外）
**没有任何一处测量或记录 provider 的调用延迟**。真正发请求的
`glm_agent_runtime.py`，`elapsed` / `latency` / `duration` 三个词零命中。

所以现状准确的描述是**半动态**：

| 维度 | 状态 |
|---|---|
| 「还剩多少时间」 | ✅ 动态。`stage_timeout = min(llm_timeout, remaining − reserve)`，`remaining` 实时算；`synthesis_reserve_for_task` 还是个按任务算的函数 |
| 「provider 有多快」 | ❌ **完全瞎**。全部输入（档位总秒数、各 reserve、`llm_timeout=75`）都是硬编码常量 |

知道自己还剩多少、不知道对面要多久——这个组合下剩余时间算得再准也没用。
**这就是为什么这套系统在 BYOK 下没法自校准：它没有校准所需的那个输入。**

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

### 任务 1（前置，先做这个）：让它会测

**这一条我最初列成「补可观测性」，当成事后能查的诊断增强。那是低估了。**
它是自适应预算的**前置条件**，不是可选项——见 §2.4(a)：系统对「provider 有多快」
完全是瞎的，而 BYOK 下这个输入不可能靠写死获得。

两件事，都写进 trace：

1. **每次模型调用的实际耗时**。`glm_agent_runtime.py` 现在连 `elapsed` 都不记
   （实测三个词零命中）。记 elapsed + 用掉的 provider + 那次调用**分到的
   stage 预算**——后两者缺一，就没法判断「超时」是 provider 慢还是预算小。
2. **本次生效的档位与预算**。现在 `report.json` / `trace.jsonl` 里
   `research_tier`、`total_seconds`、`stage_timeout` **一个都查不到**，
   事后无法判断一个 run 跑在哪档、首轮拿到几秒。我这次全靠读代码倒推。

按路线图「一块」的四件（可达性/契约/观测/变异测试），**观测这件缺着**。
做完这条，后面所有预算类问题一眼可见，也不必再手工跑 N=8 的探针。

### 任务 2：让第一次模型调用不吃 reserve

见 §2.4(b)。这是结构修正，可能比调数字更根本，而且**改动面比重标定档位表小**
（不动那张全局表，只动首轮那一刀的切法）。

判据不是「数字变大了」，而是：**首轮 stage 预算 ≥ P95**（当前 50s），
且后续轮次的 reserve 行为不变——现有那些「到点还能交出有依据答案」的测试
必须全绿，一条都不能松。

### 任务 3：用实测分布重标定 ResearchPolicy 档位表

`intelligence/services/research_contract.py:390-396`：

```python
"quick":    cls("quick",    3,  30.0, 20.0),
"standard": cls("standard", 6,  90.0, 20.0),
"deep":     cls("deep",     12, 240.0, 48.0),
```

任务 1 做完后**用 trace 里的真实分布**标定；在那之前可以先用 §2.2 那份
（N=8，只覆盖 terra 一个模型、一个时段）作为临时依据，但要在 commit message
里写明样本来源与局限。

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

### 任务 4：跑通生产线决证

预算修好后，在 **8792** 上跑：

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

### 任务 6：8788 去留（**需先问用户**）

8788 仍在跑（pid 79613，rev `9380b3b9`，落后 main），且 health 里没有
`loaded_code_root` / `code_matches_repo`——**它自己不知道自己漂了**。

我原本建议关掉，但**在 8792 跑通之前不要关**：8788 是目前唯一跑通过完整
`memory_lookup → prior_recall` 链的线，关了就失去对照。**任务 4 通过后**再处理。

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
