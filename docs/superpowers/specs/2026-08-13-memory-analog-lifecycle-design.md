# 记忆机制设计：越用越懂 × 行情对标历史 × 题材生命周期

> 日期：2026-08-13
> 状态：**六 slice 已落地并合入 `main`**（PR #318 + 契约注入修复 #322）。
> 质检与对照 agent book 原书第 3/8 章的优化点见
> `docs/superpowers/specs/2026-08-13-memory-quality-review.md`。
> 调研来源：① `docs/superpowers/2026-08-10-agent-book-chapter-audit.md`（agent book 第 3/8 章
> 对照本仓的章节审计；质检轮已改对照 GitHub 原书 raw，不只沿用审计稿）；
> ② `docs/learning/knevo-distill/` 的 E-006（记忆生命周期实测）、q9（历史类比引擎）、
> q8（行业连续跟踪契约）。

---

## 0. 一句话结论

三个愿望**都不需要新建平台**，它们分别对应三条已有的半成品链路，缺的是三块拼图：

| 愿望 | 已有的链路 | 缺的拼图 |
|---|---|---|
| 越用越懂 | foresight 反馈回路 + user_memory 四台账 + corrections | 记忆状态机、预测台账与命中数分离的度量、recall@k |
| 行情对标历史 | D8 历史类比块（**题材级**）+ 剧本卡库 | **市场级**情绪环境指纹（当前只能对标单题材自身历史） |
| 题材逻辑生命周期 | theme-radar（当前快照）+ fermentation-tracer（历史回溯）+ recognition_timeline | 生命周期阶段判定 + delta-only 跟踪契约（四态对照 / TTL / 下期关注） |

---

## 1. 两个检索源关于记忆机制的核心结论

### 1.1 agent book（第 3 章记忆与知识库、第 8 章持续进化）

来自本仓 2026-08-10 章节审计（该稿只写差距、每条标 [实测]/[推断]）：

1. **双层记忆架构**是收敛结论：结构化卡片常驻上下文提供「概览」，上下文感知检索
   按需提供「细节」。本仓双层大体具备（`.foresight/` 台账 + DuckDB/图谱/检索）。
2. **recall@k 缺失被点名为红项**：2026-08-09 的 S3 判卷说「证据只支持盘面观察，
   证不了归因」——这到底是检索不足还是题目超纲，当前没有任何指标能回答。
   *这在「越用越懂」里是关键：没有召回度量，记忆库变厚了也不知道有没有被用上。*
3. 第 8 章的持续进化链路是「在线记录证据 → **离线生成候选更新** → 验证后发布 →
   可回滚」。本仓在线记录齐全（corrections/verdicts/interactions），但**缺「候选更新」
   这一层**——经验多是人工读了再改，没有自动候选→验证→发布链。

### 1.2 knevo（E-006 实测 + q9 + q8）

1. **四平面分离**（E-006 结论原文）：这是最重要的可迁移结构，不是某个黑盒排序公式——

   ```text
   文本记忆：承载判断、框架和观察
   实体图谱：承载可结构化的世界关系
   用户记忆：承载个人判断和交互史
   预测台账：承载可验证的判断结果
   ```

   不要把所有内容塞进一个向量库，也不要把所有「命中」都当成正确。

2. **记忆有生命周期状态机**（E-006 实测）：
   `对话 → 候选提炼 → batch 聚合 → recommendation → 用户接受/拒绝 → 长期记忆 → 检索命中`。
   推荐和长期记忆**分开存储**，接受/拒绝是显式动作。

3. **两对不能混用的指标**（E-006）：
   - `hitCount / lastHit`（记忆被召回次数）≠ `prediction win rate`（判断验证后的命中率）；
   - `memory confidence`（条目可信度）≠ `calibrated probability`（可校准的事件概率）。
   记忆被反复召回只说明它「常被想起」，不说明它「判断得对」。

4. **历史类比匹配的是场景结构，不是 K 线形态**（q9）：knevo 的历史类比只查记忆
   （双层：用户复盘 + 策展方沉淀的历史场景模板），不查行情、不查 web、不查图谱。
   匹配的是供需结构 / 估值位置 / 政策周期 / 资金行为模式的相似性。
   **质量瓶颈 = 记忆库的厚度，不是模型能力**；库薄就显式说「暂无显著匹配」。

5. **行业跟踪的 delta-only 契约**（q8）：「上期基线为锚，只报变化」+
   观点四态对照（支持/削弱/无变化/信息不足）+ 观点 TTL（track 30 天、深度报告 90 天）+
   「下期关注 + 触发条件」作为下一轮跟踪的输入，报告之间形成自衔接链。
   *这正是「题材逻辑生命周期追溯」的输出契约。*

---

## 2. 现状盘点（本仓四平面对照）

| 平面 | knevo | 本仓现状 | 主要缺口 |
|---|---|---|---|
| 文本记忆 | finmemory 共享库（框架卡/场景模板） | wiki 知识库 + `market_playbooks.jsonl` 剧本卡（**6 张 approved**） | 剧本卡厚度（q9：厚度即质量瓶颈） |
| 实体图谱 | fundacore（实测很稀疏） | `wiki/relations/`（entity_exposures / evidence_index / theme_signals），带 gaps 纪律 | 无生命周期维度（只有关系，没有阶段） |
| 用户记忆 | 长期 memories + pending recommendations 状态机 | `intelligence/users/<id>/` 四台账 + interactions.jsonl 亲和度（14 天半衰期）+ `user_memory` 检索工具（专属 evidence_tier，只作先验）+ **`memory_gate.py` fail-closed 晋升门（见 §3.2 修正）** | ~~无状态机~~（入口已有）；真差距是**退出机制**（→ slice 5 已补） |
| 预测台账 | （未公开，E-006 建议单建 ledger） | foresight checkpoints/verdicts 已是雏形（可证伪点 + 回检） | 与「记忆命中」的度量还没分开呈现；无 error_class 归因字段 |

行情/题材侧的既有资产：

- **D8 历史类比块**（`intelligence/services/market_analogs.py`，已接线进 ask/turn_controller）：
  题材自身历史上的形态签名（双红天数/成交额首末比/均涨）滑窗加权距离取 K 段相似窗口，
  后续 5/10/20 日**只报 fact_sector_daily 事实不给概率**；跨题材剧本卡特征匹配，
  仅 approved 卡生效。
- **theme-fermentation-tracer**：消息面（evidence_index / recognition_timeline / 卖方覆盖）
  与盘面（双红/涨停热度/首板日）按日期对齐，输出「消息→首板→板块双红→补涨扩散」链路。
- **theme-radar**：新词→产业链→核心公司分层→证据→信号缺口的当前快照。

---

## 3. 能力 A：越用越懂（用户记忆闭环）

### 3.1 已经在做的（别重新发明）

- `foresight-feedback` skill：对话里的兴趣/否定/评分自动落 `interactions.jsonl`，
  亲和度按 14 天半衰期衰减，回灌进 foresight 排序（可解释加成）。
- corrections 强制落账 + 每日复盘/foresight 自动加载最近 corrections。
- `user_memory` 检索工具：专属 evidence_tier，「只作先验，不能冒充客观事实」的
  硬约束已有测试钉住。

### 3.2 缺口与设计（按 E-006 回灌优先级）

> 🔴 **2026-08-13 实施时的能力现状修正（本文第二处误判）**：本节初版说「没有
> 状态机」，**入口侧是错的**——`intelligence/services/memory_gate.py` 已有
> fail-closed 的记忆晋升门：`MemoryCandidate`（五种 kind）经 `MemoryGate.decide()`
> 裁决，只有「已回检且有终局裁决的 checkpoint 教训」或「provenance 严格绑定的
> 用户显式纠偏」才 eligible 进 durable 层，模型自评判断（model_judgment）与
> 易变事实（volatile_fact）一律拒绝，写入时 content SHA-256 绑定。
> 这正是 E-006 candidate→accepted 状态机的本仓版本，且比「加 status 字段」更强。
>
> **修正后的真差距是出口**：append-only 台账没有退出机制，错记/过时记录只能
> 人工删行（破坏可回放性）。

1. **记忆退出机制（P1，✅ 2026-08-13 已实现，slice 5）**：
   `intelligence/services/memory_status.py`——归档/撤销/恢复都是**追加**状态行
   （`record_type=memory_status`，指向目标记录 ts），不改历史；同一目标以最新
   状态行为准；`load_judgments`/`load_corrections` 侧过滤 archived/rejected，
   台账无状态行时行为逐字节不变（棘轮）。CLI：
   `python3 -m intelligence.cli memory-status --ledger judgments --target-ts <ts> --status archived --reason ...`
   （目标 ts 不存在时拒绝，防悬空审计链）。
   夜间回检呈现 candidate 批次的部分**未做**——入口门是同步裁决器，没有 pending
   candidates 台账；等真实出现「agent 想沉淀但无回检 provenance」的积压再建。
2. **预测台账与记忆命中分离（P1）**。foresight verdicts 已有雏形，补两件：
   - verdict 记录加 `error_class`（可复用 knevo 蒸馏 q3 的错因六分类）；
   - 呈现层区分「这条框架被召回过 N 次」与「这条框架验证后命中率 X/Y」，
     禁止用前者冒充后者。
3. **recall@k 尺子（P2）**。给检索加最小度量：判卷说「证据不足」时，
   离线跑同题多路检索，人工标注相关文档，算 recall@k——先有尺子再谈调优。

### 3.3 技术选型对比（教学点）

**「统一向量库」 vs 「结构化 JSONL 卡片 + 定向路由」**：

| 方案 | 优点 | 缺点 | 判定 |
|---|---|---|---|
| 全部进向量库（如 Chroma/Qdrant），语义检索一把梭 | 实现快、召回面广 | 类型混杂（判断/事实/偏好不分）、不可审计、E-006 明确反对 | ❌ |
| 结构化卡片分平面存 + 按维度定向路由（knevo/本仓现状） | 类型纯度、provenance 可审计、体量小时零依赖 | 召回靠关键词/规则，语义泛化弱 | ✅ 维持 |
| 折中：卡片为真本源，向量索引作为**派生**检索加速层 | 兼得，索引可随时重建 | 多一层同步 | 库过千条后再上 |

> 可迁移知识点：「真本源用结构化存储、向量索引只做派生加速」是 RAG 工程的主流做法
> （和「数据库 + 搜索引擎」的关系一样）；面试常考「为什么不直接把所有东西放向量库」，
> 答案就是类型纯度、可审计、可重建这三条。

---

## 4. 能力 B：行情结构化对标历史（市场情绪环境指纹）

### 4.1 差距定位

你要的是「看到这段区间的行情 K 线，找到以往类似的**情绪环境**」。现有 D8 是
**题材级**的（某题材自身历史的形态类比），而「情绪环境」是**市场级**的——
涨停潮/连板高度/涨家数/成交额/题材集中度共同构成的市场状态。这块目前没有模块。

### 4.2 设计：市场情绪指纹 + 相似窗口检索

数据全在主库现有表里，**不需要新数据源**：

| 维度 | 来源表 | 特征 |
|---|---|---|
| 量能 | `fact_market_daily` | 成交额、阶段标记 |
| 广度 | `fact_market_daily` | 涨家数、涨停家数 |
| 集中度 | `fact_market_daily` / `fact_theme_limit_heat_daily` | 集中度、top1 题材涨停份额 |
| 投机高度 | `fact_limit_advance_daily` | 连板最高度、晋级率 |
| 赚钱效应结构 | `fact_stock_high_daily` / `fact_sector_daily` | 新高家数、双红题材数 |
| 位置 | `fact_market_daily` | 偏离度（MA5 偏离） |

算法沿用 D8 的纪律（这是刻意的，同一套心智模型）：

1. **每日情绪向量**：上表 8~10 个维度，逐日一行；
2. **窗口签名**（默认 20 交易日）：每维取「窗口均值 + 首末变化率 + 趋势方向」，
   压成固定长度签名；
3. **滑窗匹配**：全历史滑窗（步长 5 日）算同口径签名，归一化加权距离取 Top-K
   互不重叠窗口（缺维按覆盖率惩罚，不伪造）；
4. **后续只报事实**：每段相似窗口之后 5/10/20 日的市场实际走法
   （指数涨跌/涨停数变化/连板高度变化），全部来自库内逐日行，**禁止说成概率**；
5. **缺数显式声明**：库不可用/历史不足/签名字段缺失都显式降级，禁止外推。

落点：`intelligence/services/market_regime_analogs.py`（新 D 块，形态同 D8：
纯函数核 + 只读 loader + `*_block_for_llm` 渲染 + 确定性意图路由——
命中「情绪环境/市场环境类似/历史上这种行情」类词面才注入）。

### 4.3 技术选型对比（教学重点）

「找历史相似市场状态」在量化里叫 **regime detection / market regime matching**，主流方案谱系：

| 方案 | 原理 | 优点 | 缺点 | 本仓判定 |
|---|---|---|---|---|
| **手工特征 + 加权距离**（D8 同款） | 领域特征压签名，距离排序 | 完全可解释、可审计、零训练、缺数可显式降级 | 特征选择靠领域知识；「相似」上限受特征表达力限制 | ✅ 首选 |
| **DTW 动态时间规整** | 允许时间轴弹性对齐再算距离 | 能匹配「节奏不同但形态同」的序列 | O(n²)、对多维序列要逐维加权、解释性差 | 备选：单维（如涨停数曲线）细化时可局部引入 |
| **HMM / regime-switching 模型** | 隐状态马尔可夫链，学出「牛/熊/震荡」等隐藏状态 | 学界与买方主流，能输出状态转移概率 | 要训练、状态语义事后解释、输出是概率——**违反本仓「只报事实不给概率」纪律** | ❌ 现阶段不做 |
| **窗口 embedding + 向量检索** | 时序编码器（如 TS2Vec）把窗口编成向量 | 与文本记忆统一检索面 | 黑盒、无法向用户解释「为什么像」 | ❌ |
| **LLM 印象流**（knevo 的做法） | 让模型凭训练语料「回忆」类似行情 | 零实现成本 | 无溯源、会编——q9 台账里它正是被我们的确定性版替掉的 | ❌ |

> 可迁移知识点：「特征签名 + 滑窗 + 后续事实」这套在任何时序对标场景都能用
> （运维指标异常找历史相似故障、用户行为序列找相似流失前兆）。
> 面试考点：DTW vs 欧氏距离的适用差异；HMM regime switching 是量化面试高频题。

### 4.4 配套：剧本卡库增厚

q9 的结论适用于市场级同理：**类比质量与库的厚度成正比**。剧本卡库现在只有
6 张 approved（信创/半导体/AI概念/锂电/TMT/军工）。市场级情绪对标落地后，
应同步开「市场情绪剧本卡」（如「2025-10 涨停潮退潮」「2026-04 缩量磨底」），
沿用 draft → 多源核数 → approved 的入库纪律。这是持续性工作，不是一次性任务。

---

## 5. 能力 C：题材逻辑生命周期追溯

### 5.1 差距定位

> 🔴 **2026-08-13 实施时的能力现状修正**：本节初版断言「没有生命周期阶段这个
> 一等公民」，**这是错的**——`intelligence/services/theme_lifecycle.py`（P1 批次）
> 已有**八阶段题材生命周期诊断**（新出现/旧逻辑唤醒/升温验证/加速定价/高位分歧/
> 二阶段回流/衰退观察/证伪退出），基于证据侧信号 + market_structure 状态机，
> 已接进 ask/agent 运行时。这次失误再次验证了 CLAUDE.md「断言我们没有 X 之前
> 必读能力图谱」的纪律（且实施时一度覆盖了该文件，已从 git 恢复并验证逐字节一致）。
>
> **修正后的真差距**：既有模块答「市场**现在**把题材交易到哪段」（当前态诊断），
> 缺的是「题材**历史上**怎么走过来的」（可回放时间线）。故 slice 3 的产出命名为
> `theme_lifecycle_timeline.py`，与诊断模块互补：两套阶段词表口径不同
> （交易叙事段 vs 盘面结构段），引用时须标明来源模块，不得混用。

素材盘点：theme-radar 给当前快照、fermentation-tracer 给发酵链路回溯、
recognition_timeline 给认知跃迁、theme_lifecycle 给当前阶段诊断；
缺「历史阶段切换时间线」与「逻辑从哪一版演化到哪一版」的追溯。

### 5.2 设计：事件日志 + 派生阶段（不落库状态机）

**选型先行（教学点）：状态机落库 vs 事件日志派生。**
如果把「当前阶段」写死进台账，判定规则一改历史就全错且无法重算；
改成**只存事件、阶段由确定性规则从事件重算**，规则演进时历史自动跟着修正。
这和会计的「流水 + 试算表」、前端的「event sourcing」是同一个思想——
**可重算的派生态永远优于可漂移的落库态**（本仓 sector snapshot 分代机制同理）。

1. **阶段判定（盘面侧，确定性规则，复用 tracer 已有对齐逻辑）**：

   ```text
   酝酿  消息面有证据/认知跃迁，盘面无首板无双红
   首发  首板出现（fact_limit_advance / theme_limit_stock 首板日）
   发酵  板块首次双红（fact_sector_daily：pct>0 & diff_ratio>10 & amount>500）
   主升  连续双红 ≥3 且连板高度抬升
   分歧  高位放量但双红中断（amount 新高而 diff_ratio 转负）
   退潮  双红消失 + 涨停热度份额回落
   回流  退潮后二次双红（对应跑马策略关注的「回流后再分歧」窗口）
   ```

   全部来自库内逐日行，可回放、可审计；阈值参数化，先用严格双红口径起步。

2. **逻辑演化层（消息面侧）**：每个阶段切换点挂「当时市场怎么理解这个题材」——
   recognition_timeline 的认知跃迁 + 卖方覆盖密度 + evidence_index 新增证据。
   这样「生命周期」不只是价格的生命周期，而是**逻辑版本的生命周期**：
   「v1 概念映射 → v2 订单验证 → v3 业绩兑现/证伪」。

3. **q8 契约回灌（输出纪律）**：题材跟踪输出采用 delta-only——
   - 对上期结论显式四态判定：`支持 / 削弱 / 无变化 / 信息不足`；
   - 结论带 `valid_until` TTL（跟踪结论 30 天、框架级 90 天），过期未复核自动降级为
     「待复核」；
   - 每期末尾产出「下期关注：指标 + 时间节点 + 触发条件」，作为下一轮的强制输入
     （与 foresight checkpoint 同构，但覆盖「观察清单」而不只是可证伪点）。

4. **落点与台账**：时间线模块已落 `intelligence/services/theme_lifecycle_timeline.py`
   （只读 CLI）。阶段事件台账若要建，按仓规**先在 `docs/learning/ledger-map.md` 登记**
   再创建。live 数据上段落过碎（见 §8），下一刀加滞回后再挂进 tracer/radar 输出。

---

## 6. 分期路线（可控单步，每 slice 独立可验收）

| Slice | 内容 | 动到的组件 | 风险 |
|---|---|---|---|
| 1 ✅（2026-08-13 已实现） | `market_regime_analogs.py` 纯函数核（每日情绪向量→窗口签名→滑窗匹配→后续事实）+ 合成数据单测 | 仅新增文件 + tests（`intelligence/services/market_regime_analogs.py`，证据编号 D10，18 测试全绿） | 低：不接线、不碰运行时 |
| 2 ✅（2026-08-13 已实现） | D10 接线：`evidence_registry` 注册（紧跟 D8）+ `include_regime_block` 开关 + ask provider + `ask_synthesis` claim 状态 INFERRED + `comparison_analog` 路由 + `history_analog` 操作符；workbench research_owner 的 stage 适配器面**未接**（留待需要时） | `ask_types` / `evidence_registry` / `ask.py` / `ask_synthesis` / `turn_controller` / `query_understanding`；Mac 真 venv 受影响面 9 个测试文件 218 全绿（收据 20260813T064027Z-6831f79d） | 中：完整 episode 级 live 问答尚未跑（需 LLM 中转），provider 级取数已 live 验证 |
| 3 ✅（2026-08-13 已实现） | 题材生命周期**时间线回放**只读 CLI（既有 `theme_lifecycle.py` 八阶段诊断已覆盖当前态，见 §5.1 修正；台账暂未建，建时先登记 ledger-map） | `intelligence/services/theme_lifecycle_timeline.py`（`python3 -m intelligence.services.theme_lifecycle_timeline --theme X`，14 测试全绿） | 低：只读 |
| 3.1 ✅（2026-08-13 已实现） | 时间线滞回：进「回流」须连续 ≥2 日双红确认（孤立单日不切段，起点回溯确认串首日）。live 对照：固态电池 53→25 段、信创 65→37 段；确认 3 日会过度合并（固态电池只剩 3 段，因多数双红连串仅 2 天），默认取 2 | `theme_lifecycle_timeline.py`（`reflow_confirm_days` 参数，CLI `--reflow-confirm`） | 低：只改派生规则，可回放对照 |
| 4 ✅（2026-08-13 已实现） | q8 契约回灌：跟踪表达契约（delta-only + 四态对照带证据编号 + 结论「复核期限」30/90 天 + 下期关注清单；无 [M]/[V] 基线时显式声明不虚构）。沿 scenario_tree 表达层模式，theme_track/跟踪词面命中才注入 | `track_contract.py` + `ask_types.include_track_guidance` + `ask_synthesis` 注入点 | 中：改输出形状——**样张待用户过目**，不满意关开关即回退 |
| 5 ✅（2026-08-13 已实现，范围修正见 §3.2） | 记忆退出机制：append-only 状态覆盖行（归档/撤销/恢复），loader 过滤，CLI `memory-status`；入口状态机 `memory_gate.py` 已存在（能力断言修正） | `memory_status.py` + `judgments/corrections` loader + CLI | 低：无状态行时行为逐字节不变 |
| 6 ✅（2026-08-13 已实现） | recall@k 尺子：`intelligence/eval/retrieval_recall.py`，user_memory 通道对齐 [M] 块生产语义（记录身份=ts），检索器可插拔；标注集 JSONL 需人工建 | eval 侧新增 + tests | 低：离线只读 |

依赖关系：1→2 顺序硬依赖；3→3.1 再进入 4；5、6 相互独立可并行。
剧本卡增厚（§4.4）是持续流程，不占 slice。

---

## 7. 本轮明确不做的

- ❌ 不上 HMM / embedding 检索 / rerank 模型——先把确定性版跑通、把库做厚，
  再谈语义层加速（届时向量索引作为派生层加入，见 §3.3）。
- ❌ 不接 knevo 的「按记忆条数决定检索深度」降级梯度（2026-08-04e 已被用户显式划掉）。
- ❌ 不给历史类比输出任何概率表述——D8 的「小样本历史事实，不是概率预测」红线
  原样适用于市场级与生命周期输出。

---

## 8. Live 验证（2026-08-13，经 exec-a77 隧道）

Mac 主树 `main` 有大量他人未提交改动，按 worktree 纪律另开干净树
`/Users/a77/fwp-wt-memory-analog` @ `124ca773`，只读主库
`/Users/a77/finance-workspace-private/db/market_feature_store.duckdb`。

**D10 市场情绪类比** [实测]：

- 十维全齐（`missing_features=()`），`available=True`。
- 当前近 20 日均值：成交额 23921 亿 · 涨停 79 家 · 最高连板 6 · 双红题材 40 个 · 偏离度 0.0%。
- Top-3 相似窗口：`2025-12-10~2026-01-08`（d=0.644）、`2026-03-23~2026-04-20`（0.668）、
  `2026-01-30~2026-03-06`（0.673）；后续 5/10/20 日指数累计与日均涨停已出。
- 部分窗口后续「最高连板」为 `—`：对应日期 `fact_limit_advance_daily` 缺行，按覆盖率降权，
  未伪造。这是缺数声明在干活，不是 bug。

**题材生命周期时间线** [实测]：

| 题材名 | 结果 |
|---|---|
| 固态电池 | 53 段，当前退潮；首发 2025-01-02 |
| 信创 | 65 段，当前退潮 |
| 液冷 / AI概念 | `fact_sector_daily` 无该 `sector_name`（板块名未对齐，显式降级） |

53/65 段说明「连续 5 日无双红 → 退潮」在真实双红闪烁下过于敏感，时间线变成锯齿。
规则本身可回放、可审计，但**不能当用户可读的生命周期叙事**。slice 3.1 加滞回
（最短阶段时长，或合并短于 N 日的相邻切换）后再给用户看。板块名要对齐
`dim_sector` / `resolve_query_themes`，不能硬编码口语别名。

**滞回后对照**（slice 3.1，`reflow_confirm_days=2`）[实测]：固态电池 53→25 段、
信创 65→37 段；`=3` 过度合并（固态电池只剩 3 段——多数双红连串仅 2 天，回流全被吞），
默认取 2。

**全量回归**（2026-08-13，revision `626a2c15`，Mac `.venv-workbench`）[实测]：
`4215 passed, 6 failed, 3 skipped`。6 个失败全部集中在
`test_conversation_orchestrator.py` / `test_codex_headless_runtime.py`——
三次运行（本分支全量、`origin/main` 对照、本分支隔离重跑）各挂**不同**子集，
`main` 基线同样失败，失败形态为 sqlite tmp 路径打不开与沙箱网络拒绝类，
判定为**存量环境敏感 flaky，与本分支无关**。本分支新增/触碰面的测试
（regime/timeline/memory_status/retrieval_recall/track_contract/registry/
ask_synthesis 相关）全部通过。

**隧道运维备注**：exec-a77 走 Cloudflare，单请求 >100s 会 524；长任务须
`nohup ... > /tmp/x.log &` 后台化 + 轮询日志，且 524 后原进程仍在跑，
重试前必须 `pgrep` 防双跑。
