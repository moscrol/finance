# E2 设计稿：材料题边界——编号题组拆分、material-only 契约投影与检索抑制

日期：2026-09-13 · 状态：**设计待评审（未实现）** · 分支：feat/e2-material-contract-design
立项来源：QC-2026-09-13 E2（P1，正式 PK 前置）；复审边界：设计/实现严格拆开，本稿只到设计。

## 1. 失败样本（已固化，SHA 见 e2-evidence/MANIFEST.json）

| 样本 | 现象 | 根因层 |
|---|---|---|
| T2 `run_20260913_035722_162700` | 8 题只答出 Q8 语境；答案注入 09-11 真实板块行情进虚构题 | 拆分吞题 + 无 material-only 投影 + 检索不抑制 |
| T3 `run_20260913_041146_035132` | `question=""` → kol_review「用户只提供了材料未提问」分支（query_understanding.py:1534）；未交付 Q8 的 ≤200 字备忘录 | 同上 + 逐题交付缺失 |
| QC 证据包 | `data-qc.json` / `route-parent-recheck.json` / 6 份 answer.md | — |

产生代码版本：部署快照 2ee664fa（main 5fb13a8c）。T3 会话 conv_47243ada… 含两次失败残桩，正式 PK 必须全新会话。

## 2. 数据流现状与三个缺陷点

```
raw user message
  → split_user_message (user_task.py:547)        ←【缺陷1】编号题组被当材料吞并
  → QueryEnvelope / kol_review 分支 (query_understanding.py:1534)
  → TaskFrame (task_frame.py:89)                 ←【缺陷2a】无 premise 约束载体
  → _grounding_mode (episode_factory.py:497)     ←【缺陷2b】无 material-only 分支，
                                                     全部落默认 "evidence"
  → TurnDecision.needs_retrieval / retrieval_planner.plan_retrieval (ask.py:4166)
                                                 ←【缺陷3】检索不抑制，真实行情注入
  → evidence contract / required_outputs         ←【缺陷4】无逐题交付与 memo 槽
  → final answer → semantic verifier（judge）
```

缺陷 2 的连锁：grounding 全落 evidence → 语义裁判拿真实世界证据要求虚构材料题 →
检索注入的真实行情反而「通过」了证据校验——**裁判与检索共用同一个错误前提**，
所以只改合同不改检索会让裁判对注入失明，只改检索不改合同会让材料句被数值门砍光。
这就是 QC 要求三层一起设计的原因。

## 3. 设计决策

### D1 编号题组识别（split_user_message）
- 新识别器：连续 ≥2 行匹配 `^\s*\d+[.、)）]` 且其中 ≥2 条含疑问词/问号 →
  「编号题组」，**不是材料**；每条进 `MessageParts.sub_questions: tuple[str, ...]`。
- 位置规则：题组在已识别材料块之外才生效（材料正文里的「1. 2. 3.」列举不触发）。
- T2 结果：材料 + 8 条 sub_questions（不再是「只有 Q8 是问题」）；
  T3 结果：材料 + 各条 sub_questions（不再 question="" 落材料提纯分支）。
- 纯确定性，无 LLM。

### D2 material-only 约束检测
- 触发词（用户原文显式约束）：只依据/仅根据/不要联网/不用查/假设……（反事实）/
  虚构/纯属虚构/如果……会怎样。
- 产出 `premise_mode`：`real_world`（默认）/ `material_only` / `hypothetical`。
- **关键区分**：仅「贴了材料没提问」不触发抑制（kol_review 默认目标就是
  「核对可核验项」，需要真实数据）；只有用户显式约束才触发。这保住现有研报提纯行为。

### D3 契约投影（_grounding_mode 新分支）
- `premise_mode != real_world` → 内容槽 grounding = `user_premise`
  （复用既有语义：「用户明确给出的前提视为真的假设，不能要求先证明前提」——
  与反事实条件题 `判断反事实条件` 的既有路径同族，不另造平行机制）。
- 边界/限制槽保持 evidence：答案仍须说清「结论只在材料前提内成立」。

### D4 检索抑制
- `premise_mode != real_world` → `TurnDecision.needs_retrieval = False` +
  retrieval_planner 短路：不注入数据中心/板块行情/研报检索。
- memory（用户自己的历史判断）默认保留——它是用户资产不是外部事实；
  是否一并抑制列为开放问题 OQ2。

### D5 逐题交付与 Q8 memo
- sub_questions 在场 → 答案合同要求**每题一节**；结构预检数节数 vs 题数。
- 「≤200 字备忘录」成为显式 `memo` 输出槽，带字符预算，进 required_outputs；
  结构预检核验「memo 存在且 ≤200 字」，不再靠模型自觉。

### D6 裁判不致盲 + 前提纯度反注入
- 裁判输入 = 材料（前提）+ 各题 + 答案；user_premise 契约下不要求外部证据。
- 新增负向检查「premise purity」：答案不得引用材料之外的市场数据
  （如真实日期行情、真实板块涨跌幅）——与 D4 形成纵深（检索侧堵源头，
  裁判侧兜底检测）。

## 4. 设计级验收断言（T2/T3）

- A1：T2 拆分 = 材料 + 8 条 sub_questions（Q1–Q8 全在，非只剩 Q8）。
- A2：T3 拆分 = 材料 + 各题；`premise_mode=hypothetical`（虚构约束被检出）。
- A3：T2/T3 重跑时检索计划零市场数据 provider；答案不含 09-11 真实板块行情
  （用失败样本里出现过的真实板块名做缺席断言）。
- A4：T2 答案 8 节齐全 + memo ≤200 字；judge_status 不因结构预检提前退出。
- A5：无约束的纯贴研报行为不变（检索保留、kol_review 默认目标不变）——回归锁。
- A6：S1/N1 回归锁保持绿（192 字 quick_fact、802 字 disclosure 变体）。

## 5. 开放问题（评审时拍板）

- OQ1：`premise_mode` 进 TaskFrame 新字段会改变 `task_frame_hash` 全量值
  （asdict 全字段哈希）→ 哈希键缓存一次性失效。选项：a) 接受一次性失效；
  b) 仅当 != real_world 时纳入哈希。**倾向 b**，需评审确认无侧效应。
- OQ2：hypothetical 下 memory 是否一并抑制。
- OQ3：多题交付用「单 episode 多节」（推荐，符合用户对一份答案的预期）
  还是「N 个子 episode」（编排改动大）。

## 6. 实施拆分（设计过审后）

- P1：D1 拆分识别器 + 测试（纯函数，风险最低）
- P2：D2 检测器 + TaskFrame 载体（按 OQ1 结论）+ D3 投影 + 测试
- P3：D4 检索抑制 + D6 前提纯度 + 测试
- P4：D5 逐题交付 + memo 槽 + 结构预检 + 测试
- P5：T2/T3 全新会话重跑 + A1–A6 验收 → 才谈正式 PK 就绪

## 7. 风险与回滚

- 编号题组误报（材料内列举）：靠「题组在材料块之外 + ≥2 条疑问形态」双条件压；
  回归测试含反例。
- 约束词误报（普通问句里的「假设」）：hypothetical 对该类题本就更正确
  （与既有反事实 user_premise 路径一致），误报代价低。
- 每阶段独立可回滚：D1–D5 各有 feature flag 级开关点（路由/投影/检索/合同四层分离）。
