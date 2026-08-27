# 工单：第二轮长尾对照产出——quick_fact 供数断层 + 预取锚定 + 零检索直答（2026-08-28）

- 状态：**待认领**。本单只登记发现与判据方向，不预写修法；台账行由认领修复的 session 用取号器（`scripts/claim_ledger_id.py`）现取现注册，本单刻意不引用任何 R- 号（crosswalk 正向约束）。
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
