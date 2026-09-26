# Runtime 重复恢复收尾候选

## 范围与来源

用户要求接手当前没有 agent 推进的工作，修复、测试并推进到可收尾；没有授权合 main 或部署。
本轮认领 #834 的 runtime 前向候选验收，在其评论留接手与进度记录，不改已有 owner 分支。
ReAct、历史证据、adaptive、研究尾单及生产发布由其他会话继续，本轮不接管。

- 工作树：`/Users/a77/fwp-wt-runtime-closeout-0921`
- 分支：`fix/runtime-closeout-0921`
- 主干基座：`79b11d4268a39e0c0ba1cca6e99fef46e338661e`
- 引入上游：#834 `cb16cd463db5c19b3187a5137009791082874653`
- 固定代码：`2f98a6a1fc4e9a30d5e501e904c60974eef6b5f8`

先 no-commit 合入固定上游，冲突为零；在独占树修复后用路径限定 squash 提交，保留内容而不制造 main 合入。
提交说明记录上游来源，不把全部 75 文件归为本轮原创。
上游自带 #831 测试生命周期/代码地图前置与 runtime P0/P1 切片，本候选不是仅一文件补丁。
本轮独有代码修改在 episode_restore.py；其余增量是测试、变异定义与门页说明。

## 发现顺序

1. 原存储/恢复定向 47P，未覆盖重复恢复；代码地图初始空，随后本树 build --full --postprocess minimal 成功，未据空图推断架构。
2. 新增三类场景、内存/JSONL 两种存储，修前 6F：
   - 模型已声明工具但未落派发意图，首次计划为 dispatch_tools，第二次变 model_turn。
   - 一批两调用只有第一条意图落盘，恢复重放第一条并收到结果后，第二条被跳过。
   - application_tool_call 没有派发意图时，重复恢复再次追加 tool_error。
3. 原因：resumable 把计划的 phase/reserved_ids 写成执行检查点；计划尚未执行，定位已经丢失。
4. 修复：没有合成事件不写状态；有合成事件只推进已确认事件前缀，保留原执行位置及定位 ID。
   应用调用先按 call_id 和 declaration 后的顺序点查已结算，避免重复补写。
5. 旧测试的 finalizing / 清空 reserved_ids 断言改成保留原执行定位；同步落盘、写失败直接传播、终态双确认要求未放宽。
6. 增补 ACK 写前/写后失败再读，以及两个全新 Python 进程回读；预算/授权/证据快照与其独立捕获前缀保持不变，缺当前授权仍拒绝。

## 决策与被否方案

| 方案 | 结果与理由 |
| --- | --- |
| 计划生成就推进 phase/清空 ID | 否。计划丢失或尚未执行时，再次恢复跳过真实待办。 |
| 从日志形状猜执行位置 | 否。仍以完整 EpisodeState 为入口，再按预留 ID 点查结果。 |
| 新增一套持久化 ResumePlan schema | 本切片不选。现有完整位置和点查可重算同一动作，无需第二份执行状态。 |
| 原执行位置不变，合成结算逐条确认 | 采用。只有执行者可写下一执行检查点；确认前缀可前进而不消费动作。 |
| 不保存任何恢复合成状态 | 否。已有保存确认合同保留；存储异常不得继续返回计划。 |
| 本轮顺带开放跨进程自动续跑 | 否。单写者、未知效果对账、剩余消息/查询/私有结果仍不完整，不能把计划当执行许可。 |

## 固定版本验证

以下只绑定 `2f98a6a1fc4e9a30d5e501e904c60974eef6b5f8`，不移签文档 tip、联合树或后来的 main。
Python 使用主树 `.venv-workbench/bin/python`，全量在干净独占工作树与净化环境执行。

| 检查 | 实测 |
| --- | --- |
| Ruff 全仓 | exit 0 |
| Python 全量 | 12945P / 87S / 2X，17 warnings，620.21s，exit 0 |
| 新重复恢复测试 | 11P，包含 Memory/JSONL、所有合法 crash 前缀、部分批次继续、ACK 丢失、新进程回读 |
| 新变异定义 | 5/5 拆保护后实际断言失败，逐项还原通过；前后全文件 11P |
| 原保存确认变异 | 7/7 拆保护后实际断言失败，逐项还原通过；前后全文件 18P |
| 前端 | lint/typecheck/build exit 0，组件测试 110P |
| 浏览器 E2E | desktop/tablet/mobile 共 34P / 2S，exit 0；两个 skip 为预设仅桌面绑定场景 |
| 注册表 | check-parseability/check/backfill-tables --check/generate-views --check 全 exit 0 |
| 提交前门禁 | 密钥/大文件/冲突/Ruff/层级/路径/字段/dataset/工具可达性/runtime目录全部通过 |

收据及变异原件：

- `~/.finance-runtime/test-receipts/20260921T132628Z-2f98a6a1.json`，dirty=false，failed/error=0。
- 收据校验 `--expect-revision 2f98a6a1fc4e9a30d5e501e904c60974eef6b5f8 --base-drift-max 5` exit 0（当时基座漂移 1）；不是 main 收据。
- `~/.finance-runtime/runtime-closeout-0921/repeatability-2f98a6a1f/results.json`，complete=true，含日志/JUnit/diff/字节指纹。
- `~/.finance-runtime/runtime-closeout-0921/confirmation-2f98a6a1f/results.json`，complete=true，同上。
- E2E 用独立 18891/18894、隔离用户态与现造测试库，无模型凭据；测试结束两端口无监听。

工具沉淀：复用现有 run_extraction_mutations.py，新增定义入 scripts/review_probes/；没有临时脚本替代正式门禁。
通用原则是“恢复判定不能提前消费待办”，已由重复恢复/ACK反例和变异测试锁住；不新造另一套 runner。

## 未完成与下一步

这是作者实施与工程验收，不是独立 Spec/Quality 审核或自然金融质量证明；本轮没有付费模型调用。
上游旧独立审容量中断不能由这些测试替代，旧真实研究 not_passed 不翻案。

1. 独立审本轮差异和前向候选，尤其执行位置保持与未来 driver 的交接合同；不未经授权重启付费审查。
2. 合 main 前重新冻结最新组合，跑对应门禁并等用户确认；本轮无 main merge，无 8792 部署。
3. 完整恢复仍需入口身份绑定、单写者/lease、未确认外部效果与费用对账、检查点后私有证据/消息/inbox现场恢复，再接实际 driver。
4. 本轮新进程测试只读磁盘并判下一步；没有杀掉真实生产运行、重新驱动模型/工具、或验证 exactly-once。
5. 不改判官模式，不声称防丢答案/长稿公开交付已经通过。本轮修的是恢复时丢待办与重复结算。
