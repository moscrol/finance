# R6×RAG读取组合｜2026-09-19

## 这个分支做什么
在R6拒错/交付/发布组合上接RAG分帧，保代码身份及金融partial债。

## 决策与被否方案
- 仅接20939读取片，a31/49fd已在；否整枝保稿/runtime与覆盖旧worker。
- 非阻塞批读＋显式分帧；否加超时/sleep。先排缓存、整行解码、deadline不续。
- 保精确ID/代码身份/私有pycache换代；published不升金融partial。
- 首发布基线超时保留，后串行绿不证明首红原因/已修。
理由：`../2026-09-19-8792-financial-rag-integration.md`。

## 当前状态
树`~/fwp-wt-8792-financial-r6-repair`，业务d8d6196b已提交（父文档f70，前业务d06）。实现与封存收尾，检查进程已退；不是无保留全绿/可合入。旧R6/R3仍0/4 not_passed；新live0/独立QC未跑，未push/合main/部署/切8792。
包`docs/verification/2026-09-19-8792-financial-rag-integration/`；原件`~/.finance-runtime/reviews/8792-financial-rag-integration-20260919/`。文档tip不重签业务成绩。

## 未验证 / 已知边界
- 发布首并发baseline180秒超时，runner未存stdout/XML/栈；complete=false/runs=[]不等于0执行。后单次诊断150P与一次限定串行八组通过不翻案，首因未知。
- 宿主registry红/all_passed=false不改；金融d8＋KB91725ea9＋site9f60bef五项0。不scan倒退登记。
- F2真实报告取回、自然补查复算/根预算全链/跨进程恢复未签；永久缺最终事件仍pending。RAG排锁/写请求预算、消息大小策略不在本片。
- 邻枝封存只读：答案ce673a9f/runtime a7f5cc06/data b4757709均clean；新片未审/移入，不借成绩。

## 下一步
1. 要合入准入先补runner持久日志/超时现场证据，另冻SHA做归因；不加时限或重试挑绿，旧现场缺失不能补造。
2. 保稿/证据诊断/runtime另审最小提交；扩大组合另冻SHA/跨仓输入，勿重复接a31/49fd/20939。
3. 新live、独立QC、push、合main、部署分别确认，旧样本不重发挑绿。

## 踩过的坑
同SHA不保证覆盖，按pytest.log精确收据指针核执行数。JUnit failure≠AssertionError；DID NOT RAISE与异常型另列。原日志不改，展示转换双hash；后续绿不解释前次超时。

## 已验证
d8干净：12220P/86S/2X、Ruff0、前端115P/E2E34P2S；收据20260918T181016Z-d8d6196b八项过。RAG9组6含断言/2期待异常未抛/1仅异常；发布串行8组及原6/13/13/35组红→恢复绿，分母不加。RAG正反探针exit0/1；R6原件12hash不变/连接0/登记0/0/0/1。临时finance/site/诊断树已移除，8931/8934无listener。工具包3858a6c未合，vault ae4f196c/7a1f53af；lint仍20E/17W，图谱0非质量认证。
