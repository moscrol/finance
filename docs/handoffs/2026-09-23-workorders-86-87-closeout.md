# #86/#87 候选收口快照

## 背景

本轮在隔离工作树把 #846/#847 两个候选前向到 `gitea/main@626d8a508`，保留主检出和 KB 主树的既有改动。代码候选 head 是 `6f14ed215184d5c97fae3c03513468c6c9ee9cd4`，尚未 push、合并或部署。

## 发现顺序与决策

1. 原 #847 验收器对 `briefing_hit_rps5_pct=None` 跳过值校验。独立构造正向完整标签集后确认：把来源 NULL 换成零会被旧逻辑接受；因此补为所有七个字段精确匹配，NULL 不等价于零。
2. 原验收器只看 teaching briefing 对象的聚合 `recorded_at`。构造一个早写标签和其余晚写标签后确认早写行可被 max 时间掩盖；因此逐个校验原始 `computed_at >= source recorded_at` 的日期下界。因为生产 source 是日期级 recorded_at，这不虚构同日盘中顺序。
3. 使用生产 schema 和真实 `slice_river` 做合成探针，确认 PASS、NULL/零 FAIL、早写 FAIL、行情日历不足 BLOCKED 且 labels DB 不变。没有把 ordinary river 升格成全历史冻结。
4. 新 head 上定向作者测试 24 + 14 通过。最终全量 Python 叶 14675 passed / 85 skipped / 2 xfailed / 0 failed，`--require-full-scope` 通过；前端六步与 registry 五项也全部 exit 0。
5. #87 K3 bridge 绑定业务代码 head 跑一次，28 请求后 1080 秒无模型错误但无正式 REPORT/verdict；按合同 BLOCKED，不伪造独立批准。
6. #86 另跑独立 K3：11 请求、无模型错误、报告与 verdict 齐全，限定离线 PASS；P3 非原子 rsync 风险确认是基线已有。只读调查 `~/.local/bin` 与 LaunchAgents 未发现部署脚本副本，不替换启动器。

## 被否方案

- 不按旧审查者的“早于来源也应 PASS”意见放宽日期门：那会违背 source -> label 的写成日下界契约。
- 不用对象聚合时间代替逐行 computed_at：max 聚合会掩盖部分回填。
- 不重跑 live、不造行情、不写 IMA：#61 是独立前置，当前 market calendar 不足时应 BLOCKED。
- 不把半合 KB/finance 当原子写入问题：脚本只读，半合最多 FAIL/BLOCKED；但两者输入版本要按耦合说明合入。

## 当前证据

定向收据、四叶工程门禁和合成探针索引：`docs/verification/2026-09-23-briefing-k3-r2/README.md`；树外收据/日志在 `/Users/a77/.finance-runtime/test-receipts/workorders-86-87-*`。#87 K3 原始执行：`/Users/a77/.finance-runtime/reviews/briefing-k3-r2-20260923/`；#86 K3 原始执行：`/Users/a77/.finance-runtime/reviews/deploy-help-k3-r2-20260923/`。候选 worktree clean，merge-tree clean。#87 K3 仍 BLOCKED，live 仍等 #61；用户确认前保持 WIP。
