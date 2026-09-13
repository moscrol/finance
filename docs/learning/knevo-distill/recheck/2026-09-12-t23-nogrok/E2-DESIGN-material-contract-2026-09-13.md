# E2 设计稿 v3：材料题边界——题组识别、两轴约束、冻结点授权收口与逐题对应

日期：2026-09-13（v3 按 QC 复审 commit 1f91343a 六条意见返修）· 状态：**设计待评审（未实现）**
分支：feat/e2-material-contract-design · 立项：QC-2026-09-13 E2（P1，正式 PK 前置）
保留 v2 已获认可的决定：两轴模型、单 Episode 逐题槽、memo 归 T3 Q8、全新会话 T2→T3 验收链路。

## 0. v3 返修总览（对应 QC 六条）

| # | 级别 | 问题 | v3 落点 |
|---|---|---|---|
| 1 | P1 | 授权清算落在中间层，工厂会重加 `_MODEL_OWNED_READ_CAPABILITIES`（=finance_query/evidence_search，:216/:256）；开场预取不经过工具选择直接播种证据账本 | D4 改**冻结点收口**：过滤作用于工厂所有回补之后 + dispatch 兜底；预取/补检/子研究/恢复共用同一冻结授权 |
| 2 | P1 | 零证据与必需 evidence 边界槽冲突（已复现 `missing_evidence: evidence_boundary`） | D3 边界槽改为**材料绑定的前提域声明**，不再要求外部证据，也不整体关闭裁判 |
| 3 | P1 | T3「继续上一轮……其余条件不变」无禁令短语，默认回 full | D2/D7 **会话级约束上下文**继承/覆盖/复位规则；验收用原始 T3 文本 |
| 4 | P1 | user_premises 非空 ≠ fictional（用户信念是待证伪判断） | 新增结构化 `premise_marks`，真实性/来源/作用范围显式标记，默认省略 |
| 5 | P2 | 三个脱敏副本无法按清单验哈希 | MANIFEST v2：原件哈希与仓内副本（路径/大小/哈希/变换）分开登记；external-only 显式标注（已落盘） |
| 6 | P2 | 「数八节」太弱：空行分隔规则字面矛盾、八节≠八题、黑名单误伤 | D1 规则澄清 + D5 稳定 question_id 一一对应三态校验 + D6 纯度按**来源绑定**校验 |

## 1. 失败样本
同 v2（e2-evidence/MANIFEST.json v2：21 项运行时原件哈希 + 14 项仓内副本哈希 +
7 项 external-only；三个脱敏文件的变换已登记为 `HOME→~`）。

## 2. 数据流现状（冻结点标注版）

```
split_user_message (user_task.py:547)              ← D1 题组识别
→ kol_review 分支 (query_understanding.py:1534)
→ TaskFrame（user_premises:125 / 默认省略:157）     ← D2 两轴 + premise_marks 载体
→ _grounding_mode (episode_factory.py:497)         ← D3 前提域声明投影
→ TurnDecision / retrieval_planner                 ← D4a 检索计划短路
→ 检索硬触发下限 (turn_controller.py:780)           ← D4b material_only 让路
→ 【合同冻结点】episode_factory.py:
     _authorized_capabilities (244-261)            ← 无条件重加 finance_query/evidence_search(:216,:256)
     mandatory 回补 (639-644)                       ← evidence_free 后仍回补必需能力
     _opening_prefetch_evidence (episode_tools.py:660) ← 不经工具选择直接播种证据账本
   ⇒ D4c 冻结点收口：上述全部完成后再过滤，且 dispatch 兜底
→ 合同/required_outputs                            ← D5 question_id 逐题槽
→ answer → semantic verifier                       ← D6 来源绑定纯度
```

## 3. 设计决策（v3）

### D1 题组识别（规则澄清）
- 编号项**允许空行分隔**：在材料块之外，凡以 `^\s*\d+[.、)）]` 开头的段落皆为候选
  题项；序号与上文连续（含用户原编号 1..N）即归为同一题组。「连续 ≥2 行」只是充分
  条件之一，不是必要条件（v2 措辞造成的字面矛盾废止）。
- 稳定 `question_id` = 用户原编号（q1..qN），随 MessageParts.sub_questions 逐条携带；
  正文被引用、改写、重排时 id 不变。

### D2 两轴模型 + premise_marks（v3 载体修正）
- 轴 A 前提真实性 / 轴 B 数据范围（full/local_only/material_only）维持 v2。
- **不以 user_premises 非空判 fictional**：既有字段装的是用户信念/观察/过往判断
  （如「我认为甲公司业绩改善」→ 待证伪），行为完全不变。
- 新增并行字段 `premise_marks: tuple[{text_ref, authenticity, source_turn, scope}, ...]`：
  - authenticity ∈ `fictional`（不证伪）/ `unverified_belief`（待证伪，默认）；
  - source_turn = 标记产生的会话轮次；scope ∈ `message` / `q{i}`（单题作用域）。
  - 默认省略序列化（task_frame.py:157 模式）：无标记不进哈希，旧哈希不变。
- 约束识别**只在用户指令区**（split 后的 question/sub_questions 区域）；材料正文与
  引用里的「假设/不联网/只依据」**不当命令**（QC 3 后半条）。

### D3 前提域声明槽（解决已复现的合同冲突）
- 冲突根因：v2 让边界槽「保持 evidence」——外部取证被禁后，evidence_boundary 空绑定
  被拒、填说明又被 `missing_evidence` 拒，两头堵。
- v3：「结论仅在材料前提内成立」定性为**前提域声明**——绑定到**材料本身**
  （basis=user_premise，材料即前提），不是需要外部证据的市场事实。
  边界槽 grounding 随之改 user_premise（而非 v2 的 evidence）。
- 裁判不关闭：它校验「声明存在且绑定材料」「内容句不越域引用外部事实」，
  只是不再向前提域声明索要外部证据。
- **非虚构 material_only 计算题**同法覆盖：计算输入与结果绑定材料（材料是合法
  证据源），无需外部证据即可成立。

### D4 冻结点授权收口（v3 核心返修）
1. **收口位置**：data_scope 过滤作用于 `_authorized_capabilities` 返回与 mandatory
   回补**之后**——material_only 时 `finance_query`/`evidence_search` 即使被 :256 重加、
   被 :639-644 回补，也在冻结授权中移除；冻结结果写入合同，后续不再重新推导。
2. **开场预取**：`_opening_prefetch_evidence` 对 material_only 短路——不预取、
   不播种证据账本（它不经工具选择，只关检索/memory_lookup 挡不住）。
3. **覆盖路径**：预取 / mandatory 回补 / 模型自选重加 / 补检 / 子研究 / 恢复
   （clarify 续跑等）全部读同一份冻结授权，不各自重算。
4. **dispatch 兜底**：执行层按冻结授权校验每次工具调用——模型主动请求被禁工具
   → 拒绝 + trace 留拒执记录（这是 A9 的验收钩子）。

### D5 逐题一一对应（替代「数八节」）
- 合同输出槽按 question_id 生成：`answer_q1..answer_qN`；memo 槽仅当该题显式要求
  （长度预算从题文解析，T3 q8 → ≤200 字）。
- 结构预检三态**分别**校验：
  - 遗漏：某 question_id 无对应正文段 → fail；
  - 重复：同一 question_id 对应多段（含「把 Q1 答八遍」）→ fail；
  - 明确缺口：题内声明「材料无法回答」→ 合法 gap，单独标记不算遗漏。

### D6 纯度按来源绑定（替代黑名单）
- 验收门槛：答案中市场事实类句子的绑定（basis/证据哈希）必须可追溯到**材料或
  前提域声明**；绑定外部 provider（数据中心/检索/实时）→ 拒。
- 板块名黑名单降级为调试信号，不作验收门槛（材料中合法同名实体不再误伤）。

### D7 跨轮继承（解决 T3 无禁令短语）
会话级约束上下文（conversation constraint context），规则：
- **继承**：本轮有续轮标记（继续/接着/其余条件不变/同上……）且无新约束短语
  → 继承上一轮 A/B 轴与 premise_marks。T3 原文「继续上一轮的虚构案例……其余条件
  不变」命中此条，保持 fictional × material_only。
- **覆盖**：本轮显式放宽（可以查真实数据/结合最新行情）→ 本轮 B 轴按新短语；
  显式收紧同理。
- **复位**：换题（新主语/新材料且无续轮标记）→ 回默认 real × full。
- 载体：约束上下文随会话状态（continuous-episode）持久，逐轮注入 TaskFrame；
  跨会话不继承（material_only 同时禁跨会话记忆，但**同题链上下文**——上一轮材料
  与原答——作为用户当面前提保留，见 v2 D7，本条不变）。

## 4. 设计级验收断言（v3 修订版）

- A1：T2/T3 拆分：空行分隔的编号项同属一题组；question_id = q1..qN 稳定携带。
- A2：两轴检出（T2/T3 = fictional × material_only）；约束只来自用户指令区，
  材料内的「假设」字样不触发。
- A3（改）：来源绑定纯度——市场事实句全部绑定材料/前提域声明；无外部 provider
  绑定。板块名缺席仅作调试信号。
- A4（改）：question_id → 槽 → 正文一一对应；遗漏/重复/明确缺口三态分别断言；
  T2 无 memo 要求，T3 q8 memo ≤200 字。
- A5：无约束纯贴研报行为不变（kol_review 默认核对可核验项）——回归锁。
- A6：S1/N1 回归锁绿（192 字 quick_fact、802 字 disclosure 变体）。
- A7：全新会话 T2→T3 链路，**T3 用原始文本**（「继续上一轮……其余条件不变」，不
  重贴禁令）：turn2 继承 turn1 约束；随后第三轮显式放宽可检索（覆盖），换题复位。
- A8：「假设 X，结合当前行情」：前提不被证伪且真实检索仍发生（防过度抑制）。
- A9（新）：探针强制模型请求被禁工具（finance_query）→ 执行层拒绝 + trace 留拒执
  记录；opening_prefetch 在 material_only 下证据账本零播种。
- A10（新）：非虚构 material_only 计算题（材料给数据、要求算指标）可完成，
  计算结果绑定材料，无 `missing_evidence` 误拒。

## 5. 实施拆分（设计过审后，顺序按依赖）
P1 D1 题组识别 → P2 D2 载体+premise_marks+D3 投影 → P3 D4 冻结点收口+dispatch 兜底
→ P4 D5 逐题槽+结构三态 → P5 D7 跨轮继承 → P6 A1–A10 验收（全新会话，原始文本）。

## 6. 风险与回滚
- 冻结点过滤误删合法必需能力：只对 material_only/local_only 生效，full 路径零改动；
  配 A5/A6 回归锁。
- 续轮标记误判（普通追问被当续轮继承禁令）：继承仅在「有续轮标记且无新约束」时
  发生；换题复位有 A7 断言。
- premise_marks 与既有 user_premises 消费方并存：并行新字段，不改旧字段语义；
  默认省略保证旧哈希不变。
- 各层独立开关点（拆分/载体/投影/冻结/逐题/继承），逐层可回滚。
