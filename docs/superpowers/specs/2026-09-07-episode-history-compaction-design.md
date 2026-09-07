# 设计：Episode 历史压实——工具观察先瘦身、再按批折成 E 号索引；不调模型、不动账本

日期：2026-09-07
状态：**两刀已实施（#635 lean / #636 折叠，main `e1d22b89`），env 缺省关；候选口 A/B n=3 见 `docs/verification/2026-09-07-branch-level-trace.md` §13——成本轴成立（折叠 −30–57%，10 轮对 10 轮每次调用 −20%），出口不退，绑定数 n=3 判不出，缺省未翻。** 实施与本稿差异：折叠函数放 `services/episode_history_compaction`、loop 直接调（未经 harness 方法）；`history_compacted` 事件不映射阶段。（原状态：设计稿。） 上文 `docs/verification/2026-09-07-branch-level-trace.md` §10–§12（读数）。
父稿：`2026-09-03-subagent-tool-design.md`（分支证据经父账本、按 E 号绑）；`2026-09-02-capability-amplification-output-gate-design.md`
§3.5（两家的上下文管理都是插件）。dsh 形状只读 `/Users/a77/deepseek-harness/packages/compaction/{compaction-basic,compaction-tool-result-pruner}/README.md`。

---

## 0. 一句话

**上下文成本 = 模型轮数 × 历史长度，而历史里 90% 是不再需要原文的东西。** 同题 17 遍读数：工具消息合计稳定 5–12 万字，每一轮都把它们原样重发；
19 轮那遍重发累计 96 万字，占 126 万 input tokens 一大半。第一把杠杆（派发节奏注入，#628）只对分支有效——父臂的单工具轮多是
search → fetch → l3 这种真依赖，压不下轮数。所以压**每轮重发的历史**：① 当前观察去掉模型用不上的脚手架字段（−22–28%）；
② 比最近 K 批更早的工具观察折成「E 号 + 标题 + 日期」索引（每条 ≈ 原文 10%）。**不调模型做摘要**（我们已经有证据账本，E 号就是摘要）、
**不动 durable 事件与绑定校验**（`admit_finish` 按累计证据表解 E 号，与消息里写了什么无关）、**不动 `sub_research` 当前那条**（那是分支真取到的证据，
是能力不是浪费）。模拟：lean + K=2 把重发量压到今天的 30–55%。

---

## 1. 先看清现状 [实测 2026-09-07，读自 gitea/main `c04acc37` 与今日 17 个同题 run]

### 1.1 已有的东西（不用建）

| 件 | 位置 | 现状 |
|---|---|---|
| 单条观察的模型视图 | `research_harness.project_tool_result` → `prune_tool_observation` → `budget_tool_observation` → `strip_hashes_for_model` | 去重叙述、按预算截断 observation / 每条 title·detail、去 hash 只留 E 号；**审计底稿全量另存**，两个出口 |
| 证据序号 | `evidence_ordinal_table(evidence_so_far)`；`_EpisodeToolAccumulator.evidence` | E 号按首次出现分配、整个 episode 稳定；`admit_finish` 用累计证据表把 E 号解回 hash |
| 预算注入 | `_append_tool_budget_state` | 只挂在**最后一条** tool 消息上（`runtime_budget`），#628 加了派发节奏 |
| 历史 | `ContinuousAgentEpisode.run` 里的 `messages` list；修复轮经 `_EpisodeContinuationState.messages` 复用同一份 | 每轮 `self._model.complete(messages=list(messages), …)` 原样全发；没有任何折叠 |
| 度量 | `services/context_growth.py`（按轮计 token 账单）；`eval/capability_frontier.ContextEfficiency.tool_message_chars / resent_chars_estimate`（#626） | 能从落盘工件重算每条 tool 消息的模型视图字数与重发累计 |
| 缓存 | `split_episode_prompt` docstring：「System is byte-stable… cache_control is not implemented」 | 没有依赖 provider 前缀缓存，改历史不损失已有收益 |

### 1.2 字数都在哪（`run_20260907_164332_208527`，8792，10 轮）

| tool 消息 | 证据条数 | 模型视图字数 | 其中 observation | 其中 evidence JSON | evidence 里 detail | evidence 里 title | 折成 E 索引 |
|---|---|---|---|---|---|---|---|
| `sub_research` | 132 | 55,285 | 716 | 51,953 | 13,113 | 2,772 | 6,239 |
| `finance_query` ×2 | 20 / 25 | 9,899 / 12,297 | 902 / 902 | 8,013 / 10,355 | 2,013 / 2,505 | 360 / 500 | 980 / 1,275 |
| `evidence_search` ×2 | 12 / 9 | 7,753 / 6,333 | 904 / 902 | 6,034 / 4,640 | 2,518 / 2,160 | 200 / 112 | 522 / 354 |
| 8 条合计 | 212 | **97,936** | | | | | **10,066（10%）** |

两个事实：
- **evidence JSON 的 2/3 是脚手架**：`sub_research` 那条 51,953 字里 detail 只有 13,113、title 2,772，其余 ~36,000 是每条都带的
  `"supports": []` `"contradicts": []` `"independent_key"` `"freshness"` `"evidence_tier": ""` `"source"`（常与 independent_key 同值）等键值——
  模型引用只用 E 号、标题、正文、来源、日期、分档；`independent_key` 是校验器判来源独立性用的，`supports/contradicts` 几乎全空。
- **折成索引只剩 10%**：E 号 + tool + 标题前 60 字 + 日期，就足够模型在收尾时知道「E37 是哪条、能不能绑」。

### 1.3 重发量（17 个同题 run 的模拟；口径见 §6.3 脚本）

| run | 轮数 | tool 消息字数 | 重发累计（现状） | 仅 lean | lean + K=2 折叠 | lean + K=1 |
|---|---|---|---|---|---|---|
| `134001`（19 轮离群） | 19 | 77,249 | 962,987 | 718,901 | **307,763** | 269,210 |
| `164332`（8792 切后） | 10 | 97,936 | 680,884 | 491,346 | **271,140** | 224,675 |
| `033140` | 15 | 81,507 | 673,384 | 500,518 | **254,267** | 216,091 |
| `123827`（8792） | 9 | 77,133 | 499,660 | 362,235 | **205,236** | 169,524 |
| `120927` | 5 | 100,162 | 388,214 | 282,632 | **196,396** | 150,140 |
| `161748` | 5 | 104,451 | 283,489 | 208,933 | **168,396** | 123,828 |
| `105656` | 4 | 81,765 | 221,324 | 158,510 | **129,393** | 96,814 |
| `110932`（2 轮） | 2 | 94,394 | 76,612 | 54,267 | 54,267 | 54,267 |

lean 单独 −22–28%；lean + K=2 把重发累计压到现状的 **32–58%**，轮数越多省得越多；轮数 ≤ K+1 时与 lean 相同（没有可折的）。
这是字数不是 token；同题 input_tokens 与重发字数同向（§1.2 那遍 97 万 tokens 对 68 万重发字）。

### 1.4 为什么不是「少点几轮」

#628 之后 n=3：分支 9 支里 7 支按帽成批；父臂三遍 [1,1,1,6,0] / [1,8,1,1,0] / [1,1,1,1,1,1,1,1,0,0]。父臂的单工具轮点的是
web_search → web_fetch → l3_lookup（下一步取决于上一步），本来就该逐轮；注入里「只有依赖时才逐轮」那句恰好放行了它们。
轮数是研究形状决定的，压不得；能压的是每轮背着的历史。

---

## 2. dsh 的形状：抄什么、不抄什么

| dsh 件 | 形状 | 抄 / 不抄 |
|---|---|---|
| `compaction-tool-result-pruner` | **不调模型**：超预算的 `tool/result` 改写成「头 4096 + 省略标记 + 尾 1024」，原事件留在 append-only 日志里，替换是 surface op 且带 `sourceEventSeqs` | **抄「不调模型、原件留日志、替换可追溯」**；**不抄头尾截断**——我们的观察是逐条证据，折成 E 索引比掐头去尾保真得多 |
| `compaction-basic` retention | 保留最近尾段原文（默认 16% 窗口），只折**整单元**，工具调用 / 结果配对处才能切 | **抄「保留最近尾段 + 只折整批 + 配对不变量」**；尾段按**批数 K** 不按 token（我们没有 tokenMeter，且 K 更易解释） |
| `compaction-basic` summarization | 一次 `llm/stream` 让模型写 `<compacted-summary>`，回放前缀复用 KV 缓存；摘要不缩就拒 | **不抄**：多一次调用、摘要会发明；我们有证据账本，E 号 + 标题就是无损摘要。缓存复用与我们无关（未用 cache_control） |
| `compaction/start·summary·end` 事件 + 锁 | 一次压实是带括号的事务，失败留可见孤儿 | **抄事件**（`history_compacted`），**不抄锁**：我们的 loop 单线程持有 `messages`，压实在模型调用前同步完成 |
| 触发 | 容量比例阈值（0.8 × 窗口）+ provider 溢出恢复 | **改成确定性**：比最近 K 批更早的一律折；不做溢出恢复（sol 尚未撞窗，撞了另案） |

---

## 3. 两刀

### 3.1 第一刀：当前观察瘦身（lean projection）——每条 tool 消息都改，含最新那条

在 `project_tool_result` 的模型视图上（审计底稿不动）：每条 evidence 只留 `evidence_id / tool / title / detail / source / source_date / evidence_tier`，
且 **空值不写键**（`""`、`[]`、`"None"`、`None`）；顶层 `evidence_hashes / payload_field_names / payload_sha256 / dataset / caliber` 为空时不写。
去掉的是 `supports / contradicts / independent_key / freshness` 与空值。模型引用链路一个不缺：E 号绑、标题与正文写、来源日期分档判。

预期 −22–28%（§1.3 lean 列）。风险最低：不改历史语义，只是当前观察少了几个模型从不引用的键。

### 3.2 第二刀：历史折叠（history compaction）——比最近 K 批更早的 tool 消息折成索引

每次 `self._model.complete` 之前（研究轮与修复轮同一处），对 `messages` 里 role=tool 的消息按**批**编号（同一条 assistant 的 tool_calls 是一批）：

- 最近 **K=2** 批**原文保留**（含 `runtime_budget` 那条——它永远在最后一条 tool 消息上）。
- 更早的每条替换 `content` 为：

```json
{"ok": true, "tool": "sub_research", "query": "…原 query…", "compacted": true,
 "evidence_index": [{"evidence_id": "E12", "tool": "news_search", "title": "万顺新材：高达因电池铝箔…", "source_date": "2026-09-03"}, …],
 "gaps": ["…原 gaps 原样…"],
 "note": "详情已折叠；这些证据仍在证据表中，可按 E 号绑定；需要原文可再查同一工具"}
```

  索引从 `_EpisodeToolAccumulator.evidence` 按该消息的 `evidence_ids` 取（权威表），不重新解析消息 JSON；`tool_error` 消息（`ok: false`）
  折成 `{ok:false, tool, error, compacted:true}`。
- **只换 `content`**：role / tool_call_id 不动，assistant 消息（模型自己的 tool_calls 与文本）不动，system / user 不动，配对不变量成立。
- 记一条 durable 事件 `history_compacted`：`{folded_call_ids, batches_kept, chars_before, chars_after, turn}`；`finish` 事件加 `history_compaction`
  = `{enabled, folded_messages, chars_saved}`（与 `time_budget_injected` 同款，让 eval 分得开臂）。
- 折过的不再折（幂等）；同一条消息永远只从原文折一次。

预期：与 lean 叠加把重发累计压到现状的 32–58%（§1.3）。

### 3.3 不变量（写死认领）

1. **durable 事件一字不改**：`tool_result` 审计底稿仍是全量；压实只改模型看见的 `messages`。收据按事件重算永远拿得到原文。
2. **绑定不受影响**：`admit_finish` 解 E 号用累计证据表；折叠消息里每一个 E 号都出现在索引里（测试逐个对）；hash 永不出现在模型视图。
3. **最近 K 批原文**：模型决定下一步用的是刚回来的观察，不折。
4. **`runtime_budget` 仍在最后一条 tool 消息上**且内容不变。
5. **配对不变量**：折叠前后 tool 消息条数、顺序、`tool_call_id` 集合逐字节相同。
6. **修复轮同一份规则**：修复轮复用 `state.messages`，进模型前走同一个折叠；REPAIR_GOAL 里的 E 号仍能在索引里找到。
7. **两个 env 开关，缺省关**（A/B 期）：`ASK_EPISODE_LEAN_OBSERVATION=on|off`、`ASK_EPISODE_HISTORY_COMPACTION=on|off`（另可 `ASK_EPISODE_HISTORY_KEEP_BATCHES=K`）；
   两者都关时消息逐字节同今天（已有的 `_strip_runtime_budget` 类对照测试继续成立）。A/B 拍板后缺省翻 on，开关留作保险丝。
8. **分支同一台机器**：分支跑的是同一 loop，同样受两刀；分支 4–5 批、K=2 时偶尔折 1–2 条，无害。
9. **不动 `sub_research` 的当前那条**：它折不折只看年龄（K），不看大小。放大工具面是这条线的目的，不能在这里收回去。

---

## 4. 预算、触发与接缝

- **接缝**：`ContinuousAgentEpisode` 里所有 `self._model.complete(messages=list(messages), …)` 之前（研究轮、修复轮、终局恢复）统一经
  `self._harness.compact_history(messages, evidence=accumulator.evidence, keep_batches=K)` ——放 harness（领域决定「什么可以折成什么」），
  loop 只调；`HarnessReferenceLoop` 不接（参考 loop 是对照臂，spec §5 那条「只差 runtime_budget 一个键」的测试继续成立，再多一个键就要改那条测试的剥离函数）。
- **K 的取值**：默认 2。K=1 多省 12–18%（§1.3），但把「上一批」也折了——模型常在下一轮回看上一批的正文（比较两条新闻），先不冒这个险；A/B 里可加一臂。
- **不设字数阈值**：确定性折叠比「超过阈值才折」更好复算、更好 A/B；小 run（≤ K+1 批）本来就没什么可折。
- **不做模型摘要**：见 §2。
- **成本**：折叠是纯 Python，对 200 条证据的 `messages` 毫秒级；每轮一次。

---

## 5. 可观测

- `history_compacted` 事件（§3.2）；`finish.history_compaction`。
- `capability_frontier.ContextEfficiency` 加 `compacted_chars_saved`（Σ chars_before − chars_after）与 `lean_enabled / compaction_enabled`；
  `resent_chars_estimate` 改为按**模型实际看到的**消息字数算——需要 `history_compacted` 事件里带每条的 after 字数，否则只能按底稿重算得到「未折」的值。
- 对照读数用 `eval_variance_baseline.py` 同 rev 同题 N 遍出翻转率；A/B 用 §6.3 的四个数。

---

## 6. 验收（缺一条不算）

### 6.1 有牙的单测（每条写变异）

1. **lean 字段**：evidence 项只剩七个键、空值不写；`E` 号、title、detail、source、source_date、evidence_tier 逐字保留；审计底稿仍含 `independent_key` 等全部字段
   （变异：把 `supports` 留回来 → 红；把 detail 丢掉 → 红）。
2. **只折 K 批之前**：5 批工具、K=2 → 前 3 批 `compacted: true`，后 2 批原文；`runtime_budget` 仍在最后一条且逐字不变（变异：K 判断差一 → 红）。
3. **索引完整**：折叠消息的 `evidence_index` E 号集合 == 该消息原 `evidence_ids` 集合；不含任何 40/64 位 hex（变异：索引少一条 → 红）。
4. **绑定通过**：模型收尾绑一个只出现在**已折叠**消息里的 E 号 → `admit_finish` 接受、hash 解对（变异：折叠时把该证据从累计表里删掉 → 红——证明校验靠的是表不是消息）。
5. **配对不变量**：折叠前后 tool 消息数 / 顺序 / `tool_call_id` 集合相同，assistant 消息逐字节相同。
6. **durable 不变**：`outcome.events` 里的 `tool_result` payload 与关折叠时逐字节相同；多出的只有 `history_compacted` 事件。
7. **修复轮**：进入修复轮后第一次模型调用看到的历史已折叠，REPAIR_GOAL 引用的 E 号在索引里；修复轮 `finish` 仍 `repair_model_finish`。
8. **开关**：两个 env 都关 → `model.calls[*]["messages"]` 与关闭前逐字节相同（复用 `test_harness_reference_loop` 的剥离对照）。
9. **幂等**：同一份 `messages` 折两次结果相同；已折条目不再变。
10. **frontier**：合成 run 上 `compacted_chars_saved` 与 `history_compacted` 事件之和相等。

### 6.2 门禁

全量 pytest 干净树可采信（`check_test_receipt.py --expect-revision`）；层级审计（harness 在 services，不 import runtime）；`unread-fields` 门（新字段都要有读取点：frontier 与 finish 事件）。

### 6.3 live A/B（候选口 8799，同 rev 同题，不切 8792）

- 臂：A 全关（现状）/ B lean / C lean + 折叠 K=2 /（可选 D lean + K=1）。每臂 **N ≥ 3**（同题变异大：今天同 rev 父臂 4–19 轮都出现过）。
- 读四个数（`capability_frontier --format json`）：`input_tokens / llm_calls`（每轮成本）、`resent_chars_estimate`（或 `compacted_chars_saved`）、
  `evidence_yield.bound_hashes`（绑定数不退）、`verification.judge_status + content_degraded_count`（出口不退）。
- 判据：成本下降要超过 `eval_variance_baseline.py` 的基线翻转率才算数（`--decide --observed-delta D --baseline-flip R`）；**绑定数与判官任一退化即不翻缺省**。
- 题：至少两道——本线的 theme_track（固态 vs 钠电）+ 一道公司题（长电 vs 通富，父臂轮数多、依赖链长）。

---

## 7. 排期与非目标

1. 第一刀（lean）先行：一张 PR，env 缺省关；候选口 A/B 臂 B。
2. 第二刀（折叠）：第二张 PR，env 缺省关；臂 C（可选 D）。
3. 拍板后翻缺省、切 8792、同题一遍闭环（读 `finish.history_compaction` 与 `resent`）。

非目标：模型摘要；折 assistant / system / user 消息；provider 溢出恢复；改证据账本或绑定校验；动 `sub_research` 当前观察；动每批帽或任何预算数字。

---

## 8. 被否方案

- **LLM 摘要**（dsh compaction-basic 主路径）：多一次调用（本身就是被压的成本）、摘要可发明、与「事实判断必须绑 E 号」的宪法相悖；我们有更好的无损摘要。
- **头尾截断**（dsh pruner）：观察是逐条证据，掐掉中间会把 E 号连同事实一起掐掉，绑定链断。
- **只发最后一批 + 证据表**（激进）：模型失去自己上几轮的推理线索；先做 K=2 量了再说。
- **按 token 阈值触发**：没有 tokenMeter；阈值让结果依赖题目长度，A/B 难比。K 批是确定性的。
- **在 `sub_research` 那条上单独限条数**：那是分支真取到的证据，限它等于把放大的工具面收回去（§3.3-9）。

---

## 9. 成立条件

读自 gitea/main `c04acc37`（8792=`b594a5e7`，两者差 docs）；17 个 run 全部是 2026-09-07 同题（固态 vs 钠电 theme_track）在 sol@57244 下的读数，
§1.3 的字数按 `prune_tool_observation → budget_tool_observation → strip_hashes_for_model` 从审计底稿重算，与模型当时看到的逐字一致（见 `capability_frontier._tool_context_costs`）；
lean / 折叠两列是脚本模拟，未跑 live。dsh 只读 README（两个包），未读源码。
