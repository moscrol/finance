# T-F 分层重算 + 主度量名实（**不开 900，不放宽 5pp**）

> **#136 更正**：§1 按 claim 级 `source_ids` 写「§9.3 算不出 evidence-bound」——字段找错了。
> 输出级 `diagnostics.bindings` 算得出来，但是阶跃函数、23/45 未定义。
> 本页 845 的 citations 代理与真口径 12 条命中重合，**数不用重算**。5a 理由见追加③ §0。

- 日期：2026-08-17
- 指令：`2026-08-17-dispatch-f-addendum-2-stratify.md`（追加②）
- 前序：追加① `2026-08-17-dispatch-f-addendum-pins-and-power.md`，**须连② §0 一起引**
  （「诚实闸零判别力」对 `stop_reason` 成立，对 §9.4 主度量反着；T-F 上一页 §3.1 是对的）
- 数据：`~/.finance-runtime/evals/arm-a-cal-20260816/`，45 条，九题旧 pin。判别力表不重算。
- 状态：三件已做。900 未开。5pp 未动。题集构成未改。

## 0. 一句话

`source_ids` 全空是**链路在发布面上不保留断言绑定**，不是数漏了。
现在量到的是「这次有没有发布带 citations 的答卷」。
按题目分层之后，主度量只在 4 道数据题上有方差，`v=0.275`，`required_nr≈845`。
先前接受的 450/臂够不着 5pp。加样本解决不了「多数格是常数」。换主指标是第五选项，要你拍。

## 1. `source_ids` 0/254：记录缺口，还是链路不写绑定？

亲手复算：**254 / 254 条 `claim.source_ids` 为空。** 与追加②一致。

这不是「字段忘了写进 JSON」。`scripts/run_agent_runtime_benchmark.py` 的 `_runtime_claims`
**会写** `source_ids`（单测有非空夹具）。live 路径是：

1. 对**当时的** `published_answer` 抽数字 token，和 sources 对齐；对上才给 `source_ids`。
2. 任一 `material_numeric` 且 `source_ids` 空 → `_numeric_lineage_projection` 把正文换成诚实闸模板，
   **用模板重跑一遍 `_runtime_claims`**，旧 claims 丢掉。
3. 落盘的 `claims` 是第 2 步之后的。闸模板没有实质数字 → `material_numeric=0` → `source_ids` 必空。

对照 #68：

| 观察 | 数 |
|---|---|
| 落盘 claims 的 `material_numeric` | **0 / 254** |
| 诚实闸 19 条：candidate 有数字 | **19 / 19**（例：`rebound-duration` candidate 24 个数字 / 602 字，published 0 个 / 41 字） |
| 诚实闸 `protocol_issues` 留了被挡的 C 号 | 19 / 19（如 `numeric_lineage_gap:C4,C5`） |
| `model_finish` 9 条 candidate/published 数字 | **0 / 9**（两道方法论题，正文无日期数字，没引用是正确行为） |

**判：② 为主，① 为辅。**

- ②：发布面上这条链路**本就不保留**「断言→来源」绑定。闸触发后 claims 是模板句；闸未触发时（方法论）没有可绑数字。
- ①：闸触发前那一版 claims（带数字、对不上 sources 的那些）**没有落盘**，只剩 C 号。
  所以 §9.3 的「断言绑定到证据」和「未经绑定的数字/日期断言数」都**不能从产物复原**。

`diagnostics.bindings` 的 hash 率在这 45 条上与「claims 且 citations 皆非空」**45 / 45 同值**。
它量的是同一件记录级事件，不是另一套断言绑定。

**§9.3 继续叫 evidence-bound output rate = 收据会在「我们量了证据绑定」上发假绿。**
要真量绑定：先改 harness，把闸前 claims 落盘，再谈 n。那是设计/工程，不是开 900。

## 2. 按题目分层（§4.1）

记录级指标仍用追加② §1 的配方（与上一页表逐格相同，不重算均值）：

`eb = 1` 当且仅当 `claims` 与 `citations` 皆非空。

| 层 | 题 | 该指标 | 进 5pp 分母？ |
|---|---|---|---|
| 方法论 | `counterfactual-mainline`、`unfamiliar-methodology` | 5+4 次 `model_finish`（+1 `repair_model_finish`），**恒 0** | **否** |
| 数据·结构常数 | `index-rebound-space`（fast-path 恒 0）、`ruihuatai-valuation`（恒 0）、`contextual-follow-up`（恒 1，5/5 诚实闸） | 无方差 | **否**（单独报） |
| 数据·有方差 | `rebound-duration`、`weekly-market-cause`、`current-mainline`、`theme-comparison` | 均值 0.20 / 0.40 / 0.40 / 0.40 | **只这一层做主度量检验** |

#69 的 `v=0.1375` 是 informative 八题题级方差的等权平均：
`(0.20+0+0.30+0.30+0.30+0+0+0) / 8 = 0.1375`。
四个 0 格把分母撑大，半宽被做小。「450 全进、4.85pp、刚够」是池化常数格撑出来的，**假的**。
上一页 772/臂 建在剔 infra 后的同一套池化 v 上，**作废，不沿用**。

## 3. 重推 `required_nr`（§4.2）

公式与 #69 相同：`required_nr = 2v / (0.05/1.96)²`，半宽 `< 5pp`。**不放宽。**
可行上限沿用已经接受过的 **450/臂**（两臂 900、约 22.5h）。超过就不靠加重复硬凑。

| 池 | 题数 | v | required_nr | 15 重复时 n / 半宽 | 要压住 5pp 的 r / n | ≤450？ |
|---|---|---|---|---|---|---|
| 官方八题（对照，含常数） | 8 | 0.1375 | 422.6 | 120 / 9.38pp | — | 这是旧口径，不采用 |
| 数据 7（含 fast+常数） | 7 | 0.1571 | 482.9 | 105 / 10.72pp | 69 / 483 | 否 |
| 数据 6（去掉 fast+方法论） | 6 | 0.1833 | 563.4 | 90 / 12.51pp | 94 / 564 | 否 |
| **数据·有方差 4** | **4** | **0.2750** | **845.2** | **60 / 18.77pp** | **212 / 848** | **否** |

主检验用最后一行。848 > 450。15 重复半宽 18.8pp，和 5pp 差三倍多。

冻结 30 没有 live，**不跑去补**。题单里还能看出方法论/反事实/严格定义格
（`counterfactual-mainline`、`unfamiliar-methodology`、`open-event-fed`、`C6`/`C7`/`C9` 等）。
把它们池进 30×15 会再演一遍「刚够」。**不改题集构成来制造方差。**

**够不着。** 不偷偷放宽，不加到 212 重复。

## 4. 第五选项：换主指标（§4.3）

加样本解决噪声，解决不了「指标在多数格上是常数」。下面都是候选，**要你拍**。

| # | 候选 | 它实际量什么 | 代价 |
|---|---|---|---|
| 5a | 把 §9.3 主度量**改名**为「发布面带 citations 的记录率」，5pp 仍只打在数据·有方差层 | 现在产物里真正算得出的那个二值 | 名实相符；分层后仍要 845 量级，**5pp 还是够不着**，只是不再假绿 |
| 5b | 改打 §9.3 已有的 **unsupported numeric/date claim count**（闸前） | candidate 上未绑数字/日期的条数 | 须先落盘闸前 claims；现在只有 `protocol_issues` 里的 C 号。这是 harness 改动，不是开窗 |
| 5c | **闸前通过率**：`protocol_issues` 不含 `numeric_lineage_gap` | 「数字答卷有没有通过诚实闸」 | 零改产物就能数；更近「绑定失败被拦住」，仍不是断言级绑定。分层后是否够 5pp 要另算，不算过就先报 |
| 5d | 先改 harness：闸前 claims + `source_ids` 落盘，再谈 n | 这才是 §9.3 字面的 evidence-bound | 不开 900；没有这种产物之前，收据不准写「量了证据绑定」 |

推荐顺序（仍是建议，不是代拍）：**先 5d 或至少 5a**，避免假绿；5b/5c 是「在现有闸上量闸」，不是把绑定量出来。

选项 1–4（认 #69 / 剔 infra 重锁 / 先修噪声 / 诚实闸并列读）**单独都不够**：根因是分层和名实，不是 24% 基础设施。

## 5. 没做

- 没开 900。没切 8792。没动 T / 30 / 档位 / `ASK_TOOL_BATCH_TIMEOUT`。
- 没放宽 5pp。没改冻结题集。没把 #68 当新 pin 基线。
- 没把 848 次写成「那就跑吧」。
