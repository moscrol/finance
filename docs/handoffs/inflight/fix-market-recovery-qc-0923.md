# 行情恢复 QC 修复

## 这个分支做什么
修 PR #861/#871 的 F1 接线/日志、F2 假覆盖/无效收盘价、F3 过期覆盖。最新快照：`docs/handoffs/2026-09-23-market-recovery-k3-resume.md`。

## 当前状态
业务提交 4fa70046f、981c4d629、3abb7a4d3；本轮仅封存 K3 续跑证据和交接。整体 HOLD：新候选全仓、独审、业务决策未闭合。未合并/推送/部署/数据库 staging/换库/写生产。本轮进程已退出、独占 candidate 检出已清理；验证引用保留，旧 d3 锁树未动。

## 决策与被否方案
- F1 同花顺先行、串行兜底、失败重试后停下游；尝试均落 runlog。
- F2 仅显式 recovery_members；缺 canonical 行或当日消费行 close 非有限/非正，在四张派生表写前拒绝；不删坏行凑分母。
- F3 事务内重验目标日与 literal True 授权。
- 否定「一次 45 秒超时等于 K3 不可用」；真实工具往返已通。HTTP 200/Pi exit 0 不等于交付完成。
- 不把作者测试冒充独审，不把旧全仓绿移签新候选。

## 未验证 / 已知边界
K3 explore 01 第4请求 CloudFront 504；01b 7次200但600秒无探针/终稿，分别记 PROVIDER_504 / SESSION_DEADLINE，不是 PASS。无独立探针、阳性对照、正式报告，execute/report未启动。
未知停牌、全集、53只公司行动、mootdx部分flush、完整指纹/任意并发未认证。收盘价门不认证其他字段/历史质量；恢复CLI、真实nightly与生产验收未闭合。

## 下一步
1. 独审先按F2/F1/F3拆小任务，把先写探针做成工具/阶段门；只加提示本轮无效，勿重复最小活性探针或无限重试。
2. 用户确认决策页五问、三合同、5553/5565范围与53只处置；生产5551不能写成严格齐备。
3. 最新main+修复候选补全仓门禁，核revision/scope/target；合并、推送、生产写入仍需授权。

## 已验证
- 组合45e752c，main bbd53487f，tree 3ea68688；本轮merge-tree复核一致、远程无漂移。两个独审会话候选干净且输入未变。
- 本轮13次请求：11次200（含未完成流）、2次504，正式会话工具16次成功，产品探针0。固定K3、无自动重试、未重启网关。
- 既有新候选 tests/ 2639P/62S 非全仓；24坏值用例修前全红/修后绿。旧d3全仓14798P/85S/2X仅认证旧revision。
- 证据：`docs/verification/2026-09-23-market-recovery-k3-resume/`；close-guard/full-gate旧证据保留。

## 踩过的坑
本轮证明通道可用，不证明独审完成。01返回exit0仍有模型504，01b的最后200流被预算打断。--require-full-scope只审过滤，target=tests仍不是全仓。验证引用：refs/verification/market-recovery-close-20260923。
