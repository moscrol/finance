# Claim-Scope Runtime

## 这个分支做什么
默认off、仅advisory接入；推进#75独审、#76 L5和有门禁部署，不开启revise/block。

## 当前状态
WIP PR #890，未合未部署。初冻2be85e64e完整门禁14641P/2F，原件保留；两处已返修，7模块483P。完整重验固定新revision，结果只认树外`~/.finance-runtime/reviews/claim-scope-runtime-20260923/retry-01/`的audit.json/gate-runner.log；本篇不预写通过。#75初冻explore第9次请求超时、零终稿，BLOCKED_REVIEW_NO_OUTPUT；execute/report未派。L5首发0，生产未动。

## 决策与被否方案
- CLI/在线共用映射；A最终/恢复稿、B早退/延后/最终稿盖文本hash，否了只查初稿。
- B缺工具请求账显式degraded，否了模型claim自证与在线补全集。
- 观察收据必须在终态认领成功后写；否了私有文件可先写，败方仍不能写产物。只读参数改delivered_answer，保留公开赋值门禁。
- 超时无产物就是阻塞，否了exit0当通过；工程、独审、L5分别记账。
- 详细背景/被否理由见`docs/handoffs/2026-09-23-claim-scope-runtime-blocked-review.md`。

## 已验证
初冻前端120P/E2E34P2S、registry5/5；两旧答卷CLI/runtime逐字段一致，仍报1/3条。返修实际Workbench顺序断言在旧版1红，修后相关483P；Ruff/diff过。上述不移签完整复验。原件及复验入口见`docs/verification/2026-09-23-claim-scope-runtime/README.md`。

## 未验证 / 已知边界
K3双轴未完成，独立探针0，阳性对照未执行。新L5无judge/marker/正文收据。8792只读实见3b7e473575b0/GLM；主库日期09-22、快照09-23，readiness缺market_data_consistency。禁止自行回填。B降级不等于四规则完整通过。

## 下一步
先核retry-01真实结果；新有界安排完成K3三段。固定获准候选与数据后，两原题各首发1/重发0/续问0；全部绿且readiness恢复才部署。任何新head须新收据，旧#883/#888和本轮首红均不移签，不自动续跑模型。

## 踩过的坑
AgentOutcome回放需原task_frame_hash；pi exit0也可有模型timeout；创建PR超时须先回读，不重复POST。L5旧SQL列名已修，全集仍需按实际答案日期查冻结库，不能沿用20。
