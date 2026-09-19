# KB guarded maintenance — 独立 Spec 增量审查（ea7e113e）

**结论：Spec 仍需修正，尚不 PASS。** 37437 报告的两个新发现和作者自报的根重叠已关闭；整代 publisher 已有具体实现。新增独立复现三个边界，其中前两项来自作者自审线索，第三项在独立发布故障探针中发现。只需修这些可达问题后复验，不要求执行真实上传或生产切换。

## 固定输入与验证

- 候选 `ea7e113e99dfc611252b5c629845e8d9c23dfc0c`，增量基线 `37437e1a377eaf30acb39ca6d16dcf44b131d914`；完整需求基线仍为 `1254224be89e2c4974350b7f3e985dbedb5dc043`。
- [独立 detached 树](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-ea7e113e-tree)开始与探针后 clean；不读取漂移作者树、不改源码、不合 main。
- 主仓 `.venv-workbench/bin/python`，外置访问日志与 pytest 临时目录。原定向测试文件未经修改运行：**56 passed in 32.37s**，包括真实金融双热 worker、目录 / 父目录软链、发布成功及失败分支。[日志](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-ea7e113e-evidence/targeted-tests.log)。未跑全量。
- 所有额外索引均由临时两页源和离线 hash 编码器生成。发布只调用本地内存 stub；未连接 Gitea 发布网络、未改生产 `uchg` / hooks / 8792。

## 上轮问题关闭证据

| 原问题 | ea7e113e 独立结果 |
|---|---|
| 受管未批准 / 退役代缺绑定仍能 query | 原探针主体不改，两个真实 CLI 均非零拒绝，错误为 `managed index requires a complete approved manifest startup binding`。 |
| `RagStore.save(None)` 默认写旧树 | 原调用在共同 writer 内抛 `MaintenanceError: direct writes require an explicit scratch index`，默认目录不存在。原始脚本因此提前退出 1，这是预期拒绝，不是产品回归。 |
| `--root` 指向旧输入索引先写后拒绝 | 原探针不改：`generation root must be outside source and input index trees`，**新增 0 条目**、删除 0 条目；原为新增 65。 |

原始失败 / 修复结果分别保存在旧、新目录。原脚本先原样执行，见 [原始运行日志](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-ea7e113e-evidence/original-boundary-probes.log)。为了保留其预期异常前的两个 CLI 退出码，另用外层捕获器执行同一份原始字节（记录源 SHA256，不改主体或期望），见 [replay-results.json](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-ea7e113e-evidence/original-boundary-replay/replay-results.json)。根重叠见 [results.json](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-ea7e113e-evidence/original-root-overlap/results.json)。

## 仍需修正

### [P2] 控制文件本身的软链没有被读取边界拒绝

规格第 6 项要求“启动器只读取一个已批准manifest”，第 7 项明确包含“路径换链”故障注入。目录 canonical 检查不等于控制文件身份检查。

[maintenance_io.py:42](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-ea7e113e-tree/skills/lib/rag/maintenance_io.py:42) 的 `read_json()` 直接使用 `Path.read_bytes()`。`resolve_startup()`、`assert_worker_current()` 与批准回执验证经此读取 current / approval，但未对文件本身执行已有 `stable_read()` 的软链与稳定身份校验。

临时完整已批准代中，分别把 `current.json`、`approvals/one.json` 换成指向根外同字节副本的文件软链：`verify_manifest()`、`resolve_startup()`、`assert_worker_current()` 仍全部通过。原本要求根内稳定控制文件的路径已被转移到外部可变目标。建议统一 `read_json()` 经 `stable_read()`，保留正常批准、启动、worker 与锁记录读取测试。

### [P2] 失去写锁 / 根目录身份后，异常分支仍会写失败记录

规格第 2 项：“真正副作用前获取锁”；第 7 项要求路径换链和失败恢复。成功路径有 `assert_writer()`，但 [maintenance.py:168](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-ea7e113e-tree/skills/lib/rag/maintenance.py:168) 的异常处理直接 `mkdir failures` 并写 JSON。

独立探针只替换临时 `update` 的故障边界：

- 持锁后将 `.writer.lock` 改名保留，原址放未知锁，再抛 `OSError`；仍创建 `failures/failed.json`。
- 持锁后将整个代际 root 改名保留，原址新建空目录，再抛 `OSError`；**替换后的新根**新增 `failures` 和 `failures/failed.json`。

两个案例旧 current 字节仍保留，原根恢复路径后旧 manifest 仍有效；问题是错误路径自身越过了单写者边界。建议异常落盘前先重检所有权；已失权时仅 stderr 报原异常及失权信息，不向替换根写“保留证据”。正常有锁失败仍保留现有失败回执。

### [P2] 上传期间标签改变后，发布终验仍记录成功

规格第 8 项要求标签绑定整代及 manifest，本轮明确要求远端回读校验。publisher 已检查创建后的标签 SHA，但只在 [publish_rag_index.py:100](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-ea7e113e-tree/scripts/publish_rag_index.py:100) 检查一次；上传 / 回读完成后的 [成功收据分支:118](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-ea7e113e-tree/scripts/publish_rag_index.py:118) 不重读 Git 标签。

沿作者的本地 transport fixture，仅给 `upload_asset` 外包一个故障：正常保存完整包后把 stub 的远端标签 SHA 改为 40 个 `f`。Release tag 名、notes、单资产名称 / 大小、包字节均保持正确，下载回读成功。实际 `main()` **exit 0**，回执 **`status=succeeded` / `uploaded_and_verified`**，但最终标签已经不是冻结代码 SHA。应在成功收据之前再次核对精确 tag SHA；不匹配按已有“远端可能存在、需检查”失败路径保留包 / 回执，不覆盖远端。

以上五个反例（控制文件 2、失权 2、远端 1）的完整原始数据：[additional-boundaries/results.json](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-ea7e113e-evidence/additional-boundaries/results.json)。探针：[probe_additional_boundaries.py](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-ea7e113e-evidence/probe_additional_boundaries.py)。根替换的实际误写目录另原样保存在 `lost-root/replacement-root-evidence`，未删除。

## 八项范围判定

1. 请求入口和所有已审旧 write 入口：上轮缺口关闭；显式 scratch 保留、默认保存拒绝、旧 publisher/fetch 不覆盖 current。
2. 单写者：正常锁与 root 预检通过；异常分支失权落盘仍需修。
3. 身份绑定：沿用上轮通过结论，增量无破坏证据。
4. 独立分母：沿用上轮通过结论，向量检查仍只是工程有效性，不冒充语义质量。
5. 本地发布门：沿用上轮通过结论。
6. 消费门：省略绑定、目录及父目录软链绕过关闭；控制文件软链仍需修。
7. 恢复：原半写 / 崩溃 / 旧 worker 故障通过；新增失权错误处理、控制文件路径换链需修。远端已有实际 transport 边界故障测试。
8. 远端资产：**已实现**显式批准 manifest、精确 repo/tag、单整代包、拒绝重建 / clobber / 已存在标签、远端资产和整包字节回读、失败保留；最后的标签身份终验需补。实际网络上传仍未授权且未执行；没有把这一限制误写成“无需实现”。

仅在这三项有界修复和独立复验通过后，才能将本轮 Spec 改为 PASS；生产切换、正式全量门禁及答案质量验收仍由对应工作流另行记录。
