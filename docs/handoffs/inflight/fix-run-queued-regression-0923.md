# Workbench 发布测试隔离 · 2026-09-23

## 这个分支做什么

闭合 #883 暴露的 queued/completed 测试红项，只改测试，不改生产状态机。决策见 `docs/handoffs/2026-09-23-run-publication-test-isolation.md`。

## 决策与被否方案

- 屏障绑定本次提交的存储实例和 run_id；否决全类同名报告触发，避免其他 worker 误唤醒。
- 用固定执行顺序注入干扰；否决加 sleep/延长超时，后者会遮住身份错配。
- 游标校验只造已落盘 run；否决启动无关回答后任其跨用例收尾。
- 不改 shutdown/生产状态机：已有终态锁，未观察到状态回退。

## 当前状态

实现 `833f4448d` 与候选 `0e9b4f3b7` 已由 #883 组合候选承接，用户已授权合入具备条件的内容。当前合入与承接状态以 `docs/handoffs/inflight/docs-claim-scope-final-state-0923.md` 指向的本轮原件为准；生产未部署。旧 head 的完整绿收据不移签组合候选。

## 已验证

证据根 `~/.finance-runtime/reviews/run-queued-regression-20260923/`：旧屏障红对照 1P/1F（queued != completed），修后 3P，相关两个文件 144P；Ruff/提交前检查通过。最终候选门禁放 `gates/runner.log`、`gates/receipts/gate-*/pytest.json`、`gates/frontend/frontend.json` 与 registry 分项日志，必须核对精确 revision/clean/full scope 和退出码，不读共享 latest。

## 未验证 / 已知边界

原全量现场未记录触发屏障的 run_id，旧干扰任务的时间关联不是完整调用轨迹；本轮确定性复现证明测试隔离缺陷，不证明生产状态回退。#75 独审、#76 真实模型、claim-scope 接入和生产部署不属于本次验证。

## 下一步

跟随 #883 的组合候选门禁与授权回读；#885 若被承接关闭，先留 #883 指针，不伪称另有独立 merge commit。旧 `9a0227986` 红收据原样保留，不重复派修或启动独立模型验收。

## 踩过的坑

RunSupervisor.shutdown(wait=False) 不等待已运行 worker，测试类级 monkeypatch 会被旧 worker 看见。事件只认 report.json 会误认任务。通过实例级屏障和同型干扰回归修复；未新增通用工具。
