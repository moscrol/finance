# P1b 第二片验证：根请求锚点与目标解释版本

## 结论与固定对象

**本片作者离线 Python 工程验证通过；不是完整 P1b、合入/发布批准、独立审查或金融回答质量证明。**

| 对象 | 固定值 |
|---|---|
| 工作树 / 分支 | `~/fwp-wt-harness-output-provenance-1003` / `feat/harness-output-provenance-1003` |
| 本片代码、测试 pin | **`e859b5ff9508ab1297dd15edf8a9fa3e166a9b7f`** |
| 上一片来源保真 pin | `c18d6f0fe73f1ee0c9d631ad7b302ef24727a4e6` |
| 证据根 | `~/.finance-runtime/reviews/harness-request-interpretation-20261003/` |
| 解释器 | `/private/tmp/harness-opt/tmp/arena-harness-release-1002/.venv-workbench/bin/python` |
| 环境 | Python 3.12.13、httpx 0.28.1、依赖指纹 `66726d345bf37ce5`；`FORESIGHT_LLM_KEYCHAIN=0` |

本片只开放 `goal` 解释修订，不重装配题型、主体、时间窗、输出、grounding、材料权限或预算。根请求在初始可信 `ResearchRunContext` 创建时固定；repair 执行投影不能重算根。解释 revision 与 PLAN revision 分开；内容引用只用于追溯，不是认证或语义证明。没有 push、合并、部署或新增真实模型请求。

## 实现与边界

| 接缝 | 实现 / 实测 | 不能据此声称 |
|---|---|---|
| 根请求 | `RootRequest` 保留原问题、TaskFrame hash、输出身份及材料合同；严格序列化/反序列化和内容引用校验；`replace(context, contract=repair_projection)` 保留冻结根 | 根引用能认证用户/会话，或证明模型解释正确 |
| 解释版本 | `InterpretationProposal` 严格拒绝未知字段；只从当前 revision 接纳到下一 revision；普通 PLAN revision 不重置解释 | 自然语言目标理解正确，或题型/主体/时间窗可在线改写 |
| 接纳门 | stale、跨根、越权字段、取消、deadline、规划轮次和 repair 关闭状态在工具派发前拒绝；解释与工具同包整包拒绝 | 任何 provider 都会自动遵守协议；模型永远不会提出错误目标 |
| 连续 Episode | 接纳回执进入下一次真实模型输入；事件关联 interpretation revision 和 request ref；repair 不接纳新 PLAN | 完整公开交付质量或真实金融结论正确 |
| SDK | `PlanHooks(RunHooks)` 在 provider 响应后、本地工具执行前裁决；PLAN-only 续段共享总 timeout、轮次和 provider history；离线模型走真实 SDK 派发 | 真实模型质量、跨进程磁盘恢复执行器或前端行为 |
| 授权/终局 | 无解释且根未分离时保 schema v1；解释或 root/contract 分离时用 v2 携带两者；finalizer 始终带当前解释（未修订为 revision 0） | 旧快照被迁移/重签，或合同/恢复版本已经完全分离 |
| HTTP | Workbench 真实会话 API、解释回执、观察取证、答案和持久化检查点有脚本模型专项贯通 | 自然语言模型能从完整题意稳定地产生正确解释 |

## 固定 pin 的门禁读数

### 全仓 Python + Ruff

干净 `e859b5ff9508ab1297dd15edf8a9fa3e166a9b7f` 上运行：

- Ruff：通过。
- pytest：**18,876 passed / 0 failed / 0 error / 76 skipped / 2 xfailed / 0 xpassed / 18 warnings**，耗时 **1072.80s（17:52.80）**，exit 0。
- 收据：`full-2-e859b5ff9/gate-1PINvBdI/pytest.json`；原始日志 `full-2-e859b5ff9.log` 与 `.../pytest.log.txt`。
- `check_test_receipt.py --require-full-scope --expect-revision e859b5ff9508ab1297dd15edf8a9fa3e166a9b7f`：exit 0。收集 **18,954**，与 `18,876+76+2` 对平；无 ignore、keyword、deselect、mark、maxfail 或 last-failed 收窄；revision、解释器、依赖指纹、dirty=false 均一致。
- 之前 900 秒上限中断的 `full-e859b5ff9.log` 及 `full-e859b5ff9/gate-sdgkKwxb/pytest.log.txt` 保留为未完成现场，不当作测试失败或通过；本次用新证据目录和新 basetemp 完成。
- 首次收据复核见 `full-2-receipt-check.log`。文档提交后的 `final-receipt-check.log` 因 HEAD 已不同而正确 exit 1；随后从干净临时检出的 **e859b5ff9** 复核，`pinned-recheck-receipt.log` exit 0，额外核对仓根 target。没有改校验器、旧收据或冒签后续文档 SHA；临时检出已移除。

### 本片撤保护反证

定义：`scripts/review_probes/request_interpretation_mutations.json`；结果：`mutations-e859b5ff9/results.json`；审计：`mutation-audit.json`。

- **12/12 个定义捕获**；baseline/restored-full 均 **42 passed / 0 skipped / 0 error**。
- 每个变异都记录红轮和还原后绿轮；红轮有效执行且 exit 1，绿轮与红轮执行数一致、exit 0。
- 变异树已移除；每个文件的还原 SHA-256 等于固定 pin 的 Git blob，定义内容 hash 与结果一致；开发树干净。
- 明细中的 SDK 拒绝包有参数化执行 **6F/8**，连续反馈 **1F/4**，连续 repair **1F/2**，finalizer **1F/2**；因此只能说 12/12 定义被捕获，**不能说所有参数化变体都红**。
- `mutation-audit.json` 的 `killed=12,total=12` 是本片第二片定义，不与第一片的 13 项变异相加为本片单一套件。

### 固定 pin 的定向复验与其他检查

- 干净临时检出的 **e859b5ff9** 重新执行 `test_request_interpretation.py`、`test_workbench_research_chain.py`、`test_episode_finalizer.py` 三文件：**70 passed / 0 skipped / 0 error / 1 warning**，10.64s。日志 `pinned-final-related.log`、JUnit `pinned-final-related.xml`；收据 `pinned-final-related/20261003T063847Z-e859b5ff-b063d31a9b2f.json`。不是移用提交前的70P。
- 其中 `test_http_goal_revision_reaches_tools_answer_and_durable_state` 使用真实 Workbench 会话 API 与脚本模型/来源/判官，检查解释回执、观察驱动取证、答案、入口身份和持久化检查点。证明接线，不证明自然金融质量。
- SDK 真实 SDK + 离线模型专项包含 `sdk_glm` / `sdk_gpt`、混合包拒绝、下一输入中的接纳回执、usage 汇总、共享总 timeout/轮次（`[3,2,1]`）和 timeout 后 repair 保留解释；其断言属于固定 pin 全仓及第二片42项测试。
- 本片产品提交 hooks 通过，见 `code-commit.log`：含 Ruff、层级、路径、字段、数据集归属、工具可达性和运行目录保鲜。**没有另取本片完整 registry/台账五项收据**，不搬第一片结果。本片代码 pin 之后只有文档改动。

## 失败历程与不能移签的读数

1. 全仓第一次执行在约 93% 被命令 900 秒上限中断，没有最终 pytest 收据；不能把停点读作挂死或绿。
2. 新目录复跑耗时超过 900 秒但在 1800 秒上限内完成；只用最终固定 pin 的 `full-2` 收据签全仓，不挪用第一片的 18,832 passed，也不挪用提交前 dirty 读数。
3. `unit-red.log` 保留新增能力尚未实现的初始红例；后续反馈事件未登记、工具上下文测试误用等问题在迭代中修复。`http-2.log` 的58P、`prepin-related.log` 的458P/1S、`prepin-final.log` 的70P均属于 **fde21a6c1 上的未提交迭代**，不作为 e859b5ff9 的独立固定版收据。最终全仓与上面的70项复验是新执行。
4. 12/12变异结论按定义而非参数化用例计数；`mutation-audit.json` 复核了逐项红绿、定义字节和还原后的 Git blob，不声明全部参数化变体都红。

## 未验证范围与下一片

- 前端 lint/typecheck/unit/build、浏览器 E2E、GitHub Actions、本组合独立规格/代码质量审查未执行；本片不是四叶合入门禁。
- 新增 HTTP/SDK/连续路径使用离线或脚本模型；没有新增真实模型请求，金融答案质量、自然语言解释正确性、真实用户满意度未验。
- 题型/主体/时间窗在线修订、完整合同与恢复投影版本分离、旧词面/默认槽退出、跨进程 SDK 磁盘恢复执行器仍未完成。
- 代码地图仍不可作为架构覆盖证明；Memory 回写只在独立本地候选树，未整合共享主目录。
- R17/R19 继续封存，正式 240 格不放行。后续若改代码，必须重新 pin、重新全仓和变异验证；不能把本报告收据移到新 tip。

## Memory 本地候选

候选 **`2d540127942291b5879e098d73c50f85767795b9`** 在 `~/agent-memory-wt-harness-output-provenance-1003`，含本片 `47d58730` 与记录口径修订；共享主目录未写入/推送/整合。lint仍有存量46错/31警告，新旧错误逐条一致，只有既有项目页超长警告的字节数改变；见 `memory-refined-lint-comparison.json`。图谱固定候选审计exit0，111行/338断言，新增 `RootRequest/accept_interpretation/PlanHooks` 三项均PENDING；符号存在不证明行为或合入，见 `memory-refined-frozen-graph.log`。

详细计划见[本片计划](../superpowers/plans/2026-10-03-harness-request-interpretation.md)，接手见[inflight](../handoffs/inflight/feat-harness-output-provenance-1003.md)，取舍与工具沉淀见[日期交接](../handoffs/2026-10-03-harness-request-interpretation.md)。证据根 `closeout.json` 记录最终文档 tip、Memory 本地候选与关键原件 SHA-256；不改写第一片的 closeout。
