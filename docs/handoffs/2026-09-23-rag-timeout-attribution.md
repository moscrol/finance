# RAG 超时诊断与固定组合门禁

## 身份与结论

- 分支 `fix/rag-recovery-state-0923`，工作树 `/Users/a77/fwp-wt-rag-recovery-state-0923`。
- 代码候选 `bffb098c3b4ae943e226d89a6d3f3794b5bc43e3`，包含收尾 fetch 仍为最新的 `gitea/main@0525e780e0435d44d0f47455ef604325e1a65258`。
- 本轮新增诊断插件提交 `fc62694014b25dac110cc7a104cfd7f48160fd55`。没有再改 RAG 生产逻辑、超时、readiness 或生产配置。
- **HOLD**：固定组合工程门禁通过，不等于历史超时已归因、独审完成或生产验收通过。未 push、开 PR、合 main、部署。
- 旧 `d29d554f1` 的相关 430P/1F、管道变异基线 80P/3F 原件保留；本轮绿色收据不覆盖或改签它们。

## 按发现顺序

1. 先重建代码地图，核对独立树、指定解释器及旧失败现场。原四例均在首次预热或代码换代后的查询等待中发生 2 秒/3 秒超时，具体阻塞原因仍未知。
2. 新增 `scripts/review_probes/rag_startup_trace.py`，只在显式加载 pytest 插件时启用。记录进程创建、ensure、请求写入、管道读取、截止触发和过滤后的 Python 导入耗时，不保存请求/响应正文或环境值。输出目录必须全新，避免覆盖现场。
3. 原四例保持原超时做一次诊断运行，4P；七次进程启动到首响应约 0.21-0.33 秒。另一次假 KB 启动剖析约 0.68 秒。没有重现原超时，不能据此宣称修好了根因。
4. 固定 `fc6269401`：相关十文件 431P，启动恢复 14 组、管道 12 组变异均红后还原绿；前端全链及 registry 四项通过。它们的收据仍只署名 fc。
5. 拉取发现 #887 新增夜跑固定代码根修复，合入当前分支得到 `bffb098c3`。四处主干变化是 sync/finalize plist、S7 默认根及对应测试；RAG 源码、测试和变异定义与 fc 逐字节一致。没有修改装机配置。
6. 固定 bff 后重验完整工程门禁，见下表。较重的 Python、前端、两组变异串行执行。完整 Python 启动前可用内存约 46%、磁盘约 34 GiB；同时存在其他任务，未中止他人进程。交换空间占用不作为历史超时根因。

诊断用法：指定解释器运行 `-m pytest -p scripts.review_probes.rag_startup_trace --rag-trace-dir <全新目录> <精确测试node-ID>`。导入剖析与同步写日志会增加开销，因此与正式门禁分开运行，不把其用时作为性能结论。

## 方案与取舍

| 方案 | 结果 | 理由 |
| --- | --- | --- |
| 延长原 2 秒/3 秒超时或循环跑到绿 | 否 | 会改变原条件，不能填补归因证据 |
| 看到高 swap 就判定资源是根因 | 否 | 占用可能是历史状态，缺失败时刻的事件时序和对照 |
| 显式启用分阶段诊断，再独立跑正式门禁 | 采用 | 提供后续复现的观察点，同时承认观测开销 |
| 把原始 stderr、查询或环境整体落日志 | 否 | 归因不需要正文，避免扩大敏感信息暴露 |
| 将旧 SHA 的绿收据改签新组合 | 否 | 固定新组合后实际重跑，保留两个版本各自原件 |
| 独审服务无报告时按无发现处理 | 否 | 容量/额度中断不是审查通过，本轮不再请求 |

## bffb098c3 固定工程收据

证据根 `E=/Users/a77/.finance-runtime/reviews/rag-recovery-state-0923/timeout-attribution-01/`。关键收据摘要在 `key-receipts.sha256`，逐项校验通过见 `key-receipts-verification.log`；这不是整个目录的封存清单。

| 检查 | 结果 | E 下原件 |
| --- | --- | --- |
| 全仓 Ruff + pytest | 14652P / 87S / 2X，0F / 0error，17 warnings，1804.53 秒 | `bffb098c3-full.log`、`bffb098c3-full.xml` |
| 干净、完整范围、解释器、依赖、精确 SHA、基座漂移校验 | 通过，14741 collected 无筛除；Python 3.12.13，依赖指纹 `3328bed61f3e21ea`，无门禁绕过 | `bffb098c3-full/gate-GXNmjX9C/pytest.json`、`bffb098c3-receipt-check.log` |
| 前端 install / lint / typecheck / test / build / E2E | 六项 exit 0；120 单测、34 E2E 通过，2 跳过；clean、identity_stable、complete | `bffb098c3-frontend/frontend.json` 及六份日志 |
| 启动恢复变异 | 14 组红后还原绿；基线/最终整套 29P；源码哈希还原 | `bffb098c3-startup-mutations/results.json` |
| 管道变异 | 12 组红后还原绿；基线/最终整套 83P；源码哈希还原 | `bffb098c3-transport-mutations/results.json` |
| registry 四项 | 全通过，三仓在场，61 个 SKILL frontmatter，无缺仓跳过 | `bffb098c3-registry-*.log` |

两个 E2E 跳过是同一研究绑定流程按配置只在桌面执行，非启动错误。前端隔离树 `E/frontend-tree` 固定 bff；测试服务结束、18991/18994 无监听。全仓门禁正常退出并自动清理本次通过的 basetemp，不是删除旧失败现场。

原超时四例在本次完整 pytest 中全部通过，单例总用时 0.660 / 0.576 / 0.624 / 0.249 秒；名字及结果见 `bffb098c3-original-case-timings.json`。这是单例总用时，不是诊断里的首响应指标，也不证明延迟改善。诊断原件为 `trace.log`、`trace.xml`、`trace/*.jsonl`、`startup-imports.log`。

## 生产与 CLI 观察分账

- 18:04:20 +08:00，8792 health200，仍为干净冻结版本 `3b7e473575b0`，加载/盘上代码指纹一致；不是候选上线。
- 同时 readiness503，1.005695 秒，唯一缺项 `market_data_consistency`：快照 09-23、主库 09-22；active/queued=0/0。RAG worker ready、model_load_count=1、recoveries=0，CLI 必需协议项通过，保留 legacy 可选参数警告。
- 当天 17:23 同样仅行情一致性红；不能用这两次成功探测抹去旧 16:43 超时及 16:45 CLI 协议探测红。原件 `production-*`、`closeout-*`，旧失败仍在 d29 证据根。
- 在 KB 根直接执行一次 `rag_index.py query --help` 的离线只读导入剖析，real 0.83 秒；macOS sandbox 拒绝网络及文件写入，未加载模型、更新索引。原件 `cli-help.stdout`、`cli-help-imports.log`。它不是对生产探测超时的故障复现或根因证明。
- 装机调度为快照 16:15、主库同步 18:30、finalize 20:40。观察时尚未到正式同步，不能断言当晚同步失败；未提前跑夜跑、手写生产 SQL 或修改日期。

## 未完成与接手

1. 历史测试超时和生产 CLI 超时均未归因；出现可复现场景时启用时序诊断，不加时求绿，不关闭 RAG 或降门槛。
2. 独审仍无正式报告。两次旧请求容量/额度失败保留；最近服务提示 21:27 后再试，本轮没有新增请求。作者自查与变异测试不代签独审。
3. 候选尚未做真实 BGE hybrid 冷/热查询及 Workbench 同用户同题自然会话验收；假 KB、浏览器测试不证明金融质量或模型性能。
4. 正式夜跑后再复核行情日期和有效值；用户确认后才能合 main、走独立冻结快照与可回滚部署。若届时 main 已变，先固定新组合并取得对应收据。

工具盘点：诊断插件已入本仓 scripts，并通过原四例实际启用验证；依赖项目 worker 内部接口，不包装成跨仓通用工具。可迁移的分阶段留证、观测与发布分账原则补入共享 `kill-on-timeout-is-an-amplifier.md`。旧交接见 `2026-09-23-rag-duplex-request-deadline.md`；后续文档提交不改变上述代码收据身份。
