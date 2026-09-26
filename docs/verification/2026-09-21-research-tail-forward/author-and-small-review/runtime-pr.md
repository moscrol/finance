## 目标与固定身份

前向整合 #798 与 runtime-contracts 父实现，保主干 delivery_pending/SSE尾部排空/可信上一轮证据初始化。
- 候选 `cb16cd463db5c19b3187a5137009791082874653`
- 直接基座 `ea5c3a94618a15e37f914c8b1a13e271875e4337`（#831，堆叠依赖）
- 主干基座 `f783f19c8a01fbe8d0ed70d851df7ed14598c051`

## 实质接缝

旧快照白名单拒绝主干新增的 AgentEvidence.io_effect。升级schema v3，严格保存 local_read / external_or_mixed / unknown，展示与原件须一致；v1/v2线格式/摘要兼容，旧缺来源只恢复unknown，新来源不得静默降级旧版。可信上一轮原件在首次模型调用前保存，不继承旧supports/coverage。不能删除来源字段或猜local_read来绕过保存失败。

## 已验（作者工程）

固定干净全量12870P/87S/2X/0F，Ruff、四项registry、crosswalk通过。前端六步通过：110单测、34 E2E/2跳过；首尾身份稳定、dirty=false。提交前接缝590P另记，不签父HEAD。

`run_main_gate.sh`原exit1保留：FWP_TEST_RECEIPT_DIR只被包装器读取、conftest未使用，报错文本中文括号又触发Bash变量解析错误。精确pytest收据exit0并经条件校验通过；不用global latest。包装器独立在fix/gate-receipt-selection-0921修，不改变本候选。

证据根 `~/.finance-runtime/reviews/research-tail-integration-20260921/`：runtime-resolution.json、runtime-python-receipt.json、runtime-receipt-check.txt、runtime-main-gate.log、runtime-frontend-gates/frontend.json、runtime-identity-{before,after}.txt。原全量收据 `~/.finance-runtime/test-receipts/20260921T092044Z-cb16cd46.json`。

## 未完成

- WIP，新组合独立审核尚缺；不能移签旧v2/#798审核。当前通道工具/模型容量阻塞不是PASS。
- 不含后来main#830（f2c3e9e1a24f），不签它或三领域联合组合。
- schema摘要不是用户/代码签名；不是跨进程恢复driver、单写者lease、未知效果对账或exactly-once闭环。
- 未签真实模型质量，未合main、未部署8792、未生产回填/删树；这些须另行确认。
