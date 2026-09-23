# RAG Recovery Lifecycle Followup

## 身份与范围

在初版 `6c26041cb` 的作者复核中继续检查预热、退役竞争与管道清理。
独立工作树 `~/fwp-wt-rag-recovery-state-0923`，分支 `fix/rag-recovery-state-0923`。
已将未发布的三个提交 rebase 到本轮拉取的 `gitea/main@27ca084f9ffcb9d148b749944beca340e5f4fa6c`。
固定代码候选为 `52a9bceb62390212e41d6c31786d660161ad5463`，初版代码在新历史中为
`af9f8b23c`。旧 SHA 收据保留历史含义，不改签为新候选；本篇是随后单独的文档提交。
未推送、开 PR、合 main 或部署；主脏树、冻结 runtime、生产索引均未修改。

## 发现顺序

1. 原预热只处理代际专用异常，恢复参数转换与保活线程启动在完整错误边界之外。
   已经 ready 的实例再次预热若在这些位置失败，调用抛错但聚合状态仍 ready。
   新增 generation / recipe / keepalive 三个注入用例，修复前全部复现错误就绪。
2. `close_all()` 移除注册实例后，旧引用仍可 query/prewarm；恢复线程可能已通过早期
   closed 检查，关闭之后才真正进入预热。两个直接复用用例和事件屏障固定的竞争用例
   修复前均复现子进程重生，包含不再受注册表管理的存活进程。
3. 将 closed 检查放进持锁的 query/prewarm 执行入口；将代际检查、恢复配方转换、
   实际预热与保活启动纳入实例错误处理。恢复配方先完整转换后一起替换，保活启动完成后
   才标 ready。不改变 `returncode == 0 && model_load_count > 0` 的预热成功要求。
4. 发现 selector 的管道注册在 try/finally 外。新增 stderr 注册失败注入，修复前
   `selector.close` 调用为零；将注册移入 finally 保护范围，避免系统资源泄漏。
5. 新增应用真实 lifespan 下保活启动失败的 HTTP 503 -> 200 测试；使用临时假 KB、
   轻量真实子进程，不加载 BGE 模型、不请求网络。上述补测共增加 8 条，启动恢复套件为 25 条。
6. 相关 421 条通过后提交补修，并整合本轮 main。对新固定 SHA 再跑组合回归和两套撤保护。
   新增五组定义复用现有变异运行器，无一次性执行脚本需要迁移。

## 方案取舍

| 方案 | 决定与理由 |
|---|---|
| 把遗漏异常重新锁存在模块/API | 否，会恢复初版的重复失败锁存问题；实例必须独占完整预热失败 |
| 只在恢复调度时检查 closed | 否，检查之后可能排队；在执行锁内再查才能拒绝退役后的工作 |
| 永久禁用所有 worker 注册 | 否，新的应用生命周期仍可创建新实例；只禁止旧实例复用 |
| 用 sleep 等待竞争发生 | 否，用两个线程事件固定“恢复获准 -> 关闭 -> 继续预热”的顺序 |
| 先分别写入恢复 argv 和 timeout | 否，第二步转换失败会留下半份新配方；完整转换后一起赋值 |
| selector 只保护读取循环 | 否，管道注册已使用系统资源，也必须处于清理范围 |

普通查询响应、混合检索、代际绑定、保活调度与超时策略不变；没有延长超时、退化检索或放宽 readiness。

## 已验证与证据

固定候选：`52a9bceb62390212e41d6c31786d660161ad5463`。
解释器：主树 `.venv-workbench/bin/python`，Python 3.12.13，依赖指纹 `3328bed61f3e21ea`。
证据根：`~/.finance-runtime/reviews/rag-recovery-state-0923/52a9bceb6/`。

- `related-receipt.json`：421 passed，0 failed/error/skipped，collected=421，dirty=false，
  worktree_dirty_total=0，dependency_gate_bypassed=false；含确切十个测试文件，日志及 JUnit
  分别为 `related.log` / `related.xml`。`scripts/main_gate_receipt.py` 身份复核通过。
- `startup-mutations/results.json`：12 组全部红 -> 绿，基线/最终还原整套各 25 passed。
- `transport-mutations/results.json`：9 组全部红 -> 绿，基线/最终还原整套各 78 passed。
- 两套 complete=true、final_status 为空，运行器正常退出并移除独占临时工作树。
  红集既有预期异常缺失，也有传输异常断言，不能宣传为所有用例都是语义断言。
- 全仓 Ruff、提交钩子、分层/路径字面量/字段合同检查通过；补修后的门页同步提交。
- 一次迭代命令误写 `test_rag_generation_identity.py`，exit=4、零执行；随后使用原收据的
  `test_rag_worker_generation.py` 等十个精确路径重跑。零执行收据不计入任何通过结论。

复跑仍使用初版文档中的变异运行器，将 revision 换成 `52a9bceb6`，输出目录必须新建。
初版背景与证据见 `2026-09-23-rag-recovery-state.md`，不覆写初版快照。

## 线上观察与未验边界

2026-09-23 15:58 左右，8792 readiness 一次 15 秒未返回；随后复查 health 200（0.158s）、
readiness 200（4.663s）、missing_critical=[]、RAG ready、model_load_count=1、last_error_type=null。
软链仍指向 `finance-workspace-3b7e473575b0`，服务/RAG PID 仍为 58014/58612，recoveries=0。
复查原件 `production-check.jsonl`；经 `notify_ops.py --no-desktop` 记录至 canonical alerts.log。
本轮未重启、切换、改部署账本或写生产 run。

宿主 swap 当时使用 11056 MiB，另有多项其他任务的全仓门禁；没有定位首次超时根因，
也没有停止无关任务。一次后续 ready 不证明资源余量或长期稳定性，本轮未重做任务队列验收。

本次是作者复核，不是独立审查。新候选全量 Python、前端/E2E、完整 registry 合入门禁未跑；
没有真实 BGE 模型、自然会话质量或候选部署验收。下一步先独审并固定届时 main 组合候选，
取得完整合入门禁；用户确认后才可合 main，部署再独立取证。不要重复旧 cutover 或运行 rag update。

## 沉淀

方法补入共享记忆 `failure-state-must-follow-recovery-owner.md`：错误边界必须覆盖完整生命周期，
退役状态必须在真正执行锁内复查，资源注册也受 finally 保护。门禁缺口已通过测试及撤保护落地，
不另建部署器或门禁工具；未扩大到共享记忆既有格式问题。
