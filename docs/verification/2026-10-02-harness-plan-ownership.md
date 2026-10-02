# P1a 验证：自拟计划撤回与可选输出反馈保真

## 结论与固定对象

**作者离线工程验证通过；未签合入、发布、独立评审或金融回答质量。**

| 对象 | 固定值 |
|---|---|
| 工作树 / 分支 | `~/fwp-wt-harness-plan-ownership-1002` / `feat/harness-plan-ownership-1002` |
| GitHub main 基线 | `3a2718c6c7dbf5af8ddad249b50835d09deef8a4`（开工时只读 fetch 核实） |
| 产品实现 | `12555e9adef541ee1350e1567bffa5253df2f61c` |
| 最终代码与测试验收 pin | `7513d476b90c82d9a6fbcef453879999c90c915e`（只增加 legacy deadline flush 正例） |
| 证据根 | `~/.finance-runtime/reviews/harness-plan-ownership-20261002/` |
| 解释器 | `/private/tmp/harness-opt/tmp/arena-harness-release-1002/.venv-workbench/bin/python` |
| 环境 | Python 3.12.13，httpx 0.28.1，依赖指纹 `66726d345bf37ce5`；`FORESIGHT_LLM_KEYCHAIN=0` |

方向承接并行 spec `acc743c84:docs/superpowers/specs/2026-10-02-model-owned-harness-spec.md`，不是另起总架构；范围以 [P1a 计划](../superpowers/plans/2026-10-02-harness-plan-ownership.md) 为准。未复制旧输出身份候选的整枝补丁，未改并行 owner 的树。本轮新增真实模型请求 **0**，无 push、合并或部署。

## 实现与实际覆盖

| 接缝 | 源码落点 / 回归实证 | 未据此证明 |
|---|---|---|
| 自拟计划撤回 | `research_plan.py`、`research_harness.py`：显式 `base_revision` 首次0，其后必须等于已接纳 revision；revision 严格递增；撤回需简短原因。自拟 answer_elements、branch_goals、perspectives 可撤至空。旧式无基线计划仍按原保留规则，允许显式升级、不允许降级 | 题型、主体、时间窗或用户义务可改；来源装配已迁移 |
| 在线消费与原义务 | 真实 `ContinuousAgentEpisode` + 脚本模型：新计划进入后续输入、工具/进展及 outcome；即使自拟 answer_elements 清空，缺合同必需输出的 completed 终稿仍被拒 | 自然模型会正确选择路线、原合同语义装配本身正确 |
| 资源与执行历史 | 原 root_budget/deadline 对象保留，用量继续扣减；取消阻止新计划与工具；stub 分支协调器回归保留已完成分支、证据、绑定和已报告用量，只派发一次、只作一次升档判断 | 真实异步分支的所有竞态、全入口聚合预算审计 |
| 拒绝落实在派发前 | 无效 PLAN 的每个 tool call 都得到 `invalid_plan` 回执；一次格式提示后再失败即进入原终局路径、工具菜单关闭。两条 loop 的核心 outcome 对照一致，严格消息派生检查开启 | 新增重试/默认规划调用，或取消原终局恢复规则 |
| 截止 flush | 新协议尚未被接纳或无效 PLAN 不借 flush 派工具；实际 Episode 正例覆盖普通工具与有效 legacy PLAN+工具各 flush 一次，不隐式接受计划、不发明稿、不再开模型轮 | 新协议可在截止处隐式生效，或改变既有工具执行授权 |
| 自适应反馈 | `adaptive_research.py`：新协议反馈给基线/撤回原因，旧协议仍给保留项；真实 loop 中撤回视角后未决项消失，先前证据仍在 | 真实金融答案更好 |
| 可选输出身份 | `task_fulfillment.py`：fulfilled/partial/missing 都保留 `required`；`missing_required`、补写、失败投影及序列化同源。真实 verdict→repair→重验，仅 synthesis stub；两个非特例输出 ID。完整 verdict 的失败投影不改原 spec | 上游所有建议已经变为可选；来源、正文或语义门已修好 |
| 事件往返 | 真实 `JsonlEpisodeStore` 写读 PLAN 事件，提取事件元数据后还原同一计划，`task_frame_hash` 不变；既有恢复/授权测试回归 | 新增跨进程恢复执行器、v1 快照热迁移或任务合同 v2 |

`ask_synthesis.py`、TaskFrame、任务合同与预算/恢复实现未在本片改动。PLAN 静态提示指纹显式从 `4c907c…e97` 更新为 `bf9f4a…409`，测试注释记录合同措辞变化，不是取消指纹检查。

## 固定 revision 读数

最终以 **7513d476b** 的新收据为准，不把先前脏树或不同 revision 的结果相加：

| 检查 | 结果 | 证据 |
|---|---|---|
| 33 个相关 pytest 文件 | **1045 passed / 1 skipped / 1 warning**，22.68s，exit 0；collected=1046，无 `-k/-m/ignore/deselect` | `frozen-targeted-tests.log`、`frozen-targeted-receipt.json` |
| 收据适用性 | revision、解释器、Python、依赖指纹一致；干净树、依赖门未绕过；exit 0 | `frozen-receipt-check.log` |
| 全仓 Ruff | exit 0 | `frozen-ruff.log` |
| 9 项撤保护变异 | **9/9 捕获**；每项恢复后绿；前后核心套件 **321P → 321P** | `mutations-final/results.json` 及逐项 log / JUnit / diff / hash |
| 本地提交钩子 | 产品与测试提交适用检查通过；无文件适用项标 skipped，不算执行过 | `implementation-commit.log`、`legacy-flush-commit.log` |

这33个文件覆盖 PLAN、Episode、参考 loop、adaptive、协议、履约/补写、恢复/持久化、授权、根预算、升档、子研究、verifier、SDK 回归、会话编排及应用内 Workbench HTTP integration。**不是全仓 pytest，不是新 PLAN 修订链从完整产品 HTTP 入口到公开答案的专项验收。** SDK loop 尚无 PLAN 接纳点，现有 SDK 回归绿不代表该能力全入口支持。

唯一 skip 为既有 opt-in 真 OpenAI Agents SDK smoke；本次没有删除、skip 或 xfail 正常红例。warning 为 Starlette TestClient 使用 httpx 的弃用提示，未因此更换锁环境。全量 Python、前端/E2E、GitHub Actions、本组合独立评审和自然金融质量均未执行。

### 变异明细

运行器复用仓内 `scripts/review_probes/run_extraction_mutations.py`；定义为 [harness_plan_ownership_mutations.json](../../scripts/review_probes/harness_plan_ownership_mutations.json)。隔离 detached worktree 钉住最终 pin，定义与 runner 来自同一 revision。所有变异均满足唯一锚点、可编译、实际执行非空、无收集 error/skip、撤保护断言红、字节原样还原后绿。成功后临时树已移除。

| 撤掉的保护 | 红轮失败 / 执行 | 恢复后通过 |
|---|---:|---:|
| 接受自拟项撤回 | 5 / 5 | 5 |
| 陈旧基线拒绝 | 3 / 5 | 5 |
| 撤回须有原因 | 1 / 4 | 4 |
| 新协议不能降级 | 1 / 4 | 4 |
| 可选项不混入必需补写 | 4 / 4 | 4 |
| 可选项不混入失败投影 | 2 / 4 | 4 |
| 重复无效 PLAN 不派工具 | 2 / 2 | 2 |
| deadline flush 不绕过接纳 | 3 / 3 | 3 |
| 反馈不退回一律只增不减 | 1 / 1 | 1 |

变异是作者构造的保护撤除，不是独立 reviewer 或产品误判率；没有给旧词面门做语义正确背书。

## 中间失败与证据限制

- 初始 `red-receipt.json` 为 **8P/19F**，`iteration-1-receipt.json` 为 **271P/2F**，均 dirty。初轮见到合同缺失/可选项反馈与重复无效 PLAN 派发；迭代中修正事件 payload 的元数据解包和静态指纹。原日志不改写成成功。
- 329P、922P/1S、271P 和 precommit 320P 均属中间脏树读数，范围重叠；最后代码不能只引用修改前的绿数。
- 12555e9ad 的 1044P/1S、9变异及320P前后恢复已留原件；7513d476b 增补旧协议 flush 正例后，重新跑同33文件及全部变异，不能把两版互签。
- 重放测试选择器的首次 shell wrapper 将收据 `target` 误当 list，前置 assert 退出1，pytest 未启动；按实际字符串格式解析后才产生 `frozen-*` 收据。它不是一次 pytest 红/绿读数。
- doctor 为 `offline_development`，`errors: []`，`production_verified: false`；代码地图 empty 不能推出“没有该实现”。

## 复跑与接续

在固定 pin 的干净隔离树中使用上述解释器，pytest 位置参数完整记录于 `frozen-targeted-receipt.json.target`；再运行 `scripts/check_test_receipt.py <新收据>`。仅这些位置参数构成相关范围，不能用 `--require-full-scope` 冒充全仓。

变异复跑（证据目录必须新建）：

```sh
"$FWP_WORKBENCH_PYTHON" scripts/review_probes/run_extraction_mutations.py \
  --revision 7513d476b90c82d9a6fbcef453879999c90c915e --output <新目录> \
  --definitions scripts/review_probes/harness_plan_ownership_mutations.json \
  --tests intelligence/tests/test_research_plan.py intelligence/tests/test_agent_episode.py \
  intelligence/tests/test_harness_reference_loop.py intelligence/tests/test_adaptive_research.py \
  intelligence/tests/test_fulfillment_repair_round.py intelligence/tests/test_task_fulfillment.py
```

P1b 仍需对齐 v0.1 owner：建议来源贯穿装配、题型/主体/时间窗解释 revision、稳定根请求与合同/存储版本/恢复分离、旧词面裁决退出表，以及 SDK 等入口覆盖。原输出身份候选 `4cba44a63` 的正常正文覆盖红例仍阻塞其发布，本片不能解除。R19封存、R17不重跑、R18归原owner、正式240格未放行。

决策理由与在途接续见 [日期交接](../handoffs/2026-10-02-harness-plan-ownership.md) 和 [本分支 inflight](../handoffs/inflight/feat-harness-plan-ownership-1002.md)。收尾清单及最终文档 revision 由证据根的 `closeout.json` 记录；它不把 docs-only tip 冒充 pytest 的固定 pin。
