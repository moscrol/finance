# fix/episode-slot-fill-numbers

## 这个分支做什么

子单 B（spec §6.2）：必填格的**数字与日期**从预取行/带收据的工具行填入，模型只写格间句子。
目标是让公开稿问句日数字精确对上 E1 预取行，对不上时输出结构缺口。

## 当前状态

干净树从 `gitea/main`@`dfc25221` 长出。**三刀已绿，全离线**。
- 第 1 刀 `98a02774`：预取行出结构化观察值（`StructuredObservation` /
  `PrefetchItem.observations` / `sector_timeline_observations` / `observation_value`）
- 第 2 刀 `1384a33a`：判官删句不再静默连坐真值，改记 `gaps`
  （`StructuredObservation` 下沉到 `agent_research`、`AgentEvidence.observations`、
  `grounded_values_in_text` / `describe_lost_observation` / `_gaps_with_lost_observations`）
- 第 3 刀 `fe8555e0`：缺口接上消费方——`slot_line_for_observations` /
  `_restore_lost_observations` 把连坐掉的真值以**槽行**补回稿件。
  `【预取事实】PCB概念 2026-08-07：涨跌幅=4.74；成交额亿=3432.59`
  模型一个字没写，判官无据可删；只补数值不补叙述

两刀都 TDD 先红后绿 + 变异转红后还原。18 passed（预取 12 + 判官 6）；
回归 828 passed（`-k "semantic or evidence or prefetch or answer_model or judge"`）。
`evidence_content_hash` 只吃 tool/title/detail/source，补 observations **不改证据身份**（已钉测试）。

## 已定位的刀口（省下一轮探查）

| 位置 | 是什么 |
|---|---|
| `intelligence/runtime/agent_episode.py:2144` | **封上限的实现处**。finalization 提示词写着「每个保留的精确数字必须把直接证据序号放入对应 output binding，**否则删去数字**」 |
| `intelligence/services/asof_prefetch.py:212` | `PrefetchItem(tool/title/detail/source/source_date)`。**数字埋在 `detail` 字符串里**，不是结构化字段——槽要消费它得先能取出数值 |
| `intelligence/services/research_contract.py:200` | `required_outputs`，必填格来源 |
| `intelligence/services/ask_synthesis.py:2118,2245` | `repair_grounded_composer_answer` 的两个调用点（ask 管线；episode 走 `continuous_turn_adapter`） |

**关键判断**：现在「数字必须有据，否则删」是**写在提示词里**的（spec §4 点名的堆 prompt 反模式），
所以删除力度由模型自由裁量——Gate 1 现场它把整段砍了，真话 4.74/3432 陪葬。
本刀要把它从「提示模型自己删」改成「槽由系统填、判官对槽内数字无删除权」。

## 未验证 / 已知边界

- **`agent_episode.py:2144` 那句「否则删去数字」仍在提示词里，且本单不该动它**：
  spec §6.2「不做」明写「改 prompt 抢判官层」。它归子单 C（挪约束）或另开单。
- **必填格还没消费 `observation_value`**：槽目前只在「判官删了真值」这条**修复路径**
  上生效，正常写稿路径的数字来源**未变**。Gate 1 那题若不触发 judge repair，
  公开稿仍会是 8.71。
- 从未 live。两刀都是离线单元，spec §8.1 的 3/4 步（新题 live、公开稿数字 ⊆ 桌上的行）都没跑。
- `dual_red_counts` 那条预取行还没出 observations，只有时间轴出了。
- 槽行是**追加在稿尾**的，不是嵌进必填格。spec §6.2 要的是「必填格的数字与日期
  从预取行填入、模型只写格间句子」，本刀只做到了「删了不丢」，没做到「本来就由系统填」。
- 与 #288 不叠：本树从 `gitea/main` 长出，#288 未合。**机制**独立（B 管槽、C 管锚谁），
  但**同一题上 B 的口径正确性依赖 C**——本树默认锚仍落短名 `PCB`，槽会忠实投递 8.71。
  测试因此锁「槽不混口径」（tree-independent），长名口径另用显式 subject 固定锚来验。

## 下一步

1. ~~`PrefetchItem` 出结构化数值~~ **已完成** `98a02774`（选了加字段，不解析 detail）。
2. ~~删句不连坐真值~~ **已完成** `1384a33a`。
3. ~~缺口接上消费方~~ **已完成** `fe8555e0`。
4. **下一刀**：让**正常写稿路径**的必填格直接消费 `observation_value`
   （现在只有 judge repair 路径生效）。这才是 spec §6.2 的正题。
5. `dual_red_counts` 那条预取行补 observations。
6. 验收按 spec §8.1 五步；反过拟合题不得用 PCB概念 / 低空经济。

## 踩过的坑

- `PCB` vs `PCB概念` 是**母子集**（49 ⊂ 233，只差嘉立创），不是互斥口径；数字差一倍是篮子大小。
  两口径并返是终局，但**必须先有槽**，否则等于给判官多一根绳子。
- 全库 3192 组 (板块名,日期) 会返回多行（128 个板块名撞多代码），`sector_name` 不能单独当查询键。
- 账本头部规矩：`refuted` 是最有价值的输出，不许粉饰成 `pending`。
- **不要给「含真值的句子」发免死金牌**。三筛第 2 条：那会让绑同句的编造搭便车
  = 变错，必须硬。正解是删照删、真值另记，拦信息丢失而不是拦模型表达。
