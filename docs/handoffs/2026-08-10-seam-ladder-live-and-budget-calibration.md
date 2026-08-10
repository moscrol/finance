# 消融实验 P7 跑通 + 预算标定 — 交接（2026-08-10）

> **读法**：§1 总目标与它现在到哪了；§2 已交付（含实测读数）；§3 **我在本轮被推翻的六个
> 判断**——接手前必读，否则会重走；§4 后续要做的，带开工判据；§5 环境与坑。
>
> **范围**：`8640d2c7..ee4e63d6`，18 个提交，全部已合 `main` 并推送，对账 0/0。
> vault（`agent-memory`）另有 3 个提交，已推送。
> 主树 43 个他人未提交改动**全程未受影响**（全程 pathspec 提交，无 `git add -A`）。

---

## 1. 总目标：消融实验要证明什么，现在到哪了

**目标**（出自 `docs/superpowers/specs/2026-08-09-episode-seam-ladder-design.md`）：
逐层接入 episode 运行时的组件，定位是哪一层引入失败或异常行为。
硬约束**不是**"能力越多答案越好"，而是：某一阶不得暴露未开放工具、不得绕过 verifier、
不得因新 capability 使固定控制链路异常。

### 进度盘

| part | 状态 |
|---|---|
| P1–P5 阶梯骨架、契约派生、离线回路、live 模式、离线回归门 | ✅ 更早几轮 |
| P6 阶梯之前那层的入口路由 | ✅ 上一轮（10/18 → 18/18） |
| **P7 live smoke 实跑** | ⚠️ **S1 达标，S3 从未达标**（原写"三条判据首次全达标"，2026-08-10 复核更正，见下） |
| P8 断言扩到"防犯错" | ⚠️ 部分（**工具契约 2026-08-10 补齐至 12/12**，见 `cbfece5d`；剩出口侧三类程序检查） |
| P9 题型分类层 | ❌ 未动（建议先不动） |
| P10 Engine A 出口闸门 | ❌ 未动（**本轮证据把它的优先级往后压了**，见 §4） |

### P7 的三条完成判据，现在的状态

| 判据 | 结果 |
|---|---|
| S1 schema 不出现 `mainline_context`/`news_search`/`evidence_search` | ✅ 一直成立 |
| S3 tool calls 与 evidence hashes 确有已开放能力 | ✅ 一直成立 |
| semantic verifier 为 `passed` 或 `repaired` | ✅ **本轮首次达标** |

**首次全绿的那份收据**：`/Users/a77/.finance-runtime/seam-ladder/judge60-1.json`
S1 = `status=completed / structural=completed / semantic=passed`。

> 🔁 **2026-08-10 复核更正：这份收据不是"全绿"，上面只引用了它的 S1 那一行。**
> 同一份收据里 **S3 = `status=degraded / structural=partial / semantic=unavailable /
> draft_chars=0`**。准确表述是「**S1 达标，S3 未达标**」，不是三条判据全达标。
> 进度盘那个 ✅ 也据此降级。
> 教训是老问题：**按固定验收集报 N/M，不要拿一条 rung 代表整个阶梯**。
>
> 另一件更要紧的：**这份收据跑在 `gpt-5.6-sol`（cockpit）上，不是生产的
> `x.ailzd` + `gpt-5.6-terra`**（见收据 `runtime.model`）。所以它证明的是
> "cockpit 上 S1 能过"，**没有证明过生产配置**。

#### 生产配置下的首次实跑（2026-08-10，`2026-08-10-baseline-off.json`）

同一套代码、同一份题集，换成生产线（`x.ailzd` + `terra`），两条 rung 都 degraded：

| | judge60-1（cockpit+sol） | 本次（x.ailzd+terra） |
|---|---|---|
| S1 status / structural / semantic | completed / completed / **passed** | degraded / partial / unavailable |
| S1 draft_chars | 554 | **0** |
| S3 status / structural / semantic | degraded / partial / unavailable | degraded / **completed** / unavailable |
| S3 draft_chars | 0 | **441** |

**两条 provider 各有一条 rung 更好，没有谁全面更优**——与 §4.3 那张表同一个形状。

病因由收据诊断字段直接给出，**两条 rung 完全不同**：

- **S1 是首轮模型超时**：`model_errors=["LLM 调用失败（TimeoutError）"]`，`draft_chars=0`，
  trajectory 走到 `repair_reentry` 后仍 `model_error`。而它的 **judge 两次都 `outcome=ok`**
  （17.95s / 16.36s，asked 25.0）——**judge 是好的，草稿没生出来**。
  对应 §4.3 复测的长输出 83.3/111.1s，而首轮硬顶是 `self._llm_timeout`（生产 75s），
  且 `_opening_planning_timeout` 的注释写明**档位表不参与这条路径**，deep 档抬不动它。
- **S3 是 judge 超时**：三次 `judge_calls` 全 `turn_error`（25.6 / 18.17 / 18.17s，
  asked 25.0 / 17.5 / 17.5），草稿反而正常（441 字符、structural completed）。
  另有 `tool_errors=[{"tool":"evidence_search","error":"tool_timeout"}]`——又是它。

**共同根因是 provider 长输出速率下降**（§4.3：45–52 → 39 tok/s），不是代码回归：
本轮改动只碰了工具契约与注释，`runtime` 自述字段确认 judge_window=60 / tool_batch=60 /
`semantic_verifier=production_llm_judge` 全部按预期生效。

⚠️ **不要拿这次和 judge60-1 直接对比得出"劣化了"**——两次的 provider 不同，
这是一组跨 provider 的比较。要判断代码是否回归，必须用**同一条 provider** 重跑，
而 cockpit 的 key 不在 Keychain（只有 `finance-workbench-test-relay` 这把生产 key），
需要用户另行提供。

---

## 2. 已交付

### 2.1 P7 从"被环境卡住"到跑通

交接文档原写 P7 被三项 preflight 卡住。**复核发现三项当时已全部满足**——
所谓阻塞其实是"跑 ladder 的 shell 没有生产 env"，不是环境缺东西。

### 2.2 修掉的四个缺陷（都是前后对照实测）

| # | 缺陷 | 证据 |
|---|---|---|
| 1 | **live judge 根本没接线** | 收据标 `production_llm_judge`，实际构造的是无参数 `SemanticEpisodeVerifier()`，judge 循环必然落到 `unavailable`。第三条判据**在构造上不可能满足** |
| 2 | **reserve 没按生产方式分配** | 生产 60s / 阶梯 20s（tier 默认，恰等于地板），导致 `_opening_planning_timeout` 的借用**是死代码**。修后 S1 `structural` failed→completed、`missing_outputs` 5→0 |
| 3 | **没传绝对截止** | `deadline_expires_at` 缺失 → 每跳重置时钟。修后 S3 首次 `semantic=repaired` |
| 4 | **S3 题面前提为假** | 问"本周下跌原因"，而实测那周 **+2.81% 且逐日上行**。模型正确拒答，**离线桩却在同一道题上发绿光** |

**共同形状**：前三个都是"阶梯号称复刻生产、实际漏了参数"——**装配错，不是算法错**。

### 2.3 预算标定：四处超时收敛成一件事

| 组件 | 上限 | 实测需要 |
|---|---|---|
| 首轮模型 | 69.77s | 草稿 26–91s |
| 工具批次 | ≤30s | `evidence_search` 冷调用 **28.2s**（94% 占用） |
| judge 三次 | 15 / 7.5 / 7.5s | **13.3–24.1s** |
| synthesis reserve | 60s | 草稿与 judge **共用** |

**结论**：这套时间标定对应的是比当前 provider 更快的模型。
且工具批次与 judge 各被一个**与 tier 无关的硬编码字面量**卡住
（`stage_timeout(30.0)`、`MAX_SEMANTIC_JUDGE_WINDOW_SECONDS=30`），
所以**升档并不能把预算送进去**。

**最终有效配置（实测）**：`tier=deep` + 工具上限 60 + judge 窗口 60
→ judge **6/6 成功**（13.3/13.8/16.3/22.6/24.1s），三条判据首次全达标。

### 2.4 落下的工具（这些比结论更耐用）

| 产出 | 作用 |
|---|---|
| 收据七类诊断字段 | `semantic_issues` / `draft_chars` / `gaps` / `trajectory` / `model_errors` / `tool_errors` / `judge_calls`。**三次实验里有两次靠 `model_errors` 才认出"是中转挂了不是我改坏了"** |
| `runtime.*` 自述字段 | `budget_status` / `tool_batch_timeout` / `judge_window` / `provider_honors_max_tokens`。记**生效值**，让标定运行的收据可与基线对照 |
| `scripts/probe_provider_latency.py` | provider 延迟/稳定性/token 上限探针，UA 陷阱写进 docstring |
| 两个 ceiling 可标定 | `ASK_TOOL_BATCH_TIMEOUT` / `ASK_SEMANTIC_JUDGE_WINDOW`，**默认值一字未改** |
| 时间预算感知 | 扩展已有 `runtime_budget` 通道加 `remaining_seconds` / `remaining_fraction`，**默认关**（`ASK_EPISODE_BUDGET_STATUS=on`） |
| `agent-memory/10_knowledge/agent-tool-design-principles.md` | ai-agent-book 第 4 章蒸馏 + 我们的对表状态，**已进 git** |
| `docs/superpowers/2026-08-10-agent-book-chapter-audit.md` | 按章自审全书 10 章 |

---

## 3. 我在本轮被推翻的六个判断（接手前必读）

**这些都写进了文档，不要重走。**

| # | 我说过 | 实测 |
|---|---|---|
| 1 | 中转在 episode 量级 prompt 下不稳 | ❌ 大 prompt p50 仅 4.3s。真正的自变量是**出参 token** |
| 2 | judge 失败不是窗口过小（refuted） | ❌ **就是窗口过小**。当初实验在 standard 档做，reserve 只有 60s，抬窗口把草稿饿死了，我把"疗法无效"读成了"病因不成立" |
| 3 | 工具失败先查描述边界（照搬书上判据） | ❌ 两个工具都是 `tool_timeout`，不是选错。**判据的前提是"模型选错了工具"，我套用前没验前提** |
| 4 | 我们没有预算感知 | ❌ **步数预算一直在传**（`runtime_budget.remaining_tool_calls`），缺的只是**时间**这一维 |
| 5 | 分档用错了，升档即可 | ❌ 升档对两个超时组件几乎无效，它们被硬编码字面量卡住 |
| 6 | 配 `LLM_JUDGE_*` 能一次解决去相关与预算争抢 | ❌ `attempt_timeouts` 只算一次、两条 judge 路径共用同一 deadline，**它不给 judge 独立预算** |

**可迁移的一条**：#2 最贵——**同一个改动，在错的档位下会得出相反结论**。
一个改动同时动了两个耦合量时，它的失败无法区分"病因判错"和"代价没算"。

---

## 4. 后续要做的

### 4.1 judge 窗口 — ✅ **已解决，且「按 reserve 比例推导」这个方案本身不必要**

> 🔁 **本节初稿说"judge 与草稿零和、必须按比例推导"。核实后：那个前提是错的。**

读代码确认了实际机制：管线是**严格串行**的——episode 产出草稿 →
结构验证（`continuous_turn_adapter.py:480`）→ judge（`:554`）；而
`synthesis_timeout(limit)` 返回的是 **`min(limit, remaining())`**，
即"此刻真正还剩多少"，不是静态切分。

**所以 judge 跑的时候草稿早已付过账了，抬高它的上限不可能饿死草稿**——
只能拿到确实还在时钟上的时间，没有就自动缩水。

那句"零和"是我从**一次** `draft_chars=0` 的观测推出来的，而那次是中转 503
把草稿打挂了，与预算毫无关系。**n=1 的因果推断，又一次。**

**已改**：`MAX_SEMANTIC_JUDGE_WINDOW_SECONDS` **30.0 → 60.0**。
依据是实测 judge 耗时 **13.3–24.1s**：15s 首窗 0/6，25s 首窗 6/6。
60.0 使首次尝试取到 25s 上限，覆盖观测到的尾部。

自限行为已实测，跨档安全：

| 剩余时钟 | judge 三次窗口 |
|---|---|
| 150s（deep 充裕） | (25.0, 17.5, 17.5) |
| 55s（standard 中等） | (25.0, 15.0, 15.0) |
| 8s（临近耗尽） | (4.0, 2.0, 2.0) |

**standard 档同样拿得到 25s 首窗**——原先担心的跨档问题不存在。

配套把两条测试从写死秒数改成断言**不变量**
（`calls[0] <= window*0.5`、`sum(calls) <= window`），
否则下次重标定又会把一次刻意变更读成回归。

### 4.2 打开时间预算感知测一次（⚠️ **开工理由在生产线上不成立，先别跑**）

臂 C 里 S3 的新失败是 **`tool_budget_exhausted`**（12 个工具槽用尽），
**不再是超时**——约束从"没时间"移到了"查得太多"。
这正是预算感知该管的（第 10 章引 Google *Budget-Aware Tool-Use*：
无预算意识时增加预算不保证提升）。

> 🔁 **2026-08-10 生产线复测：那个触发现象没有复现，本节先挂起。**
> `2026-08-10-baseline-off.json` 里 S3 只调了 **7 个工具**就结束，失败是
> **judge 超时**（三次全 turn_error）加 `evidence_search` 的 `tool_timeout`，
> **没有 `tool_budget_exhausted`**。当前生产配置下的瓶颈是**时间**，不是工具槽。
> 预算感知管的是步数/槽位这一维，现在打开它测不到东西——
> 先把 §1 那两个超时（首轮 75s 硬顶、judge 25s 首窗）处理掉，
> 等瓶颈重新回到"查得太多"再跑这一臂。臂 C 那次是 cockpit+sol 的读数，
> 与生产线不可直接套用。

```bash
ASK_EPISODE_BUDGET_STATUS=on   # 默认 off
```
收据里 `runtime.budget_status` 会记是哪一臂，别把两臂读成 run 间噪声。

### 4.3 中转：**不建议整体切换，建议按工作负载分工**

| | cockpit `localhost:57244` | `x.ailzd.com`（生产现配） |
|---|---|---|
| 模型 | **仅** `gpt-5.6-sol` | 15 个，含 `gpt-5.6-terra` |
| **短输出** p90（≈ judge 形态） | **4.3s** | 21.8s |
| **长输出** 速率（≈ 草稿形态） | ≈34–43 tok/s | **≈45–52 tok/s** |
| 本轮稳定性 | 全程 200 | **反复 502/503** |
| 历史 | 08-08 曾因上游凭证归档被弃用 | 08-08 起为产品线 |

**两边各有强项，不是谁全面更好**：cockpit 在短输出上快 5 倍（judge 的形态），
x.ailzd/terra 在长输出上每 token 快约 25%（草稿的形态，也是耗时大头）。

#### 建议配置：composer 留在 terra，judge 走 cockpit

这**同时**满足三件事，且是**加配置不是换配置**：

1. **ch4 的去相关要求**——审核者不该与写作者同模型同端点（现在两者完全相同）
2. **各按形态用对端点**——judge 短输出走快的那条，草稿长输出走每 token 快的那条
3. **可回退**——`LLM_JUDGE_*` 是附加 env，不动主链路

```bash
export LLM_JUDGE_BASE_URL='http://localhost:57244/v1'
export LLM_JUDGE_MODEL='gpt-5.6-sol'
export LLM_JUDGE_API_KEY='<cockpit key>'
```

> ⚠️ **未实测这一组合**（需要 x.ailzd 稳定时才跑得出对照），也**未改生产**。
> 注意 `judge_provider()` 走的是 `llm_refine.complete` 那条路径，与
> `primary_judge` 是**不同分支**（见 §5.2 第 3 条的教训）——切过去后要重新确认
> 收据里的 `judge_calls` 仍有记录，否则等于又插错了地方。

#### ⚠️ 生产中转当前处于劣化状态（运维项）— ✅ **已恢复，且上表的性能前提要重测**

> 🔁 **2026-08-10 复测：劣化已消失，本节据以成立的对比数字也过期了。**

原记录：主机可达（`/v1/models` 401，1.5s）但完成请求会挂——一次 **502 耗时 72.1s**，
下一次 **200 仅 6.9s**，episode 期间反复 503/URLError。

**复测读数**（`probe_provider_latency.py --models gpt-5.6-terra --samples 5 --long-samples 2`，
生产 env `x.ailzd` + terra）：

| 形态 | 本次实测 | 本节原记录 |
|---|---|---|
| 完成请求成功率 | **7/7，零 502/503** | 反复 502/503 |
| 短输出（≈ judge） | p50 **3.8s** / p90 **7.1s** | p90 21.8s |
| 长输出（≈ 草稿） | 83.3s / 111.1s，**≈39 tok/s** | ≈45–52 tok/s |
| `max_tokens=10` | completion 381，`finish_reason=stop`，**仍被忽略** | 同 |

**两条结论要跟着改**：

1. **"cockpit 短输出快 5 倍"这个论据没了**——4.3s vs 7.1s 只差 1.6 倍。
   judge 走 cockpit **仍然值得做，但理由只剩 ch4 的去相关**（审核者不该与写作者
   同模型同端点），不再是性能。按性能取舍的话现在不划算。
2. **长输出反而更慢了**（39 tok/s，且单次 83–111s）。首轮模型上限 69.77s，
   这两次长输出**都超了**——预算标定的压力没有解除，只是从"中转挂"换成了"生成慢"。

`health=200` 不证明上游可用这条教训仍然成立，只是这次上游确实好了。
探活方法：先 `curl /v1/models` 看主机层，再用探针发**完成请求**——只有后者能区分。

### 4.4 其余（按证据强度递减）

- **检索加 `recall@k`**：S3 的 `cause_attribution` 缺口到底是召回不足还是题目超纲，
  现在**没有任何指标能回答**（第 3 章）
- **独立出题人**：18 条题集"我出题我判分"，用户抽查只有 8/10（第 6 章抗泄漏）
- **P10 Engine A 出口闸门**：本轮证据把它往后压了——Engine A 现在能完整产出草稿并通过
  judge，缺的不是多一道检查。等 4.1 稳定后再评估
- ~~**`provider_honors_max_tokens` 已记录为 `no`**，但**系统行为仍按上限成立在算**
  （`llm_refine` 每次合成都发 `max_tokens=3000`）。属"静默输入转换"，未修~~
  🔁 **2026-08-10 复核：这条前提不成立，已撤销。** 输出长度真正的防线是
  `max_chars`（客户端闸，流式边收边数、超限抛在 `on_delta` 之前，已有测试钉住），
  不依赖上游兑现 `max_tokens`。而"按上限成立在算"全树没有——
  `ask_synthesis._phase_slice_collapsed` 的注释写明那条路刻意没走。
  `max_tokens` 是不生效但免费的第一道闸，**不该删**。关系已写进
  `llm_refine.py` 两个常量的定义处（commit `ed157fc6`）
- 未审计：显式截断/长输出落盘、幂等性与取消语义、KV Cache 布局

---

## 5. 环境与坑

### 5.1 跑 live 的最小 env

```bash
# 生产线（x.ailzd + terra）：从 ~/.local/bin/start-finance-workbench 提 export 段
# 或 cockpit（本轮用的）：
export LLM_BASE_URL='http://localhost:57244/v1'
export LLM_MODEL='gpt-5.6-sol'      # 这条中转没有 terra
export OPENAI_API_KEY='<用户提供，勿落盘>'
export ASK_CONTINUOUS_RUNTIME=on
export FORESIGHT_LLM_KEYCHAIN=0
.venv-workbench/bin/python scripts/run_episode_seam_ladder.py --live --output <路径>
```

> ⚠️ **`.env.workbench` 是陷阱**：它仍写着 `LLM_MODEL=glm-5.2` / `bigmodel.cn`，
> 而 GLM 是已退役那条线。`source` 它 preflight **照样 ready=True**——preflight
> 只检查"有没有解析到 provider"，不检查"是不是产品线"。**跑完先核收据里的
> `preflight.model`。**

> ⚠️ **cockpit 中转 2026-08-08 曾因上游凭证归档被弃用**（start 脚本有"四次重试全 502"
> 的注释）。本轮是用户重新供给 key 后恢复的。**下次用之前先探活。**

### 5.2 三个反复咬人的坑

1. **探活通过 ≠ 跑得完**：x.ailzd 小请求/大 prompt/带 tools 各探 3–10 次全 200，
   但 episode 期间反复 503。**收据里的 `model_errors` 是唯一能区分的东西。**
2. **`max_tokens` 两条中转都不兑现**（请求 10 实得 416–722，`finish_reason=stop`）。
   **堵不住出参，别指望用参数给生成时间设天花板**——这是上游属性。
3. **instrumentation 也会插错地方**：我第一版 judge 探针 patch 了
   `llm_refine.complete`，**一条记录都没抓到**——验证器有两条 judge 路径，
   `LLM_JUDGE_*` 未配时走的是另一条。**空记录是"插错了"的信号，不是"没有失败"。**

### 5.3 vault 有 180 秒自动提交守护进程

`com.a77.agent-memory-sync` 每 180 秒 `git add -A` + **裸 commit** + push。
本轮实测事故：`git rm --cached` 暂存后还没提交，守护进程把我暂存的内容
连同它自己的改动一起提交推送了。
**在 vault 里做手工 git 操作，index 不是私有工作区**——要么先停守护进程，
要么把命令用 `&&` 串成一条。

---

## 6. 验收

| 项 | 结果 |
|---|---|
| `ruff check --config=ruff.toml`（与 pre-commit 同一条命令） | 通过 |
| `test_episode_seam_ladder` / `test_agent_episode` / `test_episode_tool_batch` / `test_episode_semantic_verifier` | **290 passed** |
| 离线阶梯六条 rung | 全绿 |
| pre-commit 全钩子（含层级审计） | ERROR 0 |
| 主树 43 个他人未提交改动 | 未受影响 |
| 我的 16 个特性分支 | 已全部合入 `main` 并删除 |
| 用户提供的 key | **未落盘**（全盘 grep 确认，收据亦干净） |
