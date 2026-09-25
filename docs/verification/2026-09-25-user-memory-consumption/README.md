# 用户纠正与跨用户记忆消费：离线前置

## 结论

现有的**规范台账写入器 → CLI `prime` / 用户记忆召回 → `memory_lookup` 工具**链在临时用户根中通过；跨用户隔离、撤回和缺身份保护均通过。这个结果只证明既有 canonical `corrections.record_correction` 的写入后，两个读取入口能正确消费；**不证明 Workbench 对话已经自动识别“你说的不对”并写入台账**。

因此阶段 B 的两例拆成：

| 检查 | 结果 | 范围 |
|---|---|---|
| A 用户写入后被 CLI `prime`、直接召回和工具消费 | PASS | 临时用户根、确定性入口，无模型 |
| B 用户读取 A 的纠偏 | PASS（空结果） | 用户身份绑定及跨用户控制 |
| A 追加 `rejected` 状态后继续召回 | PASS（空结果） | append-only 状态覆盖，不改历史行 |
| 无身份时装配 `memory_lookup` | PASS（不装配） | 防止回落到 `default` 串号 |
| Workbench 用户消息自动写入纠偏 | UNKNOWN/BLOCKED | 当前仅有 CLI/底层写入器，设计稿的 Workbench 写侧尚未接线 |
| 真实模型是否主动调用工具、是否改善回答 | BLOCKED | 本轮不调用模型；生产行情/预算前置也未齐 |

## 固定边界

- 临时根由 `TemporaryDirectory` 创建，并通过 `FORESIGHT_USERS_DIR` 注入；没有读取或写入真实用户 `linxiaoqi5111`。
- A 的纠偏正文、原答和原则只在临时内存/临时 JSONL 中使用；报告只保留记录 ID、SHA-256、数量、状态和证据等级，不保存私人原文。
- 读取走真实 `prime.build_prime`、`user_memory.relevant_memory_records`、`build_episode_registry` 和 `registry.execute("memory_lookup", ...)`，不是复制一套审计实现。
- `user_memory` 证据始终标为 `user_memory`、`historical`，并带“先验，非市场事实”来源边界。
- 撤回通过真实 `memory_status.record_status` 追加状态行，之后同时从直接召回和工具证据消失；不删除或改写原纠偏行。
- 缺身份时即使 contract 授权 `memory_lookup`，工具也不注册；这是保护，不是消费通过。

## 收据

- 运行输出：`probe.json`。
- 同一树定向回归：`clean-targeted-receipt.json`，绑定 `6d4bb99d1`，117P/0F/0S，包含脚本回归、纠偏、用户记忆、退出状态和 episode 工具测试。
- 代码收据需绑定收据内的准确 revision；本报告不把这组离线结果移签给生产版本。

## 可复现

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
cd /Users/a77/fwp-wt-architecture-audit-0924
"$PY" scripts/verify_user_memory_consumption.py --json
"$PY" -m pytest -q tests/test_verify_user_memory_consumption.py \
  intelligence/tests/test_corrections.py \
  intelligence/tests/test_user_memory.py \
  intelligence/tests/test_memory_status.py \
  intelligence/tests/test_episode_tools.py
```

退出码 0 只认证临时台账消费与隔离合同。要完成 Workbench 纠偏输入闭环，需另按 `docs/superpowers/specs/2026-08-30-workbench-correction-loop-design.md` 的授权、测试和真实入口验收实施，不能用本收据代替。
