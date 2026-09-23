# #81 / #832 在途交接

## 这个分支做什么
文档载体#892；唯一产品#832仍WIP。产品固定d1b30e1a068ccd0559f091f3c664ca2ca82f1e7c，基线626d8a508，不改产品或追逐后来main。

## 当前状态
用户「执行」后的新有限#75批已停：27请求（准入4/探索23），无重试，BLOCKED_EXPLORE_NO_PROBES。结构报告合法、EXPLORE.md已落，但零探针/零产品测试；Spec execute/report及Quality未启动。模型/controller/19899已退出。
新根 `~/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/`；新342件封存 `docs/verification/2026-09-23-react-trace-chain/receipts/independent-qc-hardened/`。原44工程件、旧49请求BLOCKED及371独审件不变。收口main为5bf47a5ae9aa，候选/作者仍同头clean。

## 未验证 / 已知边界
六项全部not_verified；真实模型execute未跑，离线pytest/SQLite准入不能补分母。C6真实出口/幸存定义/恢复次序/N条豁免仍须动态验证。
#76另授权、旧not_passed不变；旧a140终稿不移签。工程旧E2E两轮红及时延限制保留，单次双绿非稳定性认证，不证明后来main集成；#841归#68。

## 下一步
新批前先并入 `read-delivery-control-v2/after/` 的读取修正，补宿主权威剩余额度/产物计数与早期首探针里程碑，离线验证后重封配方及两轴准入，再另授权有限#75；不原地恢复、不自动加帽。#76/合并/部署/生产仍另办；产品头变化须重取工程收据。

## 决策与被否方案
真实exit用固定argv、报告用typed终止工具、准入跑到pytest与文件SQLite/WAL，否了仅靠提示/包装返回值/import放行。
阶段缺探针就停，不凭合法JSON放行。停后read修正仅在独立副本验证，不改执行时工具或补签；详见 `docs/handoffs/2026-09-24-react-trace-qc-hardened.md`。

## 已验证
原工程Python14710P/85S/2X、Ruff/registry，固定main/候选前端各120P/E2E34P2S。新两轴离线准入各2P、必红及伪stdout真实exit1；38封存输入、112阶段产物哈希、27请求对账通过。结构终止工具真实交付BLOCKED。read对照400短行一读/长UTF-8两读完整，超长单行显式拒绝，均零模型。

## 踩过的坑
模型第21请求自计16；硬帽不等于进度。read二次尾截断曾吞页首50行，底层字节帽又虚报选中终点，模型「完整读diff」不采信。execution.report_structural=false此轮是缺探针，非JSON非法。共享harness脏树未改；私有工具未推广，Gitea写后必须回读。
