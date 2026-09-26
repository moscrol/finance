# Runtime 单写者作者反例复核：运行器与驱动重入

## 背景与权限

用户在上轮提出先审 #843、补反例、再验最新主干组合后说“执行”。本轮推进作者反例复核与修复，未启动新的付费外审、自然模型、合并或部署。独立审查入口需要外部模型；本轮没有产生独立审查报告。隔离检出不改变作者身份，不能称作独立验收。

工作树 `fwp-wt-runtime-closeout-0921`，分支 `fix/runtime-closeout-0921`。开工干净 `b2e06f4ac27c2b6af7f4ea54f501272861d50293`，PR #843 open/WIP，review 列表为空。前轮运行时 `be6bc04f0` 的全量证据只对旧版本成立，见 [单写者快照](2026-09-21-runtime-single-writer.md)。

## 发现顺序

1. 核对 PR、工作树、验收流程，刷新代码地图至开工版本。固定旧版隔离检出位于 `~/.finance-runtime/reviews/runtime-writer-author-recheck-20260921/code`。原 writer 与 restore/live-drive 相关测试 26P，只证明已有覆盖通过。
2. 真实反例：同一 ContinuousAgentEpisode 驱动 task A、B，两把任务锁均成功，但共享 `_active_inbox` 被 B 覆盖。两者停在 model_pending 后关闭 A，实际 suspend 了 B 的 inbox；A 的旧 inbox 仍开放且接受落账。
3. 新测试覆盖上述反例、run/resume 双向争抢、执行中的 step/close 竞争和不同实例并行。原实现 7F/1P：跨任务未拒绝；执行中 generator.close/next 抛 ValueError，原实现异常清理还会错误标 finished。最初一次 inline close 探针因 IndentationError 未执行，不作为证据；后续回归和撤保护才是有效证据。
4. 新增非阻塞运行器实例控制锁，同时包住任务 writer；新增驱动操作锁，竞争者进入状态修改/异常清理前即抛 EpisodeWriterBusy。新增异常释放测试，合计12项新回归。原任务锁、身份/前缀验证、inbox 排空合同保持。
5. 扩展运行时迭代623P/3S/1X、全仓Ruff通过，随后冻结 `9fbcc9196a6834718a81c0bb11a8d6f495508b1d` 并推送。该提交含实现、测试、门页与变异定义五文件。
6. 固定提交独占树跑完整 Python、前端、registry 和四组撤保护。测试期间不修改该树；全部结束后才写本交接。

## 决策与被否方案

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 只保留按 task ID 的 writer | 不能约束同实例共享 inbox/取消信号，不同任务锁各自合法仍串线 | 否 |
| 同一运行器非阻塞控制锁 + 原任务锁 | run/manual_drive/resume 完整持有；忙碌不等慢模型，失败可释放；不同运行器/任务仍并行 | 采用 |
| 全局锁 | 串行化不共享状态的不同运行器，扩大争用 | 否 |
| 把全部运行器状态改成任务映射 | 可支持单实例多任务，但扩大状态、取消及回调合同，当前不必要 | 不在本片实施 |
| 让 Python 生成器自己拒并发 | ValueError 进入原异常清理，将活驱动标结束；拒绝并发不应污染原操作 | 否 |
| 驱动 step/close 共享非阻塞操作锁 | 执行中竞争抛 EpisodeWriterBusy，原驱动继续持有任务所有权，不改 finished/outcome | 采用 |
| 把 close 作为在飞模型取消接口 | 生成器执行中不能关闭，也不能撤回已发送外部请求 | 否；须等当前 step 返回后 close |
| 隔离检出叫独立审查 | 仍为同一作者，认知与测试设计不独立 | 否；只称作者反例复核 |

`Lock` 而非可重入 RLock 用于控制/操作互斥：同线程回调再次驱动也必须被拒。inbox 投递/spool 原有 RLock 不变，那里回调读取需要可重入。

## 验证与收据

解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python 3.12.13，依赖指纹 `3328bed61f3e21ea`。固定干净 `9fbcc9196` 的完整结果：

| 检查 | 结果 |
| --- | --- |
| Python全量 | 12980P / 87S / 2X，17 warnings，1035.63秒；exit_status=0 |
| Ruff | 全仓通过 |
| 注册表 | parseability/check/tables/views 四项通过 |
| spec台账对账 | exit 0；反向98条warning，不当新修复 |
| 前端 | frozen install/lint/typecheck/test/build/E2E 六步exit 0；组件110P，E2E34P/2S |
| 撤保护 | 新重入5 + writer9 + 重复恢复5 + 保存确认7，共26项逐项红后还原绿；四份complete=true、final_status为空、文件SHA256还原一致 |

全量收据 `~/.finance-runtime/test-receipts/20260921T161050Z-9fbcc919.json`，dirty=false、worktree_dirty_total=0，精确revision、解释器、依赖校验通过；基座漂移2 <= 5不代表组合验收。

证据根 `~/.finance-runtime/reviews/runtime-writer-author-recheck-20260921/`：
- `python-9fbcc9196.log`：完整输出。
- `frontend-9fbcc9196/frontend.json`：六步退出码与日志哈希；首尾身份一致且干净，六份日志SHA256回验通过。
- `reentry-9fbcc9196/results.json`、`writer-9fbcc9196/results.json`、`repeatability-9fbcc9196/results.json`、`confirmation-9fbcc9196/results.json`：定向红绿与还原记录。
- `ruff-9fbcc9196.log`、`registry*-9fbcc9196.log`、`ledger-crosswalk-9fbcc9196.log`：辅助检查。

原版本26P收据 `20260921T154232Z-b2e06f4a.json`；新增反例7F/1P为迭代脏树收据 `20260921T154448Z-b2e06f4a.json`；扩展623P/3S/1X为 `20260921T155129Z-b2e06f4a.json`。这些不冒充提交后的完整验收。耗时单样本且同机并发环境变化，不宣称性能提升。

本轮全量PID69176已退出，18891/18894无监听。未停止其他会话进程，8792未改。旧版只读检出保留供复查。

## 主干与待审范围

fetch后 `gitea/main=e82717d9a7c3dfa811a4538bd44985b61258355a`，与固定候选merge-tree exit 0，树 `ff4a595b2185482bd8ea59c2fe2d21ac9c8c724f`。树diff仅 `docs/learning/ledger-map.md` 两行替换；未创建/测试实际合并提交。没有把候选全量移签该树、最新主干或后续文档tip。

独立审核应覆盖整个PR及前置来源，不限本轮两个反例：任务锁与实例锁生命周期、旧inbox与关闭排空、run/resume双向争抢、异常与跨线程操作拒绝、原状态不被竞争者污染、身份与磁盘前缀、恢复判定不授执行许可。建议独立审核者自行构造未被本轮测试命名诱导的反例；付费调用须先获授权。

仍仅合作式本机保护，不覆盖旧版本/raw写入/跨机/逃逸外部请求。入口用户绑定、未知效果费用对账、检查点后私有证据/查询/消息现场与执行器接管仍待。没有证明重启模型工具并完成研究或exactly-once，金融质量、判官超时保稿和自然长答不在本轮通过范围。

## 工具与后续

新增回归与5项撤保护定义已入仓，沿用现有变异运行器，不增重复脚本。稳定原则回写 `agent-memory/10_knowledge/recovery-plan-is-not-execution.md`：锁范围覆盖实际共享状态，拒绝方不修改原操作状态。本片未新增通用构建工具，不改 harness-reference 工具清单。

下一步先取得真实独立审查并修反例，再冻结最新组合验合并门禁；合并和部署分别等用户确认。不要自动启动新付费审查、重跑自然模型、切生产，也不要凭工程绿开放自动续跑。
