# feat/e2-material-contract-design：E2 材料题边界设计（设计稿待评审，未实现）

## 这个分支做什么
QC E2（P1，正式 PK 前置）的设计任务。按复审边界「设计/实现严格拆开」：本分支只产出
设计稿 + 失败样本固化，**不动 split_user_message 一行**。

## 已落盘
- 设计稿：`docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok/E2-DESIGN-material-contract-2026-09-13.md`
  ——数据流四个缺陷点、设计决策 D1–D6、验收断言 A1–A6、开放问题 OQ1–OQ3、实施拆分 P1–P5。
- 失败样本固化：同目录 `e2-evidence/`（T2/T3 关键工件 + QC 证据包，MANIFEST.json 21 项带 SHA-256）。

## 待评审拍板
- OQ1：premise_mode 进 TaskFrame 会改变 task_frame_hash 全量值——倾向「仅 != real_world
  时纳入哈希」，需确认无侧效应。
- OQ2：hypothetical 下 memory 是否一并抑制。
- OQ3：多题交付单 episode 多节（推荐）vs N 子 episode。

## 待用户确认的另一件事
`fix/l2-pct-chg-backfill-0913` @ 3458a7f0 复审已通过（三个 P2 闭环、9554 passed/0 failed、
收据 20260913T122812Z 复核一致），按会话规程**等用户明说「合」再合 main**。

## 下一步（设计过审后）
P1 拆分识别器 → P2 约束检测+契约投影 → P3 检索抑制+前提纯度 → P4 逐题交付+memo 槽
→ P5 T2/T3 全新会话重跑 + A1–A6 验收。每阶段独立 feature flag 级开关、可回滚。

## 不要做
- 设计过审前不实现任何一层。
- 不在主检出树（共享脏树 b4a35fa2）跑 CI/下结论。
- 不在 E2 修复+重验前宣称材料题就绪或启动正式 PK。
