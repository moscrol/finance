# 共享层审计与合成链解阻 — Codex 对齐 TODO（2026-08-03）

> **给 Codex 的读法**：第 0 节是已定案事实，**不要重新论证**。T1 是唯一阻塞项，
> T2 可并行，T3 依赖 T1 的数字，T4 必须等 T1/T3 完成。每个任务给了完成判据，
> 判据没满足就不要报完成。

---

## 0. 起点状态：已定案，不要重开

以下结论已写入 `docs/verification/2026-08-03-a4-grounded-budget-m2-triage.md`
（更正版，commit `07887e92`）。它们是本轮的**前提**，不是待验证项。

| 事实 | 值 | 证据 |
|---|---|---|
| brief 自然完成耗时 | **69.740s** | `smoke-phase-check.json@6c16b73a`，A1，17/17 claim |
| composer 耗时下界 | **>20.261s**（被 child 截断，非完成值） | 同上 |
| judge 耗时 | **无任何样本**（历史全部 artifact 中从未运行过） | 全量 phase 扫描 |
| 当前预算 | root=120s，child=115s，brief cap=`115×0.25`=28.75s，judge reserve=28.75s | `ask_synthesis.py` `_GroundedPhaseBudget` |
| PRIMARY | 三次串行 LLM 的工作量与 115s child / 120s root **不相容** | H5 = CONFIRMED |
| 当前分支 | `fix/grounded-chain-critical-path` 是**负实验收据**，不是 merge-ready 产品修复 | 同上 |

**推论（已定案）**：给足 brief 约 70s 后，composer 只剩约 16.5s，低于其观测下界。
**继续调 cap 是死路。** 不要再做 brief-only replay、不要再逐级加秒、不要再跑 live A 组。

### 语义分期（读历史 artifact 必须先分期）

`elapsed_ms` 在不同 revision 含义不同，跨期用同一分类器会读错：

| epoch | revision 范围 | `elapsed_ms` 的含义 |
|---|---|---|
| **E0** | `< cd175a0e` | phase 时间片**未在网络强制点被读取**；是自然完成值或 child 截断值 |
| **E1/E2** | `>= cd175a0e` | grant 被硬执行；失败时 `elapsed_ms ≈ grant`，只是**下界** |

根因见 `intelligence/services/llm_refine.py:117-128` 的 `call_timeout` docstring
（时间片传下去了但消费端没读——「预算字段必须在强制点被读取」）。

---

## 1. 工作区现状（开工前核对）

```
主工作树   /Users/a77/finance-workspace-private   branch: fix/grounded-chain-critical-path
运行时工作树 /Users/a77/.finance-runtime/finance-workspace-751ef706  (detached 751ef706)
解释器     .venv-workbench/bin/python   (3.12.13；系统 python3 是 3.14，缺依赖)
脏文件     15 个（含用户既有未跟踪文件，勿擅自清理）
```

**红线**：
- 运行时工作树属主是 launchd，**不要手工 kill + nohup 起服务**；切指针必须走重启流程。
- 离线 replay 脚本**加载哪份代码由 cwd 决定，不是 PYTHONPATH**——必须在主工作树根目录执行。
- 跑测试一律 `.venv-workbench/bin/python`。13 条红是宿主基线，不是你引入的。

---

## T1 — 【阻塞】离线 replay 取得 composer / judge 的完成值

### 为什么这是第一件事

T3 的架构选择（扩容 vs 确定性 brief）需要知道整链到底要多少秒。现在缺两个数：
composer 只有下界，judge 一个样本都没有。**没有这两个数，扩容方案报不出目标值，
E 方案也说不清省了多少。**

### 关键前提：不用重跑 brief

那次成功 brief 的产物**完整留在盘上**：

```
/Users/a77/agent-memory/.foresight/linxiaoqi5111/runs/run_20260803_142959_204791/
  ├── decision_brief.json           # 8 字段齐全，deterministic_issues 为空
  ├── answer_spec.json              # 冻结的合成输入
  ├── daily-review-skill-result.json
  └── grounded_composer_shadow.json # 同一份 brief 也在这里
```

`decision_brief.json` 字段：`direct_answer` / `core_tension` / `supports`(6) /
`counterevidence`(2) / `unknowns`(1) / `upgrade_conditions`(2) /
`downgrade_conditions`(2) / `chain_mapping`(**0，空**)。

所以 composer 可以**直接吃这份冻结 brief**，零成本跳过 70 秒。

### 要做的

1. 新建 `intelligence/eval/grounded_replay.py`，一个离线 replay 入口：
   - 输入：`--run-dir <foresight run 目录>`、`--phase {composer,judge}`、`--grant-seconds N`
   - 从 run 目录读冻结的 `answer_spec.json` + `decision_brief.json`，
     复用 `ask_synthesis.py` 里现成的 prompt 构造（**不要另写一份 prompt**，
     否则测的就不是生产路径了）
   - 输出一份 artifact：`status` / `elapsed_ms` / `completion_tokens`（provider
     没给就写 `null`，**不要估算**）/ `finish_reason` / 产物文本
2. 先跑 composer：`--grant-seconds 115`，记录它**自然完成**需要多久。
3. composer 成功后，用它的输出跑 judge：`--grant-seconds 115`，取得 judge 首个样本。

### 待检验的预测（写进 artifact，跑完对账）

冻结 brief 输出 1098 chars / 69.740s ≈ **15.7 chars/s**。composer 的
`max_tokens=2400` 是 brief `1200` 的两倍（`ask_synthesis.py:1805` vs `:1876`）。
若吞吐相近且产出按 token 上限等比放大，**预测 composer ≈ 110–180s**。

- 若落在该区间 → 整链 ≈ 70 + 140 + ~70 ≈ **280s**，`120s root` 差约 2.3 倍，
  T3 应选 E（或 deep-mode 大幅扩容）。
- 若 composer 显著快于预测（<40s）→ 吞吐模型错了，T3 的扩容方案重新变得可行，
  此时才允许讨论 root 扩容的具体秒数。
- 若 composer 在 115s 仍超时 → 记为 `>115s` 下界，**不要再加秒重试**，直接判 E。

### 完成判据

- [ ] `grounded_replay.py` 存在，能在主工作树 cwd 下跑通
- [ ] composer 的 `elapsed_ms` 有确定值或明确的 `>115s` 下界
- [ ] judge 至少有一个样本（composer 成功的前提下），或明确记录「因 composer 未完成而无法取得」
- [ ] 三段真实耗时写回 M2 报告的 residual_uncertainty 段，把 judge 那条 unknown 消掉
- [ ] **零次 live A 组运行**

---

## T2 — 【可并行】把 `synthesis_health` 变成阻塞门禁

### 现状

`intelligence/eval/synthesis_health.py` **已经存在且正确**。四态口径
（`full_pass` / `released_unverified` / `template_fallback` / `not_synthesized` / `unknown`）
已经实现，旧产物也已单独归入 `unknown` 而不是默认算好。实测：

```bash
.venv-workbench/bin/python -m intelligence.eval.synthesis_health \
  intelligence/eval/runs/20260803T091451Z-a4-post-budget-fix.json
# → 模板降级 1/1；真实完整通过率：0/1 = 0%
```

**它只差一个退出码。** 现在它永远返回 0，所以不能当门禁用。

### 技术选型（对比，选 A 先做）

| 方案 | 做法 | 成本 | 换来什么 | 判断 |
|---|---|---|---|---|
| **A（选）** | `synthesis_health.py` 加 `--gate --min-full-pass N`，不达标退出码 1 | 零新依赖，约 2 小时 | 确定性断言、CI 可用 | **先做这个** |
| B | 引入 Promptfoo（OpenAI cookbook 用的那套） | Node 依赖 + YAML 配置 + LLM-judge 调用费 | LLM 语义断言、现成报告 UI、eval 用例可版本化 | 有语义断言需求时再引入 |
| C | 复用 `agent_eval.py` 的确定性打分器 | 中 | 已有 hard gate 框架 | 它管的是引用/免责声明/工具预算，**层级不同**，别硬塞 |

> **为什么不直接上 Promptfoo**：门禁的第一需求是「三段跑没跑完」，这是**确定性**判断，
> 不需要 LLM 当裁判。用 LLM-judge 去判一个 JSON 字段存不存在，是把确定性问题
> 随机化。Promptfoo 的价值在语义断言（比如「正文是否真的回答了双红问题」），
> 那属于下一层，等 T1/T3 解阻后再引。
> **可迁移知识点**：门禁分层——确定性断言在前、语义断言在后。语义门禁挂了要能
> 区分「被审对象坏了」还是「裁判自己抽了」，确定性门禁没这个歧义，所以它该先建。

### 要做的

1. `synthesis_health.py` 加 `--gate`：
   - `--min-full-pass <float>`：真实完整通过率低于阈值 → 退出码 1
   - `--fail-on-unknown`：出现 `unknown` 口径的 turn → 退出码 1（防止旧产物混进来被当成通过）
   - 保持默认行为不变（不带 `--gate` 仍然只打印、退 0），**别破坏现有调用方**
2. 加测试：对 `20260803T091451Z-a4-post-budget-fix.json` 断言 `--gate --min-full-pass 1.0`
   退出码为 1；对一个构造的 full_pass artifact 断言退出码为 0。

### 完成判据

- [ ] A4 的两份 artifact（pre/post）在 `--gate --min-full-pass 1.0` 下都退 1
- [ ] 不带 `--gate` 的输出与现在逐字一致
- [ ] 测试覆盖「full_pass 通过」和「unknown 被拦」两条路径

---

## T3 — 架构决策：扩容 vs 确定性 DecisionBrief（依赖 T1）

**在 T1 出数之前不要动手实现任何一个方案。** 这里只写清判据和各自的范围。

### 选项 A：扩容 root / 引入 deep-mode

- 前提：T1 显示整链总耗时落在一个可接受的墙钟内。
- 影响面：A4 canary 的 120s 判据本身要重新定义；用户侧等待时长要重新取舍。
- **这是产品决定，不是工程决定**——不要自行拍板扩到多少秒，出数后交用户定。

### 选项 E：确定性 DecisionBrief（砍掉一次 LLM 往返）

`DecisionBrief` 定义在 `intelligence/services/answer_model.py:414-438`，8 个字段。
按 M2 的拆分：

| 字段 | 性质 | 说明 |
|---|---|---|
| `direct_answer` | 投影 | 可从 answer_spec + skill 契约确定性生成 |
| `supports` / `counterevidence` / `unknowns` | 投影 | 已是 claim id 引用（如 `daily-review:fact:2`） |
| `upgrade_conditions` / `downgrade_conditions` | 投影 | 同上，冻结样本里也是 claim id |
| `chain_mapping` | 投影 | 冻结样本里为**空**——见下方风险 |
| `core_tension` | **生成** | 这是真正需要语言模型的那一个字段 |

- **不要把 8 个字段都称作纯投影。** `core_tension` 在冻结样本里是一段有判断的自然语言，
  确定性映射做不出来。要么单独留一次极小的 LLM 调用，要么降级为模板化表述并
  显式标注，二选一，在设计文档里写明。
- **风险项**：冻结样本 `chain_mapping` 为空（`n=0`）。`answer_model.py:422-425`
  的注释说明这个槽位当初就是为了让 12 条 `company:` claim 有处可放才加的，
  空值会让下游 `chain_mapping` 必需输出不满足而 fail-closed。冻结样本是 A1
  （市场总览，可能本就无产业链映射），**A4 未必同理**。做 E 之前先确认
  A4 的 registry 里有没有 `company:` claim。

### 完成判据

- [ ] T1 的三段耗时数字已入档
- [ ] 两个方案各写一段「若选它，A4 canary 判据如何改」
- [ ] 交用户决策，**不自行选定**

---

## T4 — 跨 harness 共享层审计（解阻后才做）

### 为什么必须排在最后

自建 Agent 的 synthesize 段现在有一个**必然触发**的阻塞。此时跑 5–6 个跨 harness
对比任务，任何碰到合成链的任务首次分叉都会落在 `synthesize`，把其它真实差异全部盖住。
会拿到 6 条 trace 说同一件事。**先解阻，再审计。**

### 第 0 步是归一化，不是采数

Agents SDK tracing 给的是 span（generation / function call / handoff / guardrail）；
Codex 给的是 rollout session JSONL。粒度和语义不同，**在不可比的 trace 上做首次分叉
得到的是格式差异，不是行为差异**。

复用现成词表——`docs/verification/2026-08-03-a4-grounded-budget-m2-triage.md` 里
那套 L1 step：`configure / intent / route / retrieve / observe / synthesize / stop`，
以及 `native_or_normalized` 字段。先把 Codex 侧的外部行为映射到这七步，别的都是后话。

### 要做的（解阻后）

1. 定义 `docs/trace-profile.md` 的跨 harness 扩展：Codex rollout → 七步词表的映射规则
2. 选 5–6 个「Codex 里效果好、自建里明显变差」的任务，两侧各跑一次
3. 按 M2 那套 A/B 差分格式出报告：first_divergence_step + pre_divergence_equivalence
4. 换不换 SDK 的结论**放在最后**——目前为止的全部证据都没有指向 SDK

---

## 5. 明确不要做的事

- ❌ 再跑 brief-only replay（69.740s 完成值已存在）
- ❌ 逐级调大 brief cap（已证伪：给足 brief 后 composer 必挂）
- ❌ 在 T1 出数前跑 live A 组 10 题
- ❌ 引入 `halo-engine`（0.3.x 第三方包）做优化建议——本轮真实 bug 是「没人读
  隔壁目录的 artifact」，一个扫 OTel trace 的 LLM optimizer 会犯同样的错
- ❌ 把 `fix/grounded-chain-critical-path` 合进 `main`（它是负实验收据；合并需用户确认）
- ❌ 手工 kill/nohup 运行时服务

## 6. 本轮方法论沉淀（值得写进 `.agent-memory/10_knowledge/`）

**声明「缺某个测量值」之前，先扫相邻 artifact 和代码内实测注释。**
本轮 M2 初版判 H5 = INCONCLUSIVE 并计划再花一次调用去测 brief，而那个数
（69.740s）当时既在同目录的 `smoke-phase-check.json` 里，也逐字写在
`llm_refine.py` 的 docstring 里，全程在工作树中。
扫描全部 phase artifact 的成本是一条 20 行的脚本，比一次 live run 便宜两个数量级。

---

**参考**：OpenAI cookbook《Agent Improvement Loop with Traces, Evals, and Codex》
<https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop>
（Traces → Feedback → Promptfoo Evals → Validation → HALO → codex_handoff.md）。
本 TODO 借用了它的 loop 形状与 handoff 段落契约，**未采用** HALO 依赖与合成数据闭环，
理由见 T2 选型表与第 5 节。
