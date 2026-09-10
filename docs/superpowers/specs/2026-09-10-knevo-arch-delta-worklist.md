# 工作清单 · Knevo 架构自白对照后的 delta（E-009 下游）

- 优先级：**P2**（除 W1/W2 为 P1）。不阻塞在途工作；由 knevo 架构自白对照量出
  （`docs/learning/knevo-distill/E-009-architecture-self-disclosure.md`）。
- 来源：用户 2026-09-10 转贴 knevo 自答 +「把要做的列一份 spec」。
- 性质：按 divergence-distill §4，**以下全是候选，逐条等用户裁决**（采纳 / 改写 / 拒绝 / 降级为矿），
  人未过闸不写回。E-009 已核：knevo 声称的机制我们大多有同构，真 delta 只有 W1/W2 两处，
  其余是我们领先的项或双方空白，**不为对齐而对齐**。
- 已存在、别重写的部分：`memory_gate.py`（写侧 fail-closed，volatile_fact 拒升 durable）、
  `user_memory.py`（[M] 召回块 + PEER_HIT_LINE 胜率行 + KC-11 min-N 闸）、
  `reading_baseline.py` CR-04（单一指标不定性）、`episode_semantic_verifier` / `conclusion_five_element_lint`
  （它自承没有的事实校验闸门，我们已有）。本清单全是增量，没有重建。

## W1（P1）· 读侧「记忆 = prior」断言 —— harness/runtime 池

**这意味着什么**：我们的「易变事实不进答案」目前只靠写侧闸门（memory_gate 拒升 volatile_fact）
加召回池内容自律（user_memory 只召回 judgments/corrections/verdicts）。任何未来新接的记忆源
只要绕过写侧闸门，脏东西直进答案，没有读侧兜底。knevo 声称的「路由层物理只走 provider」
在结构上对这个失败形状免疫，我们不免疫。

**做法**：契约测试钉住 `user_memory` 召回池的三类白名单（judgments / corrections / verdicts），
新增第四类来源时测试变红、强制回来声明该源为什么不含易变事实。只钉召回池构成，
不试图 lint 答案正文（「把记忆当事实引用」不可机械判定，超出本项范围）。

**失效条件**：未来记忆架构重写（如召回池改成向量库混合召回），届时白名单换成源级标签断言。

**验法**：测试钉红绿变异（删掉白名单断言 → 红；加回 → 绿）+ 收据。

## W2（P1）· 逐条 ownership 标注 —— harness/runtime 池

**这意味着什么**：现在 [M] 是块级标签——整块「你的旧判断」，块内逐条没有归属。
knevo 的 ownership 是 schema 层逐条强制，答案里引用时能标「这是你 X 日的判断」。
颗粒度差异的后果：块内混进一条过期判断时，块级标签救不了单条。

**做法**：`user_memory` 渲染改为条目级——每条召回带 `ts` + 来源台账名 + 固定前缀
（如 `[M·你的判断 2026-08-30]`）。只改渲染与注入断言，不动召回打分。

**失效条件**：条目级前缀显著稀释 prompt 预算（召回 5 条 × 前缀）——若实测预算紧张，
前缀缩写但不删字段。

**验法**：注入断言（条目前缀出现在 system prompt 对应块）+ 扩展现有 test_user_memory；
开关关闭时零注入不变。

## W3（P2）· 召回降权闭环 —— 可靠性池

**这意味着什么**：verdicts 胜率现在只在召回时展示（PEER_HIT_LINE），不反向影响召回。
它自承没有记忆可靠性打分；我们有雏形但没闭环——低可靠判断类照样等权浮上来。

**做法**：同类判断历史命中率低于阈值且 N ≥ KC-11 min-N 时，召回排序降权 + 附加警告行
（「该类判断历史命中率低」）。阈值先进 evolution 队列回测，不拍脑袋定数
（reading_baseline 纪律：结构先行，单点阈值回测过了才升）。

**验法**：单测（构造高/低胜率两类判断，断言排序与警告行）+ 下次同构题抽样审计到场。

## W4（P2）· AB 双盲台账处置：补 verdict 或宣判废弃

**现状**（2026-09-10 核）：`docs/learning/knevo-distill/ab-ledger.md` 目标 30 天 ≥25 样本，
实际 2 个样本（AB-001/002），最后更新 2026-07-10；两个样本的 verdict 均「待回检」，
T+1/T+3 到期日已逾期两个月；AB-002 knevo 侧已判协议违规作废。

**做法（二选一，请用户定）**：
a. 补回检：两个样本的行情数据都在本库，按既有 verdict 口径补打分，台账复活；
b. 宣判废弃：在 `docs/learning/ledger-map.md` 标注废弃原因（采集成本高、收益被
   E 系列探针替代），防「机制在、没人用」的空转。

**红线**：不允许维持现状（目标写着 25、样本停在 2、verdict 永远待回检）。

## W5（P2）· G1a 接线：解锁 _PENDING_RULES 的 SPT-A06

**这意味着什么**：reading_baseline 的 pending 规则 SPT-A06（秒板未换手则后排无价值）
卡的缺口 G1a 是「有封板时间但无块输出」——2026-09-10 核实 `fact_theme_limit_stock_daily.
first_limit_time / last_limit_time` 有 149,728 行非空。**数据在，缺的是数据块。**
（G1b `open_times` 152,264 行全 NULL 仍成立，不在本项。）

**做法**：给 first_limit_time 建数据块（挂到对应块的注入路径），块落地后按
divergence-distill §5 的 pending 验法把 SPT-A06 从 _PENDING_RULES 移入 _BLOCK_RULES，
配注入断言。

**验法**：注入断言（SPT-A06 出现在命中该块的题形 system prompt）+ 漂移门禁不红。

## W6（P3）· E-007 P3/P4 判据 × Polymarket 表

**依赖**：`polymarket-macro-odds-impl` 分支未合并（合并须用户确认）；且 E-007 定了
「本仓不补宏观分析，最小版本 = 宏观事件进日历 + 回检打标签」。

**做法**：合并后拿 E-007 的 P3/P4 形状验收 `fact_polymarket_macro_odds_daily`
够不够格当宏观事件日历源；同时解决该表已知洞（truncated 只印 stdout 未落库）。
在此之前不动。

## 登记不立项

- **矛盾笔记自动去重**：knevo 自承没有，我们也没有；corrections 靠用户显式纠正覆盖。
  双方空白，不构成 delta，不立项。
- **knevo 声明面三态表**：E-009 §3 已建防误抄清单（声称 / 实测过 / 实测破功），
  后续抄它的设计前查 E-009，不另建表。
- **reading_baseline 新增判读规则**：本轮材料是记忆架构不是判读方法，无候选；
  「单条命中须交叉」已有 CR-04。
