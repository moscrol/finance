# feat/e2-material-contract-design：E2 材料题边界设计（设计稿待评审，未实现）

## 这个分支做什么
QC E2（P1，正式 PK 前置）的设计任务。按复审边界「设计/实现严格拆开」：本分支只产出
设计稿 + 失败样本固化，**不动 split_user_message 一行**。

## 已落盘
- 设计稿：`docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok/E2-DESIGN-material-contract-2026-09-13.md`
  ——数据流四个缺陷点、设计决策 D1–D6、验收断言 A1–A6、开放问题 OQ1–OQ3、实施拆分 P1–P5。
- 失败样本固化：同目录 `e2-evidence/`（T2/T3 关键工件 + QC 证据包，MANIFEST.json 21 项带 SHA-256）。

## 状态：v1 被 QC 复审返修（docs/qc-l2-e2-merge-0913@3af70caa），v2 已按四条意见重写
- ①证据落错树：MANIFEST/qc-pack 曾误落主检出树（cp 时 cwd 被重置），已搬回本分支；
- ②抑制只关 retrieval_planner → v2 改三层落点（检索计划/硬触发让路/capabilities 清算），
  全部复用既有先例（turn_controller:780/:794、episode_protocol:165）；
- ③「不联网/假设/只依据」不等同 → v2 改两轴模型（A 前提真实性 × B 数据范围）；
- ④memo 归 T3 Q8 不归 T2；T3 验收在全新会话 T2→T3 链路上（A7）。
- OQ 全部按复审意见落地：OQ1 默认省略序列化（task_frame.py:157 模式，旧哈希不变）；
  OQ2 material_only 禁跨会话记忆、保留显式同题链上下文；OQ3 单 Episode 逐题槽。

## 待评审：v2 设计稿（同路径，已覆盖 v1）

## 下一步（设计过审后）
P1 拆分识别器 → P2 约束检测+契约投影 → P3 检索抑制+前提纯度 → P4 逐题交付+memo 槽
→ P5 T2/T3 全新会话重跑 + A1–A6 验收。每阶段独立 feature flag 级开关、可回滚。

## 不要做
- 设计过审前不实现任何一层。
- 不在主检出树（共享脏树 b4a35fa2）跑 CI/下结论。
- 不在 E2 修复+重验前宣称材料题就绪或启动正式 PK。
