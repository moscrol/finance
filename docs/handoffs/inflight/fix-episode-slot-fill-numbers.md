# fix/episode-slot-fill-numbers

## 这个分支做什么

子单 B（spec §6.2）：必填格的**数字与日期**从预取行/带收据的工具行填入，模型只写格间句子。
目标是让公开稿问句日数字精确对上 E1 预取行，对不上时输出结构缺口。

## 当前状态

干净树从 `gitea/main`@`dfc25221` 长出。**只有一笔** `2099718e`（账本登记），**代码未动**。
账本已补 `R-20260821-02`（本刀）/`-03`（#288 现状，写清只过了预取层）/`-04`（判官封上限预测）。

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

- 代码一行没写，TDD 红都还没起。
- `PrefetchItem.detail` 是格式化文本，取数需要新的解析或让 `collect_prefetch_items` 额外产出结构化值——**两条路都没选**，先做的人定。
- 与 #288 不叠：本树从 `gitea/main` 长出，#288 未合。两者互不依赖（B 管槽，C 管锚谁）。

## 下一步

1. 定 `PrefetchItem` 出结构化数值的方式（加字段 vs 解析 detail）。加字段要过「字段契约」门禁——必须有人读。
2. TDD 红：判断槽出现的涨幅/成交额/双红个数对不上预取观察值 → 结构缺口。
3. 变异：把槽改回自由作文必须转红。
4. 验收按 spec §8.1 五步；反过拟合题不得用 PCB概念 / 低空经济。

## 踩过的坑

- `PCB` vs `PCB概念` 是**母子集**（49 ⊂ 233，只差嘉立创），不是互斥口径；数字差一倍是篮子大小。
  两口径并返是终局，但**必须先有槽**，否则等于给判官多一根绳子。
- 全库 3192 组 (板块名,日期) 会返回多行（128 个板块名撞多代码），`sector_name` 不能单独当查询键。
- 账本头部规矩：`refuted` 是最有价值的输出，不许粉饰成 `pending`。
