# knevo 机制来源清单：证据等级 × 落点 × 状态（2026-10-10）

状态：**清单文档；只登记，不授权实施。** 来源：44 轮原文（`agent-memory/60_dialogues/knevo/2026-08-08-工具编排与step上限-44轮原文.md`，逐行读完）、
探针文档（`10_knowledge/knevo-engineering-probes-2026-08-07.md`）、三份蒸馏 / 会话稿、26 篇对话、主文档 `knevo-reverse-engineering.md`。
由 2026-10-09 深夜的机制抽取子 agent 完成通读后汇总，本文件把它的结论落成仓内可审计的台账。

等级：**实测**＝原文可见工具 input/output 或行为验证；**实测(skill正文)**＝`load_skill` 真实返回的文本，不证明运行时照做；**自述**＝knevo 口述；**推断**＝我们推的。
落点：`OS`＝`skills/finance-mode`；`app:<name>`＝对应专项；`code`＝需要改运行时；`—`＝未落。
状态：已炼化 / 部分 / 待炼化 / 故意不抄。

## 0. 先纠四个前提（防止反向归因）

1. **`task_stage`、「[方法论路由] 命中 workflow-card-today-review@40」、「同一缺口只恢复一次」、「依赖批 / 并行批」（作为规则名）、「结构化块数 ≤2/≤5」在全部 knevo 材料里零命中。** 它们来自本仓 `intelligence/runtime/research_progress.py`、`episode_issues.py` 与 `docs/learning/knevo-distill/E-005-comparison.md`，是 8792 自己的词表。2026-10-08 用户贴的「六层图」若含这些词，按本仓产物处理，不按 knevo 实测处理。
2. knevo 没有 `list_skills` / `use_skill`；真名是 `search_skills`（finance workspace 恒返回空）、`load_skill`（返回 `{name, description, icon, triggers[], body}`）、`read_skill_file`（404）、`load_workflow`（按 id 返回编排指令，非 DAG）。「列举与加载分离」是实测事实。
3. `finance_memory_write` **直写 durable 且同步可查**（44:L3036）；「agent 只有提案权」是 skill 纪律，不是 harness 限制。
4. `recommend_decision` 在全部材料里**从未被调用**；`suggest_options` 实测 44 轮里 20 次、常在正文前调，不是「每轮必调」；`finance_statement` 路由表指向它但实测 disabled；记忆条目实测无 `hitCount` 字段。

## 1. 机制表

### 工具层

| 机制 | 等级 | 出处 | 落点 / 状态 |
|---|---|---|---|
| 统一返回信封 `{ok, status∈ready/degraded/disabled/missing_config/NO_DATA_FOR_QUERY, data, sources, gaps, fallbackTargets, results[{elapsedMs, fallbackUsed}]}`；日志 success 只表传输，真值看 ok；**少返时 gaps 仍为空**（它的缺陷） | 实测 | 44:L2836, L2915, L2931 | code：本仓 `research_tool_registry` 逐项状态已比它强（程序化 stale/partial/empty/截断/晚于截止）；待补「少返必报 gaps」。部分 |
| 时间戳字段逐工具不同（`fetchedAt/tradeTime/marketState`、`as_of`＝披露日、`report_date`、`asOf`、`freshness_status`） | 实测 | 44:L1898, L2584, L2915, L2947 | code：本仓观察已带 source_date / 截止日；已炼化 |
| **工具返回夹带行为约束**：图谱返回 `finalAnswerRule`（引用 ≥1 条 edgeClaim/fact/evidence，edgeClaims 空不得说 verified）、`sourceScope`（不得声称搜了全图）、`agentGuidance`（仅 no_neighbors 时下发）；记忆返回 `ownershipNote` | 实测 | 44:L2966, L4319, L5154；P:L1254–1262 | code：**待炼化**（纪律走数据通道，不受上下文稀释）。候选位置 `research_tool_registry` 的观察投影；与 Codex 线文件无重叠需再核 |
| `finance_instrument` 一次拿全（基础档 + 现价 + 日K + 新闻 + 龙虎榜）「PREFER over separate」 | 实测 | 44:L3186–3301 | code：本仓按表分工具；故意不抄（我们的 dataset 覆盖面说明更细） |
| 图谱两工具：`entity_resolve` 置信三档 + `suggestedAction`；`graph_context(hops/max_facts/max_edges/max_evidence)` 返回 `edges/edgeClaims/facts/evidence/gaps∈entity_not_found/no_neighbors/no_facts`；edges 恒等于上限是截断值 | 实测 | 44:L3366–3398, L4950 | code：`graph_lookup` 弱版；待炼化（三类缺口码便宜，先做） |
| 文件 / 执行层：写入重定向、shell 白名单、sandbox network=none、web_fetch 截断落盘 | 实测 | 44:L3014–3052, L5615 | 本仓只读无外呼，不适用 |
| 渐进披露：模型只见 name + description + schema；市场边界与时间语义藏在 description | 自述 | 44:L3710–3720 | 已炼化（本仓工具 description 已是这个形状） |

### skill 层

| 机制 | 等级 | 出处 | 落点 / 状态 |
|---|---|---|---|
| skill 对象 `{name, description, icon, triggers[], body}`；文件不在 workspace；列举与加载分离 | 实测 | 44:L1337–1355, L1046, L2852 | Pi 臂 `--skill` 渐进加载；已炼化 |
| 清单：finance-mode（OS，自动注入）+ 8 专项（finance-analyze-stock / finance-earnings-review / finance-industry-report / finance-industry-track / finance-forecast-event / finance-kol-analyze / finance-associate / finance-review-check） | 实测 | 44:L1080–1090 | OS + 7 个专项文件已落：`finance-earnings-review` 的业绩点评骨架并入 `finance-analyze-stock`（同对象的窄切面）；`finance-industry-report` 并入 `finance-industry-track` 的 report 模式（report↔track 接力需要同一文件）；已炼化 |
| finance-mode 九段：硬触发 T1–T5 + 并行 + 「必须实际调用」+「快答＝检索后短答」+ 三豁免 / 关键词五法 / 身份 / 跨市场时序 + 来源词典 / 流程九步 / 路由表 / thesis check 七条 / 记忆纪律七条 + 抽取正反例 + 写回 + 改写 ≤3 / provider 表 / fallback + 输出纪律 + 交付契约 + 产物路径 + 禁止四条 | 实测(skill正文) | 44:L1365–1716 | OS：硬触发 / 并行 / 豁免 / 反顺从 / 记忆纪律 / 缺数 / 输出纪律 / 自检已落；**待并入**：关键词五法里的「多形态扩展」「复合拆解」、身份与表达段、跨市场时序 + 两级来源词典、流程九步、意图→专项路由表、thesis check 七条全文、记忆抽取正反例、交付契约「禁用完成状态 / 详见附件替代正文」。（finance-mode 当前由 Pi 线持有，本分支不改） |
| 专项通式八章：使用边界 → 标准流程（不要跳步）→ 分析框架 → 输出骨架（标题逐字）→ 来源标注 → 回复风格 → 输出契约 → 交付后（用户触发）；均以 `🎯 核心结论` 收尾 | 实测(skill正文) | 44:L1743–1831 | app：analyze-stock / industry-track / forecast-event / review-check / associate / kol-analyze 已按八章改写；market-review 由 Pi 线持有未改。部分 |
| 专项硬规则：analyze-stock 禁「现价÷记忆 EPS 硬算」、同源同 as-of、有效期；track 不复述无变化项；forecast 两到五互斥情景 + 决策者模拟、禁退化成「查记忆 + web 给概率」；review-check 六维 + verdict + FAIL 阻塞写回；associate 先图谱两跳、六维标来源、空维标「暂无显著关联」 | 实测(skill正文) | 44:L1735, L1867, L2029, L2045, L2053, L2271 | app：已炼化（阈值数字不抄，见 §3） |
| OS / 应用裁决：应用只能加不能改不能删；冲突 OS 赢；四类裁决 | 自述 | 对·技能规则冲突裁决 | OS §0；已炼化 |
| 注入层级：平台规则 → preset（turn entry 自动注入、变更即重注）→ load_skill body → 会话 → 用户；skill 可收紧不可授权 | 自述 | P:L245–257；44:L732–745 | Pi 臂：OS 进 system 节、专项按需；已炼化 |
| 遵守失效形态：自估遵守率无测量；finance-mode ≈ 五千 token + 专项 ≈ 三千 稀释；**中段否定性规则被忽略**；「快点回答」压力下跳硬触发；知道但省略 as_of | 自述 | 44:L637–689 | 设计约束：硬规则放段首段尾、否定句不埋中段、OS 体量不超它；本仓 OS 当前约五千字符。已炼化为写法纪律 |

### 路由与编排

| 机制 | 等级 | 出处 | 落点 / 状态 |
|---|---|---|---|
| 四层链路：workspace 路由（对模型透明）→ skill 注入 → 模型语义路由（finance-mode 九行「意图 → preset → skill」表，照表直接派单）→ 工具 | 自述 + 实测(skill正文) | 44:L741–819, L1508–1523 | OS §4 有三档 × 四维；**待并入**意图→专项路由表 |
| 直答 vs 派单：对话层给了**三套互斥阈值**（记忆≥5 / 0–2；轻 1–3 轮·中 4–8·重派单；四象限）且无优先级 | 自述 | 对·瑞华泰、深研升档、强制检索 | OS §4 只写一套作启发式；故意不抄成规则 |
| report vs track：时效词、有效期、今天刚讨论不派；report 埋跟踪信号 → track | 自述 | 对·report与track | OS §4 + app:industry-track；已炼化 |
| 预算与截断：无硬 step / 墙钟上限；每 turn token / 轮次预算；截断落在「工具结果已回、尚未 emit」的边界；实测最大 36 调用 / 子代理、同轮并发 6–8、3–4 子代理并发 | 自述（截断点）/ 实测（计数） | 44:L41–71, L110–151；P:L441–481 | code：本仓预算底座独立职责，保留；不抄数字 |
| 并行全或无：同轮 tool_calls 全并发、跨轮串行；首批无依赖 → 回来后补调 | 实测 | P:L464–481 | OS §2 / §3；已炼化 |
| sub-agent 协议：`spawn_sub_agent(task, preset∈六档, mode isolated/snapshot/inherit, skill_ids, memory_ids, attachments)` → `bg-<id>`；`wait_for_signal` 超时返 cancelled；`inspect` 只给 args；`get_bg_task` → final_report；emit(terminal) 注入父会话；子代理上下文＝task + finance-mode + 专项 + 空历史 | 实测 | P:L100–134, L377–394；44:L3620–3670, L4174 | Pi 臂 `spawn_sub_agent`（只读预设、恒挂 OS + 一专项、并行 ≤4、深度钉死）；mode / memory_ids / attachments 不抄。部分 |
| task 契约七要素：用户意图 / 标的与代码 / 市场 / 时间窗 / 已收集来源摘要 / 输出格式 / 输出语言 / 不允许实盘边界；主线程只路由 / 澄清 / 汇总 | 实测(skill正文) | 44:L1525–1529, L2876 | OS §5 写的是三段式；**待并入**七要素 |
| 失败处理：改写重试首次 + ≤2 = 3 次，三触发（空 / entity_not_found / 混合中英），手段序列（中英 → 简全称 → 名↔码 → 裸数↔后缀）；降级链 provider → 其他 provider → web → 用户文件 → gap；**实测缺口**：edit 失败才改路径、ls 被拒不换 find、read_skill_file 不重试 | 实测(skill正文) + 实测 | 44:L1621–1624, L2884–3052, L5610–5627 | OS §2；已炼化（手段序列已含） |
| 复合编排判据：标的独立 / ≥3 标的 → 并行；B 需 A 结论 → 串行；三到四个工具能覆盖 → 主线程混合；并行 ≤3–4、串行 ≤2 跳 | 自述 | 对·技能复合编排 | OS §5；已炼化 |
| 空确认：纯架构轮也调 `stage_extraction(candidates=[])` → `{status:"empty"}`；非每轮 | 实测 | 44:L398, L4760 | code：对应本仓 `judgment_extract`；待炼化（8792 接线时） |

### 记忆与图谱

| 机制 | 等级 | 出处 | 落点 / 状态 |
|---|---|---|---|
| 三库与默认范围：user-finmemory（可写）/ finmemory（只读）/ fundacore（后台）；**实测默认 sources 不含 user-finmemory**，查个人须显式传 | 实测 | P:L677–689；44:L178, L4968 | 本仓个人层单库；不适用 |
| `memory_query(query, sources[], kinds[], days, limit≤30)` → items 含 ownership / kind 七类 / tags / entityRefs / confidence / updatedAt；hybrid 双路；独立于 limit 的相关度截断（单查漏约三成五） | 实测 | P:L1352–1411 | code：`memory_lookup` 单 query；待炼化（复用 `closed_loop_retrieval` 窄 / 宽 / 反） |
| 写入两路：`finance_memory_write` 直写 durable、无删除工具；`stage_extraction` → pending batch → 用户 accept/reject | 实测 | 44:L3036–3041, L3422–3456 | code：本仓 `judgment_extract` pending→accept 在 Engine B；待接 Episode。**门要做在工具层不是 skill 层** |
| 抽取规则：提炼非复述、脱离原对话可懂、同一判断合并、时点绑定观察不暂存（正反例） | 实测(skill正文) | 44:L1592–1608 | OS：**待并入** |
| 图谱分界：能写成三元组且可追溯原文 → 图谱，其余 → 记忆；边 `{source, target, relationType, confidence, fact, evidenceChunkIds}` | 自述 | 对·图谱与记忆分界 | 知识库仓职责；不在本仓 |
| 冲突裁决：事实层 图谱 evidence > 个人 > 共享 observation > 共享 insight，时效可翻转，数据源可裁则替代全部记忆；判断层不选边写分叉条件 | 自述 | 对·三库检索合并、矛盾记忆 | OS §6；已炼化 |
| 召回三桶 + 阈值 + 同源去重（`updatedAt` 同分钟 + 同骨架按一条计） | 自述 + 实测 | 对·召回结果分层；P:L1264–1330 | OS §6 定性三桶；去重规则 code 待炼化（便宜） |
| 短期记忆目录只注入标题行，`recall_short_term` 展开 | 实测 | P:L514；44:L3676 | code：输入层「相关记忆 N 条标题行」待炼化（路由记忆丰度维度需要） |

### 输出与方法论

| 机制 | 等级 | 出处 | 落点 / 状态 |
|---|---|---|---|
| `suggest_options` 二到四条、每条 ≤20 字、用户口吻；四角度 A 纵深必选 | 实测 + 自述 | 44:L18, L3700；对·追问设计 | OS §8 + 各专项结尾；8792 侧 `followups.py` 确定性生成保留。已炼化 |
| `recommend_decision` 八字段；**从未被调用** | 自述 | 44:L3685–3698 | code：本仓 `judgment_extract` 八字段在，接线待做；不抄「调用」形状 |
| 交付契约：正文必须是完整结论，禁「分析完成 / 已写入文件 / 详见附件」；terminal emit 自包含；骨架标题逐字 + 🎯 收尾 | 实测(skill正文) | 44:L1694–1702 | app 各专项「输出契约」节已落；OS **待并入** |
| 数量上限：suggest 2–4；decision 1；情景 2–5；跟踪要点 3–5；产业链 2–3 跳；结论段五要素 | 自述 | 44:L2543；对·结论段 | 定性抄形状、不抄数字（见 §3） |
| 来源词典：personal → sourceLabel；shared →「(共享记忆库:label)」；provider/web 两级「渠道 + 底层来源」；纯推理 → `[inference]` | 实测(skill正文) | 44:L1469–1477 | app 各专项已用 `[inference]` 等标签；OS **待并入**两级标注 |
| 无硬质检门：自承无 post-gen reviewer，来源 / as-of / 事实-推断分层全靠自觉 | 自述 + 实测 | S9:L47–57；44:L365–377 | 设计依据：本仓出口门降为 lint（Codex 线在做）；review-check 作为模型执行的审查 |
| as-of / 时序：盘中「截至 HH:MM」、EOD「截至日期收盘」；跨市场时段表；后发生不解释先发生 | 实测(skill正文) | 44:L1437–1467 | OS **待并入**（本仓 A 股为主，跨市场段按需） |
| thesis check 七条 | 实测(skill正文) | 44:L1541–1558 | OS §1 有四条；**待并入**全七条 |
| 检索三口径 + 自评四问 | 实测(skill正文) + 自述 | 44:L1395–1401；对·检索词构造 | OS §6；已炼化 |
| 缺数三档；可信度五级（权威 / 券商 / 咨询媒体 / PR / 推断）；多源冲突不取平均给区间 | 自述 | 对·缺关键数字；P:L706–719 | OS §7 三档已落；五级可信度待并入（定性） |
| 突发六步 / 券商分歧不选不求和 | 自述 | 对·突发消息、券商预测分歧 | app:forecast-event 六步已落；分歧呈现待并入 analyze-stock |

## 2. 材料间矛盾（引用前先看这里）

1. 写权限：直写 durable（实测）vs「只有提案权」（主文档）——提案是纪律不是限制。
2. 风远94 ＝ finmemory 的一个来源（44:L5307）vs 全部来自风远94（L5762）vs UI 把 finmemory 整体命名风远94（P:L1131）。
3. 主线程压不压缩：「不二次压缩」（44:L4191）vs「汇总＝提炼」（主文档）vs「交叉对比 / 封装」（对·重档路由实演）。
4. 默认 sources：UI 勾选三库（P:L687）vs 实测不含个人库（44:L178）。
5. 图谱底座：description「SQL-backed」vs 探针「图数据库最强信号」vs 自述「不是传统 GraphRAG」。
6. resolve → graph「写死两步」（44:L3398）vs 轮 30/31 直接调 graph。
7. suggest_options「每轮一次结尾内联」vs 实测 20/43、正文前调。
8. 直答 / 派单阈值三套互不兼容，且与「全面分析→必派」「今天刚讨论→不派」同时命中无优先级。
9. `finance_statement` 路由指向它 vs 实测 disabled。
10. `hitCount` 列为返回字段（探针）vs 实测样本无此字段。
11. finance-mode 注入方式四说（对话开头块 / 每轮注入 / preset 预加载 / load_skill）。
12. 来源强度：「个人 > 共享」vs「图谱 evidence > 个人」vs 反顺从「用户观点先当假设」——三者分别管记忆、事实、用户当下表态，不矛盾但要分清对象。
13. 自述折价：轮 2/4/6/7 用户带答案提问，knevo 开头依次「你的推断是对的 / 基本准确 / 完全正确」——这几段截断 / 注入自述可信度要下调；轮 26「消融实验」被 skill 知识污染。
14. knevo 自认夸大：护城河、飞轮漏人工闸门、自审先「有」后「无」、工具数 26→36→39。

## 3. 故意不抄的数字与形状

| 不抄 | 理由 |
|---|---|
| 阈值数字：三桶 7/30/90 天、置信 0.7/0.8/0.9、review 偏差百分比、有效期 90/30 天、情景 2–5、要点 3–5 | 量纲是它的；本仓阈值按自己台账定，运行时 skill 不写数字（`test_knevo_skill_layer` 钉住） |
| `finance_instrument` 一次拿全 | 本仓 dataset 覆盖面说明更细，合并会丢边界 |
| sub-agent 的 mode=snapshot/inherit、memory_ids、attachments | 本仓只读验证臂不需要 |
| 程序化「按记忆条数定工具数」 | join-kernel spec §9 否决成立；OS 启发式 |
| 第二总控 / 照六层图重写 | 架构审查已否 |
| 共享记忆平面 | 2026-08-28 gate 证伪 |

## 4. 最可迁移但还没做的（按便宜程度排序）

1. 工具返回夹带行为约束（finalAnswerRule / sourceScope / agentGuidance / ownershipNote）——数据通道不受稀释。
2. 返回信封「少返必报 gaps」（补 knevo 自己没做的一条）。
3. 图谱返回三类缺口码。
4. 记忆同源去重（updatedAt 同分钟 + 同骨架）。
5. `memory_lookup` 复用闭环检索窄 / 宽 / 反。
6. 两阶段记忆提交 + 空确认接到 Episode（`judgment_extract`），门做在工具层。
7. task 契约七要素进 OS §5；thesis check 七条、流程九步、路由表、交付契约进 OS（等 Pi 线放手 finance-mode 后做）。
8. review-check 的六维阈值进审查台账（不进 skill 正文）。

以上 1–6 涉及运行时代码，按「每次只改一个变量、先红后绿、先 Pi 臂后 8792」的纪律推进；本分支不实施。
