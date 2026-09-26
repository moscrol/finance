# RAG Startup Recovery And Safe Child Diagnostics

## 背景与身份

线上 #862 部署后的诊断发现：模型缓存恢复并不必然恢复 readiness。已注册 worker 自愈为
ready 后，模块和 API 生命周期仍保留同一次启动失败，导致聚合状态永久 failed。
另一层失败发生在 JSON 协议建立之前，进程级 stderr 原先被丢弃，无法辨认缺模块等原因。

本次从 `gitea/main@bbd53487f` 建独立树 `~/fwp-wt-rag-recovery-state-0923`，
分支 `fix/rag-recovery-state-0923`；不动脏主检出树、冻结 runtime 或生产知识库。
代码提交 `6c26041cb6600e43264603e6df8b56e20e44f4f5`。本文件及 inflight 是后续文档提交，
不把代码提交的收据改签为文档提交，也不称完整合入门禁已通过。

## 发现顺序

1. 新测试先复现 worker 已恢复而聚合状态仍 failed；同批缺失诊断断言为红。
2. 将配置检查失败留给 `kb_rag.prewarm`，构造失败留给 `rag_worker.prewarm`，
   已注册实例的失败留给 `PersistentRagWorker`；API 不再重复记录实例故障。
3. JSON 预热失败提取安全原因；进程级 stderr 用原 selector 同时排空，私有尾部最多
   4096 字节。新增 `WorkerExecutionError` 和 `last_error_diagnostic`，公开字段限于
   stage/reason/returncode/白名单 error_type；不保留原始 stderr 到异常或公开状态。
4. 原 transport 的 selector 替身只返回布尔，更新为真实事件形状；退出异常保留旧提示前缀。
   两条既有变异锚点因读取循环加一层缩进而同步调整，未删保护或更改验收目标。
5. 真实应用 lifespan + TestClient 验证缓存失败先 503，修复后由真实 readiness 端点调度
   自愈转 200；配置失败无 worker，探针不会自愈，修正配置并显式预热后才转绿。
6. 额外覆盖进程在写请求前已退出的 BrokenPipe 分支；测试资源清理需容忍关闭已断 stdin
   时再次抛 BrokenPipeError。该修正仅在测试 finally，不吞生产诊断异常。
7. 固定干净代码提交重跑相关回归与两套撤保护。全部临时变异树已由运行器正常移除。

## 取舍

| 方案 | 决定与理由 |
|---|---|
| 任何 worker 成功就清全局错误 | 否：会掩盖另一实例或尚无实例的配置失败 |
| 状态按恢复责任归属 | 选：实例失败只有一个所有者，实例恢复后无需跨层清第二份标志 |
| 暴露全部 stderr 或直接拼进异常 | 否：可能含查询、路径、凭据；公开诊断只允许固定字段和值域 |
| 独立 stderr 读线程 | 未选：现有 selector 已负责非阻塞 stdout，可同时排空两条管道；不增加线程生命周期 |
| 无界 stderr 缓存 | 否：保留私有末尾 4096 字节；关闭进程清空，恢复成功清空错误摘要 |
| 放宽 readiness / 退化 BM25 / 延长查询超时 | 否：不解决状态归属，且会掩盖启动失败；既有混合检索与代际门禁保持 |

`last_error_type` 仍标识父侧异常，子侧可识别的类型在 `last_error_diagnostic.error_type`。
未知类型为 null，不猜异常原文。尾部截断、没有标准异常行或退出码尚不可知时诊断可能不完整。
普通查询 WorkerResponse 的 stdout/stderr 合同不变；本次不为常规查询重做诊断投影。
管道并非空闲时持续读日志的服务，读取在请求等待期间发生；不宣称所有第三方后台输出策略均已验。

## 验证与原件

解释器均为主树 `.venv-workbench/bin/python`，没有加载生产模型或更新索引。

- 固定代码提交相关回归：413 passed，0 failed/error/skipped；包含新增 17 条，覆盖 RAG worker、
  transport、generation、keepalive、kb_rag、readiness 和完整 `test_workbench_api.py`。
- 干净树收据：`~/.finance-runtime/test-receipts/20260923T071402Z-6c26041c-53033ec65c38.json`。
  revision 全 SHA 一致，dirty=false，worktree_dirty_total=0，collected=413，解释器及依赖指纹已核对。
- 新增撤保护：7 组均产生目标断言红，还原后绿；整套基线及还原为 17 passed。
- 既有管道撤保护：9 组全部红→绿；整套基线及还原为 78 passed。
  部分旧组的红是预期异常未抛或传输异常，不把它们宣传为全部语义断言型覆盖。
- 原件根：`~/.finance-runtime/reviews/rag-recovery-state-0923/6c26041cb/`，
  `startup-mutations/results.json` 与 `transport-mutations/results.json` 均 complete=true，
  含固定 revision、命令、JUnit、diff、源文件还原哈希与空 final_status。
- 全仓 Ruff 和提交钩子均通过；未运行本候选全量 Python、前端及 E2E、完整 registry 合入门禁。
  本机另有其他任务的全量门禁运行，本次不争用生产模型或停止它们。

可复跑命令（在独立树根，`$PY` 为上述解释器；输出目录必须不存在）：

```bash
$PY scripts/review_probes/run_extraction_mutations.py --revision 6c26041cb \
  --definitions scripts/review_probes/rag_startup_recovery_mutations.json \
  --tests intelligence/tests/test_rag_worker_startup_recovery.py --output <新目录>
$PY scripts/review_probes/run_extraction_mutations.py --revision 6c26041cb \
  --suite rag-transport --output <另一个新目录>
```

## 线上与边界

2026-09-23 15:17 +08 附近只读复核：8792 health/readiness 均 HTTP 200；运行 revision
仍为 `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`，ready、missing_critical=[]、
任务 active=0/queued=0、RAG ready、model_load_count=1、last_error_type=null。
本次未重启、部署、切换软链、改账本、写生产 run 或更新 RAG 索引。

后续需要独立审查、最新基线整合及完整合入门禁；合 main 须用户确认。
生产模型缓存恢复、真实自然会话、资源余量和新版本部署仍须各自取得新证据。
#874、#858/#867 及 Engine B answer_status 不在本次修改范围；不因这次修复改判旧验收。

## 沉淀

复用已有变异运行器，只新增固定测试与 7 组定义，无一次性 /tmp 手工工具待迁移。
可复用方法是失败状态归属必须与恢复执行者一致，并用无关故障阴性对照限制清理范围；
共享记忆 `failure-state-must-follow-recovery-owner` 记录判据。没有新建通用部署器或另一套门禁。
