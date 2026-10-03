# P1b 第二片日期交接：根请求锚点与目标解释版本

## 背景

P1b 第一片 `c18d6f0fe` 已把输出来源和必需性贯通到装配、连续 Episode、SDK 初始输入及履约投影，但仍缺一个边界：模型可以理解错用户目标，且 repair 合同会改变执行投影；如果直接把当前合同当作原请求，修复就会漂移根身份。本片只处理“固定根请求 + 独立版本化的目标解释”，不把完整题意重装配一次性塞进同一改动。

固定代码 pin 是 `e859b5ff9508ab1297dd15edf8a9fa3e166a9b7f`。工作树 `/Users/a77/fwp-wt-harness-output-provenance-1003`，分支 `feat/harness-output-provenance-1003`。本地完成，无推送、合并、部署和真实模型请求。

## 按发现顺序

1. 先发现既有 `apply_unreachable_downgrade()` 会改变执行合同。若每次从当前合同生成 request ref，repair 会把根请求改写。因此新增冻结值对象 `RootRequest`，只在初始上下文创建时从可信合同捕获；`replace(context, contract=repair_projection)` 保留原根。
2. 题意解释不应和 PLAN revision 共用计数。新增 `InterpretationProposal` / `TaskInterpretation`：提案以根 request ref 和当前解释 revision 为基线，接受后只递增解释 revision；普通研究计划变化不清空解释。
3. 解释提案不能成为权限入口。提案只含 `request_ref/base_revision/goal/reason`，未知字段拒绝；不调用 factory，不新建预算，不修改输出、材料合同、截止、取消、已消费账或证据原件。题型、主体、时间窗留到后续合同切片。
4. 发现 provider 返回后 SDK 可能已经执行本地工具，所以不能只在最终 runner 返回后解析。通过 `PlanHooks(RunHooks)` 在 provider 响应后、本地工具派发前接纳；解释与工具同包整包拒绝，先回执再派工具。
5. 连续 Episode 和参考 loop 同步了接纳回执、事件元数据及 repair 关闭语义。SDK PLAN-only 续段共享一次总 timeout、递减轮次和 provider history；timeout 后同 session repair 保留已接受解释，但没有新增磁盘恢复执行器。
6. 授权快照需要区分旧实物和新增状态：无解释且根未分离时保 schema v1；有解释或执行投影已脱离根时使用 v2，携带 `root_request` 与可空解释。旧快照只精确验证入口当前授权，不迁移或重签。
7. 固定 pin 全仓复跑前曾在 900 秒命令上限中断，未产生最终收据；换新证据目录和 basetemp、延长到 1800 秒后完成，才签固定 pin。变异审计另以逐项红/绿、还原 SHA 和 Git blob 复核，避免把部分参数化红误写成全红。

## 非显然决策与被否方案

| 决策 | 被否方案 | 理由 |
|---|---|---|
| 根请求从初始可信合同冻结 | 每次从当前 repair 合同重算 | repair 是执行投影，不是用户原文；重算会让修复漂移身份，且不可逆地污染恢复依据 |
| 解释 revision 与 PLAN revision 分开 | 每次 PLAN 都清空/递增解释 | 研究步骤变化不等于题意变化；合并计数会制造无意义的目标变更或倒退 |
| 复用 PLAN 作为唯一提案入口 | 新增强制解释调用或第二协议 | 旧 PLAN、无 PLAN、直接取证路径仍需兼容；新增入口会扩大协议面而非解决接纳顺序 |
| 提案只开放 goal | 同片开放题型、主体、时间窗、输出和 grounding | 这些字段会重装配合同、权限和恢复身份，必须有独立版本/审计边界，不能借解释提案越权 |
| 同包解释+工具整包拒绝 | 先执行工具、事后解析解释 | 工具副作用已发生，无法回滚；先接纳再派发是可验证的顺序 |
| SDK 在 provider hook 接纳 | runner 最终返回后解析 | 最终返回时工具可能已执行，顺序已失守；真实 SDK + 离线模型证明 hook 位于本地工具前 |
| v1 保原形、v2 携带根和解释 | 自动迁移/重签旧快照 | 迁移会把新声明伪装成旧授权；恢复必须精确比较入口当前授权，不把保存内容当新许可 |
| 延长一次全仓门禁 | 过滤慢测试或借用第一片数字 | 第一片和提交前 dirty 读数不属于本 pin；范围收窄会破坏收据身份，必须完整重跑 |

## 验证与收据

- 固定 pin 全仓：Ruff 通过；pytest `18,876 passed / 76 skipped / 2 xfailed / 0 failed / 0 error / 18 warnings`，耗时 `1072.80s`。收据 `~/.finance-runtime/reviews/harness-request-interpretation-20261003/full-2-e859b5ff9/gate-1PINvBdI/pytest.json`。
- 收据复核：`check_test_receipt.py --require-full-scope --expect-revision e859b5ff9508ab1297dd15edf8a9fa3e166a9b7f` exit 0；`collected=18954`，读数和收集面对平，dirty=false、解释器/依赖一致。
- 本片变异：`mutations-e859b5ff9/results.json` 与 `mutation-audit.json`；12/12 定义被捕获，42P→42P，0 collection error/skip，变异树移除，还原字节等于固定 pin Git blob。SDK 拒绝包 6F/8、连续反馈 1F/4、连续 repair 1F/2、finalizer 1F/2，不能读成所有参数化变体全红。
- 固定 pin 定向复验：新检出的 e859b5ff9 上解释、Workbench HTTP、finalizer 三文件 **70P/1 warning**，10.64s；见 `pinned-final-related.log`/XML/收据。HTTP 新用例贯通会话入口、解释回执、观察取证、答案和持久化，但模型/来源/判官均脚本化，不是自然模型金融质量证据。`http-2.log` 的58P仅是提交前迭代，不能移签。
- 原始 900 秒中断日志 `full-e859b5ff9.log` 保留；不能把中断当失败根因，也不能把它当通过。文档 tip 上复核旧收据被正确拒绝（`final-receipt-check.log`）；临时检回原 pin 后 `pinned-recheck-receipt.log` exit 0，临时树已移除。

## 未完成与下一步

未完成：题型/主体/时间窗在线修订；完整合同与恢复投影版本分离；旧词面/默认槽退出；跨进程 SDK 磁盘恢复执行器；前端、浏览器 E2E、GitHub Actions、独立规格/代码审查、真实金融质量。代码地图为空/不新鲜时不作架构覆盖结论。Memory 只有独立本地候选树，未写共享主目录。

下一片应先为合同/恢复版本边界建立独立设计和反例，再决定是否允许更多解释字段；必须继续保持“解释修订不能删用户义务、撤销权限、返还预算或抹掉历史”。如改代码，重新建立新 pin、全仓 full-scope 收据和对应撤保护；不要把本片收据移签到新 tip。

## 工具沉淀盘点与 Memory

- 12项撤保护定义及42项解释测试已进仓，HTTP/finalizer消费者也有正式测试；复用 `run_extraction_mutations.py`，没有只在临时目录存在的产品探针。
- 保存失败、SDK派发前时点、跨段总额度和repair根漂移是本片发现的承重点，已落实到产品与回归；字节还原核验消费既有 runner 的结果，不另造平台。
- 可迁移原则“根请求、模型解释、执行授权分开；副作用前先接纳”补入 Memory 现有闭环原则页。解释是否正确仍要语义判断/澄清，不适合把自由文本目标硬化成关键词门；这部分保留为手法和后续质量任务。
- 仅修改独立候选树 `~/agent-memory-wt-harness-output-provenance-1003` 的现有项目索引、能力图与闭环原则，候选 tip 以本片证据根 `closeout.json` 为准。共享主目录有自动同步，本轮未写入、推送或整合它。
- Memory lint基线及候选均46错/31警告，错误列表相同；只有原项目页超长警告的字节数改变。能力图只检查符号，不证明行为或合入；新增锚点使用 `RootRequest/accept_interpretation/PlanHooks`，避免以老类名存在冒称新功能已合。

## 明确不要做

- 不把 request ref 当认证、用户身份或解释正确性证明。
- 不在 repair/deadline flush 中隐式接纳尚未回执的新 PLAN。
- 不用解释提案扩大工具、材料、历史或输出权限。
- 不恢复 R17/R19、不放行正式 240，不发真实模型请求；自然质量另行授权验收。
