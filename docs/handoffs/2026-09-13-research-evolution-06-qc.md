# 研究进化06审查快照

2026-09-13，用户要求“审一下06”。固定候选4e95c20b、组合基底5f931258，创建独立审查树 `/Users/a77/fwp-wt-qc-research-evolution-06`。执行者树与主树其他改动未碰。

采用code-review双轴：规范轴审查事务/幂等/副作用，规格轴审查可达用户路径；主审通过独立API反例验证“旧判断＋无关run闭合”、时钟推进重试、生产证据接口和跨会话重放。

完整发现、证据、修复方向与收据条件：[review.md](/Users/a77/.finance-runtime/reviews/research-evolution-06-qc-20260913/review.md)。规范3项、规格10项，最高各P1。63项原测全绿，但不足以支撑engineering_complete。

不采用“需要真人才验得了”的解释：规格允许固定市场输入和合成事件，继续核查422、缺生产run观察器等均无需真人可证。真实有效性仍未验，不能从工程样本外推。

生产适配探针先尝试文件故障，实际先被River的cutoff>as_of默认拒绝捕获；遂追到此更早的接口分叉，并用真实适配器确认历史绑定读取退为invalid_slice_request。报告未沿用最初“损坏库会500”的猜测。

可迁移教训补入既有知识笔记 `gate-covers-only-its-return-value.md`；此轮探针作为审查收据保存，不擅自修改执行者实现或生产门禁。下一步由06执行者按S/R编号返修，再验完整用户路径与最终revision门禁。
