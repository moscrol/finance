## 目标与固定身份

接替 #797，将财务比例修复与其 R6/保稿/发布边界/研究交付/RAG 父实现前向整合，同时保留主干的新材料、股票代码、精确发布与 writer 收尾保护。旧枝现场不动。
- 候选：`d82cb16b5ef31d23339a1bef7084a0dcb8221e15`
- 直接基座：`ea5c3a94618a15e37f914c8b1a13e271875e4337`（#831，堆叠依赖）
- 主干基座：`f783f19c8a01fbe8d0ed70d851df7ed14598c051`
- 来源与逐路径解析身份：证据根 `financial-resolution.json`。不是只摘两个末端比例模块，也不是整枝覆盖 main。

## 接缝选择

- 财务坏差值、metric 补修债，与主干 unknown_stock_code / 日期与材料合同分区共存；引用编号排除不放松数字门。
- API / UI / SSE 共同守精确 publication 及 delivery_pending：事件已提交但 writer 未结束仍 pending，消息可见不等于 writer 结束或答案完整。
- 保留同会话追问的加载代际，旧轮迟到 trace 不抹新追问；测试按真实 message.complete → published run 顺序搭夹具，不降低生产门迁就旧测试。
- RAG 同时保主干 RSS 观察与旧线缓冲/abandoned/超时清理。无真实进程的测试替身隔离 RSS 采样，不删除生产保护。

## 已验（作者工程，非独立审核）

固定干净候选：全量 pytest **13305 passed / 87 skipped / 2 xfailed / 0 failed**（17 warnings，900.85秒）；Ruff、四项 registry、crosswalk 各 exit0，crosswalk 保留98条既有反向警告。前端安装/lint/typecheck/test/build/E2E 六步均0：**118单测，34 E2E通过/2跳过**；首尾同SHA、dirty=false、identity_stable=true。

精确全量收据：`~/.finance-runtime/test-receipts/20260921T095428Z-d82cb16b.json`，exit0、非绕过依赖门、Python3.12.13、依赖指纹3328bed61f3e21ea，条件校验已过。不是同SHA的零计数收据，不借并发global latest。

证据根：`~/.finance-runtime/reviews/research-tail-integration-20260921/`。详见 financial-pytest.log/.rc、financial-python-receipt.json、financial-receipt-check.txt、financial-frontend-gates/frontend.json、financial-identity-{before,after}.txt。首轮RAG替身/前端夹具/新接缝误分句失败原件均保留。

## WIP / 不可外推

- 新组合独立 Spec/Quality 另行执行；旧 #797 审核不能移签。
- 不含后来的 main #830（f2c3e9e1a24f），不签该新main或财务/历史/运行时联合树。
- 旧 R6/R3 整题自然质量仍0/4 not_passed；本轮离线接缝与脚本化发布测试不是新自然金融验收。
- 未合 main、未部署8792、未生产回填/夜跑装机/删树，均需用户另行确认。旧#797保留并补接替指针。
