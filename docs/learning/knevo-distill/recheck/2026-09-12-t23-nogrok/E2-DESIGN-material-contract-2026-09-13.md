# E2 设计稿 v2：材料题边界——编号题组拆分、两轴约束模型、工具授权抑制与逐题交付

日期：2026-09-13（v2 按 docs/qc-l2-e2-merge-0913@3af70caa 复审返修）· 状态：**设计待评审（未实现）**
分支：feat/e2-material-contract-design · 立项：QC-2026-09-13 E2（P1，正式 PK 前置）

> v1 被否四处，本版逐条修：①证据落错树（已搬正）；②只关 retrieval_planner 不够，
> 必须约束最终工具授权（改走既有 evidence-free/user_premise 复用点）；③「不联网/
> 假设/只依据材料」不能等同（改两轴模型）；④memo 归 T3 不归 T2、T3 验收须在同一
> 全新会话的 T2→T3 链路上。

## 1. 失败样本（已固化，SHA 见 e2-evidence/MANIFEST.json）

| 样本 | 现象 | 根因层 |
|---|---|---|
| T2 `run_20260913_035722_162700` | 8 题只答出 Q8 语境；答案注入 09-11 真实板块行情进虚构题 | 拆分吞题 + 无 premise 投影 + 工具授权未抑制 |
| T3 `run_20260913_041146_035132` | `question=""` → kol_review「只贴材料未提问」分支（query_understanding.py:1534）；未交付其 Q8 的 ≤200 字备忘录 | 同上 + 逐题交付缺失 |
| QC 证据包 | `data-qc.json` / `route-parent-recheck.json` / 6 份 answer.md / 复跑脚本 | — |

产生代码版本：部署快照 2ee664fa（main 5fb13a8c）。原 T3 会话 conv_47243ada… 含两次
失败残桩，**验收必须另起全新会话**，见 §4 A7 的链路形状。

## 2. 数据流现状与缺陷点（v2 修正版）

```
raw user message
  → split_user_message (user_task.py:547)          ←【缺陷1】编号题组被当材料吞并
  → kol_review 分支 (query_understanding.py:1534)
  → TaskFrame (task_frame.py:89；已有 user_premises:125 与默认省略序列化:157)
  → _grounding_mode (episode_factory.py:497)       ←【缺陷2】无 fictional-premise 分支，
                                                       全落默认 "evidence"
  → TurnDecision.needs_retrieval / capabilities    ←【缺陷3】两层都漏：
       retrieval_planner.plan_retrieval (ask.py:4166)   a) 检索计划不抑制
       检索硬触发下限 (turn_controller.py:780)            b) 硬触发下限会把材料里的
       capabilities 清算先例 (turn_controller.py:794)      标的/时效词重新拉起检索
       user_premise 槽工具禁令先例 (episode_protocol.py:165)  c) Episode 仍可自行调
                                                              finance_query/evidence_search
  → evidence contract / required_outputs           ←【缺陷4】无逐题交付与 memo 槽
  → final answer → semantic verifier（judge, episode_semantic_verifier.py:389-410
     已有 user_premise 语义：用户前提视为假设，不要求证明）
```

只改合同不改授权会让裁判对注入失明；只改授权不改合同会让材料句被数值门砍光；
只关 retrieval_planner 不关 capabilities，Episode 会在生成期自己把真实行情查回来。
三层一起设计是硬约束，不是偏好。

## 3. 设计决策（v2）

### D1 编号题组识别（split_user_message）
- 新识别器：连续 ≥2 行匹配 `^\s*\d+[.、)）]` 且 ≥2 条含疑问词/问号 → 「编号题组」，
  **不是材料**；每条进 `MessageParts.sub_questions: tuple[str, ...]`。
- 位置规则：题组在已识别材料块之外才生效（材料正文里的编号列举不触发）。纯确定性。
- T2 → 材料 + 8 条 sub_questions；T3 → 材料 + 各条 sub_questions（不再 question=""）。

### D2 两轴约束模型（替代 v1 的单一 premise_mode）

QC 指出「不联网/假设/只依据材料」语义不同，本版拆成两个独立轴：

| 轴 | 取值 | 驱动 |
|---|---|---|
| A 前提真实性 | `real`（默认）/ `fictional` | grounding 投影（fictional → 前提句按 user_premise 对待，不拿来对照真实世界证伪） |
| B 数据范围 | `full`（默认）/ `local_only` / `material_only` | 检索计划 + 工具授权 |

触发词映射（均为用户原文显式短语，确定性检测）：
- 只依据/仅根据（以上）材料 → B=`material_only`（连本地库也不许用）；
- 不联网/不要联网/别查实时 → B=`local_only`（本地 DuckDB 历史事实可用，禁止实时拉取类工具）；
- 假设/虚构/纯属虚构/如果……会怎样 → A=`fictional`，**B 不变**（除非同时出现上两类）——
  「假设 X，结合当前行情会怎样」因此仍可检索真实行情，前提本身不被证伪。
- 组合示例：T2/T3（虚构 + 只依据）= A fictional × B material_only。
- **关键区分保留**：仅「贴了材料没提问」两轴都不动（kol_review 默认「核对可核验项」
  需要真实数据），现有研报提纯行为不变。

载体：A 轴复用既有 `TaskFrame.user_premises`（前提句入列，extract_user_premises
已有提取先例 :407）；B 轴新增 `data_scope: str = "full"`，**序列化沿用
task_frame.py:157 的条件省略**——默认 `full` 不进 payload/hash，旧哈希全不变（OQ1 解）。

### D3 契约投影（_grounding_mode 新分支）
- A=fictional → 前提派生句按 user_premise（与既有反事实路径 :508/:542 同族，
  复用 `_is_evidence_free_task` 的 evidence-free 判定入口而非另造平行机制）；
  边界/限制槽保持 evidence（仍须声明「结论只在材料前提内成立」）。
- B 轴不改变 grounding，只改变工具面（见 D4）。

### D4 工具授权抑制（v2 核心返修：三层落点，全部复用既有先例）

1. **检索计划**：B≠full → plan_retrieval 短路对应 provider 集合
   （material_only 全禁；local_only 禁实时类）。
2. **硬触发下限**：turn_controller.py:780 的检索硬触发对 B=material_only 让路——
   显式用户约束优先级高于下限（设计裁定；配回归测试防复辟）。
3. **最终工具授权**：B=material_only → 该 turn 的 capabilities 清空市场数据类工具
   （比照 turn_controller.py:794 chat  lane 的 `capabilities=()` 清算模式），
   Episode 生成期无法自行调用 finance_query/evidence_search；user_premise 槽的
   工具禁令（episode_protocol.py:165）已对前提槽生效，无需新机制。
   local_only → 仅摘除实时拉取类，保留本地 fact 表读取。

### D5 逐题交付与 memo 槽（v2 修正归属）
- sub_questions 在场 → 合同要求**每题一节**，结构预检数节数 vs 题数（OQ3 解：
  单 Episode、逐题输出槽，不起 N 个子 Episode）。
- **memo 槽只在题目显式要求时生成**：长度预算从该题原文解析（如「≤200 字」）。
  T3 的 Q8 命中 → memo 槽 + ≤200 字符预算进结构预检；T2 无此题 → 无 memo 要求。
  （v1 把 memo 错记为 T2 要求，已修正。）

### D6 裁判不致盲 + 前提纯度反注入
- 裁判输入 = 材料（前提）+ 各题 + 答案；user_premise 语义已有
  （episode_semantic_verifier.py:389-410），不另造。
- 新增负向检查「premise purity」：B=material_only 时答案不得引用材料外市场数据
  （真实日期行情/真实板块涨跌幅），与 D4 形成纵深。

### D7 记忆边界（OQ2 解）
- B=material_only → **抑制跨会话记忆**（memory_lookup 不注入）；但**显式引用的
  同题链上下文保留**——T3 在同一全新会话里引用上一轮 T2 的材料与原答，属于用户
  当面给的前提，不是外部记忆。A=fictional × B=full 时 memory 不受影响。

## 4. 设计级验收断言（v2 修正版）

- A1：T2 拆分 = 材料 + 8 条 sub_questions（Q1–Q8 全在）。
- A2：T3 拆分 = 材料 + 各题；A 轴 fictional × B 轴 material_only 被正确检出。
- A3：T2/T3 重跑时市场数据类工具授权为空、检索计划零市场 provider；答案不含
  09-11 真实板块行情（用失败样本中出现过的真实板块名做缺席断言）。
- A4：T2 答案 8 节齐全，**无 memo 要求**；T3 答案各节齐全 + 其 Q8 memo ≤200 字。
- A5：无约束纯贴研报行为不变（检索保留、kol_review 默认目标不变）——回归锁。
- A6：S1/N1 回归锁保持绿（192 字 quick_fact、802 字 disclosure 变体）。
- A7（新）：**验收链路形状**——另起全新会话，turn1=T2（带原材料），turn2=T3
  （带原材料、自然引用上一轮），验证同题链上下文保留（D7）与两轮均满足 A1–A4；
  不复用含失败残桩的 conv_47243ada…。
- A8（新）：`假设 X，结合当前行情` 类题：前提不被证伪且真实检索仍发生
  （两轴模型的正向用例，防 D2 过度抑制）。

## 5. OQ 结论（按复审意见落地）

- OQ1 → 默认省略序列化（task_frame.py:157 模式），旧哈希全不变。
- OQ2 → D7：material_only 禁跨会话记忆、保留显式同题链上下文。
- OQ3 → D5：单 Episode 逐题输出槽。

## 6. 实施拆分（设计过审后）

- P1：D1 拆分识别器 + 测试（纯函数，风险最低）
- P2：D2 两轴检测 + TaskFrame 载体（省略序列化）+ D3 投影 + 测试
- P3：D4 三层抑制（检索计划/硬触发让路/capabilities 清算）+ D6 前提纯度 + 测试
- P4：D5 逐题槽 + memo 槽 + 结构预检 + 测试
- P5：按 A7 链路全新会话重跑 + A1–A8 验收 → 才谈正式 PK 就绪

## 7. 风险与回滚

- 编号题组误报：双条件（题组在材料块外 + ≥2 条疑问形态）+ 反例回归。
- 约束词误伤：两轴模型把「假设」从数据轴上摘开，误伤面从「全局不检索」缩到
  「前提不被证伪」，代价可控（A8 锁正向用例）。
- 硬触发让路的越权风险：仅限 B=material_only 且约束短语显式命中，配审计日志。
- 每层独立开关点（拆分/两轴/授权/合同四层分离），逐层可回滚。
