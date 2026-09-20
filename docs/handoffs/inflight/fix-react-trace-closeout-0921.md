# ReAct trace 最小修复

## 这个分支做什么
只推进引用数量隔离、安全查询诊断、冻结参数进展记账三片；不是#790-#794全完成。

## 决策与被否方案
取最小提交，不整包合历史/保稿候选；诊断不作市场证据，不加预算；Mapping只在JSON投影复制，不用default=str。K3走既有订阅、OS只读沙箱，不新增付费外审。详见 `../2026-09-21-react-trace-closeout.md`。

## 当前状态
PR #809仍WIP。业务fe9a626d/b1345a7d/dda5895a已提交推送；本次文档封存随本交接提交。未合main/未部署，8792仍bf662e93。8856/8857测试服务已停。树 `~/fwp-wt-react-trace-closeout-0921`；runtime树与独立QC树保留固定dda5895a。

## 已验证
dda5895a干净全量11972P/85S/2X、Ruff、前端六步通过，E2E34P/2S，严格收据通过。K3单独会话Spec/Quality PASS，116P及3组自造探针；接手复跑同过，3处撤保护均红。封存 `docs/verification/2026-09-21-react-trace-closeout/`。

## 未验证 / 已知边界
registry check因kb/rag-query漂移仍红，基线同红，其他4项过。新真实run已交付但金融质量not_passed：删条件后留“满足两条”、ranking_intent=false、数值原件未绑定进核验视图。history_query错误后续查成功，不代签finance_query自然纠参。#791-#794未完成。文档SHA不继承业务SHA的全量结论。

## 下一步
先用新run剩余问题推进#793/#794与既有答案保留工作；解决registry归属后，在实际合流身份重验。合main/部署/新增付费外审须停，不因K3绿越权。

## 踩过的坑
K3首次鉴权失败0工具但CLI rc0，不算通过；原件保留。首红探针预期修正见事件，probes.log仍是首红。共享refs被其他并行分支更新，不能声称全局未变；候选/作者树未变。接手首个pytest漏TMPDIR在收集前失败，另留116P复跑。失败run汇总tool_calls=0不可信，新run8结果与10请求也要分账。外部原件根 `~/.finance-runtime/reviews/react-trace-closeout-0921/`。
