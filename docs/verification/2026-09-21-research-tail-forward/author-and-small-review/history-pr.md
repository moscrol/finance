## 目标与固定身份

将 #783/#800 历史研究链前向移植到当前已测基座，保主干的新材料合同/上一轮复核/市场广度提示，不覆盖旧枝现场。
- 候选 `7edfe24e76afbd5c365fbf97dd2414847b086f88`
- 直接基座 `ea5c3a94618a15e37f914c8b1a13e271875e4337`（#831，堆叠依赖）
- 主干基座 `f783f19c8a01fbe8d0ed70d851df7ed14598c051`
- 来源 `fix/history-closeout-0920@e4675eab28d83378016874c5396634fff5ab95ba`

## 已验（作者工程，不是独立审）

固定干净候选：全量 pytest 12631P/87S/2X/0F，Ruff、四项 registry、crosswalk通过。前端六步通过（110单测、34 E2E/2跳过），首尾身份稳定且dirty=false。新增8接缝测试覆盖程序条件≠虚构依据、真假设、复核/历史续问同守读取上限、引用文本不授权。

原 `run_main_gate.sh` exit1 原样保留：无效 FWP_TEST_RECEIPT_DIR 导致查错目录，错误文本 `$LATEST（...` 在macOS Bash/UTF-8被识别为不存在的变量；不是pytest红。精确pytest收据exit0、校验通过，不挪用并发global latest。门禁包装器独立修复 `fix/gate-receipt-selection-0921`，不改冻结候选凑绿。

证据：`~/.finance-runtime/reviews/research-tail-integration-20260921/` 下 `history-resolution.json`、`history-python-receipt.json`、`history-receipt-check.txt`、`history-main-gate.log`、`history-frontend-gates/frontend.json`、`history-identity-{before,after}.txt`。原全量收据 `~/.finance-runtime/test-receipts/20260921T091040Z-7edfe24e.json`。

## 未完成与禁止外推

- WIP：尚缺新组合独立Spec/Quality；审核通道当前工具/模型容量阻塞，不视为PASS。
- 新main `f2c3e9e1a24f` 含#830，未移入本候选；本PR不是该新main或三领域联合树的验收。
- 历史原四题自然质量not_passed未推翻，本轮零重跑；不因此关闭#793/#794。
- 历史证据绑定孤儿片#829未包含，#809不改。
- 研究授权窗/信息截止/观察窗三分；助手旧答不授权，晚授权终点不抬信息截止。
- 用户尚未授权合main/8792部署/生产回填/删树。旧#800保留并补接替指针，不静默关闭。
