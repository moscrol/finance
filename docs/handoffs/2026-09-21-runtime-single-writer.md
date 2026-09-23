# Runtime 本机单写者补强

## 背景与版本

用户要求继续推进 runtime 候选。前轮已经修复重复恢复提前消费待办，但恢复判定、活驱动和修订仍可能各自读取同一旧现场后写账。本轮补控制操作的独占所有权，不开放跨进程自动续跑，不接管 ReAct、历史证据、adaptive、研究尾单或部署线。

- 工作树：`/Users/a77/fwp-wt-runtime-closeout-0921`，分支 `fix/runtime-closeout-0921`，WIP PR #843。
- 运行时固定提交：`be6bc04f0ee915f32450b6f724b63e532120dcc7`，已推送。
- 目录说明修订：`7a2545025d153c3a57e08b7b3b0c7a89986df1ec`，已推送；相对前者仅改竞态目录一条说明字符串。
- 前轮来源和重复恢复决策见 [重复恢复快照](2026-09-21-runtime-repeatability-closeout.md)。其旧收据仅对应 `2f98a6a1`，不覆盖本轮。
- 未合 main、未部署 8792、未启动新付费外审或自然模型复验。作者测试不是独立审查。

## 按发现顺序

1. 增加 `EpisodeStore.writer()` 和 `EpisodeWriterBusy`。Memory store 按存储对象与 episode 互斥；JSONL store 在 episode 目录持有不删除的 `.writer.lock`，使用非阻塞 POSIX `flock`。Fenced store 和 conformance oracle 转发所有权，不把竞争拒绝误判成存储故障。
2. `restore_episode()` 在 load 前取锁，连只返回计划、读取终态也遵守；检查 checkpoint 的 episode 身份。活驱动暂停在 model_pending 时，第二个恢复入口抛 `EpisodeWriterBusy`，不写账。
3. `manual_drive()` 经 `_drive_owned()` 覆盖整个生成器生命周期；新 run 拒绝已有日志/状态；正常完成、异常和显式 `close()` 释放。`close()` 不伪造 finish。任务 ID 规范化与 ledger 一致。
4. 同进程 `resume()` 校验 store、context、goal、previous outcome 身份；加锁后比较磁盘事件/状态与旧 ledger，拒绝过期修订，防拿另一存储的锁保护旧账本。
5. 早期清空正常完成后的 `_active_inbox` 导致三条兼容回归。修正为正常完成保留已关闭 inbox，迟到输入仍返回 inbox_closed；异常退出撤下活动入口。
6. 旧 inbox 引用也是写入口。新增 `suspend()`，在释放 episode 所有权前等待在途投递完成、关闭旧 inbox，保留未决消息。`send()` 与 spool ingest 共用可重入 `_spool_lock`，避免另一把 delivery 锁与 spool 锁反序死锁。
7. 更新 restore-vs-live-drive 夹具；pending inbox 恢复用独立 crash snapshot。新增 23 项参数化 writer 回归和 9 项撤保护定义，含真实驱动子进程被杀后锁释放及重新判计划。
8. 冻结 `be6bc04f0` 完整验证后，发现竞态目录仍写活驱动时返回 retry_model。仅修该说明为 EpisodeWriterBusy，单独提交 `7a2545025` 并跑干净定向 44 项；未修改运行时逻辑。

## 决策与被否方案

| 选择 | 被否方案 | 理由与边界 |
| --- | --- | --- |
| 控制入口先锁再读，完整操作持有 | 只锁 append/put_state | 后者允许两个控制者先读同一旧位置再轮流写。 |
| 本机 POSIX 内核文件锁 | 单独依赖超时 lease | 长模型调用可超过 lease，旧调用仍活着时会出现双写。内核锁随进程退出释放；不推广为跨机合同。 |
| 锁文件不删、不替换 | 退出时清理锁文件 | 新旧 inode 可分别被锁住，同路径不再代表同一所有权。 |
| 持久 store 缺 writer 就拒绝 | 静默退为空锁以兼容旧实现 | 缺保护的持久后端不能冒称支持该合同。无持久 store 的本地运行不借此获得跨进程保证。 |
| 身份和磁盘前缀同时校验 | 只核对 task_id | 旧 ledger 或外来存储/outcome 不能凭相同文本 ID 获得修订许可。 |
| 退出先排空投递并 suspend | 先释放所有权再关闭 inbox | 旧入口会在新控制者已接管时继续写账。未决消息保留，不伪造消费。 |
| 投递与 spool 共用 RLock | 新增独立 delivery 锁 | send 回调可查询 pending，多锁反序会死锁；同一可重入锁保持一致顺序。 |
| 计划返回即释放本次锁 | 把 ResumePlan 当执行许可 | 真正执行器须重新取得所有权并复核现场；锁不证明未知请求未执行、未计费或只执行一次。 |

## 固定版本验证

解释器始终为 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
下表完整工程读数仅绑定干净 `be6bc04f0ee915f32450b6f724b63e532120dcc7`，不移签到说明修订、交接 tip 或组合 main。

| 检查 | 结果 |
| --- | --- |
| Python 全量 | 12968 passed / 87 skipped / 2 xfailed，17 warnings，1577.66s，exit 0 |
| Ruff 全仓 | exit 0 |
| writer 新测试 | 23 passed，含跨实例/进程、真实驱动杀进程、投递关闭交错、身份与旧前缀 |
| 撤保护测试 | writer 9、重复恢复 5、保存确认 7，逐项实际断言红后还原绿；三套 complete=true，文件字节指纹恢复 |
| 前端 | frozen install、lint、typecheck、test、build、E2E 六项 exit 0；组件 110 passed；浏览器 34 passed / 2 skipped |
| 注册表 | check-parseability、check、backfill-tables --check、generate-views --check 四项 exit 0 |
| 提交门禁 | 全部适用项通过 |

原件路径：

- Python：`~/.finance-runtime/test-receipts/20260921T151812Z-be6bc04f.json`；全量目标为本树根，dirty=false，worktree_dirty_total=0，exit_status=0，failed/error=0。
- 完成时运行 `scripts/check_test_receipt.py <上述收据> --expect-revision be6bc04f0ee915f32450b6f724b63e532120dcc7 --base-drift-max 5` 通过，基座漂移 1。后台 PID 94294、父 shell 94292 与 tracker 21975 均已退出。
- 全量日志：`~/.finance-runtime/runtime-closeout-0921/python-be6bc04f-clean.log`。
- 变异：`~/.finance-runtime/runtime-closeout-0921/{writer-mutations,repeatability,confirmation}-be6bc04f/results.json`。逐份核对精确 revision、complete、还原字节指纹与干净 final_status。
- 前端：`~/.finance-runtime/runtime-closeout-0921/frontend-be6bc04f/frontend.json`。前后 SHA 一致、dirty=false、identity_stable=true、complete=true；六份日志 SHA256 与收据一致。隔离端口 18891/18894 已退出，未动 8792。
- `7a2545025` 仅目录说明改动：`python -m pytest -q intelligence/tests/conformance/races intelligence/tests/test_episode_writer.py` 为 44 passed；收据 `~/.finance-runtime/test-receipts/20260921T152022Z-7a254502.json`，dirty=false，精确 SHA 和覆盖目标校验通过。这不是该提交的全量收据。

验证异常也保留：第一次全量受 600 秒上限中断，约 84%，不能计通过。完成的重跑使用净化环境、完整范围、`faulthandler_timeout=120`；期间观察到真实知识库检索子进程及同机其他全量并行，不据单次时长声称性能退化或改善。新变异定义未提交时对旧 HEAD 的 FileNotFoundError 不算测试结果，相关干净临时 worktree 已核查并移除；早期错误测试路径的零执行也不算通过。

最新核查主干 `028a251a1b2ca98245326a6b59376f4f7f8e5e81`。对 `be6bc04f0` 的 merge-tree 无冲突，模拟树 `b9f816b81f87b4ee19d735dd4650a48ef842b753` 与该提交仅差 `docs/learning/ledger-map.md`。这不是实际合并，也不是最新组合的验收收据。

## 工具与知识沉淀

复用正式变异 runner `scripts/review_probes/run_extraction_mutations.py`，新增定义为 `episode_writer_mutations.json`，没有另造临时 runner。并发故障与保护失效均落成可执行回归，不只写操作提示。

跨项目原则补入共享 `10_knowledge/recovery-plan-is-not-execution.md`，项目能力图谱和一行交接指针同步。没有修改 harness 搭建工具，因此不新建第二份 KIT 工具清单。内核锁选型保留为有明确适用条件的方法，不包装成通用跨机锁库。

## 下一步与禁区

1. 独立审 #843，重点看生成器关闭/异常释放、旧 inbox、身份与修订前缀、恢复计划与未来执行器的交接；作者工程绿不能代签。启动付费外审仍需用户授权。
2. 自动恢复 driver 仍需入口用户绑定、未知外部效果及费用对账、检查点后私有证据与查询/消息现场、执行器重新取得所有权的合同。当前测试杀的是本地真实驱动子进程，之后仅判恢复计划，未证明重新驱动模型/工具完成。
3. 锁仅保护合作式本机新代码。不约束旧进程、直接 append/put_state、跨机共享存储、逃逸线程或已发出的外部请求；获取锁不等于 exactly-once。
4. 合 main 前冻结最新组合并跑对应门禁，等用户确认；不把 merge-tree 无冲突或作者候选全绿当成合并授权，不自行部署 8792。
5. 不改变判官策略，不删减长稿；保稿公开交付、自然金融质量和其他线旧 not_passed 不由本轮翻案。
