# KB guarded maintenance — 独立 Spec 审查（37437e1a）

结论：**此固定提交尚未满足八项最小验收，不应据此宣布维护链完成。** 两个新发现已用隔离探针复现：受管新代可借“无清单环境”走 legacy 查询豁免；底层 `RagStore.save()` 仍会默认回写代码根。另有作者已自报的根重叠预检，以及根代理已明确授权补齐的整代远端发布实现；后二者单独跟踪，不重复算作未知发现。

## 固定范围与方法

- 基线：`1254224be89e2c4974350b7f3e985dbedb5dc043`。
- 候选：`37437e1a377eaf30acb39ca6d16dcf44b131d914`。
- 独立 detached 树：[spec-37437e1a-tree](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-37437e1a-tree)，开始、测试后、探针后 `git status --short` 均空；未继续读取会漂移的作者树。
- 验收依据：[维护计划八项](/Users/a77/fwp-wt-open-work-spec/docs/handoffs/2026-09-18-kb-guarded-maintenance-plan.md:40)及用户附件“先维护链、保留生产保护、不切 8792”。
- 只读代码与独占临时小索引；全部使用确定性 `hash` 编码器，不下载模型、不调用模型、不连接发布网络。未操作生产索引、flags、hooks 或服务。
- 主仓解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。独立定向运行原封不动的 `skills/lib/rag/tests/test_guarded_maintenance.py`：**30 passed in 16.40s**；日志见 [targeted-tests.log](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-37437e1a-evidence/targeted-tests.log)。包含真实金融 `PersistentRagWorker` 双索引热查询、换代拒绝、关闭及重启；金融树固定在 `dca1bd6e73f443ca09d08ef0a6c8b9b2bb0018a9`。没有借用作者全量收据，也未另跑全量。

## 两个新发现

### [P1] 缺少清单环境时，受管新代被误当成 legacy 消费

规格原句：“启动器只读取一个已批准manifest，并固定代码根/wiki根/双索引绝对路径”（第 6 项）；“未批准代不能成为current”（第 7 项）。实现已经提供这个启动器，但真实查询入口的兼容分支仍能绕过它。

代码：[generation.py:130](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-37437e1a-tree/skills/lib/rag/generation.py:130) 只按 `RAG_GENERATION_MANIFEST` 与 `KB_RAG_GENERATION` 是否存在判断 legacy；新进程两者都没有就直接返回，没有检查实际 `RAG_INDEX_DIR` 是否位于 `.rag-generation.json` 管理的目录中。因而既不验证批准，也不检查 current。

复现使用真实冻结代码 CLI，未 mock 查询结果：

1. 用临时 `wiki/sources/order.md` 和 `raw/raw.md` 准备 `one`，保留未批准状态。
2. 清除清单相关环境，仅设置 `RAG_INDEX_DIR=<one>/standard` 和 `KB_VAULT=<one>/source/wiki`。
3. 运行 `<one>/code/scripts/rag_index.py query alpha --mode bm25 --json`，实际 **exit 0，1 个命中**。
4. 批准并激活 `one`，再准备、批准并激活 `two`，相同省略绑定的旧 `one` CLI 仍 **exit 0，1 个命中**。

这不是旧生产兼容所必需的行为：目标已有受管 marker。迁移时漏配清单变量会使审核和换代门失效。应按最终解析的索引目录检测管理边界，受管索引缺完整 manifest 绑定一律拒绝；无 marker 的旧生产只读模式可以保留。应覆盖目录软链、父目录软链和普通 / 全文两种选中目标。

证据：[原始结果](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-37437e1a-evidence/boundary-probes/results.json)、[未批准查询 stdout](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-37437e1a-evidence/boundary-probes/unapproved-generation.stdout.txt)、[退役查询 stdout](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-37437e1a-evidence/boundary-probes/retired-generation.stdout.txt)。复现主体：[probe_spec_boundaries.py](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-37437e1a-evidence/probe_spec_boundaries.py)。

### [P2] 共同保存接口仍允许无显式目标回写默认旧树

规格原句：“手动build/update和publisher/fetch也不得写current指向的目标；禁止默认回退旧树”（第 1 项）。CLI 已改成显式目标，但共同 writer 没有完全落实最后一句。

代码：[store.py:232](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-37437e1a-tree/skills/lib/rag/store.py:232) 仍计算 `out_dir or config.index_dir()`；[config.py:26](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-37437e1a-tree/skills/lib/rag/config.py:26) 无 `RAG_INDEX_DIR` 时返回代码根 `.rag_index`。之后 `assert_index_writable()` 对未带代际 marker 的旧目录放行。公开的 `RagStore.save()` 因而保留原默认写入路线。

独立探针清掉 `RAG_INDEX_DIR`，仅把进程内的 `config.REPO_ROOT` 指向探针自己的空目录，调用真实 `RagStore.load(临时标准索引).save()`，实际创建 `.rag_index` 及 **11 个索引文件**。没有改候选文件或触碰真实旧索引。此处证明的是写入目标仍被默认推断，并非声称绕过生产 `uchg`。

建议在共同保存接口先调用 `explicit_index_target(out_dir)`；无参数且无显式环境目标时须在 mkdir / 写文件前拒绝。显式 scratch 与锁内受管候选路径应继续可用。原始证据与探针同上，记录名 `library-implicit-old-tree`。

## 八项验收逐项结论

| 项 | 此提交结论 | 依据与边界 |
|---|---|---|
| 1 请求入口 | 部分满足 | hook / ingest 仅入队；CLI build/update 与单索引 publisher/fetch 的退役守卫有效；共同 `save(None)` 留默认写回缺口。 |
| 2 单写者 | 核心锁满足，整体前置门待补 | `flock` 按根绑定、PID / 启动身份记录、SIGKILL 后恢复、未知锁和 inode 替换拒绝均有通过收据；根重叠仍先产生副作用，见下一节。 |
| 3 身份绑定 | 在独立根配置下满足 | 代码 SHA + 实际字节清单、解释器及依赖身份、冻结源清单、两份各自继承配置；新候选路径与双份失败阻断通过。 |
| 4 验收分母 | 满足本轮工程约束 | chunking 前枚举允许文件集合，再逐份核实块 / 隔离集合；非空零块、缺块、NaN 向量、伪证据均拒绝。逐行向量验证为形状 / 有限 / 非零检查，不代表语义向量质量评测。 |
| 5 发布门 | 本地候选门满足 | 双份、精确冲突字节和显式健康问题名单、真实独立进程正负例后才生成 manifest；失败 seal 无法批准；冲突保留 degraded。 |
| 6 消费门 | 未满足 | 完整绑定路径的标准 / 全文真实热 worker 测试通过，但无绑定 legacy 分支允许受管未批准和退役代直接查询。 |
| 7 恢复 | 部分满足 | 第二份失败、半写、崩溃、锁遗留、路径替换、源变更、带绑定旧 worker 拒绝均通过；远端传输尚无实现，现有“拒绝上传”测试不能替代实际发布失败注入。 |
| 8 远端资产 | 尚未满足，已授权补实现 | 此 SHA 仅 approved local pack，旧 publisher / fetch 拒绝。未实现显式 repo/tag、标签与整代包 / manifest 绑定的安全发布；见范围澄清。 |

## 已知工作项与范围澄清

根重叠由作者主动自报，独立复验确认：`prepare --root <legacy-standard>` 最终报 `input index changed during maintenance`，但旧输入目录已新增 **65 个条目**，包括 `.writer.lock`、候选代码 / 资料 / 双索引及失败记录；原条目未删除。源于 [maintenance.py:78](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-37437e1a-tree/skills/lib/rag/maintenance.py:78) 与 86–91 行的创建顺序。修复需在 root 创建 / lock 写入之前拒绝根与代码、源、旧索引、已受管代重叠，并保留合法独立根。证据：[root-overlap/results.json](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-37437e1a-evidence/root-overlap/results.json)、[独立探针](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-37437e1a-evidence/probe_known_root_overlap.py)。

第 8 项最初被根代理派发为“guard 或计划面”，作者按该授权交付了 local pack，因此不能归因为作者擅自漏做。根代理现已按用户原八项授权补安全整代发布实现：明确批准 manifest、单个完整代包、显式 Gitea repo/tag、tag 绑定 manifest、禁止旧 build / 单份覆盖 / 隐式 latest；仅本地 stub 故障测试，不执行真实网络上传。**“未授权实际上传”限制的是执行动作，不能用来把必要实现和失败恢复测试标成已满足。**

未发现需另行列出的 scope creep。此报告保存 37437 的失败状态，后续固定修订须另写复验报告，不能覆盖这里的反例。
