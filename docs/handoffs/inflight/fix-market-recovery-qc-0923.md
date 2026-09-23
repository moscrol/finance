# 行情恢复 QC 修复

## 这个分支做什么
修 PR #861/#871 的 F1 夜跑接线/日志、F2 假覆盖率、F3 过期覆盖。新快照：`docs/handoffs/2026-09-23-market-recovery-full-gate.md`。

## 当前状态
代码已提交 `4fa70046f`、`981c4d629`；本轮仅补证据。整体 HOLD：完整 Python 门已绿，独审与业务决策未关。未合并、推送、部署、数据库 staging、换库或生产写入。测试/审查进程已退出。

## 决策与被否方案
- local 先同步同花顺，再在 stock-daily 串行兜底；失败重试后停下游，尝试必须落 runlog。
- F2 仅显式 recovery_members 路径逐一核 canonical bar，不擅自改默认分母。
- F3 在事务内重验目标日与 literal True 覆盖授权；否了只验 build 状态与自动清残留。
- 全量绿不代签独审；独审无报告/通道超时记 BLOCKED，不换模型硬顶。

## 未验证 / 已知边界
K3 explore 360.91 秒触帽，无探针/正式报告；重试前预检45秒超时，execute/report/阳性对照均未运行。未知停牌、供应商全集、mootdx 部分 flush、完整输入指纹/任意并发仍未认证。恢复 CLI 参数未擅自启用。真实 nightly/生产恢复未验。

## 下一步
1. 独审需从 explore 重开；不能拿作者测试替代签字。
2. 用户确认 `docs/handoffs/2026-09-22-market-recovery-decision-page.md` 的五问、三合同、5553/5565 范围、53只除权/送转处置。
3. 如合同带来改动，最新 main 新组合重跑完整门禁；合并/推送/生产写入另需明确授权。历史已授权换库不抹掉。

## 已验证
- main `5f35da17`，干净 /Users 预览 `d3abd6703368`：14798P/85S/2XFAIL，0F/0E，runner rc0，收集14885全部对账；收据身份与全范围校验 rc0，基座漂移0。
- Ruff/消费注册表/技能注册表通过；三仓在场，解析61份（本仓39+知识库22）。webapp零diff，前端/E2E不适用本补丁。
- 封存原件离线审计 rc0，新产物与旧件同 SHA `abfa67b2...10fdae8`，production_ready仍false，不是生产回读。
- 完整证据：`docs/verification/2026-09-23-market-recovery-full-gate/`。旧429P/1S与较早2631P/63S/2F原样保留，不拼读数。

## 踩过的坑
/tmp 会被沙箱 minimal 读权限覆盖；测试树用 /Users。收据只认证 d3abd670，不自动认证后续文档提交或合并tip。HTTP200只证明当时最小载荷可用。复用现有 runner/审计/收据工具，未另造通用件。
