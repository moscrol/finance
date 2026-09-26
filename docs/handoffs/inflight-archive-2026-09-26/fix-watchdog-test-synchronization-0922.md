# Watchdog 测试同步修复（在途）

## 这个分支做什么
接替 main `e82717d9a7c3dfa811a4538bd44985b61258355a` 的唯一 watchdog 全量红灯，只修测试时序隔离，不改 runtime、不部署。

## 决策与被否方案
- 选局部 `ResearchDeadline` 时钟 + 真实线程/Event；否了把业务预算从 0.2s 调大，因为那会掩盖预算耗尽路径。
- 将“worker 已启动后超时”与“前置编排已耗尽预算”拆成两条测试；否了继续断言 worker 必须启动，因为该断言不符合合法早退路径。
- 0.8s 只量“到期事件→watchdog 返回”；否了量整轮 `run_turn`，因为前置处理和落盘不属于 watchdog 返回合同。
- 日期背景与负向探针记录：`docs/handoffs/2026-09-22-watchdog-test-synchronization.md`。

## 当前状态
- 已提交并推送 `eb23f84015a0d48da996b98af1d906a6b6ce9d0f`，分支 `fix/watchdog-test-synchronization-0922`，工作树应保持干净。
- Gitea 分支已存在；两次创建 PR API 请求客户端超时，最终回读 open/all PR 均没有该 head，**尚无 PR 编号**。不要把分支推送误认为 PR 已创建。
- 生产保持 recovery `adcda94b5e40`，未部署、未重启；#846 仍 WIP，未解除保护。

## 已验证
- 指定解释器 + `env -i` + `umask 022`：编排模块与 `test_research_contract.py` 共 `107 passed`；收据 `/Users/a77/.finance-runtime/test-receipts/20260921T164752Z-eb23f840.json`，完整 SHA/干净/基座漂移校验 exit 0。
- 全仓 Ruff exit 0；`git merge-tree --write-tree e82717d9... eb23f840...` clean。
- 正常版、前置/线程延迟 0.25s 对照均通过；六种进程内撤保护各按预期产生 1F/1P，证据 `/Users/a77/.finance-runtime/reviews/watchdog-sync-20260922/committed-controls/execution.json`。

## 未验证 / 已知边界
- 未在该 revision 跑完整 Python/前端/registry 全叶门禁；107P 不能覆盖 main 原全量 `12509P/1F`。
- 延迟复现证明 `worker_started=false` 失败形状可由前置预算耗尽触发，不证明上一轮全量失败的唯一因果；原丢失 trace 不补造。
- 负向探针是进程内 mutation，不是生产源码收据；并发旧探针的秒级原生收据曾同名覆盖，不能引用旧共享收据。
- 磁盘曾低至约 4.5 GiB，勿在未检查空间前启动全仓门禁或批量清理。

## 下一步
1. 回读/恢复 Gitea PR 创建；成功后保持 WIP，贴证据评论。
2. 独立验收固定 base/head，确认测试修改只覆盖目标红灯。
3. 固定合流候选跑全叶门禁，再请求合并授权；实际 merge commit 另验，不移签。
4. 在根因未确认前不发布、不重启 8792。

## 踩过的坑
- 原测试在 watchdog 入口前自然耗时超过 0.2s，直接断言 worker 启动会把合法 early-return 当成生产故障。
- 只撤进度外层保护仍会绿，必须同时撤 `record_progress` 的两层检查；本轮已用顺序、唯一目录的 mutation runner 验证。
