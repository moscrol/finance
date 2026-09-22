# Runtime 未知效果 / 费用对账

## 这个分支做什么
堵住「崩溃窗口里的外部请求可能已计费，但账本记 0」这个洞：恢复把未知窗口登记成不可擦除的 durable 凭证，并在花这份余额之前设闸。不做跨进程续跑驱动，不做自动对账（对账要能付钱的人来做，恢复只登记）。

## 当前状态
栈在入口身份分支之上：基线 `671fbffc5`（`fix/runtime-entry-identity-0922` 的 HEAD），本分支 `fix/runtime-effect-reconciliation-0922`，单提交 `aec5a6d50`。**两条都未合并、未部署、未独审**——合入要按顺序。

## 问题的形状（先证伪再动手）
两条记账路径都是**事后结算**，而 `budget_snapshot` 只在相位边界拍：

    put_state(tools_pending)   ← 快照在此，不含本批
    tool_request               ← 意图
    ……外部请求真的出门了，供应商计费表在走字……
    tool_result                ← 结算
    consume_call               ← 账本此刻才扣

崩在中间三行的任意一行，恢复方读到的是**派发前**的余额。`restore_root_budget` 里那句 `A future driver must reconcile unknown effects` 悬空多轮，**没有任何机制兜底**。三个真实后果：同一笔钱可花 N 次（崩溃循环下无上界）；`retry_model` / `replay_tools` 恰恰在提议再付一次却什么都不记；`AgentUsage` 恢复后少报。

`replay="safe"` 是关于**效果幂等**的声明，不是关于**费用**的声明——注册表默认就是 `cost="external"` + `replay="safe"`，「重跑语义无害、财务照付两次」正是默认配置。

## 原则
**未知效果双向保守：对证据按「没发生」处理（不伪造结果），对成本按「已发生」处理（不伪造退款）。**
两句话朝相反方向保守，因为风险不对称——凭空造结果污染答案，凭空退款烧真钱。此前代码只做对了前一半：合成 `tool_error{interrupted}` 对证据是诚实的，但在事件流里与「这次调用从未发生」无法区分。

## 决策与被否方案
- 凭证挂 `EpisodeState.unreconciled_effects`；否塞进 `budget_snapshot`（会污染账本 schema，且「扣账」与「清空」变成两次写，中途崩溃留下脑裂态）。放 state 使**对账 = 扣账 + 清空**成为一次原子跃迁，清单本身即去重凭证。
- 恢复只**登记**不扣账；否「恢复时自动扣账」——恢复是读者、且静默，让它改余额等于让诊断路径动钱。
- `charge_unknown_effects` 作用在**快照**上；原设计作用在活账本上有先有鸡还是先有蛋（未对账时闸不放行 → 拿不到活账本 → 无处可扣），被自己写的测试证伪后改正。
- 只扣**调用格**不扣**秒**；窗口真实耗时无从得知（崩溃到重启的挂钟时间与调用耗时无关），编一个数字是伪造测量值。
- 格数不够如实记 `slots_unavailable`，绝不写负余额；这是在结算已经可能发生的工作，把它变成新失败源撤不回任何东西（与 `_settle_tool_batch` 同源纪律）。
- 无快照却有未清效果 → **抛错**；返回一份「已对账」的空快照等于把账销掉，这种情况只能人工判。
- `restore_root_budget(unreconciled_effects=...)` **必填、无默认值**；有默认值就等于「忘了传 = 无账可对」，静默失效。
- 派发前预留（reserve-then-settle）：否——代价落在热路径，每次调用多一次写；且本轮要解决的是**已经存在的**日志怎么读。留作后续若要 exactly-once 再议。
- 未派发的声明（`application_tool_call` 没变成 `tool_request`）**不**进清单：请求没出门，没有外部效果也没有费用，算进来是虚报。已有专门断言。

## 已验证
全量 `pytest -q -p no:randomly`：**13059 passed / 85 skipped / 2 xfailed / 0 failed**（39m41s）。pre-commit 全门禁绿（层级、路径字面量、字段契约、dataset、工具可达性、目录保鲜、ruff）。

新套件 `test_episode_effects.py` 10P：凭证损坏抛错、`unknown` 按可能已计费、合并幂等、扣格不扣秒/不写负余额、无快照拒绝对账、整道闸（拒绝 → 对账 → 放行）、必填参数无默认值、重复恢复不膨胀、热路径带凭证、状态往返。

**做过变异测试**（首次全绿被判定可疑）：分别打坏四处关键实现，每次都正确变红——热路径不带凭证（红 1）、merge 退化成拼接（红 3）、闸门放行（红 2+）、`retry_model` 路径不登记（红 2）。测试不是摆设。

## 顺带修掉的真盲点
事件发射扫描器有**两份副本**（`test_episode_event_lanes.py` 与 `scripts/gen_runtime_catalog.py`），都只认 `ledger.` / `self.` 的 `.add()`，漏掉 `episode_restore` 的 `synth.add()`。补上后 `docs/runtime/events.md` 里 `model_error` / `tool_error` / `finish` / `finalization_recovery_outcome` 才第一次显示出 `episode_restore.py` 这个发射点——它们一直从那儿发，目录一直没记。

## 被调整的断言（重要，别当成"改测试迁就实现"）
多处断言写的是「恢复一字不写」，那只是 INV-R3 的**代理指标**。真正要守的是：不伪造**结算**、不推进**程序计数器**。已逐条收紧为这两条，并额外断言新增的恰好只有 `effects_unknown`、phase/reserved_ids 不动。涉及 `conformance/test_inv_r3_restore.py`、`conformance/races/test_race_store_failure_vs_memory_ledger.py`、`test_episode_restore_persistence.py`、`test_episode_writer.py`。

其中 race order B 的原注释就写着「不保证前次未计费或可安全重试」——它当年承认了这个洞却断言恢复什么都不写。现在那句话有了凭证。

## 未验证 / 已知边界
- **闸只拦 `restore_root_budget` 这一扇门。** 别处若直接拿 `budget_snapshot` 造账本，绕得过去。合入后应审一遍还有没有第二扇门。
- **没有对账的执行者。** 本轮只提供 `charge_unknown_effects` 与闸；谁在什么时机调用、失败了找谁，属于跨进程续跑驱动的范围，未做。当前非空清单 = episode 停在那里等人，这是**有意**的 fail closed，但也意味着**一次崩溃会让 episode 需要人工介入**才能继续。这是本轮最重要的取舍，合入前请确认可接受。
- 秒数永远对不上：只扣格。跨崩溃的 `consumed_seconds` 仍然少报。
- `may_have_been_billed` 是启发式：模型轮一律算，工具看声明，解析不到的按 `unknown`（= 可能已计费）。它决定的是收据里的计数，不决定扣多少格。
- 负载敏感红两条（`test_skill_timeout_degrades_one_module_and_continues`、`test_rag_worker::test_warm_worker_survives_first_timeout_and_drains_the_late_response`）：上一轮全量各红过一次，本轮全量均绿；与本改动无路径交集，单跑各 3–5 次全绿。**是既有脆弱点，不是回归**，不改 sleep、不放宽断言。

## 下一步
1. 跨进程续跑驱动：要求 `RestoreResult.entry_identity_bound=True` 才允许自动续跑，并在续跑前执行对账（扣账 + 清空写同一份检查点）。这是让「非空清单」从人工介入变成自动处理的唯一出口。
2. 审第二扇门：全仓搜还有谁能绕过 `restore_root_budget` 拿到余额。
3. 合入顺序：先 `fix/runtime-entry-identity-0922`，再本分支。

## 踩过的坑
`restore_episode` 的 `close()` / `resumable()` 重建 `EpisodeState` 时**逐字段列举**——身份轮已在此栽过一次，本轮加 `unreconciled_effects` 同样必须在这两处透传，外加热路径 `_EpisodeLedger.put_state`（不带下去 = 用下一个检查点把「有笔账没对」静默改写成「无账可对」）。**加字段先看这三处。**

`close()` 里登记必须排在 `_synthesize_finish` **之前**：terminal 校验要求 `latest_finish.sequence == last_sequence`，finish 后面不能再有事件。
