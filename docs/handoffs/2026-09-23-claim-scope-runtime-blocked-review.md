# Claim-Scope 接入与独审阻塞

## 背景

用户明确要求继续做此前排除的四项：运行时接入、#75 K3 独审、#76 L5 真实模型验收、有门禁的生产部署。授权原话、消息ID和时间均已从 pi 原会话核对，树外 `protocol.json` 留出处。此前 #883/#888 的合入、红绿收据和清理是历史事实，不迁移到本轮候选。

工作树 `fwp-wt-claim-scope-runtime-0923` 独占；主检出树有其他任务，不触碰。实现与证据入口见 `docs/verification/2026-09-23-claim-scope-runtime/README.md`。本篇记决策，实际验收数字以该文件及原件为准。

## 发现顺序

1. 复核两条引擎的最终交付出口：只在 semantic verifier 看初稿会漏掉 A 的投影/异常恢复稿与 B 的延后合成稿。
2. 把 CLI 证据映射抽成共用 `claim_scope_context.build_context`；观察结果绑定真正公开文本的 SHA-256，不绑定潜在旧稿。
3. B 没有 A 的结构化工具请求账，不能拿模型自己的 claim 补证。因此缺口进 degraded，观察档位不静默认证完整性。
4. 开发测试和两份旧答卷回放完成后，前向纳入 main 文档收尾，固定 `2be85e64eeaffc6e37b66898ecc1a740acd6a7fd`。工程门禁与独审分别建独立 detached 树，避免混合树收据。
5. K3 一发网关小载荷200/READY后，独立 explore 读源码8轮，第9次预占请求超时；208.492秒退出。宿主CLI exit=0，但事件流明确 `Request timed out.`，没有探针或最终报告。
6. 按 #75 工单把 explore 记 `BLOCKED_REVIEW_NO_OUTPUT`，execute/report 未派，不用作者测试补签。#76 L5 两原题提交数均为0；没有冻结数据、启动旁路或生产改动。
7. 创建 WIP #890 的 POST 客户端超时；随后只读查询确认服务端已创建，不重复 POST。生产只读复查仍为原 revision/GLM，readiness仍缺 market_data_consistency。
8. 条件卡里的板块归属SQL用了旧列名，本轮按 schema 修为 stock_ts_code/sector_ts_code；并没有因此查询或认定本次全集数。
9. 首轮完整Python门禁14641P/2F：B收据在终态认领前落盘，以及只读public_answer参数与公开赋值棘轮冲突。把落盘移到认领成功之后、只读参数改名delivered_answer；不改门禁。加强实际Workbench顺序断言，在旧冻结版恰好1红，返修7模块483P。首轮前端120P/E2E34P2S/registry5项已过但不移签，完整重验另起retry-01并绑定新revision。

本篇是返修候选冻结时的决策快照；后续门禁完成与否读取证据根retry-01的audit.json和gate-runner.log，不从本篇推定通过。

## 决策对比

| 决策 | 采用 | 被否方案与理由 |
|---|---|---|
| 启用档位 | 默认 off，仅 advisory；未实施档位留诊断后off | 直接 revise/block 会改变答案与终态，超出本轮分档接入边界 |
| 证据映射 | CLI/在线共用解析；缺失显式degraded | 两份解析器易漂；用模型claim自证会把观察器变成循环证明 |
| 检查时点 | 核验后及最终稿出口重盖文本hash | 只查初稿不足以描述用户实际收到的稿件 |
| 运行费用 | advisory零新模型/取数调用 | 在线拉归属全集会增加外呼和预算，改变既有权限合同 |
| K3超时 | 留原件、未知即阻塞、不自动重试 | exit=0不代表审查完成；源文件已读也不等于双轴有结论 |
| L5与部署 | 候选未获接受则不派L5；readiness红不部署 | 旧答卷重放/工程通过不能替自然答案签字；换代码不能恢复数据一致性 |
| 收据 | 固定revision/tree与实际检查范围 | 后续文档提交也不移签；旧#888完整门禁不是新功能的门禁 |

## 工具沉淀盘点

产品可复用部分已入仓：claim_scope_context/review、A/B出口接线、claim_scope_census与回归测试。树外 replay.py、run-gates.sh、QC runner 是这两份历史答卷和本次固定revision的实验控制器，保留脚本hash及事件原件，不冒充通用SDK；QC复用了已有K3 runner/凭证工具，不新造一套审查框架。超时/空输出阻塞、先查副作用是否已落地的纪律已有现成文档，本轮没有新增跨项目方法论。

## 接手与禁区

完成 #75 需要新一次明确的有界审查安排，依次 explore/execute/report，各自独立会话并分开作者测试与自造探针。新候选、主干或依赖漂移后重新跑门禁，不能靠此处历史数值合入。L5必须用两道原题、首发1/重发0/续问0，候选和数据冻结、旧阳性对照保持报红，声明实际网关和K3剥参路径。生产数据一致性恢复需独立证据，不自动回填；全部前置通过后才可部署。保留WIP、旧失败现场、两棵冻结检出，不结束为“已部署”。
