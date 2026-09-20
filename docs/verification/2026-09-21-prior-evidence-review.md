# 旧证据复核 V3

## 结论

本轮接通“无需新检索，但需要研究交付”与受控旧工具输入恢复。
原始复核追问在真实 Workbench 入口恢复 14 条原件、零新增工具，并撤回部分无证据断言。
**研究求证整体行为仍未验收**：首答继续过强归因；复核仍混淆成交占比与成交增量；虚构材料仍拒答。
默认关闭 `FINANCE_RESEARCH_REASONING`，未 push/PR/合 main/部署。不得据此开启生产。

## 本轮合同

- `project_turn_decision` 将交付类型与读取需求拆开。material_only 走 research，但 needs_retrieval=false、capabilities=()；未决语义仍先澄清。
- 只在完整、可信会话窗口中，用户明确要求复核上一答、继续只用已取得数据，且未显式改日期/转题时恢复。
- 上一答必须有唯一对应用户消息，属于同一会话及本轮材料链；来源限已完成的 local_only 原始 continuous Episode。
- RunStore 固定读取登记的内部 `continuous-episode.json`，校验用户/run/会话、路径、软链接、大小和 SHA256。原件上限 16MiB。
- 恢复器核对原问题、消息、TaskFrame/contract/outcome hash；只接受当前完整 AgentEvidence schema、至多128条，不猜缺字段。
- 只接纳本地读取白名单工具证据；无日期、越截止日、派生计算不接纳，重复内容身份拒绝。结构化观察值保留，旧 supports/contradicts 清空。
- 旧内容身份本身不是完整性证明，完整性由登记的整份工件 SHA256 保证。原子反序列化必须无损。
- 通过专门的 `model_input:prior_tool_evidence` 播种本轮证据账，而非伪装成工具调用/预检索。重新编 E 号，记录 old_ref/new_ref/hash/run 映射。
- 不继承旧答、旧完成状态、覆盖状态和读取权限；原件缺失不退回查库，也不让 Engine B 绕过材料门。

范围有意保守：不支持跨会话、多层复核链、混合联网原轮、任意日期窗口重新筛选，也不是崩溃 checkpoint 恢复。
原轮已取到的其他日期证据保留其原日期，不代表可拿来解释目标交易日；逐句适用性仍需语义验证。
文件检查不宣称能抵抗有权限在校验期间恶意替换父目录的本机进程。

## 真实入口

复用 `intelligence.eval.live_probe` 与 `scripts/workbench_probe.py`；正式 conversations/messages 入口。
隔离端口18893，glm-5.3-flash，hybrid/max，研究求证提示 on。helper 的 grounded presenter 仍为 off，非生产展示配置完整复刻。

原件目录：`~/.finance-runtime/reasoning-boundaries-20260921/v3/`。
保留 `health.json`、`candidate.patch`、`candidate-code.tar.gz`、sidecar日志和隔离用户的完整 run/conversation 工件。
候选是 `84b9d851` 上的补丁；运行时 loaded/repo fingerprint 均为
`b5270eb57116b97ea3903246ed4b28c2b5cba2702728d6e5a10dd1134fa35c2a`。
补丁 SHA256：`c23001e3b3b84ce2637777292aced0896e1a3bc9ddede4edc888bc8a85406d82`。
之后只强化了“等长篡改”测试，运行时代码未改。测试撤保护的临时变异均已恢复。

| 题目 | 会话 / run | 观察 |
|---|---|---|
| 本地量价原题 | `conv_5427a1d2da2f43ebabf3b65cccf1fa76` / `run_20260921_013104_707446` | 有交付，但仍说“出逃式交易”“资金集中于大票”“小票/超跌股反弹”；行业占比被写成成交增量集中 |
| 原始复核追问 | 同会话 / `run_20260921_014132_656073` | material_only、空能力、14条旧原件、2次模型调用、0工具；明确撤回出逃/大票定性，指出09-18不能解释09-11/14。仍保留“成交增量集中”的错误表述；末尾双红结构也不足以唯一识别新增资金 |
| 虚构供需材料 | `conv_1930aada5d9a4958a24fb22682d8a3cd` / `run_20260921_014419_838928` | 0工具、2次模型调用、2次无效终止，最终证据不足拒答。不得算作材料研究成功 |

复核来源工件 SHA256：`67abf80527add0dc05ff26a9eb37defeeb576983a5e00d7bcdbff00bf7b261c5`。
同源 judge/`completed` 不是独立验收；上表为阅读公开答案的人工判断，不声称完成了独立盲审。
只有一组复核样本，未跑留出题、同版本on/off、重复配对。V1/V2失败原件未覆盖。

## 自动检查

- pytest/ruff 解释器均为主树 `.venv-workbench/bin/python`。本轮相关17个测试文件：836 passed。恢复保护后的收据：`~/.finance-runtime/test-receipts/20260920T175101Z-84b9d851.json`。
- 提交后干净 `7d0afaff` 同组836P、exit0、dirty=false；收据 `~/.finance-runtime/test-receipts/20260920T175433Z-7d0afaff.json`。
- 全仓 Ruff、diff --check 通过。
- 哈希门变异：撤掉 digest 比较后，等长且schema合法的3126→3127篡改测试失败，收据 `20260920T174821Z-84b9d851.json`。
- 会话门变异：撤掉源run.session_id比较后，跨会话元数据测试失败，收据 `20260920T174845Z-84b9d851.json`。
- 全仓 pytest 在约57%处超过600秒命令上限被终止，无完整exit/收据，不计通过。相邻模块单测219P不能替代全仓结论；同时存在其他树全仓任务，但未证明超时原因。
- 未跑前端/E2E/registry合流检查，不具备合并资格。

sidecar 已停止。收尾实读生产8792为 `bf662e9310ff751a4c31763815ee78fb7d6d5122`、healthy、clean、代码一致，未重启。
