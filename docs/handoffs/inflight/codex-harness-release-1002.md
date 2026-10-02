## 这个分支做什么

把已验证的 harness 工程、证据与会话状态改进合成可审查的发布候选；保留模型决定任务和工具的空间。

## 决策与被否方案

- 合入 PR8、PR10、PR11–14、PR15；否掉 20 号模型档位硬语义政策，因它把弱模型继续锁进补丁车道。
- 保留身份、权限、预算、证据版本、错误反馈；否掉 11/16/17/19 语义路由、A7、数字字段候选和工具差分分支，因迁移收益未证。
- 把 10/1 错标快照修成一次性派生数据修复；不把它冒充代码部署，代码仍需交易日三态保护。
- 保持 evidence_read 默认关闭、显式能力授权；不把补读改成固定流水线。完整取舍见 `docs/handoffs/2026-10-02-harness-release-scope.md` 与 `docs/verification/2026-10-02-harness-release-disposition.md`。

## 当前状态

- 分支 `codex/harness-release-1002`，HEAD `cf17788fa523b24b59405be66b6272ea560c623c`；源码干净，发布/交接文档仍未提交。
- 四次 no-ff 合流已完成；证据补读覆盖修复尚未落地。实现与审查子任务因配额中止，未改代码。
- 生产代码仍为干净 detached 版本 `2c394978…`；一次性快照修复后 readiness/health=200，但这不是代码发布。

## 已验证

- 集成 focused 收据：970 passed、1 existing xfail、0 failed/error/skipped；改动 Python 的 Ruff 通过，收据已核对 revision/collection。
- Gitea 无 push mirror，GitHub 推送不会被反向覆盖。快照修复 receipt 记录 served=2026-09-30、DB unchanged=true。

## 未验证 / 已知边界

- 未跑最终全量 Python、前端、E2E、registry、GitHub Actions；未跑真实模型六条验收，也未证明 2×2/留出题净收益。
- 休市日交易日保护代码未写；证据补读重读记账仍有已知回归。生产代码尚未切换到此分支。

## 下一步

先修证据覆盖并按“规格→质量”审查；再加交易日三态快照保护。用最终 SHA 跑等价 CI 和真实多轮验收，收据绿后开 GitHub PR，待保护检查与用户确认再合入/切 detached 生产，随后做健康检查和收尾交接。

## 踩过的坑

- `deploy_workbench_runtime.sh` 拒绝 Git detached snapshot，不能当部署器；不要把 focused 收据写成全量绿。
- `latest` 快照只允许单调前进，历史错标必须先核对 `trading_day_verdict` 再原子修复；未知日期应 fail closed。
- 不提交凭据、原始用户运行数据或一次性 `/tmp` 实验原件；不删枝、吊销 token、写预测台账，除非另有明确授权。
