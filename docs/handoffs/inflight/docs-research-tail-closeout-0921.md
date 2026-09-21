# 研究尾单前向整合协调 · 2026-09-21

## 这个分支做什么
封存#797/#798/#800前向候选、#831独立小片与接替关系；只文档，不合main/部署。

## 决策与被否方案
- #831先行、三个领域分别堆叠；否三枝混包，避免旧绿代签新组合。
- io来源用schema v3、缺来源unknown；否删字段/猜local，防隐式扩权。
- 精确publication与writer收尾分验；否终态即完成，防迟到覆盖追问。
- 收据正式修复沿#814；c35停止为诊断，否维护第二套。
- 展开：`../2026-09-21-research-tail-forward-integration.md`。

## 当前状态
源码均已推且保持干净：#831 ea5c3a946、#833 7edfe24e7、#834 cb16cd463、#835 d82cb16b5。后三者直接基于#831，主干基座f783f19c8，不含后来#830/f2c3e9e1。
#831独立报告Spec/Quality PASS，根QC有限接受；一个session双节，非两位审核者。
三领域独立审均at capacity→exit1/无报告，BLOCKED_PROVIDER_CAPACITY；所有本轮后台已结束，不等候旧PID、不自动重开。旧#797/798/800有接替评论、不关闭。
#829仅孤儿片保全；#832/#814/#817/夜跑/归档保持原归属，未接管。

## 未验证 / 已知边界
新main及三领域联合树未验；历史原四题、财务R6/R3自然not_passed不翻；runtime不是跨进程driver/lease/未知效果对账/exactly-once。没有合main/8792部署/夜跑装机/生产回填/删树授权。

## 下一步
先读封档README及domain-review-operator-qc；另确认有界订阅审核恢复方式，再各枝补独立审。形成新组合后重跑实际组合，不能拼绿收据。
本轮交接集中本docs枝，源码树未加文档以保固定身份；用git show本枝读对应inflight。

## 踩过的坑
旧包装器原rc1保留，pytest准确收据exit0不互相替代；不用global latest。c35全量主动SIGINT，收据exit2、包装器rc4，不称全量绿。审核报告亦须核原事件：#831强限额/挂起Timer来自正式回归重跑，独立probe不单独证明；财务首/usr/bin/timeout不存在，原输出已从events恢复。

## 已验证
作者四候选全叶齐备：Python12444/12631/12870/13305P，各87S/2X；前端110/110/110/118P，各E2E34P2S，Ruff/四registry/crosswalk0（既有98警告）。#831独立105P1S；领域局部runtime315P、财务240P不代终审。
证据：`docs/verification/2026-09-21-research-tail-forward/`两包，原件`~/.finance-runtime/reviews/research-tail-integration-20260921/`。
