# 行情恢复 QC 续验

## 这个分支做什么
修复#871/#861的F1/F2/F3与FinanceQuery截止；工程叶子已绿，恢复整体仍HOLD。

## 决策与被否方案
| 选了什么 | 否了什么 / 理由 |
| --- | --- |
| 固定候选串行完整门禁 | 不用定向绿覆盖旧红，不放宽超时；六项旧失败根因未证 |
| GLM独立澄清原报告 | 不由作者改原文；静态代码和作者151P不增加独立覆盖 |
| 有界资源准入与观测 | worktree非资源隔离；不杀别人任务、不追main循环重跑 |
展开：`docs/handoffs/2026-09-23-market-recovery-suite.md`。

## 当前状态
代码仍f22cd22b6，本轮无产品改动。固定1de68567e740（tree de67ee72b9e，base c9dd71dfd）完成全部工程叶子；15:48 UTC收尾零漂移、两树净、执行进程/测试服务已退出。未push/合入/部署/写生产。证据入口`docs/verification/2026-09-23-market-recovery-suite/README.md`，179机器归档/180原件。此前5213完整4F与前端2F保留，不改判。

## 未验证 / 已知边界
F1真实CLI/subprocess/release/夜跑；F2默认daily、其他字段、并发、严格写前时序；F3真实build-then-stale、完整指纹、并发、部分写后回滚仍缺。旧F1/F2/F3独审只签50330cf；新截止独审仅签1de。main已有受托业务决策文档，不再说五问无人决定，但本会话没有真实恢复/换库/发布授权。

## 下一步
补上述隔离边界，工程绿不等于恢复准入；冻结原件空白使完整文档差异检查exit2，未改字节/加豁免。新代码或基座需重组候选重验，不移签本轮结果。原件在`~/.finance-runtime/reviews/market-recovery-qc-20260923/suite-followup/`，候选/ref和失败scratch保留。

## 踩过的坑
macOS comm截断导致漏数pytest，非UTF参数会解码失败；v2错误放行仅停本轮进程，98秒中断保留，v3解析7项自测通过。作者收集被目录metadata挡住，补该目录元数据后151P且内容仍拒读。核验v1猜错positive_control.xml，被断言拦住，实际positive.xml。一次性脚本未推广为通用隔离工具。

## 已验证
完整Python14911P/85S/2X、14998 collected、0F/0E；前端120P、E2E34P/2S，lint/typecheck/build和注册表五项绿；全范围收据校验exit0。GLM三阶段6请求全200，独立4P、1阳性对照检出、旧版2行为失败/2P，澄清PASS_WITH_LIMITS；作者151P另账。原截止测试本次JUnit0.032秒，不证明实时保证或旧红归因。旧候选RAG三文件诊断90P、52观测子进程退出，不累加到完整覆盖。
