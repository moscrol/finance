# #834 运行时证据前向整合

## 这个分支做什么
整合#798/runtime-contracts，保主干io来源、上一轮证据与delivery_pending/SSE尾部保护。

## 决策与被否方案
schema v3严格存io_effect；否删新字段/默认local_read，来源参与权限不可猜。v1/v2线格式和摘要不改、缺来源unknown；同hash展示不许改来源。
可信旧原件在首模型调用前保存，不继承旧supports/coverage；否把“恢复证据”当“继承完成”。详见`../2026-09-21-research-tail-forward-integration.md`。

## 当前状态
WIP #834已推cb16cd463db5c19b3187a5137009791082874653，源码clean；直接基座ea5c3a946（#831），main基座f783f19c8。旧#798接替评论5360、不关闭。
独立sol审六模块315P后10:41:23Z因at capacity结束exit1，无报告/独立probe，首尾净树；BLOCKED_PROVIDER_CAPACITY，不是运行中、不自动重开。
交接在docs/research-tail-closeout-0921，源码树保持固定身份。

## 未验证 / 已知边界
新v3及组合未获独立签字，旧v2审核不可移签。schema摘要非用户/代码签名；跨进程driver、单写者lease、未知效果对账/exactly-once未验。不签后来main#830或财务/历史联合树；未合main/部署/生产操作。

## 下一步
先读runtime-sol-review原事件/操作员裁决，明确单次审核恢复方式再补来源伪造、旧版兼容、保存失败的独立消费者反例。若叠入新main或其他领域，验实际新组合。

## 踩过的坑
旧白名单遇AgentEvidence.io_effect会fail closed，不能删除来源绕过。改动树590P不签父HEAD。
原包装器rc1与pytest收据exit0分别记，显式回放不是重跑；不用global latest/无效目录。正式门禁修复沿#814，c35停为诊断。

## 已验证
固定作者12870P/87S/2X，Ruff/四registry/crosswalk0；前端110P、E2E34P2S，六步0且首尾净树。准确收据20260921T092044Z-cb16cd46.json。独立局部315P不代终审。
封档：`docs/verification/2026-09-21-research-tail-forward/`两包，原件`~/.finance-runtime/reviews/research-tail-integration-20260921/`。
