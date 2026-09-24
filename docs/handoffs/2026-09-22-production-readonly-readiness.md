# 生产只读核验：行情一致性仍阻塞，RAG 未获上线结论

## 范围与采样

用户授权执行生产只读核验，不改配置、不重启、不部署、不重发生产题。核验窗口跨过午夜，封存收据时间为 2026-09-22 00:17:26 +08:00。

工作分支 `fix/rag-probe-diagnostics-0921`，采样时 HEAD `18c621579`。生产仍运行 `adcda94b5e401158f1c3aa51f210e1e8d0f0b713`，不是本分支的 single-flight 实现。此次只新增证据和交接文档，不修改业务代码。

本地证据目录：`tmp/production-readonly-20260922/`，目录权限 0700，采样产物 0600。原始 help 输出、日志尾段、健康响应、代码清单及结构化结果均留存本地，不提交原件。

## 按发现顺序

1. **服务存活，但 health 不是 readiness。** 端口 8792 的服务 PID 3095，启动于 9 月 21 日 21:26:33；`GET /api/health` 返回 healthy，依赖存在性检查全部为 true。该接口不证明真实检索和市场数据就绪。
2. **readiness 有写侧行为，本轮没有调用两个 readiness URL。** 生产 `intelligence/api/app.py::health_ready` 会调用 `rag_worker.ensure_recovery()`，并创建 run store 目录；worker 死亡时可能启动恢复。因此不用 GET 的方法名推断它只读，改为从文件、进程和只读数据库复算。
3. **当前行情一致性判据为 false。** 生产模式 `ASK_CONTINUOUS_RUNTIME=on`。主库五张关键事实表的最大交易日均为 2026-09-18；快照 served/requested 日期为 2026-09-21。生产判据要求主库日期不早于快照，这一项已经足以阻塞 readiness，但不能断言它是唯一失败项。
4. **行情未推进的直接失败链可追溯。** 9 月 21 日 18:30 的 S7 staging 同步里，`sync-stock-daily-snapshot` 经 `sync_eastmoney_stock_snapshot.py::_get_json` 取数据时发生 `http.client.RemoteDisconnected`。同步自身已有第二次尝试，也失败；当日个股行情为零，板块/统计/派生步骤连带失败。18:36:35 同日质量门未通过，日志明确记载不替换生产库、保留 staging。20:50:08 finalize 再次因同步数据不完整而中止；资金流步骤亦报告当日行情缺口。未发新外部数据请求，不能据此确认供应商当前状态或断连的网络根因。
5. **快照通过现有契约，不等于所有字段完整。** 用生产版本的 `validate_market_snapshot_root` 只读校验，结果 PASS/ready。快照有 52 个题材和 103 个强势股，但 `market.amount_ratio=null`、`capacity_top3=[]`，并保留上游连接失败记录。此次只确认当前程序的判据，不为快照质量或供应商结果作额外背书。
6. **运行代码没有发现本次可观测的漂移。** health 的代码指纹由 create_app 在启动时计算，不是请求时重算。本轮另外复用生产指纹函数重新哈希当前 `intelligence/`，结果与启动时一致；生产 runtime 的受跟踪文件状态干净。代码目录、软链及进程 cwd 都指向 `finance-workspace-adcda94b5e40-recovery-20260921`。不覆盖第三方依赖原地替换或进程内动态修改。
7. **模型尚未切换。** health 的 agent runtime 为 `continuous_glm` / `glm-5.3-flash`；进程环境的通用 `LLM_MODEL=glm-5.3` 不是本轮实际写手证明。`ASK_SEMANTIC_JUDGE` 未设置，生产 `semantic_judge_mode()` 的缺省值为 llm，未关闭模型判官。没有发模型请求，不声称观测到了实际判官调用。
8. **RAG 仅有有限正向证据。** worker 子进程 PID 3299 仍存活，从生产 runtime 的 `rag_query_worker.py` 加载共享 KB；服务 Python 为 3.12.13 / `.venv-workbench`，worker 使用 KB `.rag_venv` 对应的 Python 3.14。没有进程内只读 worker 状态端点，本轮不启动新的 worker、不向它发 query，故 active/state/查询计数/当前检索质量仍未知。RSS 不当作模型是否加载的依据。
9. **单次 help 通过，未重试。** 使用当前 KB 解释器和 `scripts/rag_index.py query --help`，5 秒预算，退出码 0，309.335ms；四个必要参数齐全，五个可选过滤/receipt 参数仍缺。通过 macOS sandbox 禁止文件写和联网，并关闭字节码写入；只传生产环境里的路径/标量子集，加离线标记，因此不是原生产 HTTP 的等价重放。help 只经过导入和参数解析，不加载真实检索结果。n=1 不证明历史间歇超时消失，也不验证 single-flight 性能。
10. **索引元数据对齐，不等于内容新鲜。** KB HEAD 为 `8a413cde59cd0d6a7757c845243024a3016b50bc`；索引标记 BGE-m3，构建于 9 月 18 日，169635 块。向量与 BM25 倒排元数据的块数和来源指纹一致，未加载完整索引来验证载荷。KB 保留未提交内容及未解决实体冲突，未触碰。`source_dirty=true` 不能单独推出整库拒答：当前 KB 按切块/年龄作整库判定，再对命中页核验内容；金融旧 `check_rag_readiness.py` 的 dirty-source 判据不作为本次生产检索结论。
11. **日志不足以归因 RAG timeout。** 已有访问日志末段出现 readiness 503，但未带逐次失败 body 和可靠逐行时间，不能定位原因。stderr 中 PID 3095 启动标记之后只有启动信息，没有 timeout 或 maintenance_launch 错误记录；旧错误在启动标记之前。生产旧探针不输出本分支的结构化失败字段，不能把未搜到 `nonzero_exit/code_changed` 当成功证明。

## 决策与被否方案

| 选用 | 未采用 | 理由 |
|---|---|---|
| 从当前生产判据复算行情一致性 | 直接轮询 readiness | 两个 readiness URL 都有恢复和目录写入副作用 |
| 当前代码指纹对照启动指纹和 Git 状态 | 只相信 health 的 code_matches_repo | health 指纹是启动快照，不是当前文件校验 |
| 单次、5 秒、沙箱 help | 重试求绿、延长预算、真实 query | 保留失败语义；真实 query 会写 KB access log，超出只读范围 |
| 标记 worker 进程存活、内部状态未知 | 用新进程调用 rag_worker.status | 新进程看不到生产单例，会给出误导状态 |
| 记录行情同步直接失败链 | 自动补库、挪快照日期或绕过一致性门 | 修数据需要单独授权；改标签不修事实缺口 |
| 索引只报元数据对齐、内容未验 | dirty-source 一票否决/声明整库健康 | 与现版按页新鲜度实现不一致；元数据不能证明内容 |
| 保持 RAG 与 K3/judge-off 分次变更 | 顺势部署或恢复模型切换 | 当前仍有硬阻塞，也没有目标 tip 的完整门禁和部署授权 |

## 收据与验证边界

- `receipt.json`：采样时间、当前生产身份、行情日期、help 结果、日志摘要、保护文件对照。
- `health.json` / `processes.txt`：服务自报身份与 OS 进程观测，不公开原始环境。
- `database-dates.json`：使用 `.venv-workbench/bin/python` 和 `duckdb.connect(read_only=True)` 查询五张 canonical fact 表。
- `snapshot-contract.json`：复用生产版本的纯读契约函数。
- `help-receipt.json` / `help.stdout` / `help.stderr`：单次 help 原件；失败不覆盖、不删除。
- `kb-code-before.json` / `kb-code-after.json`：CLI/RAG 代码 40 文件本轮前后相同。
- `protected-before.json` / `protected-after.json`：启动器、LaunchAgent、快照及两份索引元数据哈希相同；主库 size/mtime/inode 相同。这里不声称做过 3.7GB 主库内容哈希或排除一切并发写入。
- `*.raw-tail.log`：日志尾段取证；日志元信息带原始字节流哈希和 LF 行号。早期终端的 splitlines 还会拆 CR 进度行，不能直接把那种行号当文件行号引用。
- `manifest.json`：封存目录内原件的 SHA256 清单。

本轮没有运行全量、前端、E2E 或真实检索质量测试；没有业务代码变更。前轮 230 passed/4 skipped 仍仅属于 single-flight 的定向验证，不能移签为本次生产验收。

## 工具沉淀盘点

本轮使用已有 health、生产契约校验器和代码指纹函数，没有新增产品接口或通用量具。`collect.py` 是绑定本机路径、PID 和时间窗的一次性证据收集器，保留在私有目录以便追溯，不晋升为部署工具；泛化需要配置输入、脱敏和副作用边界的专门测试，超出本次只读核验。可迁移原则已有实例：GET 不保证纯读，启动快照不保证当前状态，进程存活不保证载荷可用。未修改跨仓工具底座或能力图谱，因本轮没有新增运行时能力。

## 下一步与禁止项

1. 将行情链作为独立阻塞处理：先在独立任务确认当天完整行情的合法可用来源；若授权修复，保留失败 staging 与收据，通过 daily-full 正门重跑质量门，不手工推进日期或直接替换生产库。
2. PR #844 继续等待独立审查和明确合并授权；目标合并 tip 重跑完整适用门禁。此次只读核验不是批准合并或部署。
3. 获授权后单独部署 RAG 诊断/并发去重，受控验证真实 query、worker、失败分类与回退，再另行授权 K3/judge-off。
4. 不修改共享 KB 冲突、不重建索引、不调用带恢复行为的 readiness、不重发生产问题，不用本次 309ms 单点证明 timeout 已修复。
