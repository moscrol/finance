# river 接线：全量 CI 补写回归与测试合同修复

## 背景与发现顺序

接线的模型接口证据见[消费快照](2026-10-08-river-history-consumption.md)。其中 `7389549bc` 与文档版 `1a055b87` 的本机读数均是 1785P/44S 的关键词定向范围，不是全仓。

1. 先前阶段观察只看到 CI 运行中。回读终态后，`7389549bc` 的 Python 为 **9 failed / 20971 passed / 167 skipped / 2 xfailed**；`1a055b87` 也得到同一红集。两次都是 `test_fulfillment_repair_round.py` 的九例在 `answer_spec.candidate_facts` 报 `AttributeError`。
2. 在同一锁定 Python 3.12.13 环境复现：干净 main `82de3fb73` 的原补写测试 **16P**；干净 `1a055b87` 为 **9F/7P**。逐项 ID 与 CI 一致，不按失败数量猜归属。
3. 原补写测试把 `answer_spec` 设为裸 `object()`，并替换了旧 registry 函数。新共用接缝需要先读 `candidate_facts`，故更早撞上这个不符合类型合同的替身。核过 `AnswerSpec` 定义和 `conversation_orchestrator` 调用：生产参数是结构化对象，`candidate_facts` 默认空元组。没有据此证明整个生产入口已验。
4. 测试提交 `0154b06d1ed3adcdcc5236d6441155e44d4ab37c` 只改两个测试文件：原九例共用的夹具换成合法最小 `AnswerSpec`；消费测试增加两个补写实例。生产代码未改，原断言与重新过门禁要求保留。
5. 新例从离线 `answer_query` 生成真实 D10 `AnswerSpec`，经过实际 `repair_unfulfilled_answer` 和 registry 预算逻辑，到模型接口替身；不替换 registry。拥挤输入仍收到与原 context 逐字一致的完整镜头和限制，`claim_type=inference`；超预算则既不调模型，也不进入答案重判。正常补写只调一次，并把新文本及同一 spec 交给重判接口替身。
6. 撤掉必需行占位的进程内变异使两例均红：正常输入丢 D10，超预算错误地发出请求。还原后两文件 **51P**。首次变异量具错用了 `trylast`，变异发生在测试之后，所得 2P 无效，原件保留；改 `tryfirst` 后才有上述 2F 证据。

## 决策与被否方案

| 方案 | 评价 / 结果 |
|---|---|
| 合法最小 AnswerSpec + 真实 registry 路径测试 | 采用；测试替身保留数据合同，断言仍覆盖一次补写、来源限制及重新过门禁 |
| 生产代码 `getattr(..., ())` 容忍任意对象 | 否决；为不合法测试输入放宽数据合同，会把真正缺字段隐藏成无证据 |
| 只替换新的 helper 让旧测试变绿 | 否决；新读取与预算逻辑再次被替身跳过，不能证明补写接线 |
| 删除/跳过九例或只重跑原关键词范围 | 否决；定向漏面正是这次全量 CI 暴露的问题 |
| 取消原失败记录、用后一次绿覆盖旧 SHA | 否决；每次收据只对其版本和收集面成立 |

## 固定证据与 CI 归属

原件根：`~/.finance-runtime/reviews/river-consumption-20261008/`，不公开上传本机原始日志。

| 证据 | 结论 |
|---|---|
| `ci-code-python.log` / `ci-code-python-annotations.json` | `7389549bc` 的 9F 全量 CI；运行 `37689283789` |
| `ci-docs-python.log` / `ci-docs-python-annotations.json` | `1a055b87` 的 9F 全量 CI；运行 `37691469323` |
| `fulfillment-baseline.*` | `82de3fb73` 净树 16P |
| `fulfillment-before.*` | `1a055b87` 净树 9F/7P |
| `fulfillment-after.*` / `fulfillment-restored.*` | 实现期 51P，dirty，不移签 |
| `fulfillment-without-pinning-corrected.*` | 仅进程内撤保护，两个具名反例失败，文件未变；首次错误量具另存 `fulfillment-without-pinning.*` |
| `fulfillment-fixed-code.*` | `0154b06d1` 净树 51P；`fulfillment-fixed-code-check.log` 校验 revision/解释器/依赖/净树/基座漂移 0 通过，明确是定向 |
| `fulfillment-ruff.log` / `fulfillment-commit.log` | 全仓 Ruff 与实际提交门通过 |

`7389549bc` 的 E2E 在 Chromium 安装阶段触及 20 分钟上限，测试未执行；其 Python 是独立的九例失败，不能一概归为安装噪声。`1a055b87` 的 registry/frontend/E2E 成功，Python 与聚合失败；不是全绿。

本快照形成时，`0154b06d1` 之后的文档 HEAD 尚未执行完整工程门。下一轮在固定文档 HEAD 上跑全量 pytest、前端/E2E 与注册表组合，分别留新收据，终态回读 PR Checks；不把计划写成通过。

## 能力沉淀与边界

- 复用已有 `run_main_gate.sh`、`run_frontend_gate.py` 和收据校验器，不为一次 CI 下载造第二套工具。新增保护落在持续执行的补写测试里，并有撤保护红证人。
- 可迁移手法：替身可以隔离 IO，但输入结构必须满足真实类型合同；修正夹具不能止于绿灯，还应保留一条不替换关键接缝的路径测试。归属仍需读调用方/定义，不宜用自动替换 `object()` 代替语义判断。
- 此处重判与模型均为离线替身，不认证金融文本质量；完整 Workbench `TurnOrchestrator.run_turn`、B generic owner、真实模型利用仍未覆盖。
- 保持草稿 PR #75；未合并、部署、写生产或改画像。教学特征/PIT 与环境剧本闭环的约束沿用消费快照，不为 CI 通过降低领域判据。
