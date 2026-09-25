# Workbench 纠偏写侧：离线前置

## 结论

在审计分支中已接入 P0 写侧，并通过确定性离线验收：Workbench 编排在研究前识别“纠正上一条已完成 assistant 答案”的消息后，写入该用户的 `corrections.jsonl`；普通市场评论、无上一条答案、工程纠偏和探针身份不写。写入失败时只产生受限降级，不阻断研究主链。

这不是生产部署验收，也不是完整纠偏闭环：下一轮研究开口必取 `memory_lookup` 的覆盖单仍未完成；本轮没有模型调用、没有真实用户写入、没有切换 8792。

| 冻结场景 | 结果 |
|---|---|
| W-corr-1：上一条完成稿 + “不对，应该先看板块容量” | PASS，写入 |
| W-corr-2：没有上一条 assistant | PASS，`no_prior_answer`，不写 |
| W-corr-3：`这波不对，应该是情绪退潮` | PASS，`market_commentary`，不写 |
| W-corr-5：`tester` 身份 | PASS，`identity_skipped`，不写 |
| `default` 身份正例 | PASS，写入 |
| 写入异常 | PASS，fail-open 单测通过 |
| 纠偏成功收据 | PASS，trace 只含 ID、原因、plane、被纠正消息 ID |

## 实现边界

- 纯文本门位于 `intelligence/services/workbench_correction_ingest.py`，只接受显式路径；不读取环境变量，不导入 runtime。
- runtime 负责 `PYTEST_CURRENT_TEST`、`default`、`tester` 和探针前缀守卫；`default` 明确允许写入。
- 上一条被纠正的消息只接受倒序最近一条 `role=assistant`、`status=completed` 且正文非空的消息，不复用只看 `turn_intent` 的 `previous_turn_message`。
- 纠偏记录使用既有 `corrections.record_correction`，追加 `source`、`conversation_id`、`corrected_message_id`、`plane=user_method` 旁路字段；旧记录加载仍兼容。
- 成功 trace 名为 `user_correction_recorded`，不带用户原文；普通跳过不污染既有 trace 首步顺序。
- `principle` 不自动生成，主题为空时不猜测，符合 P0 的慢变量保护边界。

## 收据

- 探针：`probe.json`。
- 同一代码路径定向回归收据：`clean-targeted-receipt.json`，绑定 `f3d39d7d2`，231P/0F/0S；它包含纠偏服务、编排器、纠偏台账、用户态、记忆状态和 episode 工具测试。
- 该收据只证明审计分支的临时状态，不移签生产版本。

## 可复现

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
cd /Users/a77/fwp-wt-architecture-audit-0924
"$PY" scripts/verify_workbench_correction_ingest.py --json
"$PY" -m pytest -q \
  intelligence/tests/test_workbench_correction_ingest.py \
  intelligence/tests/test_corrections.py \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_userspace.py \
  intelligence/tests/test_memory_status.py \
  intelligence/tests/test_episode_tools.py
```
