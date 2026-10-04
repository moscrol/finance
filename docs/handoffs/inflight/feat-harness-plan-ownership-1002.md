## 这个分支做什么

P1a：允许撤回模型自拟 PLAN，保真可选输出身份；不是完整在线语义修订。
树 `~/fwp-wt-harness-plan-ownership-1002`；分支 `feat/harness-plan-ownership-1002`。

## 决策与被否方案

| 选定 | 否决/延期 | 理由 |
|---|---|---|
| 显式已接受基线+撤回原因 | legacy热迁移、协议降级 | 可拒陈旧提案，保旧档原义 |
| 计划与用户合同分离 | 删必需项、改hash、重建预算 | 可改研究意图，不改用户义务及资源 |
| 无效PLAN闭工具回执，再失败收口 | 第二次派发、无限纠错 | 原一次格式提示额度不扩 |
| required贯穿实际消费者 | 补词表、放宽正文门 | 修身份丢失，不伪造语义正确 |

背景/完整取舍见 `../2026-10-02-harness-plan-ownership.md`。

## 当前状态

基于GitHub main `3a2718c6c`；产品已提交 `12555e9ad`，补legacy flush正例后验收pin `7513d476b`。本地候选，未push/合并/部署。P1b尚未实施，原输出身份候选的正常红灯不由本片解除。

## 已验证

干净7513d476b：相关33文件1045P/1既有SDK opt-in跳过/1弃用warning；Ruff/收据校验通过。9变异均红→绿，前后核心321P，临时树已清。新模型请求0。
证据 `~/.finance-runtime/reviews/harness-plan-ownership-20261002/`：`frozen-targeted-receipt.json`、`mutations-final/results.json`；范围见 `../../verification/2026-10-02-harness-plan-ownership.md`。

## 未验证 / 已知边界

SDK loop无PLAN接纳点；上游建议来源未迁移。JSONL事件往返不等于跨进程恢复执行器。未跑全仓Python/前端/E2E/Actions、独立审查、新PLAN完整HTTP公开交付或自然金融质量；既有Workbench integration不能替签。分支协调器回归用stub。

## 下一步

与v0.1 owner对齐P1b：建议来源/有效必需性、题型主体时间窗解释revision、根请求与合同/存储版本/恢复分离、旧词面门退出表及全入口覆盖。发布前按最终组合SHA补门禁与独立验收。R19封存、R17不重跑、R18不接管、正式240格未准入。

## 踩过的坑

撤回不抹证据/用量/已派分支；不可重建context拿预算。deadline flush拒未接纳新协议，合法legacy工具仍兼容。事件payload先去at/hash再送严格PLAN parser。测试只用锁定workbench解释器（报告有路径）；中间dirty绿数不替签。Memory会auto-sync，修改前先钉基线，后台同步≠人工push。
