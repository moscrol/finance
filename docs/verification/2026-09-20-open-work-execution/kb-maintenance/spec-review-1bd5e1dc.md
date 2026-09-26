# KB guarded maintenance — 最终独立 Spec 复验（1bd5e1dc）

**Spec PASS。** 固定 `1bd5e1dc8d48f59461c79f35ea553e1cda71a6ec` 已满足本轮维护实现及隔离故障注入的八项最小验收。此前有证据支持的缺口均关闭，没有遗留 Spec 阻断项。此结论可交给独立 Quality 审查；不代替合并全量门禁，也不宣称生产切换或真实远端上传完成。

## 固定输入与独立收据

- 全需求基线：`1254224be89e2c4974350b7f3e985dbedb5dc043`；本次最小增量基线：`ea7e113e99dfc611252b5c629845e8d9c23dfc0c`。
- 候选：`1bd5e1dc8d48f59461c79f35ea553e1cda71a6ec`；[独立 detached 树](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-1bd5e1dc-tree)开始、测试后及终验均 clean。
- 本次增量为四文件，实际行为修正仅统一稳定 JSON 读取、异常落盘前重核 writer 身份、成功发布前重核远端精确 tag SHA；其余为回归测试。
- 使用主仓 `.venv-workbench/bin/python`、独占临时索引和外置访问日志，原定向文件未修改：**61 passed in 35.24s**。[测试日志](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-1bd5e1dc-evidence/targeted-tests.log)。其中实际金融 `PersistentRagWorker` 来自干净 `dca1bd6e73f443ca09d08ef0a6c8b9b2bb0018a9`，覆盖普通 / 全文热查询、换代拒绝、关闭旧进程及重启。
- 额外独立探针全部使用旧文件原始主体与原判据，输出新目录。机器断言再次读取原始结果并核候选身份：[verified-results.json](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-1bd5e1dc-evidence/verified-results.json)，包含原探针 SHA256；[判定脚本](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-1bd5e1dc-evidence/check_evidence.py) exit 0。
- 未跑全量、未改作者树或源码、未合 main。所有源为临时两页，hash 编码器无需模型；远端仅本地内存 transport stub。未操作生产索引、`uchg`、post-*、launchd、8792 或发布网络。

## 原反例逐项闭环

| 原反例 | 1bd5e1dc 实测 |
|---|---|
| 受管未批准代省略 manifest 绑定直接 query | 真实 CLI 非零拒绝，命中管理边界错误。 |
| 受管退役代省略 manifest 绑定直接 query | 真实 CLI 非零拒绝；完整合法绑定与真正 legacy 只读测试保留。 |
| `RagStore.save(None)` 隐式回写旧树 | writer 前抛明确错误，默认目录未创建；显式参数 / 环境 scratch 仍通过。 |
| root 与旧输入索引重叠 | 预检拒绝，新增 0 条目、删除 0 条目；原 37437 新增 65 条目。 |
| current.json 文件改成根外软链 | `MaintenanceError: symlink/alias path is not allowed`，拒绝读取。 |
| approval JSON 文件改成根外软链 | 相同稳定读取门拒绝。 |
| update 抛错前写锁 inode 被替换 | 不写失败文件；异常同时保留原 update 错误及失权原因；旧 current / manifest 仍有效。 |
| update 抛错前 root 被替换 | 替换根保持空目录，不写 `failures`；旧 current 保留，恢复原路径后旧 manifest 有效。 |
| 上传期间远端 tag 指向其他 SHA | publisher exit 1，回执 `failed`、`remote_may_exist=true`，保留本地整代包及“远端状态不确定”记录；不再标成功。 |

证据：[原消费 / 保存探针回放](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-1bd5e1dc-evidence/original-boundary-replay/replay-results.json)、[原 root 重叠探针](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-1bd5e1dc-evidence/original-root-overlap/results.json)、[新增五 case 原始结果](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-1bd5e1dc-evidence/additional-boundaries/results.json)。原 `save()` 探针在期望拒绝处抛错，回放只在外层捕获并核“未创建默认目录”，没有改原输入或放宽判据。

## 八项最终判定

验收原文：[维护计划最小八项](/Users/a77/fwp-wt-open-work-spec/docs/handoffs/2026-09-18-kb-guarded-maintenance-plan.md:40)。本表的 PASS 均限于代码实现与隔离验收。

| 项 | 结论 | 已核行为 |
|---|---|---|
| 1 请求入口 | PASS | hook / ingest 仅排队；共同 writer 无默认旧树回退；显式 scratch 保留；受管代拒绝直接 build / update / BM25 写入；旧单索引 publish / fetch 拒绝覆盖。 |
| 2 单写者 | PASS | 按代际根的进程 `flock`、PID / 启动身份记录、正常 / SIGKILL 恢复、未知锁与路径替换拒绝；根重叠在创建前拒绝，异常失权后也无写入。 |
| 3 身份绑定 | PASS | 同一代冻结代码 SHA / 实际文件字节、解释器 / 依赖及源清单；两份分别继承 model / include_raw / max_files；只写新候选，第二份失败不能以单份发布。 |
| 4 验收分母 | PASS | chunking 前枚举允许源，实际块 / 隔离集合逐份核对；非空零块、缺块、异常向量及伪证据拒绝。全部向量做形状、有限与非零检查；并未冒充语义质量评测。 |
| 5 发布门 | PASS | 双份、精确隔离名单 / 字节、明确健康例外和独立消费者正负例通过后才产 manifest；冲突保持 degraded，失败 seal / 候选不可批准。 |
| 6 消费门 | PASS | 单一已批准 manifest 固定代码、wiki、双索引与解释器环境；受管目录和别名缺绑定拒绝，current / approval 换链拒绝；真实双热 worker 换代拒绝、关闭旧进程后新代预热通过。 |
| 7 恢复 | PASS | 第二份失败、半写、崩溃、锁遗留、路径换链、冻结源变化、旧 worker 和远端 transport 失败均有定向证据；旧代保留，未批准代不能 activate；失权不再向未知根写失败文件。 |
| 8 远端资产 | PASS | 显式批准 manifest、明确 Gitea repo 与绑定 manifest 的精确 tag、单个完整代包；拒绝旧 build / clobber / 隐式 latest / 已存在标签；回读 Release / 资产 / 整包字节并在终验再次核 tag SHA，失败保留包与回执。未执行实际上传。 |

原始失败报告 [37437](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-review-37437e1a.md) 与 [ea7e113e](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-review-ea7e113e.md) 及各自原始探针、误写证据均保留。没有用这次成功覆盖之前失败，也没有把“代码可以安全执行”写成“生产已经执行”。
