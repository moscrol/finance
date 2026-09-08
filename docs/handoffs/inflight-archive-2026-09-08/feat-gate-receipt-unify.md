# feat/gate-receipt-unify

## 这个分支做什么
W3：ask / episode 产物同构 `gate_receipt`，探针读同一张表。不合并引擎。

## 当前状态
已提交待你确认合。基线 `gitea/main@b42a82d6`。issues[] 仍是字符串（W1 后改 code）。

## 未验证 / 已知边界
- **live sidecar 双入口对拍未跑**（不碰 8792/8793/8795/8799/8801）。单测用两份产物 diff `gate_receipt`。
- 未与 W1/W2 共存。
- Ask 无语义判官：`verified_status`/`judge_status`=`not_applicable`，禁止假 completed/passed。
- 消费者盘点：`docs/learning/api-runs-consumer-inventory.md`。生产 UI 不 POST `/api/runs`；活消费者是 live_probe + 测试。

## 下一步
1. 干净 sidecar 非保留口：同题 `live_probe ask` vs smoke conversation，diff `gate_receipt`。
2. 合入等你确认。勿强推、勿合 main。

## 踩过的坑
- smoke summary `sort_keys=True`，表列顺序不能按插入序断言。
- `inspect_run_dir` 函数头勿被新 helper 冲掉。

## 已验证
定向：gate_receipt / live_probe / smoke / conversation_orchestrator 94 / workbench_api 102 / ruff / layer_audit。

## 工具沉淀盘点
`gate_receipt.py` 是本仓双引擎收据块，不进 TOOLKIT（换项目无此双入口）。
