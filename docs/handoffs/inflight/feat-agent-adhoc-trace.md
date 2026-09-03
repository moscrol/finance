# feat/agent-adhoc-trace

## 这个分支做什么
让 agent **直调积木**时也能写出与 Workbench 同构的 `runs/<id>/trace.jsonl`，好跟网页那条路 diff loop。不把 agent 塞进 `TurnOrchestrator`。

## 当前状态
脚本 + 12 条单测已绿，**未提交、未推、未合**。树 `/Users/a77/fwp-wt-agent-trace` @ `feat/agent-adhoc-trace` ← `gitea/main@3ac070a2`。

## 未验证 / 已知边界
- 还没拿原题真跑一对（我直调 vs 8792）
- `workbench-trace` mapper 没有 `tool` 枝，工具级差异要读原始 `name`
- `finance_query` 裸名会被拒写；`step_id` 写成 `retrieve.finance_query`
- 退出码 0 只表示对比算完，等不等价看 JSON 的 `comparison`

## 下一步
1. 你点头后再 commit
2. 原题各跑一臂：8792 网页 / 我这边 `scripts/agent_trace.py`，再 `compare`

## 踩过的坑
- `RunStore(root=)` 是扁平测试布局，和生产 `<users>/<uid>/runs/` 不一致 → 必须走 `FORESIGHT_USERS_DIR`
- 改完环境变量不还原，会污染同进程后续调用
- 本机多个 Workbench 各有各的根；不显式指定就 fail closed

## 已验证
`pytest intelligence/tests/test_agent_trace.py` **12 passed**；ruff 绿。解释器 `.venv-workbench`。

## 工具沉淀盘点
`scripts/agent_trace.py` 是本仓对照件，未抽到 `~/harness-reference`（一次实现，样本不够）。
