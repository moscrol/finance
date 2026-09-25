# Workbench 纠偏写侧与开口读侧：离线前置

## 结论

在审计分支中已接入 P0 写侧，并通过确定性离线验收：Workbench 编排在研究前识别“纠正上一条已完成 assistant 答案”的消息后，写入该用户的 `corrections.jsonl`；普通市场评论、无上一条答案、工程纠偏和探针身份不写。写入失败时只产生受限降级，不阻断研究主链。

P1 开口读侧已在审计分支 `9533417c3` 接通并通过临时根测试，见下节。它证明写入后下一轮首请求可自动带入相关纠偏，不再依赖模型主动调用工具。仍不是生产部署或完整行为闭环验收：未调用真实模型、未读写真实用户、未切换 8792。

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

## P1 开口读侧

- 代码 revision：`9533417c3412300e7edbc9d51ce4ec5dff9b40b3`。
- 干净定向收据：`clean-opening-receipt.json`，641P/0F/0S，`dirty=false`；精确测试清单在 `target` 字段。旧 P0 的 231P 收据保持原 SHA，不移签。
- 全仓 Ruff、`git diff --check`、提交门禁通过；P0 写侧探针重新执行 PASS。
- 入口夹具：`intelligence/tests/test_memory_opening_prefetch.py::test_workbench_write_reaches_next_first_request_without_tool_call`。实际调用 Workbench 写侧方法、装配器与 ContinuousAgentEpisode；模型替身仅返回固定结束消息，真实模型调用为零。

| 场景 / 验收层 | 状态 |
|---|---|
| 临时用户 P0 写入后，无“上次”提示的下一轮首请求含纠偏 | PASS；首请求送达、哈希入账、先验槽绑定，模型工具调用为零 |
| 同一纠偏自动预取与显式工具读取的 content_hash 一致 | PASS |
| 另一用户空结果、无身份不装配、不回落 default、缺授权不读取 | PASS |
| 撤回后下一轮为空；市场/方法论/未解析主体不预取 | PASS |
| 空结果显式 gap；读错/损坏行显式 unavailable | PASS；失败不伪装为空 |
| 超时、根期限耗尽、合成保留、饱和繁忙、迟到不回灌 | PASS |
| 记忆不能绑定市场事实；gap 不能充当历史判断 | PASS；终止校验与后验校验分别覆盖 |
| 真实 Workbench HTTP / UI 会话、CLI 对照、真实模型实际采纳 | UNKNOWN；本轮未运行 |
| 金融回答质量、长时间并发稳定性 | UNKNOWN |
| 合 main、生产装配与部署、完整发布门禁 | BLOCKED；未实施，仍需 owner 复核和用户确认 |

范围与取舍：

1. 有明确公司/题材主体的个股、题材、跟踪、买卖、估值、财务研究题，默认合同增加记忆授权；显式能力白名单、身份双闸与 material scope 仍优先。`material_only/local_only` 继续保持无预取，不扩大 E2 读权限。
2. 复用 `memory_lookup_runner`、`user_memory.relevant_memory_records` 和 `evidence_content_hash`，不新增检索索引或模型判官。`prior_recall` 只为可选先验槽，不凭空制造必交的用户历史。
3. 写侧从被纠正的 completed assistant 的 `turn_intent.primary_subject` 透传 `themes`。否则省略主体的“应该先看兑现”虽写入，下轮按公司召回仍可能漏掉；缺主体时不猜。
4. 开口观察明确标注 `user_memory` 或 `user_memory_gap`；空/超时/错误/繁忙分开。只限当前召回口径，不声称用户从来没有写过笔记，也不保证语义召回完整率。
5. 1 秒子期限与根研究剩余时间（扣除合成保留）取交集，最多两个后台读取，无积压队列。Python 线程不能杀死已经卡住的磁盘调用；槽位占用期间后续请求返回 busy，迟到结果不写回注册表。进程退出时仍可能等待底层 IO，不能将此测试称为硬取消或生产故障演练。
6. 旧 CLI 默认容错读取保持兼容；工具/自动预取使用 strict 读取。新坏 JSON 行不能被静默跳过后误报“无命中”。报告不保存完整提示词、用户原文或评分原因。

快速复现 P1（全套定向命令见收据 `target`）：

```bash
cd /Users/a77/fwp-wt-architecture-audit-0924
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_memory_opening_prefetch.py
```

## P0 可复现

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
