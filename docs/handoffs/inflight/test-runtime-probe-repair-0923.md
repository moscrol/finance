# Runtime 合同量具补验

## 这个分支做什么
修复可复跑量具、验收K3写手局部产物；不改运行时产品源码。

## 决策与被否方案
复用现有变异runner加沙箱和具名失败校验，不另造引擎。K3写手与宿主验收分账，否决局部绿改写全局独审。详见 `docs/handoffs/2026-09-23-runtime-contract-followup.md`。

## 当前状态
已推Gitea，PR #884 WIP，平台回读mergeable=false；未合main/部署。代码0099486f6，原件归档f0f75625b。当前树自有变更已提交；主工作树其他agent改动不碰。
入口 `scripts/review_probes/run_runtime_contract_checks.py`，四组runtime/writer/reentry/inbox；新输出根+完整SHA+干净候选。说明见旧identity工具README。

## 未验证 / 已知边界
历史K3独审C1-C8仍未签字，整体BLOCKED；本轮主要是既有作者测试的宿主重放，不能当新的独审。K3第三场仅写完6例并基线通过，deadline停、无终稿；宿主接手完成变异与还原。
没有本枝全仓/前端门禁。未验完整跨进程续跑driver、跨机锁、真实费用对账、所有入口异常收口。unlink故障不等于真实崩溃恢复，spool只证明at-least-once。

## 下一步
先完成本枝等价CI再申请合工具PR；不重复合#865。完整独审须另按合同授权补验，不自动续K3/买额度/移签旧main收据。harness-reference的BUILD.md有他人改动，未动；量具已入本仓，通用目录登记待安全窗口。

## 踩过的坑
锁观察钩子消失不算行为失败，要观察close是否提前返回。JUnit可能无type属性；KeyError只允许精确变异/用例/字段组合。两个失效源码锚点已修，先唯一匹配/编译再执行。runtime最终原拒收与重新裁决分开，后者未重新执行测试。原始日志不做空白格式化；probe命名*_checks.py不进默认收集。

## 已验证
冻结5f35da172：身份16P及两组撤保护/还原；磁盘恢复等8文件178P。d542658a7：runtime71P/13变异、writer23P/9、reentry12P/5，还原均绿。0099486f6：K3原样inbox6P/1变异2指定红/还原6P；另在5f35验shadow。合计28种源码变异，不重复累计同一保护。验收器35P、目标Ruff绿。
归档 `docs/verification/2026-09-23-runtime-contract-followup/`，MANIFEST所列241个提交blob字节核对通过；不宣称完整模型会话归档。所有本轮测试/写手进程已退出。
