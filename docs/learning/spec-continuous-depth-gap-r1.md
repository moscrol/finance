# Spec：continuous runtime 深度差距（R2）——第五轮同题对比归因与优化项

> 分支：`spec/continuous-depth-gap-r1` ｜ 日期：2026-08-19 ｜ 状态：R2 评审修订
> 触发：第五轮 Knevo vs Workbench 同题对比（外盘传导题），Knevo 内容实质明显胜出。
> 性质：问题定义 + 优化清单。不含实现。P0-A 实施另开代码分支。
> 修订：R1 把「授权被收窄」写成「工具没挂上」。R2 对照 `run_20260819_000940_130301` 一手契约改诊断与优先级。

## 一、背景：第五轮对比事实

### 题目

「基于周二的盘面数据，你认为主线是什么。今晚美股科技调整较多，你认为明天盘面会怎么走，哪个方向可能有机会」（2026-08-18 夜）

### 双方行为（实测）

**Workbench**（`run_20260819_000940_130301`，:8792，continuous runtime）：

- `question_type=market_forecast`，`subject=美股市场`，`evidence_policy=current_market_scenarios`；**没有进入 `external_market` 车道**。
- episode `allowed_capabilities`：`market_data` / `mainline_context` / `finance_query` / `evidence_search`。`news_search`、`web_search`、`memory_lookup` 均未授权。
- 2 次工具调用（`market_data` + `mainline_context`），全部本地 A 股盘面；23 条证据绑定（E1–E23）。
- 「美股调整」标为 `user_premise` 未核验，条件化挂起。
- draft 已写情景树 A/B/C；verification → repair 一轮；`status=partial`。核验裁掉的是发明阈值（成交 ≥2.2 万亿 / 跌破 2 万亿 / 涨停 ≥60 / 电子占比 27%），不是「深结论」本身。
- `scenario_tree` 已是 required output，覆盖记为 `uncheckable`，satisfiability 记为 `suspicious`（没有工具声明能产出它）。

**Knevo**（同题同夜）：

- 工具调用 13+：`finance_memory_query` ×2、`finance_news` ×5、`finance_quote`、`finance_northbound`、`finance_margin_market`、`finance_memory_stage_extraction`、`suggest_options`。
- 核心分析动作：**领跌结构裁决**（闪迪 −9.29% / 海力士 −8.11% / 美光 −7.47% vs 英伟达仅 −2.71%）→ 存储周期担忧 ≠ AI 逻辑证伪 → 结构性冲击而非全面杀跌 → 错杀买点 / 退潮确认的分支判断。
- 调用用户历史框架（CSP CapEx 证伪信号）与缓存判断（天风口径「找不到恶化的数据」）参与推理。

### 判定

内容实质 Knevo 明显胜；证据纪律 Workbench 胜（E 编号 vs 零引用）。本轮差距主战场在**混合题授权与外盘个股结构**，不在纪律，也不在「货架上有没有 W7 / [M]」。

## 二、四层归因

### 第一层：授权收窄（表层，本轮主因）[实测]

`news_search` / `web_search` 已在 `build_default_tools`；`memory_lookup` 已在 episode 注册（身份 + 授权双闸）。R1 写成「已建未挂 continuous」是七月 ask 流水线叙事，对本 run 不成立。

本轮零新闻、零外盘、零记忆，是这条链路的交积：

| 环节 | 本轮读数 | 后果 |
|---|---|---|
| `route_table.market_forecast` | 能力集只有 `memory / market_quote / graph`，故意不含 news/web | 控制器不给外盘核验工具 |
| `current_market_scenarios` floor | 只有 `market_data + mainline_context` | 预测题被收成纯 A 股结构 |
| `resolve_evidence_plan(market_forecast)` | 只计划 `MARKET_DAILY` + 可选 D4 | 计划层也不补 W7 |
| 题面含「今晚美股」 | 仍走 `market_forecast`，不走 `external_market` | 外盘前提只能挂 `user_premise` |

这和 2026-08-18「死资产：够得着 ≠ 想得到用」同形，并且更窄：这题是**够得着也被题型授权收掉了**。

纯 A 股预测（「昨天的反弹能持续多久」）保持本地-only 是既有纪律，见 `test_market_forecast_runtime_uses_current_structure_without_causal_web_tools`。R2 不推翻那条；只对**隔夜 / 外盘混合预测**开缺口。

### 第二层：因果假说缺口（中层）

`research_contract` 已要求 `scenario_tree`。本发 draft 写了 A/B/C（成交维持抱团 / 缩量降级避险 / 美股缓和科技走强）。缺的不是「情景树这个槽」，是 **Knevo 那种因果竞争假说**（AI 逻辑证伪 vs 存储周期见顶），以及用领跌结构做裁决。

Workbench 情景树 = 反弹 / 下跌 / 量能路径。Knevo 假说排除 = 同一现象的互斥解释。同族，不是同一物。R1 写成「没有竞争性假说步骤」过满。

数据块使用要求仍是**防错型**（「不得把分歧写成主升」）。求真型（「必须列竞争假说再裁决」）尚未写入情景树契约。

### 第三层：验证器激励（深层）[本发已坐实；机制收窄]

本发核验裁的是**无据数字触发线**，不是深度本身。留下的稿仍有主线结构 + 条件化推演。

「深度在当前激励里是负资产」说重了。更准确：无据数字触发线是负资产。四连 partial（08-17 中际旭创 ×2、08-19 英伟达传导、08-19 外盘题）仍是模式，但本发不能外推成「核验禁止领跌裁决」——领跌裁决没出现，是因为美股个股数据从未进入授权。

验证器消融（关 repair 裁剪）仍要做，预期是：关掉之后多出来的是发明阈值，不是闪迪 / 美光结构。

### 第四层：记忆复利缺位（对位差距）

Knevo 的 `finance_memory` 提供三样东西：程序性框架（供给侧排序 / 锚龙双锚 / 三阶段轮动）、陈述性先验（天风口径缓存判断）、价值权重（该用户在意什么）。Workbench 的 `memory_gate` 严格（fail-closed + 人审晋升）。纪律有、长期复利薄。对应 70_tutor T9「认知复利 vs 可靠性复利」。

### 补充实验：长期记忆消融（2026-08-19，第五轮 B 面）

同题关掉长期记忆库复跑 Knevo（答案底部明示「与 0 条记忆相关」）：

- 工具：`recall_short_term` + `finance_memory_query`（0 命中）+ `finance_news` ×2 + `finance_quote` ×2 + `recommend_decision`
- **深度特征不降**：假说排除（纳指 −1.07% vs 美光 −6.98% vs 英伟达 −2.37% → 结构性调整非 AI 证伪）、边际转向（天风纪要改为新闻现取）、反常识推理（国产算力周二先跌 = 二次错杀）、领先 / 确认 / 滞后三层信号 + 决策确认块
- 仍引用「你昨天的复盘 / 你预案」——来自**短期会话召回**，非长期记忆库

**修正第四层（不是第三层）**：长期记忆不是深度主引擎，是个性化 / 连续性来源。深度主引擎 = ①循环内实时数据工具（须先被授权）+ ②可选的因果假说骨架。Workbench 同样具备会话上下文，故与「无长期记忆 Knevo」的真实差距收敛为：**混合题授权 + 外盘个股结构**；假说契约是下一刀，不是本轮主因。

仍缺的对照（实现 P0-A 后先跑，再决定是否上 P1-C）：Workbench **只开 news/web 授权、不加假说模板** 复跑本题。若领跌裁决已经出现，P1-C 不是 P0。

## 三、优化项（按本轮 ROI）

编号按 R2 重排。R1 的 P0-1 / P0-2（再挂 [M] / W7）作废，不再施工。

### P0-A 隔夜混合预测授权（本轮主因，零新数据源）

- 内容：`question_type=market_forecast` 且题面含隔夜 / 外盘标记时，`resolve_evidence_plan` 追加 `news_search` + `web_search`。纯 A 股预测保持本地-only。
- 标记最小集：美股 / 纳指 / 纳斯达克 / 费半 / 费城半导体 / 道指 / 标普 / 外盘 / 隔夜 / soxx / qqq / 海外。不把单独的「今晚」当触发（「今晚复盘」会误开）。
- 缝：`intelligence/services/evidence_capabilities.py` 的 `resolve_evidence_plan` → `runtime_capabilities_for_frame`。不改 `build_default_tools`，不改 verification，不改 `memory_gate`，不改 `route_table` 让所有预测都带 news。
- 验收（离线）：第五轮原题授权含 `news_search` 与 `web_search`；「昨天的反弹能持续多久」仍只有 `market_data + mainline_context`。
- 验收（live，sidecar，不切 8792）：同题复跑，trace 允许调用 news/web；「美股调整」不得再只标 `user_premise` 然后结束。不要求本刀就写出领跌结构表。

### P0-B 美股领跌个股结构（收窄后的 #2b）

- 内容：给混合预测题结构化的美股龙头 / 存储链涨跌，而不是从零再接一遍 web-access CDP。指数层已有：`external_market.py`（DJI/SPX/IXIC/SOX/QQQ）、`global_index_daily`、ask 侧 #2b（PR #160）。
- 缺的是个股结构：英伟达 / 美光 / 海力士 / 闪迪（或当期等价领跌样本）进证据编号。
- 验收：美股混合题给出领跌结构表，数字带来源；`external_market` 车道空不再是本项判据（本轮没进那条车道）。
- 依赖：P0-A。没有授权，有数据也叫不到。

### P1-C 情景树扩因果假说（并入 #9+12，不平行新契约）

- 内容：在已有 `scenario_tree` 上加「现象 → ≥2 互斥因果假说 → 裁决证据编号 → 裁决或两假说并立 → 操作含义」。裁决只能引用已检索证据编号；裁不了必须写「证据不足，两假说并立」。禁数值概率纪律不变。
- 不做：再注入一套与情景树平行的模板。本发已经写了 A/B/C，再加仪式段会让第六轮假绿。
- 验收：同题出现互斥因果假说（不是量能三分支换皮），且裁决句带证据编号。
- 前置：P0-A 对照复跑。若只开授权就已经出现因果裁决，本项降级或取消。

### P1-D [M] / `memory_lookup` 个性化

- 内容：`current_market_scenarios` 默认仍不授权记忆（预算理由见 `evidence_capabilities` 注释：广授权会挤掉盘面查询）。只在题面点名「我上次 / 你昨天的复盘 / 我的框架」或用户身份已解析且题材命中时打开。
- 验收：引用用户历史判断；不当深度判据。R1「注册进 `build_default_tools`」不做。

### P2-E 框架资产（与 P1-C 同一工作流）

- 内容：`foresight_methodology.md` 作为人审载体，写入竞争假说排除 / 领跌结构裁决 / 行为模拟。不单独做「答案出现框架名」验收。
- 与 P1-C 合并施工，不另开优先级。

### 移出本 spec

- R1 P2-5「当日事件驱动主线」（涨停潮 / 炸板率 / 晋级率）：不是本轮 Knevo 胜负手；#14 在七月清单里也不是这个含义。另立案。
- R1「把 W7 / [M] 再注册进货架」：工具已在。

## 四、总验收：第六轮同题对比

钉完 **P0-A** 后先做对照复跑（只开授权，不加 P1-C）。过了再决定是否钉 P0-B。判据：

1. 第五轮原题的 episode 授权含 `news_search` 与 `web_search`；纯 A 股预测题授权不回退。
2. 外盘前提必须被工具核验或显式缺口（来源 / 日期 / 未取到），禁止只写 `user_premise` 然后结束。
3. 不得发明无据数字触发线（本发被裁的 2.2 万亿 / 60 家 / 27% 同类）。
4. 证据编号纪律不回退（E 覆盖率不低于本轮 23）。
5. `[M]` / 框架名引用**不是**本轮深度判据。
6. 保留题集至少再加一道不含外盘词的预测题，确认本地-only 不回退。

P0-B 完成前，不把「写出闪迪 / 美光 / 英伟达领跌表」写成 P0-A 的通过条件。P1-C 完成前，不把「≥2 假说段」写成通过条件——本发 draft 已经有 A/B/C。

## 五、边界与不做的事

- **不放宽 verification**：partial 是纪律不是故障。本发裁掉的发明阈值说明闸是对的。目标是「让它有料可深」，不是「让它敢说」。
- **不动 `memory_gate` 晋升纪律**：`model_judgment` 仍不自动晋升。
- **不把所有 `market_forecast` 打开 news/web**：纯 A 股预测保持现有本地-only 测试。
- 第三层机制收窄后，验证器消融仍做：同题关闭 repair 裁剪，预期多出的是无据阈值，不是领跌结构。若结果相反，再回头改本层表述。
- 不切生产 8792。live 对照走 sidecar。
