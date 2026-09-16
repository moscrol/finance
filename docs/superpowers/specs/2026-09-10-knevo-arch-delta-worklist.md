# 工作清单 · Knevo 架构自白对照后的 delta（E-009 下游）

- 优先级：**P2**（除 W1/W2 为 P1）。不阻塞在途工作；由 knevo 架构自白对照量出
  （`docs/learning/knevo-distill/E-009-architecture-self-disclosure.md`）。
- 来源：用户 2026-09-10 转贴 knevo 自答 +「把要做的列一份 spec」。
- 性质：按 divergence-distill §4，**以下全是候选，逐条等用户裁决**（采纳 / 改写 / 拒绝 / 降级为矿），
  人未过闸不写回。E-009 已核：knevo 声称的机制我们大多有同构，其余是我们领先的项或
  双方空白，**不为对齐而对齐**。真 delta 按性质分三类（2026-09-11 评审收窄，替代初稿
  「真 delta 只有 W1/W2」的笼统说法）：
  - **机制已有、验收缺位**：W1——读侧分层（evidence_tier / 先验自标）主干已有，但没有一条测试钉住；
  - **机制已有、颗粒度不全**：W2——逐条日期与过期降级已有，缺逐条归属出处 + 工具路径验收；
  - **实际功能缺口**：W3——胜率只展示不干预，且两种统计口径并存未定。
- 已存在、别重写的部分：`memory_gate.py`（写侧 fail-closed，volatile_fact 拒升 durable）、
  `user_memory.py`（[M] 召回块 + 逐条日期后缀 + `valid_until` 过期降级 + PEER_HIT_LINE 胜率行
  + KC-11 min-N 闸；主干已接入 methods 方法验证读数为第三召回源）、
  `episode_tools.py` memory_lookup（逐条组装证据，自标 `evidence_tier="user_memory"` +
  「先验，非市场事实」，internal_locator 不外发）、
  `reading_baseline.py` CR-04（单一指标不定性）、`episode_semantic_verifier` / `conclusion_five_element_lint`
  （它自承没有的事实校验闸门，我们已有）。本清单全是增量，没有重建。
- 复核：2026-09-11 评审（基于 39a2b775，对照 gitea/main @ 3ed44703）修订 W1/W2/W3/W5/W6；
  W4 无实施硬伤，维持原文。

## 2026-09-16 状态复核（先于下文历史立项前提阅读）

读数：13:56 北京时间，`gitea/main=32bff514`。下文保留 09-10/11 的设计背景，
其中「缺测试 / 只展示不干预 / 分支未合」不能继续当成当前状态。

| 项 | 当前代码 / 验收事实 | 仍不能推出什么 |
|---|---|---|
| W1/W2 | `f63a2352` 已是 main 祖先。`test_user_memory.py` 钉三类召回来源与先验脚注，`test_episode_tools.py` 钉 user_memory 证据等级与先验自标；W2b 的其他出口见下文及 `test_judgments.py` / `test_prime.py` / `test_corrections.py` / `test_red_team.py` | 证据等级与归属测试不保证模型每句话都正确使用历史记忆 |
| W3 | `user_memory.reliability_downweight` 与真实召回接线已有，按计分率降权，口径/小样本/无分类均有测试；**`RELIABILITY_DOWNWEIGHT_THRESHOLD=None`**，关闭降权与警告。`test_threshold_defaults_to_none_until_backtested` 锁住该状态；Q-001 已测但不足定阈值 | 不是功能没实现，也不是生产已降权；`structural_neighbor_demoted` 是别的遥测，不能替代本项证据。本轮未实测生产进程的内存值，不改阈值 |
| W4 | 用户先前授权的 AB-001/002 补分已完成；#758 又合入 AB-003 回检与「暂停 B 线」建议，当前台账见 `ab-ledger.md` | 建议进入 main **不等于用户批准暂停**；Knevo 干净样本为 0，不能写胜率 |
| W5 | D18 出口及同花顺回退实现已在 main；`test_limit_seal_time_block.py` 验空日不注入、历史截止、换源与不夹带 SPT-A06 | 夹具通过不等于今日生产数据完整；SPT-A06 仍 pending，不改规则启用状态 |
| W6 | `251a2cf6` 已是 main 祖先；`test_event_pricing.py` / `test_sync_polymarket_macro_odds.py` 的日历 as-of 与赔率判据已落，验收详见 `docs/verification/2026-09-11-e007-p3p4-criteria.md` | 验收包含「truncated 不落库」的已知洞测试，不是洞已修；不等于赔率接入 agent 或夜跑 |

本轮这五个定向测试文件（user_memory / episode_tools / limit_seal_time_block /
event_pricing / sync_polymarket_macro_odds）复跑 **151 passed**，日志
`/tmp/audit-followup-e009.log`；这是作者分支复验，不给生产部署或金融效果代签。
因此本轮不重做 W1/W3/W5/W6，只做 E-008 工具菜单投影与审计订正。

## W1（P1）· 读侧「记忆 = prior」断言 —— harness/runtime 池

**这意味着什么**【2026-09-11 评审修正】：读侧并非完全无闸——主干已有分层：`memory_lookup`
证据自标 `evidence_tier="user_memory"`、`source` 带「先验，非市场事实」、`freshness="historical"`
（episode_tools.py），[M] 块自带使用要求脚注（易变项以本轮检索为准）。真正的缺口是
**这些分层全靠约定、没有一条测试钉住**，两个失败形状都没人拦：
(a) 来源清单会静默漂移——主干已把 methods（方法验证读数）接进召回池，本 spec 初稿
写的三类白名单当场过时，就是例证；
(b) 「来自 judgments」不代表条目正文里没有旧价格、旧订单——来源名单全对，
也不能证明记忆不会被当成当前事实。所以白名单只是辅助，防线主体必须落在证据分级上。

**做法**（两步，第二步是核心）：
1. 先更新来源清单再钉：召回池现为 judgments / corrections / methods 三源
   （verdicts 只喂校准行与 PEER_HIT_LINE，不作为召回条目入池）。契约测试钉住该清单，
   新增来源时测试变红、强制回来声明该源为什么不含易变事实。
2. 断言「记忆证据不能单独支撑当前硬事实」：钉 `memory_lookup` 每条 AgentEvidence 的
   `evidence_tier == "user_memory"`、`source` 含先验自标、`freshness == "historical"`；
   钉 [M] 块尾部使用要求行存在。只钉证据分级与自标，不试图 lint 答案正文
   （「把记忆当事实引用」不可机械判定，超出本项范围）。

**失效条件**：未来记忆架构重写（如召回池改成向量库混合召回），届时白名单换成源级标签断言；
证据分级断言不受架构重写影响，继续有效。

**验法**：红绿变异，重点验「错误升级证据等级」——把 memory_lookup 证据的 `evidence_tier`
改成 `"news"` / `"public_web"` 等事实级 → 红；删掉 `source` 的「先验，非市场事实」自标 → 红；
删掉来源清单断言 → 红；全部恢复 → 绿。+ 收据。

## W2（P1）· 逐条 ownership 标注 —— harness/runtime 池

**这意味着什么**【2026-09-11 评审修正，范围收窄】：初稿写「块内逐条没有归属」偏大。
实况：判断/纠偏条目**已逐条带日期**（`（YYYY-MM-DD）` 后缀）且有 `valid_until` 过期降级
（`downgrade_expired_text`）；真缺的是逐条**归属与出处**——这条是「你的判断」还是
「你纠正过的原则」、出自哪本台账，目前只在块标题一次性声明。且召回有两条真实出口
（⚠ **数错了，判断类实为四条**——漏了 prime 与 foresight，见下面 W2b，2026-09-11 补登）：
- 复盘链的 [M] 块经 `prior_parts` 拼进 **user 消息**（ask.py），不是 system prompt；
- Workbench `memory_lookup` 工具直接逐条组装 AgentEvidence，**绕过 build_memory_block 渲染**。
只改渲染、只验 system prompt，两条路都会漏。

**做法**：缩小为补齐归属与出处——
- [M] 块条目级前缀补归属（如 `[M·你的判断 2026-08-30]` / `[M·你的纠偏原则 …]`），
  日期沿用现有 `ts`，**保留既有日期后缀与过期降级**，不动召回打分；
- `memory_lookup` 证据对齐同一形制：已有 `source` 自标与 `source_date`，补台账归属名；
  `internal_locator` 继续不外发。

**失效条件**：条目级前缀显著稀释 prompt 预算（召回 5 条 × 前缀）——若实测预算紧张，
前缀缩写但不删字段。

**验法**：分别断言两条出口——[M] 块（复盘链 user 消息 + ask 链 provider 块）条目前缀
含归属+日期，既有日期与过期标记不回归；`memory_lookup` 每条证据 source/source_date 完整。
扩展 test_user_memory + test_episode_tools；开关关闭时零注入不变。

## W2b（P1）· 漏圈的出口：prime 与 foresight —— 2026-09-11 交付后补登

**为什么补这一条**：上面「召回有**两条**真实出口」数少了，是**评审时漏圈范围，
不是执行漏做**。漏掉的是 `judgments.render_for_prompt` 这个**另一个渲染器**的两个
生产调用方（解析器数，2026-09-11 `grep -rn "render_for_prompt(" intelligence/services/`）：

- `prime.py:137` —— prime 前缀。`skills/dispatcher/scripts/route.py` 默认**每轮路由
  都附带**（`--no-prime` 才关），是所有出口里触达最频繁的一条。
- `foresight.py:561` —— 拼进「我近期的核心判断」段送进 foresight 发问提示词。

所以判断类归属的真实出口是 **4 条**（[M] 块 / `memory_lookup` / prime / foresight），
不是 2 条。修在渲染器层，后两条一次覆盖。

**当时的实况**：prime 只有块级标签 `【核心判断｜在此基础上往前推】`，块内逐条连
「核心判断」四个字都没有——**比 W2 改造前的 [M] 块还弱一档**，正是 W2「块内混进
一条过期判断时块级标签救不了单条」点名的失败形状。同一条台账两个出口实测：

```
prime   ：- 液冷：液冷二次侧出清见底（2026-08-30）
[M] 块  ：- [M·你的判断 2026-08-30][液冷]：液冷二次侧出清见底
```

**已做**：`render_for_prompt` 补逐条归属前缀 `[你的判断 YYYY-MM-DD]`，日期从行尾
后缀移入前缀（仍逐条）。**不带 `M·` 命名空间**——prime 不是 [M] 证据块，冒用已注册
的块号等于伪造引用出处。

**验法（已落）**：断言钉在 `build_prime` / `render_prefix`，**不钉渲染器**。W2 自己的
教训就是「出口比渲染器多」（差点漏掉 `memory_lookup`）——只改渲染器而没接上 prime
时，这条测试同样红。变异实测：退回块级旧形制 → `test_judgments` 2 条 +
`test_prime` 1 条红。

**corrections 侧的日期缺口：已补（2026-09-11 同日）。** 再数一次，corrections
一共 **7 个渲染点**：`corrections.render_for_prompt` 的 5 个生产调用方
（`ask_synthesis.py:836` / `prime.py:129` / `foresight.py:548` / `ask.py:1059` /
`framework_interpretation.py:277`）+ [M] 块的 `user_memory._correction_lines`
+ **`red_team.py:76` 自己拼的一份**。最后那处是唯一**不走共享渲染器**的——
改渲染器改不到它，这正是「出口比渲染器多」的第三次现形。

缺的不是归属（正文自带「原则 / 别再说 / 应为」语义标签，不会被误读成市场事实），
是**日期**：三个月前的原则和昨天的在提示词里长得一模一样。[M] 块那条本来就有
（`[M·你的纠偏原则 2026-06-01]`），其余六处没有。

**已做**：渲染器与 red_team 各补 `[你的纠偏 YYYY-MM-DD]` 前缀（分隔用空格不用
「：」，正文本身以「原则：」开头）。两处**各自变异实测**都会红——red_team 那条证明
它确实不受渲染器保护。无 `ts` 的历史记录降级成 `[你的纠偏]`，不丢条。

**留给后人的一条**：本项证明「出口清单」本身会漂——而且**会漂两次**。本节初稿写
「第三条出口是 prime」，仍然数少了（漏了 foresight）。往后动召回渲染，先用
`grep -rn "render_for_prompt(" intelligence/services/` 数出口，别信任何写死的条数，
**包括本节的**。

## W3（P2）· 召回降权闭环 —— 可靠性池

**这意味着什么**：verdicts 胜率现在只在召回时展示（PEER_HIT_LINE），不反向影响召回。
它自承没有记忆可靠性打分；我们有雏形但没闭环——低可靠判断类照样等权浮上来。
【2026-09-11 评审补】且主干现存**两种命中率口径并存**：PEER_HIT_LINE 按整命中计
（partial 进分母不进分子——4 命中 + 6 部分命中 → 4/10 = 40%）；checkpoints 校准器按计分率
（partial=0.5 → score_sum/n = 70%）。同一阈值在两口径下可能得出相反的降权结论，
口径不先固定，降权就是掷硬币。

**做法**（顺序不可倒）：
1. 先固定统计口径：降权用哪个指标（整命中率 or 计分率）、partial 如何计、
   分母 = 已终态裁决数（hit/partial/miss；unverifiable 不进分母），写成代码常量与注释；
2. 阈值进 evolution 队列回测，不拍脑袋定数（reading_baseline 纪律：结构先行，
   单点阈值回测过了才升）；
3. 达阈值且 N ≥ KC-11 min-N 时，召回排序降权 + 附加警告行（「该类判断历史命中率低」）。

**验法**：单测必须覆盖——高/低胜率两类（断言排序与警告行）；**部分命中混合样本**
（口径固定后同一组数据读数唯一，钉死 4+6partial 场景）；小样本（N < min-N 不降权
不出警告）；**无分类记录**（category 解析为 None 时不误伤）。+ 下次同构题抽样审计到场。

## W4（P2）· AB 双盲台账处置：补 verdict 或宣判废弃

**现状**（2026-09-10 核）：`docs/learning/knevo-distill/ab-ledger.md` 目标 30 天 ≥25 样本，
实际 2 个样本（AB-001/002），最后更新 2026-07-10；两个样本的 verdict 均「待回检」，
T+1/T+3 到期日已逾期两个月；AB-002 knevo 侧已判协议违规作废。

**做法（二选一，请用户定）**：
a. 补回检：两个样本的行情数据都在本库，按既有 verdict 口径补打分，台账复活；
b. 宣判废弃：在 `docs/learning/ledger-map.md` 标注废弃原因（采集成本高、收益被
   E 系列探针替代），防「机制在、没人用」的空转。

**红线**：不允许维持现状（目标写着 25、样本停在 2、verdict 永远待回检）。

## W5（P2）· G1a 接线：封板时间数据出口（不迁 SPT-A06）

**这意味着什么**：reading_baseline 的 pending 规则 SPT-A06（秒板未换手则后排无价值）
卡的缺口 G1a 是「有封板时间但无块输出」——2026-09-10 核实 `fact_theme_limit_stock_daily.
first_limit_time / last_limit_time` 有 149,728 行非空。**数据在，缺的是数据块。**
【2026-09-11 交付后更正】**这个立项前提是错的，别照抄这种论证。** 149,728 是**累计**
非空数，而该列自 2026-09-03 起逐日全 NULL（行照常进）——不是上游断供，是风控后写入方
换成 `local:limit-rule` 本地自算链路，它按设计只写 12/38 列，封板时点属盘中事实产不出。
累计数在断供后仍然很大，所以它不能证明「数据在」。据此交付的 D18 块上线即惰性，
事后补了第二个源（`fact_limit_pool_hithink` 的 `limit_up` 池，双源交叉验证 49 只逐只
到分钟一致）按日回退才救活。**判某列是否日更，用 `group by trade_date, source`。**
【2026-09-11 评审修正】但封板时间只覆盖规则的「秒板识别」半边；「未经充分换手」半边
靠 `open_times`（G1b，152,264 行全 NULL，静默降级未修）。按 reading-rules-inventory §5
更正块的既定裁决：**G1b 未解决前，SPT-A06 整体留在 _PENDING_RULES**。初稿「块落地即迁
_BLOCK_RULES」违反该裁决，撤回。

**做法**：本项只交付数据出口——给 first_limit_time 建数据块（挂到对应块的注入路径）。
**不迁移 SPT-A06**；规则迁移等 G1b（open_times 查证需外呼 fupanhui 比对 payload，
CDP proxy + 登录态）修复后另立项。

**验法**：注入断言（命中题形时块出现、封板时间字段在）+ **反向验收：当日无封板时间
数据时不注入、不出空块** + 漂移门禁不红。

## W6（P3）· E-007 P3/P4 判据落位：日历验收归事件日历，赔率表另验

**依赖**【2026-09-11 评审修正，拆成两半】：
- 日历半边依赖 `feat/event-pricing-slice1`（已有 `event_calendar.latest_known()`，
  正是承接 P3/P4「截至某日最新已发布的是哪一期、未发布期何时发布」的函数）；
- 赔率半边依赖 `polymarket-macro-odds-impl`（本地分支未合并，合并须用户确认）。
两分支合并前不动。E-007 底线不变：本仓不补宏观分析，最小版本 = 宏观事件进日历 + 回检打标签。

**做法**：
- E-007 P3/P4 的日历验收**归事件日历**（latest_known() 的 as-of 语义）——赔率表的
  市场截止日是交易截止，不是官方发布日，不能替代日历判据；
- `fact_polymarket_macro_odds_daily` 另验两件事：快照时点（as-of 完整性）与落库完整性，
  含已知洞 truncated 只印 stdout 未落库。

## 登记不立项

- **矛盾笔记自动去重**：knevo 自承没有，我们也没有；corrections 靠用户显式纠正覆盖。
  双方空白，不构成 delta，不立项。
- **knevo 声明面三态表**：E-009 §3 已建防误抄清单（声称 / 实测过 / 实测破功），
  后续抄它的设计前查 E-009，不另建表。
- **reading_baseline 新增判读规则**：本轮材料是记忆架构不是判读方法，无候选；
  「单条命中须交叉」已有 CR-04。
