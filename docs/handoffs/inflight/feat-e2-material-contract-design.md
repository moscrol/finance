# feat/e2-material-contract-design：E2 材料题边界设计（v3 待评审，未实现）

## 这个分支做什么
QC E2（P1，正式 PK 前置）的设计任务。设计/实现严格拆开：本分支只产设计稿 +
失败样本固化，**不动 split_user_message 一行**。

## 状态：v3 已按 QC 复审（commit 1f91343a）六条意见返修
1. 授权收口移到**合同冻结点**：过滤作用于 `_authorized_capabilities`（:244-261，会
   无条件重加 finance_query/evidence_search，:216/:256）与 mandatory 回补（:639-644）
   之后；开场预取（episode_tools.py:660）对 material_only 短路；预取/补检/子研究/恢复
   共用同一冻结授权；dispatch 兜底拒绝模型主动请求（A9 验收钩子）。
2. 合同冲突（missing_evidence: evidence_boundary 已复现）：「结论仅在材料前提内成立」
   定性为前提域声明，绑定材料本身（basis=user_premise），不索外部证据；裁判不关闭，
   改验「声明存在+内容句不越域」。非虚构 material_only 计算题同法（A10）。
3. T3 跨轮继承：会话级约束上下文，续轮标记+无新短语→继承；显式放宽→覆盖；换题→
   复位。验收用原始 T3 文本（不重贴禁令）。约束只在用户指令区识别。
4. 新增并行字段 premise_marks（authenticity/source_turn/scope，默认省略旧哈希不变）；
   不以 user_premises 非空判 fictional，旧字段行为不变。
5. MANIFEST v2：原件哈希与仓内副本（路径/大小/哈希/HOME→~ 变换）分开登记，
   14 in-repo + 7 external-only，QC 复核的 21 项原件哈希全匹配。
6. 逐题交付改稳定 question_id→槽→正文一一对应，遗漏/重复/明确缺口三态分别校验；
   纯度按来源绑定校验，板块名黑名单降级为调试信号；题组识别允许空行分隔。

## 已获认可、不变的决定
两轴模型（A 前提真实性 × B 数据范围）、单 Episode 逐题槽、memo 归 T3 Q8、
全新会话 T2→T3 验收链路。

## 下一步（v3 过审后）
P1 题组识别 → P2 载体+投影 → P3 冻结点收口 → P4 逐题槽三态 → P5 跨轮继承
→ P6 A1–A10 验收（全新会话、原始文本）。

## 另一分支状态
fix/l2-pct-chg-backfill-0913 @ 917a0e50：复审通过 + 门禁齐（9554/0 + 前端 76 +
E2E 15 + lint/typecheck/build），等用户「合」。QC 口径提醒：该 E2E 是真实浏览器+
隔离测试服务/夹具数据，符合合并门禁，但**不是**真实模型答案质量验收，不能用来
证明材料题已修好。

## 不要做
- 设计过审前不实现任何一层；不宣称材料题就绪；不动正式 PK。
- 不在主检出树（共享脏树 b4a35fa2）跑 CI/下结论。
