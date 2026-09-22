# Runtime 行为合同 P0：保存失败与截断边界

## 范围与版本

- 依据既有 OPT-08；前置审计在 `baseline/runtime-absorption-audit-0918:docs/handoffs/2026-09-18-pi-dsh-runtime-absorption-audit.md`。
- 实施分支 `fix/runtime-contracts-0918`，基线 `gitea/main@0a1cb8c4`。
- **本次验证的代码：`4882306200e17b14783a29b79f531ca8be0b09b1`，干净树。** 后续文档提交不能冒充新代码全量收据。
- 用户授权列 TODO 并实施；未 push 金融分支、未合 main、未部署、未中断生产、未调用真实付费模型。
- 自有 runtime + ResearchHarness 保留，不叠加 pi/dsh 两套框架。P0 是活进程故障隔离；P1 恢复/子存储/回读/插话、P2 工具属性另验。

## 按发现顺序

1. 审计反例：必需记录写失败仍 completed；明确截断的工具回复被执行。先锁这两种失败，避免恢复 driver 放大未知效果。
2. Ledger 区分 `ephemeral/durable/failed`（旧调用方默认 `unknown`）；关键保存失败停用 store，停止新模型、工具、finalizer、repair、子研究效果，保留已经发生的结果与 usage。进度 sink 失败仍不夺执行权。
3. `finish` 同步冲刷既有结算，再确认 `done` 检查点，之后才广播完成。写后抛错仍 failed/uncertain，不能回滚落盘前缀伪造「未发生」。内存 `persistence_failed` 不是保证已落盘的故障记录。
4. Workbench 的初始、缺口修复与补全 candidate 都检查保存失败；不再被语义判官、句数限制或「保留更好答案」吞掉。草稿、证据、费用只在私有工件，`learning_eligible=False`；公开失败说明，事件仍走 `project_durable_events`。
5. 真装配测试发现 Episode 与注入模型拿的不是同一取消对象。装配根共享执行 `CancelSignal`，但 adapter/orchestrator 仍使用原用户谓词：内部 hook/storage_failed 不是用户点停。保留 first-cause-wins。
6. 工具队列在 runner 前再检查取消；保存失败允许已收结果私有结算，但缓存发布守卫仍拒绝。未决 future 明示 `storage_failed_inflight`，不无限等线程，不退还已提交但效果未知的槽位，不允许迟到结果改已返回 outcome。
7. Inbox 的 inserted/claimed/discarded 同步冲刷；失败不假 ACK、不删 spool、不伪造送达，未结算队列留作诊断。不是已完成重启恢复。
8. 真 HTTP 装配（叶子为 double）验证 Run/assistant failed、私有稿仍在、无 judge/repair。新增 SSE 竞态：第二次读到 cursor 之后的终态，须先发给客户端，不能直接关连接。
9. 模型 envelope 将 `length/max_tokens/content_filter` 贯通至 ModelTurn；即使参数/FINAL_JSON 可解析也清调用并报 incomplete，不隐藏重试或换 provider。保留 usage/停止原因；缺元数据不补造 stop。流式/非流式、legacy/provider-chain、直接 ModelTurn、finalizer 均有测试。

## 非显然取舍

| 决策 | 被否方案 | 理由 |
|---|---|---|
| 关键保存失败 fence，新效果停止 | 所有通知失败都中止；或所有 store 错误都只告警 | 进度通知不是执行所有者，恢复记录却决定后续是否安全重做 |
| 已收结果私有保留，未知结果明确未知 | 取消后清空所有结果；无限等所有线程 | 清空会抹掉费用/证据，等待不可终止线程会破 deadline |
| 执行取消共享，用户取消独立 | 上下游各包布尔谓词；内部故障当 user cancel | 前者丢本地首因，后者歪曲产品终态和修复策略 |
| finish 冲刷 + done 确认后发布 | 先发完成再保存；改写已落盘历史 | UI 完成必须有保存依据，不确定前缀不得被美化 |
| Inbox ACK 需要落盘确认 | 入内存即 accepted；失败删除投递副本 | 入箱/认领/送达是不同事实，必须能对账 |
| 明确截断直接失败 | 能解析 JSON 就放行；自动重试掩盖截断 | 语法合法不证明意图完整；重试可能重复计费 |
| 同一固定 revision 做变异与四叶 | dirty 局部绿或审计旧收据当验收 | 测试结果是带条件事实，不是仓库的永久属性 |

## 验证与收据

证据根：`~/.finance-runtime/reviews/runtime-contracts-48823062/`。
解释器：主树 `.venv-workbench/bin/python`，Python 3.12.13；pnpm 10.12.1。

| 检查 | 结果 | 原件 |
|---|---|---|
| 全仓 Ruff | exit 0 | `ruff.log` |
| 全仓 pytest | **11495 passed / 81 skipped / 2 xfailed**，858.22s，17 warnings | `python.log`；`~/.finance-runtime/test-receipts/20260918T091215Z-48823062.json` |
| 前端 lint / typecheck / test / build | 均 exit 0；Vitest **107 passed** | `frontend-*.log` |
| 浏览器 E2E | 修正启动变量后 **34 passed / 2 skipped**，58.9s | `e2e-corrected-ports.log` |
| registry 四项 + ledger/spec crosswalk | 均 exit 0 | `registry-*.log`、`crosswalk.log` |
| 13 项撤保护变异 | 每项真实执行后断言失败，恢复后绿；baseline/restored-full 各 **167 passed** | `mutations/results.json`、逐项 JUnit/log/diff/字节指纹 |

收据核验用相同虚拟环境执行 `scripts/check_test_receipt.py <receipt> --expect-revision 48823062 --require-target <实施树>`，七项通过。曾误用宿主 python 检查而提示三项环境不符；改用正确解释器即一致，不是重跑测试或改收据。SessionStart 的全局 latest 可能被其他分支覆盖，应使用上面精确文件。

**保留失败**：首轮 E2E 1 failed / 33 passed / 2 skipped；服务改到 8894，但 spec 的 `RE06_E2E_URL` 未传，仍访问 8794 连接拒绝。补传 URL 后同 revision、同断言通过，未占用/停止其他服务。首轮日志 `e2e.log` 保留。离线 pnpm install 提示忽略 esbuild 安装脚本，但本轮实际 build 已通过，不靠修改批准名单绕过。

变异 ID：terminal_completion_fence、pre_model_dispatch_fence、tool_intent_fence、terminal_flush、neutral_completion_boundary、nonstream_finish_reason、provider_no_hidden_retry、inbox_no_false_ack、inbox_flush_before_ack、assembly_cancel_propagation、received_tool_result_retention、queued_runner_fence、sse_terminal_delivery_race。定义在 `scripts/review_probes/runtime_contract_mutations.json`，复用 `run_extraction_mutations.py --definitions ... --tests ...`。`restored-full` 指全部所选的三个测试文件，**不是仓库全量**。零执行/collection error 不接受为杀死变异。

早期 607P/447P 等 dirty 定向读数互相重叠，不加总，也不替代上面的冻结验收。

## 已知边界与下一步

- 磁盘写后确认丢失可能留下完成前缀或 terminal state；内存失败收据未必重启后可见。本次不解决外部 exactly-once（效果恰好一次）、未知费用或崩溃续跑。
- 在飞/排队工具用可控 Future 确定性验顺序，不是外部进程强杀/线程排空实测；新 HTTP 测试实际运行装配、API、存储与 SSE，但模型/工具是替身。
- `restore_episode` 仍只判定/合成 `ResumePlan`；下一批先检查快照足以恢复哪些状态，再写 driver。已确认模型/工具不能重做；未决模型重试的费用须诚实记账；未知写效果必须先对账。
- 子研究完整 store、压缩 E 号原件回读、Workbench 插话仍未实施；不擅自开启压缩或自动恢复，不扩大 SDK 后端合同。
- P2 须逐工具声明 replay/parallel/exclusive，既有 capability/IO 门不替代它。
- 工程四叶通过不是独立复核或研究质量胜出；同模型同冻结数据同预算对照另立收据，合 main/切生产仍需用户确认。

## 工具与知识沉淀

本轮没有第二套 mutation runner：扩展既有固定 revision runner 接仓内 JSON 定义与测试列表，失败保留还原树与证据，成功删自建临时树。通用失败形状是「只断言最终状态，漏掉上游同一信号是否真传到消费者」以及「存储可见不等于客户端已送达」；已落回归及撤保护验证，不仅写提醒。路由摘要/通用正文另在 harness-reference 的 `docs/runtime-contracts-0918` 分支维护，不碰主树他人的 `BUILD.md`。
