# Claim-Scope Runtime

## 这个分支做什么
接入 off/advisory，并推进 #75 独审、#76 L5 与有门禁的部署；不自动开启 revise/block。

## 当前状态
代码 702776000；已前向纳入 main@f47d464eb，组合 4f52bd0fc。准备冻结审查/门禁，尚未合入或部署。授权：pi 会话 01a0cbdf-8033-71c3-9314-9cf6c26bc033，消息 a7d8d0e6（用户要求把此前排除四项也做）。后续真实状态以树外证据根 `~/.finance-runtime/reviews/claim-scope-runtime-20260923/` 为准；本文件只记录冻结前状态，不是通过证明。

## 决策与被否方案
- 复用 CLI 解析，不另写一套判据；A 核验后及最终/恢复出口检查最终文本，否了只检查初稿。
- B 早退、延后合成与 Workbench 最终落盘均覆盖。只读来源记录，否了拿模型 claim 自证。
- B 无等价工具请求账，显式 degraded；线上不查板块全集。范围规则比较数已知/全集未知仍会命中，设计稿“沉默”描述不准确。
- 默认 off，不改正文/终态/模型预算；revise/block 不实施且写 unsupported。
- 工程/独审/L5/部署分别验，不互相代签。说明见实施单 `docs/superpowers/specs/2026-09-23-claim-scope-advisory-runtime-workorder.md`。

## 已验证
开发期定向 110P、扩大六文件 498P、补落盘后专项 22P；Ruff 全仓/层级通过。两原冻结答卷 typed runtime 映射与 CLI 全字段相同：材料1条/行情3条。以上开发期含脏树，不是 clean head 完整收据。11:00Z K3单发小载荷200/READY（约4.9s），不算独审或L5。

## 未验证 / 已知边界
完整门禁、#75双轴、L5两题与部署均待验。开工8792实读3b7e473575b0、GLM、clean；readiness只有market_data_consistency=false，不能用换代码掩盖。禁止自行回填或在生产跑验收。B降级不是四条规则完整通过。

## 下一步
固定新head独立检出；先K3三段审查与真实冻结重放，再完整门禁/L5（每原题首发1、重发0、续问0）。红则记录阻塞，不合、不切。旧#883/#888收据不得移签。

## 踩过的坑
重建 frozen AgentOutcome 时必须带原 task_frame_hash，否则构造器拒收；dev-parity首轮是夹具失败，dev-parity-02才是有效一致证据。B原注释称质检已落trace，实读并未完整落盘，故新增私有收据。
