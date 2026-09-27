# Claim-Scope Advisory Runtime

## Scope And Authorization

2026-09-23 用户要求本轮同时处理 claim-scope 运行时接入、#75 K3 独立审查、#76 L5 真实模型验收及生产部署。本单承接接入设计，实施范围仅 off/advisory；revise/block 保留为未授权、未实施档位，配置它们须记录 unsupported 并有效回落 off，不得偷偷改答案或新增模型调用。

- 基座：`b59d6eed0356ae093b52bd291ab328628de8790e`。
- 工作树：`/Users/a77/fwp-wt-claim-scope-runtime-0923`。
- 分支：`feat/claim-scope-runtime-0923`。
- 主检出树有其他会话改动，不用于本单测试或部署。

## Decisions

1. CLI 与在线共用证据解析纯函数，不复制正则。默认/off 不新增序列化字段、不改变公开答案。非法配置写私有诊断，不静默启用。
2. 引擎 A 在 verifier 出口记录，并在 adapter 最终公开稿与保留旧稿的 partial 出口重新检查；后续投影不可沿用旧稿的 clean 收据。
3. 引擎 B 覆盖 answer_query 的提前返回与后置 synthesis；只追加 advisory 检查，不增加 actionable warn、不触发改稿。
4. 不预取归属全集、不增加 DuckDB 查询。缺少范围分母明确 degraded，不捏造比较数。B 的文本块没有等价结构化工具请求时也记录映射限制。
5. known_scope_total 的线上取数、revise/block 及其升档阈值另行决策。本单不修改离线规则、不修写手策略。
6. #75 作者测试与外部审查分账；#76 L5 只跑两道原题，每题首发一次、重发和续问为零。未知或失败不得补签通过。
7. 生产切换依赖工程门禁、独立审查、L5、部署就绪检查全部通过，失败不切换。2026-09-23 开工时 8792 readiness 的 market_data_consistency=false，仍须独立解决，不用部署掩盖。

## Acceptance

- 冻结材料题/行情题的在线映射与 CLI 的规则、原句、理由、数量、degraded 逐字段一致；行情冻结重放显式注入 scope_total=20，不能将它当线上默认值。
- 撤日期/单位规则的阳性对照；off 输出保持不变；缺映射必落 degraded；advisory 无模型调用、不变正文/终态/修订轮。
- A 正常与恢复出口、B 提前返回与后置合成各有执行回归。
- 标准库规则层不增加跨层依赖；独立固定 clean revision 完整门禁；收据不移签。
- 观察面从冻结收据离线统计，不新增 live 请求。
- K3/L5/生产各留独立结论，任何阻塞具体记录；本单文档不是验收通过证明。
