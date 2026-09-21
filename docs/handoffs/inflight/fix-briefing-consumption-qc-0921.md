# 晨汇消费修复

## 这个分支做什么
修IMA缺输入假成功，验证晨汇经教学旁路进入长河；不部署生产。

## 决策与被否方案
缺输入exit2，不泛改runner；只读行情+独立标签库，不覆盖共享库；缺行情BLOCKED，不造行。单端点失败不等于无审查入口，但部分测试不代签独立批准。展开见 `docs/handoffs/2026-09-22-briefing-k3-incomplete.md`。

## 当前状态
代码a7288f503；PR #847保持WIP，送审1dc45ff5e，KB #157送审05f1220ad。main仍e82717d9a，KB base=d0caf3114。本轮仅新增收据/交接，未合main、未部署；文档tip不冒称全量受测。
K3两新会话已结束：finance37请求/48工具，KB35请求/49工具，均429 credit_exhausted_5h，无REPORT/verdict。进程exit0不代表审查完成；qc-summary明记INCOMPLETE。无后台等待任务。

## 未验证 / 已知边界
独立Claude两次无结论，K3本次亦无最终结论，无独立PASS。生产绑定、官方事实、语义索引发布、线上自然问答未验。本轮未重查行情，既有09-18晨汇消费BLOCKED未解除。
普通切片trade_date_only，无冻结行情快照；只证晚写教学对象过滤。长河是市场汇总非全文。旧Python全量期间KB改日志号，投影未变但跨仓输入非完全冻结。

## 下一步
额度恢复后先核head/base与KB日志号，再明确新一轮有界补审，优先串行节省共享额度。补齐完整独立报告，用户确认后才可合入。正式main收据另跑；生产核代码/KB/标签绑定，补行情后以真实时刻重建再验。

## 踩过的坑
每条bash显式cd；KB测试显式FINANCE_WS。pi模型429可能exit0，必须查model_errors及完整报告；execution.complete只指采证结束。投影market_confirmed布尔值不等于教学聚合NULL。扫描日志号非原子预占。

## 已验证
旧合流338db9114：Python12520P/85S/2X、Ruff/注册表通过；前端110P，E2E34P/2S；KB e4cca9531全量529P。旧真实消费09-15 PASS、09-18 BLOCKED。
本轮K3部分证据及协调者复现：finance12P、KB11P、抽取1338行一致；七合成场景返回码符合预期。只证这些检查，不是独立批准；合成周六行非真实行情。首尾送审树不变。收据 `docs/verification/2026-09-22-briefing-k3/`。
