# feat/pi-research-loop

## 这个分支做什么
兑现 8792 的 Pi 式研究行为；P0完成，P1组合离线完成，真实研究仍待前置放行。

## 决策与被否方案
复用 ContinuousAgentEpisode + FinanceResearchHarness；否掉第三条生产Loop、宿主Shell放权、重复改#868。只在本任务树组合候选，不改原owner受审树、不自动增模型额度。
背景/收据：`../2026-09-24-pi-research-p1-offline.md`；P0历史见`../2026-09-24-pi-research-p0.md`。合同：`docs/superpowers/specs/2026-09-24-pi-style-research-delivery-design.md`。

## 当前状态
独立树`~/fwp-wt-pi-research`。已组合#868候选f531d2d00add，合并提交d21a42efe；开关双态/深度复核测试提交59ab6e5cf。相对f531未改生产逻辑；仅本分支组合，未push/合main/部署。本交接为文档收尾，不改变受测代码。
旧交接ce2/166-209过期。最新核`~/.finance-runtime/reviews/pr868-glm-qc-20260924-2105/STATE.md`及batch/authorization：候选f531，spec有保留通过（C3/C7未验）；quality/explore路径漏/Users被拒，整批BLOCKED_NO_RETRY，累计213/244、余31，不足完整quality新轴39。原owner的工程结果不移签本组合；complete协议已修，不重复做。未分类探针不是产品缺陷。

## 已验证
研究链36场景：off/on、quick/deep、观察追查、空/异常换路、越权/假引用拒绝、一次复核后续查、耗尽/取消、变异对照。真实Runtime/Harness，替身模型/源，严格消息对账，零真实模型请求。
干净59ab6e5cf定向606P/3S/1X，收集610；ruff/提交钩子通过。收据校验通过：`~/.finance-runtime/test-receipts/20260924T134639Z-59ab6e5c-1160ab7b55b4.json`。范围为conformance、runtime/progress/adaptive/plan/semantic/harness七目标，不是全仓门禁。X为既有codex_headless修复收据缺席基线。

## 未验证 / 已知边界
未验真实HTTP门、真实来源/子研究、自然模型主动改向/反证/修稿与公开稿一致性。本组合未跑全仓/前端门禁或独审。未核8792活进程能力。文档HEAD不接收59ab测试收据。

## 下一步
1. 原owner确认#868最新状态、即时交付校验、新批预算/范围；不续1405/2105封存批。
2. 独审闭合后按#76逐行授权跑真实Workbench；候选若变，重验确切组合。
3. 完整门禁与用户确认后才合入/部署，不把P1离线当P2质量改善。

## 踩过的坑
无工具菜单可能是复核或预算收口，要读消息区分。授权快照会先截菜单变异；漏扣账测试要区分已授额度与hard cap。不要拿其他revision/旧交接的绿或额度给当前签字。
