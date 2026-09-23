# Runtime 合同量具补验

## 这个分支做什么
修量具、验K3写手局部代码、补#884工程门禁；不改运行时产品行为。

## 决策与被否方案
K3写手与宿主验收分账，不以局部绿改全局独审。先写完文档再冻结提交，最终收据树外绑SHA，避免写收据又改变tip。快照：`docs/handoffs/2026-09-23-pr884-gate-freeze.md`。

## 当前状态
PR #884 WIP，未合main/部署。fc7fed47b已将固定main bbd53487f4ce带入本枝。最终工程结论唯一读取点：`~/.finance-runtime/reviews/pr884-gates-20260923-02/verification.json`及#884最新门禁评论。只有四叶通过、预检通过、revision与PR当前head全等才可采信；文件缺失或不符即未完成，不回退旧收据。
首轮480cad07057c的Python被宿主中止，不能报全绿；原因及23原件在 `docs/verification/2026-09-23-pr884-gates/`。

## 未验证 / 已知边界
历史独审C1-C8仍未签字、整体BLOCKED。K3第三场只完成6例及基线，deadline停无终稿；变异/还原为宿主接手。工程四叶不等于独立语义验收。
未验完整跨进程续跑driver、跨机锁、真实计费、全部入口异常收口。spool只证明at-least-once；预检只验IPv4 TCP及security CLI，不声称完整主机隔离。

## 下一步
核对当前head与最终回执；不齐先复验，齐后等用户明确确认合#884，不自动去WIP。不重复合#865，不续K3/买额度/移签旧main收据。harness-reference BUILD.md仍有他人改动，本轮不碰。

## 踩过的坑
本机CI的generic allow network*配local/remote会漏放外连；应按入站/出站分别授权并先动态预检。首轮已作废，坏策略exit1/正确策略exit0留证；旧runtime全禁网策略不受影响。关闭等待要观察close，不能等被删除的锁钩子。JUnit可无type；KeyError只接纳精确变异/用例/字段。首红不覆盖，日志不格式化。

## 已验证
旧冻结版本：身份16P及两种撤保护；磁盘恢复178P；runtime71P/13变异、writer23P/9、reentry12P/5；K3原样inbox6P/1变异2指定红，均还原绿。241原件hash已验，详见 `docs/verification/2026-09-23-runtime-contract-followup/`。
本轮新增预检后验收器44P、目标Ruff绿。首轮前端120P、E2E34P/2S、注册表5/5仅保留为诊断旁证，不当最终提交验收。
