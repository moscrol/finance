# 工单：第二轮长尾对照产出——quick_fact 供数断层 + 预取锚定 + 零检索直答（2026-08-28）

- 状态：**已收口（2026-08-29 复核回写；修复本体 2026-08-28 晚已完成）**。三个家族由 PR #489（F1/F3 路由 + F2 flush + R5 退出披露，合入 `2ad22b92`）与 #495（路由组合门禁 `112187f1`）修复，台账行 `R-20260828-05/06/07` 已翻 **confirmed**（#493），`R-20260828-08` 为路由层复审追加项。8792 已切含修复代码（28c `b77df25c` → 28d `7a8cefc1`）。收口证据见文末 §3。
- 原始登记（留档）：本单只登记发现与判据方向，不预写修法；台账行由认领修复的 session 用取号器（`scripts/claim_ledger_id.py`）现取现注册，本单刻意不引用任何 R- 号（crosswalk 正向约束）。
- 来源：第二轮 react vs 8792 对照（`~/.finance-runtime/react-round2-20260828/`，7 题 × 2 臂，两臂同代码面 `e5d459338982`）。题面/真值冻结先于运行；判分 = 四臂 v2 尺（已过变异测试）。读数汇总与逐题 trace 细节见 `analysis/round2-summary.md` / `analysis/round2-report.json`。
- 读数（mean_rate，[实测]）：react **1.000**（7/7，档 B plan 地标首轮生效）· 8792 **0.357**（R3/R7 满分，R5 半分，R1/R2/R4/R6 零分）· Δ +0.643。
- 混杂声明（四臂工单 §1.2 同源）：react 臂=Claude Fable 驱动（与上轮 Opus 不同代际），跨臂读数只作假设生成；各家族的确认一律走 8792 自对照消融。

## §0 · 三个家族（全部 [实测]，trace 锚点在 round2-report.json）

### F1 · quick_fact 供数断层（R1 排名 / R2 板块成员冠军 / R5 退清单板块；3/7 权重最大）

- 现场：controller 干净（lane=research、`llm_failure_reason=""`），`question_type=quick_fact` 路由进 legacy ask 路（trace：`route → ask:001:ask_root → ask:002:generic_research_owner → retrieve`），全程 **0 次 finance_query**，终态 `evidence_gap_fallback`。
- 判别：**该路够不着结构化取数工具面**——同题 react 臂用同一注册表 1-2 跳全对；8792 侧 R3（general_finance_qa→episode）/ R7（workflow lane）能到 finance_query 的路由全部满分。层假设=路由拓扑（GRAPH/ROUTING），非模型层。
- 消融方向（认领者定）：quick_fact 且主体/意图含市场取数特征时改派 continuous episode（或给 ask 路挂 finance_query 供数面）；判据=R1/R2/R5 复跑 rate、以及 quick_fact 现有通过面不回归。

### F2 · 预取锚定抑制补查（R6 五日涨幅冠军）

- 现场：theme_analysis→episode，#484 预取按**成交额** top12 供成员表；题问 **5 日涨幅**冠军。模型答案逐字声明「上表仅覆盖按当日成交额排序的前 12 大成员，未覆盖板块全部个股」，**却未发它有权发的补查**（contract 含 finance_query；真值耐科装备成交额 2.67 亿在 top12 外），按预取内 top 答成华虹宏力，judge repaired 照常发稿。
- 判别：「知道缺、不去补」——与 08-25「task_frame 冻结后观察不能改写检索计划」同族的新现场；也是 #484 预取的第一个负外部性样本（供数变锚定）。
- 消融方向：预取排序维度 ≠ 问题意图维度时触发 bounded requery（P2 家族），或预取 rule 行追加「若声明覆盖缺口则必须补查/降低断言强度」；判据=R6 复跑 rate>0 且不引入预取回归（R-20260828-02 的 live 判据不得倒退）。

### F3 · 零检索直答（R4 周内峰值日）

- 现场：quick_fact + subject=None + 区间词形（终点周六），trace `configure→controller→plan→generate`——**连 ask 路都没走**，零检索直答，`verified_fallback` 照常交付，四天里挑错日。
- 判别：needs_retrieval 判定面漏洞，与 D6 controller 地板（unparsable 触发）不同触发面（本次 controller 输出健康、判定本身错）。
- 消融方向：市场数据类问句（日期+成交额/涨跌词形）的 needs_retrieval 确定性地板；判据=R4 复跑走检索路且 rate 达标。

## §1 · 对照臂过程注记（v2 产物首轮，供跨臂 M2 复用）

- react 臂 7/7 session 含 `plan.landmark_version=2`（step 预算+工具白名单），前缀门槛 3/3 首次可用。
- 2 次可恢复参数错（`pct_chg`→`return_pct`），均按工具错误提示一发自愈——错误消息带全字段清单是已验证的好设计，quick_fact 修复不要破坏它。
- R4 撞新鲜度闸（区间终点非交易日→拒答）后收窄交易日边界重发——产品臂修 F3 时该恢复动作可作对照剧本。
- R5 工具原生披露「构成要素退出，非数据陈旧」可直接引用：供数面诚实基建是够的，F1 败在路由够不着。

## §2 · 非目标

- 不动 react 驱动器（档 B 已完）；不重跑上轮已收口的 D 组题；不在本单内做模型/引擎胜负结论（混杂声明见头部）。
- R6 家族修复不得以扩大预取覆盖硬扛（top12→top全量会炸上下文预算）——方向是补查触发或断言降强，不是加大小抄。

## §3 · 收口记录（2026-08-29 复核回写）

### 根因订正（独立复核推翻了本单两处初判，未来读者以此为准）

- **F2 订正**：不是「知道缺、不去补」——R6 首轮 `model_turn.tool_calls` **已发出**正确的 `finance_query[sector_stock_daily] order_by=return_5d_pct`，是 `_consume_root_seconds` 失败把已发出的查询从邮箱里丢掉（`stop_reason=deadline_exhausted`、`carried_draft_chars=0`）。修法=consume 失败且本轮已有 tool_calls 时 flush 再停（`R-20260828-06`，HARNESS_FIX）。§0/F2 的「补查触发或断言降强」消融方向因此**未采用**，预取锚定假设不成立。
- **F3 订正**：不是 needs_retrieval 判定面漏洞——controller/判定输出健康，是 `calendar_disclosure` 日历罐头对「区间终点非交易日」过触发，整题被 canned 在 plan 后直接 generate。修法=区间题且含可检索交易日时不 canned，休市句改为检索后前置声明（`R-20260828-05` 的 ①）。C1/C2 单日休市罐头保留。
- **F1 按原判**：路由拓扑层。`quick_fact` 移出 `DETERMINISTIC_OWNER_TYPES` 进 episode（合同含 `finance_query`，单日问句 cutoff=requested）（`R-20260828-05` 的 ②）。追加发现：以 question_type 为键的手写名单 ≥5 张分布 3 文件、组合矛盾无门禁（F1 正是三表各自「对」、组合成死路）→ runner 支持集提常量单一真本源 + `test_route_composition_gate.py`（`R-20260828-08`）。

### 判据兑现（对照 §0 各家族验收）

冻结集生产复评（8792@`b77df25c`，会话路 `skill_mode=auto`，产物 `~/.finance-runtime/live-probe-8792-round2-post489/`，详见 `docs/handoffs/2026-08-28-489-live-reeval.md`）：

| 判据 | 读数 |
|---|---|
| F1：R1/R2/R5 复跑 | R1 **1.0**（数据中心 6671.51）· R2 **1.0**（寒武纪 125.89/+4.28）· R5 **0.5**（见残余）；四题均见 `finance_query` |
| F1：quick_fact 现有通过面不回归 | C1/C2 单日休市仍 0 LLM 罐头；切流门禁全量 6884P/1F/12S（1F 为本机 codex 沙箱探针，与本批无关） |
| F2：R6 复跑 rate>0 且预取不回归 | R6 **1.0**（已派发 `return_5d_pct` 命中耐科装备 +15.9）；prefetch 未改动，`R-20260828-02` live 判据未触碰 |
| F3：R4 复跑走检索路且达标 | R4 **1.0**（`finance_query[market_daily]` 08-18..22，非 generate-only，公开稿前置周六休市句） |

复评均值 0.929（R5 半分）vs 修复前 0.357。2026-08-29 在 main@`c3514529` 定向复跑六个钉住文件（quick_fact_routing / route_composition_gate / continuous_turn_adapter / agent_episode / honesty_gates / episode_tools）**312 passed**，收据 `~/.finance-runtime/test-receipts/20260829T065620Z-c3514529.json`（注：主检出树含他人未提交文档/数据改动，均不触 `intelligence/`）。

### 残余（评测侧，非产品缺口，不另立产品单）

- R5 判 0.5 是**判分尺**的拒答词表未覆盖「无数据行」表述；产品行为正确（首跳 observation 即「构成要素退出」+ 07-24 末次出现，答案未把近邻「航空」数字当主体，`R-20260828-07` confirmed）。第三轮若重跑对照，由出题人决定是否在 v2 尺重冻结时扩拒答词表；本轮冻结尺不回改。
- 复评当晚公开稿七题被 `judge_unavailable` 扣下（复核服务容量桶），按台账纪律不记内容红；live 判据以 episode 工具面与私有稿为准。
- 遵守 cutover 交接「不要做的」：不为 R5 近邻再开抑制单、不为 R6 再开 prefetch PR、不重切 8792。
