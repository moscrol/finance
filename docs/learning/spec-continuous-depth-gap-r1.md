# Spec：continuous runtime 深度差距（R2）——第五轮同题对比归因与优化项

> 分支：已收编 `gitea/main`（原 `spec/continuous-depth-gap-r1` 分支随 R5 合入后关闭，勿再续写分支副本）｜ 日期：2026-08-19 ｜ 状态：R5（R4 勘误 + 并回 main 副本的第六轮/隔夜新闻 live 记录）
> 触发：第五轮 Knevo vs Workbench 同题对比（外盘传导题），Knevo 内容实质明显胜出。
> 性质：问题定义 + 优化清单。已合 `gitea/main`：P0-A/B #212；P1-C + E5 #216（`da0731ba`，live `run_20260819_095742_377275`）；残差检索下限 #215；隔夜新闻挂载 #221；门禁爆炸半径 #224（他轨）。本文件是相对已落地代码的增量清单，不是绿地施工单。施工派单：`docs/handoffs/2026-08-19-depth-gap-execution-dispatch.md`。
> 修订：R1 把「授权被收窄」写成「工具没挂上」。R2 对照一手契约改诊断。R4 纠正「P1-E 从零做」「同题一次验 C+E」，并记入 P1-C 已关闭。R5 收敛两处副本：R4 在分支上写就时未含 main 副本新增的第六轮/隔夜新闻两段 live 记录（现四.5/四.6），直接合分支会把它们覆盖掉；自此只认 main 上这一份。

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

P0-A/B 对照已跑完（四.1 / 四.2）：只开授权没有长出 AI 证伪 vs 存储见顶；有领跌裁决仍无互斥因果假说。**P1-C 保持 P1，不取消。**

## 三、优化项（按本轮 ROI）

编号按 R2 重排。R1 的 P0-1 / P0-2（再挂 [M] / W7）作废，不再施工。

### P0-A 隔夜混合预测授权（已关闭，#212）

- 内容：`question_type=market_forecast` 且题面含隔夜 / 外盘标记时，`resolve_evidence_plan` 追加 `news_search` + `web_search`。纯 A 股预测保持本地-only。
- 标记最小集：美股 / 纳指 / 纳斯达克 / 费半 / 费城半导体 / 道指 / 标普 / 外盘 / 隔夜 / soxx / qqq / 海外。不把单独的「今晚」当触发（「今晚复盘」会误开）。
- 缝：`intelligence/services/evidence_capabilities.py` 的 `resolve_evidence_plan` → `runtime_capabilities_for_frame`。不改 `build_default_tools`，不改 verification，不改 `memory_gate`，不改 `route_table` 让所有预测都带 news。
- 验收（离线）：第五轮原题授权含 `news_search` 与 `web_search`；「昨天的反弹能持续多久」仍只有 `market_data + mainline_context`。
- 验收（live，sidecar，不切 8792）：同题复跑，trace 允许调用 news/web；「美股调整」不得再只标 `user_premise` 然后结束。不要求本刀就写出领跌结构表。

### P0-B 美股领跌个股结构（已关闭，#212）

- 内容：给混合预测题结构化的美股龙头 / 存储链涨跌，而不是从零再接一遍 web-access CDP。指数层已有：`external_market.py`（DJI/SPX/IXIC/SOX/QQQ）、`global_index_daily`、ask 侧 #2b（PR #160）。
- 缺的是个股结构：英伟达 / 美光 / 海力士 / 闪迪（或当期等价领跌样本）进证据编号。
- 验收：美股混合题给出领跌结构表，数字带来源；`external_market` 车道空不再是本项判据（本轮没进那条车道）。
- 依赖：P0-A。没有授权，有数据也叫不到。

### P1-C 情景树扩因果假说（已关闭，#216）

- 内容：在已有 `scenario_tree` 上加「现象 → ≥2 互斥因果假说 → 裁决证据编号 → 裁决或两假说并立 → 操作含义」。
- 落地：`build_scenario_guidance` 第 6 条 + `episode_scenario_rule` 接到 `episode_protocol` 的 `track_rule` 拼接位（不改静态契约指纹）。**没有**缺段 stub——施工计划写明 stub 会让第六轮假绿。**没有**新 `required_output`。
- live：`docs/verification/2026-08-19-scenario-causal-hypotheses-live.md`。H1 存储周期 vs H2 AI 整体回调，裁决带 E17–E21。生产 8792 未切。
- 不要再做一遍。不要补 `ensure_causal_hypotheses_visible`。

### P1-D [M] / `memory_lookup` 个性化

- 内容：`current_market_scenarios` 默认仍不授权记忆（预算理由见 `evidence_capabilities` 注释：广授权会挤掉盘面查询）。只在题面点名「我上次 / 你昨天的复盘 / 我的框架」或用户身份已解析且题材命中时打开。
- 验收：引用用户历史判断；不当深度判据。R1「注册进 `build_default_tools`」不做。

### P1-E 输出契约（R4：相对 08-13 增量，不绿地重做；不与 P1-C 绑一次验收）

**已落地（禁止再造第二份契约）**：

| 子项 | 08-13 已有 | 还缺 |
|---|---|---|
| E1 四态对照 | prompt + stub + `contract_missing_outputs` 收据（可并入 repair 词表）；episode 有 `episode_track_rule` | 没有 `prior_verdict_check` 字段；episode **运行时**接线仍是 2 档（注释写明归缝持有者） |
| E2 修订版在前 | ask 路径 `compose_revise_on_warn`：WARN 回灌修订，正文换修订版，意见进「输出质检」附录 | **continuous 编排器显式 `compose_revise_on_warn=False`**；issue 格式是「检查名 + note」，不是 Knevo 四件套 |
| E3 判断 TTL | 「复核期限：YYYY-MM-DD」文案，30/90 天 | 没有机器可读 `valid_until`，没有过期降级程序 |
| E4 下期关注 | 答案侧已要求「指标+时间+触发」 | **消费端没有**：`followups.py` 对跟踪题跳过 recheck；foresight checkpoint 不读这份清单 |
| E5 框架资产 | #216 已写入 `foresight_methodology.md` §八「竞争假说排除」 | `reading_baseline.py` 还在 `feat/reading-rules-baseline-batch1`，未入 main。那支合入时必须把 §八登记进 `_METHODOLOGY_OVERLAP`，否则漂移门禁红 |

**证据链**：附录 A（q4/q8 原文）+ 2026-08-19 三 run（液冷/今日复盘/陶瓷纤维）证明「信息在、骨架不显形」。注意：这三发**不是** `theme_track`——「今日复盘」走市场复盘，液冷/陶瓷纤维多半是 `theme_analysis`。现有 `track_contract` 对它们本来就不会注入。四.3 不能当「跟踪契约没落地」的证据，只能当「非跟踪题的散文终稿」观察。

**下一刀（只做未落地增量，另开验收，禁止与预测题捆一次）**：

- **E4（先做）**：只做消费端——从跟踪题答案 parse「下期关注」→ `checkpoints.register_checkpoint`（`category=下期关注`，`source=track_next_watch`）→ 次日 foresight 系统提示词强制对照。不要再产出第二份清单。`followups.py` 对跟踪题跳过 recheck 的行为保留，但必须有 checkpoint 消费补上。
- **E2（其后）**：只接通 continuous 呈现顺序（修订版在前）。**不换**仓内 `output_review` 的 6 项。附录 A.1 缺口 ②③ 不在本项。
- **E1/E3（更后）**：`contract_missing_outputs` 已有收据；缺的是 episode 运行时真正送进 repair。禁止再注入第二套文案。
- **E5**：已写，不要再写一遍。

**验收（另备题，禁止套第五轮隔夜预测题）**：1 道 `theme_track`（最好带上期 [M]/[V]）+ 1 道无基线跟踪题。看四态或「无上期基线」、TTL、下期关注是否进入次日输入。E 覆盖率不回退。

**边界**：骨架是契约不是模板；TTL 过期不自动删结论只标注；禁数值概率纪律不变。

### 移出本 spec

- R1 P2-5「当日事件驱动主线」（涨停潮 / 炸板率 / 晋级率）：不是本轮 Knevo 胜负手；#14 在七月清单里也不是这个含义。另立案。
- R1「把 W7 / [M] 再注册进货架」：工具已在。

## 四、总验收

### 四.0 P0 已关闭（不要再当开工门槛）

P0-A/B 的授权与领跌表判据见四.1 / 四.2，代码在 `gitea/main` #212。下面 1–6 是 **P0 的历史验收**，不是 P1-C 的开工条件：

1. 第五轮原题的 episode 授权含 `news_search` 与 `web_search`；纯 A 股预测题授权不回退。
2. 外盘前提必须被工具核验或显式缺口（来源 / 日期 / 未取到），禁止只写 `user_premise` 然后结束。
3. 不得发明无据数字触发线（本发被裁的 2.2 万亿 / 60 家 / 27% 同类）。
4. 证据编号纪律不回退（E 覆盖率不低于本轮 23）。
5. `[M]` / 框架名引用**不是**本轮深度判据。
6. 保留题集至少再加一道不含外盘词的预测题，确认本地-only 不回退。

### 四.0b P1-C 已关闭（#216 + 四.4 live）

历史验收条（均已过）：互斥因果 ≠ 量能三分支；裁决带证据编号或并立；不新增 `required_output`；禁数值概率不回退。

P1-E 验收见第三节「另备 theme_track 题」。禁止用第五轮隔夜预测题验四态对照。

## 四.1 P0-A live 对照（2026-08-19 sidecar :8796）

读数：`docs/verification/2026-08-19-overnight-forecast-auth-live.md`（代码分支）+ `~/.finance-runtime/overnight-auth-live/receipt.json`。生产 8792 未切。

- 授权六件套含 `news_search` / `web_search`。模型第二轮调用 `news_search`，E24–E29 为 8-18 夜东财标题（费半跌 6%、SK 海力士 −7.4%、闪迪 −8%、光通信 −17%）。零 `user_premise`。E 覆盖 29。
- `web_search` 已授权未调用。公开稿被核验裁掉标题数字（E24 被当成时间戳），看起来像「美股没核验」，账本不是。
- **P0-A 关闭。P1-C 不取消**：没有自发长出 AI 证伪 vs 存储见顶。下一刀仍是 P0-B（可绑定的指数 + 领跌个股字段），不是再挂工具。
- 验证器消融预期要改：本发裁掉的既有发明阈值苗头（首稿 25% / 30 家），也有标题里已出现的领跌数字。

## 四.2 P0-B live 对照（2026-08-19 sidecar :8796）

读数：`docs/verification/2026-08-19-overnight-us-leaders-live.md`（代码分支 `feat/overnight-us-leaders` @ `9f0f6324`）+ PR #212。

- `run_20260819_014201_011150`：E17–E20 为 Yahoo 结构化报价（费半 −5.45% / 英伟达 −2.06% / 美光 −7.39% / 闪迪 −9.90%，2026-08-18）。公开稿写出领跌并用于情景树。海力士 8-13 滞后未绑定。
- 前一发 `013934` 误用 16:15 收盘规则绑到 8-17 上涨场，已用 `overnight_session_date`（09:30 起取当晚 bar）修掉。
- **P0-B 关闭。P1-C 保持 P1**（有领跌裁决，仍无互斥因果假说模板）。

## 四.3 输出结构差距证据（2026-08-19 三 run，P1-E 依据）

液冷（`run_20260819_130415_219019`）/ 今日复盘（`134948_697611`）/ 陶瓷纤维（`134948_765208`）三频段探针：骨架六段一致、工具自适配正确、引用密度 3/22/8 与证据可得性成正比。但三发终稿均为 prose 一大段——判断强度/证据缺口/继续条件全在，骨架不显形。对照蒸馏库 q4 自认「我们只给意见清单，不产可直接用的修订版」、q8 自认「synthesis 更新没有对上期结论的显式判定字段」。差距在**输出契约未定死**，不在模型能力。E 段（终稿合成）是施工落点。

注意：这三发不是 `theme_track`，不能当「跟踪契约没落地」的证据。

## 四.4 P1-C live 对照（2026-08-19 sidecar :8796）

读数：`docs/verification/2026-08-19-scenario-causal-hypotheses-live.md` + `~/.finance-runtime/scenario-causal-live/receipt.json`。代码 `#216` / `da0731ba`。生产 8792 未切。

- `run_20260819_095742_377275`：公开稿单独写【互斥因果假说】。同一现象=美股科技大跌。H1 存储供给/价格周期（E19–E21 vs E18）vs H2 AI 高位获利了结（费半 −4.98%，E17）。裁决倾向 H1 为主、H2 叠加，缺同窗口新闻归因则「两假说部分并立」。
- 情景 A/B/C 仍在且与假说段分开。核验裁掉 B 支正文，假说段留下。E 覆盖 28。outcome `partial`（发明阈值闸未放宽）。
- **P1-C 关闭。** 不要再施工、不要补缺段 stub。
- 后记（2026-08-19）：写就时「生产 8792 未切」；P1-C 已随 `15510ad7` 链切上生产（台账 10:50 行），当前生产为其后续 tip。

## 四.5 第六轮 live 补记（2026-08-19 sidecar :8796）

读数：`docs/verification/2026-08-19-sixth-round-live.md`（生产快照 `15510ad7`，含 P0-A/B + P1-C + #215）。不为文档追切 8792。

- 主发 `run_20260819_105845_919694` @ `15510ad7`：spec §四 条 1–5 通过。Yahoo 五票全绑定，含 HYNIX −8.51%（2026-08-18）。公开稿【互斥因果假说】A 存储见顶 vs B 情绪回吐，倾向 B。`news_search` / `web_search` 已授权未调用。主发未发明 2.2万亿 / 60 / 27%。
- 对照 `run_20260819_110003_775678`「昨天的反弹能持续多久」：无 news/web 授权（条 6 过）；公开稿发明「约2.2万亿」。
- 相对 P1-C live：同一领跌相对强弱，本发读成「英伟达抗跌 → 情绪回吐」，P1-C 更偏存储周期并立。两边都把缺新闻归因写成缺口。n=1 波动，不是回退。
- **残留 Knevo 缺口是隔夜新闻未挂上，不是 P1-D。** overnight news hang（`feat/overnight-news-hang`）在 `market_data` 已跑时顺挂东财 `news_search` 证据，同形于 P0-B Yahoo 领跌。不是预执行工具（#215 否决）。

## 四.6 overnight news hang live（2026-08-19 sidecar :8796）

读数：`docs/verification/2026-08-19-overnight-news-hang-live.md` + PR #221。

- 首发 `run_20260819_113527_705804` @ `d969cc51`：挂载空。`as_of` 误用 A 股 `served_date=2026-08-18`，隔夜东财标题是 08-19；检索词「美股科技」标题整词不命中。
- 复跑 `run_20260819_114317_390006` @ `87f3c5c0`：第一次 `market_data` 观察 27 条里有 6 条 `news_search`（E22–E27，全 2026-08-19）。模型不再另调 `news_search`。公开稿用 E23 新闻 + E18–E21 相对强弱写互斥因果（存储周期 vs AI 基建抛售）。
- **本刀 live 关闭。** 不升 P1-D。后记（2026-08-19）：写就时未合；#221 已合（`d969cc51`）并随 `d2ebf693` 链切上生产（台账 13:01 行）。

## 五、边界与不做的事

- **不放宽 verification**：partial 是纪律不是故障。本发裁掉的发明阈值说明闸是对的。目标是「让它有料可深」，不是「让它敢说」。
- **不动 `memory_gate` 晋升纪律**：`model_judgment` 仍不自动晋升。
- **不把所有 `market_forecast` 打开 news/web**：纯 A 股预测保持现有本地-only 测试。
- 第三层机制收窄后，验证器消融仍做：同题关闭 repair 裁剪，预期多出的是无据阈值，不是领跌结构。若结果相反，再回头改本层表述。
- 不切生产 8792。live 对照走 sidecar。

## 附录 A：Knevo 蒸馏原文（P1-E 依据，全文内嵌）

> 来源：`docs/learning/knevo-distill/q4-finance-review-check-skill.md` 与 `q8-finance-industry-track-skill.md`（2026-07-09 蒸馏，Knevo 经 `read_skill_file` 全文转述自己的 skill 定义）。内嵌于此使 P1-E 施工自包含，免二次检索。

### A.1 q4：finance-review-check（事实审查 skill）自述

**6 维事实审查框架**（数值/实体/来源/逻辑/时效/完整性）：

- A 数值：核心数据偏差 >0.5% → critical
- B 实体：公司名/ticker 消歧（平安银行≠中国平安）
- C 来源：强论断无出处 → critical
- D 逻辑：证据→结论链条、前后矛盾、推理跳跃
- E 时效：数据过期、政策/财报新版
- F 完整性：按报告类型查结构缺失（缺风险变量、缺估值锚）

**输出契约**：Verdict（PASS/WARN/FAIL）→ **修订版报告全文在前** → 审查详情附录在后；每个 issue = 原文引用→偏差→真值来源→修订。FAIL 阻塞写入记忆。

组合模式：先写后审（生成型 workflow → 审查型 workflow）；记忆入库把关（sub-agent finance-reviewer 执行，FAIL 阻塞写回 user-finmemory——与本地 qa_ingest 同构）。

蒸馏时本地缺口记录：①无「修订版在前、审查在后」输出契约（只给意见清单）；②无数值偏差分级阈值；③无实体消歧显式检查项。

### A.2 q8：finance-industry-track（行业连续跟踪 skill）自述

1. **track vs report 边界**：有上期基线/固定周期/只要新信号/跟踪自己 thesis → track；首次系统看行业 → report。「深度报告建立框架，行业跟踪维护框架」。
2. **delta-only 契约**：只保留有信息量的变化，无变化项直接跳过，「上期结论还在就写无变化，不水字数」——反凑字数的显式输出纪律。
3. **输出骨架**：本期要点 / 数据速览 / 个股异动 / **观点更新（对照上期：支持/削弱/无变化/信息不足四态）** / 下期关注（指标+时间节点+触发条件）/ 一句话结论。
4. **自衔接循环**：第 5 段「下期关注+触发条件」是下一轮跟踪的输入——报告之间形成链。
5. **基线缺失降级**：无上期基线时用 `finance_memory_query` 拉历史记忆观点替代，但明示「用户口述基线质量最高」。
6. **观点有效期分级**：track 结论 30 天复查，深度报告 90 天——输出带 TTL（存活期）标注。

蒸馏时本地缺口记录：①synthesis 更新无对上期结论的显式判定字段；②「判断/结论」本身无有效期字段（证据 45 天复核标记只管证据新鲜度）；③foresight checkpoint 只覆盖可证伪点，不覆盖「下期观察清单」衔接。
