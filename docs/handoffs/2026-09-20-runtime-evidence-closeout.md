# Runtime evidence closeout · 2026-09-20

固定基线 `a7f5cc06c087c2d9db896450bb6033851e8e5789`，独占树 `fwp-wt-runtime-evidence-closeout-0920`，分支 `fix/runtime-evidence-closeout-0920`。原 `fwp-wt-runtime-contracts-0918` 只读。代码提交 `7199db11`、`7c3b36b4` 已推到 Gitea，本文件是本轮决策快照，不替代独立复核。

## 背景与发现顺序

原新增快照已有独立回归与历史全量收据，但复核给出了两个合法输入反例。先以同一解释器、同一基线复制并执行原探针，输出保存在外部 `~/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-fix/`：

1. `spec/probe_future_evidence.py`：混合日期两格原本正常；全为截止外材料时，ephemeral 抛 ValueError，durable 返回 storage_failed，均只走到一次模型调用。
2. `standards/probe_mixed_duplicate.py`：同原件相同关联为正常控制组；父直接调用与子研究返回同hash、不同supports时，parent_calls=1、storage_failed。此脚本本身退出0，红的依据是原始JSON结果格。
3. `spec/probe_api_timer.py`：真实 Timer 已进入 claim_failed_run 并停在事件屏障，fixture drain 返回后仍存活，回调读到还原后的 FORESIGHT_USERS_DIR。

事实账本坚持 first writer wins 没有问题。缺口是 v1 仅用 presented_hashes 指向账本，无法表达本次请求的展示用途，也无法表达“材料晚于查询截止日”的提示。Timer 反例则是测试清理只等线程池，已触发的定时回调属于另一条线程，且可能已被 _forget 从任务表删除。

## 方案与取舍

| 方案 | 评价 | 结果 |
|---|---|---|
| 只比content_hash | hash不是日期、结构化观察、内部定位等全字段签名，会放过原件替换 | 否 |
| 修改首写账本以迎合展示 | 会改owner、targets、coverage与原件身份 | 否 |
| v2保存独立展示原件/顺序/分类 | 账本职责不变，完整读取可重建同一展示；增加私有快照体积 | 采用 |
| 所有未入账展示都放行 | 未知当前原件、无效日期也会绕过事实准入 | 否 |
| 完整解析真实日期且晚于固定cutoff才允许future_of_cutoff | 保留精确原提示，不凭标题推定；恢复账本仍只读entries | 采用 |
| v1读回即升级v2 | 会在EpisodeState读取时悄悄改schema/digest | 否；保留所读版本，仅新capture写v2 |
| 排空时只看当前timer表 | 已触发但被pop的回调仍会遗漏 | 否 |
| 枚举全进程线程或修改生产shutdown | 会等待其他任务或改生产停止策略 | 否 |
| fixture专属timer表记录全部owned引用 | 提交测试任务前安装，executor排空后无新Timer产生，再cancel/join所属Timer | 采用；跳过自身及未启动Timer |

v2读取和capture共用有限差异规则：已入账展示仅supports/contradicts可变，其他完整AgentEvidence字段必须与账本首写原件相同。展示关联不写targets/coverage。分类、原件、顺序均被整份摘要覆盖；未知/缺字段、重复身份、伪造覆盖、篡改观察或日期仍拒绝。恢复不append展示项，因此截止外原件不能被mark_output_covered认领。

## 验证与收据

- 指定 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，共12个相关测试模块，定向348P；覆盖快照、证据账本、store/restore、授权、子研究持久化、API配额/额度/排队与夹具生命周期。改动文件Ruff和提交钩子均绿。
- 新的真实Episode测试包含全部未来/混合日期及durable/ephemeral；真实GLM父混合batch也覆盖两模式，均可进入第二次父模型调用。模型与外部来源均为离线脚本，运行时、账本、存储及真实Timer为实际实现。
- 原future四格、mixed两格均转绿；展示读回等于完整对象及顺序，账本读回仍等于first-writer。
- Timer新测试先在旧helper跑出三红；修复后三夹具均绿。从另一线程发起teardown，确认它进入owned Timer的join且尚未完成；release后回调观察到测试环境，teardown完成。此前worker已完成且当前timer表为空，另一个无关Timer仍存活。原同步timer探针仅作红证据，其释放顺序不能作为修复后的绿判据。

六个有限撤保护（脚本和所有原日志均在证据目录；不重跑旧全矩阵）：

| 变异 | 红 | 还原绿 |
|---|---:|---:|
| M1只校验hash | 11F/2P | 13P |
| M2未知展示冒充future | 11F | 11P |
| M3v1读回升级 | 1F/4P | 5P |
| M4恢复时把展示写进事实 | 2F | 2P |
| M5去掉Timer join | 3F | 3P |
| M6仅等待当前任务表Timer | 3F | 3P |

`manifest.json` 绑定最终SHA、树状态、各源文件摘要、外部日志及固定版本的最终收据。测试使用FWP_TEST_RECEIPT=0停用共享latest写入，另留本分支外部收据，避免覆盖其他树的测试状态。最初新增mixed测试误用了晚于子任务cutoff的日期；同输入真正红证据以原独立mixed探针为准，已将新增测试日期改为2026-07-21后验证两模式。没有把失败尝试删成一次全绿。

## 边界与后续

本补丁尚待协调者安排独立Spec→Quality。没有创建PR、合main、部署、修改8792、真实模型请求或数据外呼；没有跑全仓四叶门禁，原11766P等历史收据不移签。它也不完成恢复driver、入口用户绑定、跨进程租约/单写者、未知效果对账，以及检查点后的全部查询/消息/私有结果现场。

可迁移经验已直接落实为测试和私有快照校验；本次外部撤保护脚本只是固定补丁的审计量具。harness-reference在开工事实中为脏树，未修改。共享项目记忆一行索引由协调者统一收尾，避免多代理同时改看板。
