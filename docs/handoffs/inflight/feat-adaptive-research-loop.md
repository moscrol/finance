# feat/adaptive-research-loop 在途

## 这个分支做什么
#72 / PR #868，及 #76 L6、#75独立工程审查。保持WIP，不合入、不部署。

## 决策与被否方案
- 候选固定31f1b40dd；全量收据7ad61a0d3；新工装2f4b5f089仅45P定向，不移签。
- L6失败停批、实际1/1/0；否了补Q3/重发和扩大off对照，旧原件不改。
- 新shim单独修/验；取消变异仅改内存AST，否了改固定候选文件。
- #75零终稿停止候选，否了加时/换模型/发report补签。详情 `../2026-09-23-adaptive-qc-harness.md`。

## 当前状态
L6仍NOT_PASSED：Q1 partial/判官不可用，Q2超时零工具，Q3未交。
#75已尝试，宿主终态BLOCKED_REVIEW_TRANSPORT_DEADLINE，非独立verdict。网关3请求通过；Spec explore 14请求，末次HTTP200后120秒未完成、terminated，无探针/终稿。execute/report/Quality模型均未启动，重试0。归档 `docs/verification/2026-09-23-adaptive-qc-harness/`。
独占候选与私有原件：`~/.finance-runtime/reviews/pr868-k3-qc-20260923-1530/`。进程已退出，19899已释放，候选干净。本轮没有金融题、生产操作或合入。

## 已验证
2f4b5f089干净树45P，收据 `20260923T073620Z-2f4b5f08-5a926a26676f.json`，解释器/依赖/身份校验通过。新shim首块透传、断连清理、退出计数、配额预占等12项离线通过。固定候选wrapper/tools/synthesis取消：原版3绿、撤转发3红、还原3绿。最终沙箱正反准入通过、请求计数对账17、密钥模式扫描无命中。

## 未验证 / 已知边界
45P是作者测试，不是独审。K3自造探针0、作者测试复跑0；必红控制只在宿主准入执行，独立execute未验。最后一发有流式内容，不能将中断唯一归咎供应商/工装，更不能反证历史L6根因。Q1无实际repair新稿，parse_error或Q2零工具不证明数据不存在。新head全量门禁、联合最新main、双轴终稿仍缺。

## 下一步
1. 新#75批须新证据根和明确请求形状/预算；不续跑本批execute、不擅改上限。让explore更早落盘局部探针须先验证。
2. 自然验收另获授权，不能补本批金融题。跨模块预算和内容保真仍待独立证据。
3. main持续漂移，合前重冻head/base，跑完整门禁与联合树，再等用户确认。

## 踩过的坑
HTTP200/进程exit0/execution.complete都不等于审查完成。completed代理计数只代表传输结束。macOS宽放回环再排除端口未实效，最终只准26001–26008；随机端口作者测试受限，EPERM不能记产品缺陷。Deadline无slice()。共享harness-reference有他人改动，未碰。
