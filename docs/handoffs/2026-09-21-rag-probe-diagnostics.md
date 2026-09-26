# 2026-09-21 RAG 探针诊断决策快照

## 背景
生产曾出现 RAG capability probe 间歇超时，随后回滚 K3/judge-off 部署。回滚前后都曾观察到超时，但本轮固定的 10 次 CLI help 采样与 12 次 readiness 采样未复现，不能把导入耗时、负载或回滚恢复说成根因。

## 发现顺序与选择
1. 调用链确认 readiness 每次启动 `rag_index.py query --help`，默认 5 秒；CLI 在 parse 参数前 eager import 检索模块。已有 profile 只能说明一次 import 成本，不能证明生产尾部。
2. 选择在 `RagCliProbe` 记录 `elapsed_ms`、`timeout_seconds` 和固定 `failure_kind`，并把字段纳入 API 序列化。分类覆盖 configuration、missing_script、timeout、os_error、execution_error、nonzero_exit、protocol_incompatible。
3. 保留原判定：required 参数缺失才不兼容；optional 缺失仍是 legacy 可用。没有加入重试、成功缓存、提高 5 秒帽或改变 HTTP 503 语义，因为这些会改变故障信号。
4. 故障注入验证成功/失败序列、超时子进程回收、API 503、字段脱敏和 exactly-one invocation；两次临时变异均按预期被测试击穿并已恢复。
5. 生产只读复核时 8792 曾连接拒绝。日志显示旧 runtime 目录中的 `run_store.py` 不认识已写入 run JSON 的 `maintenance_launch`；部署台账随后记录了同 revision 的干净 recovery 树切换与启动，health 重新 200，readiness 只剩既有 `market_data_consistency` 红。不能从这些记录断言 recovery 树由启动器自动构造；旧目录当前有大量未提交漂移，也没有编辑该目录。

## 验证与结论
提交 `ea5df3ea4` 已推到 `fix/rag-probe-diagnostics-0921`。净化环境定向测试 172 passed/4 skipped；跳过是未显式设置 `KB_RECEIPT_CODE_ROOT` 的跨仓集成，不是通过。ruff、pre-commit、diff check 通过。结论仅是“诊断信息可安全落盘并有故障注入保护”，不是“历史超时已解释”或“生产可重新切换”。

## 后续与禁做
先审阅 PR，合并必须另获授权；合并后按新 tip 重建门禁、候选快照和一次有界部署验收。不要重发此前两道生产题，不要用当前 recovery 成功翻案原部署失败，不要把 health 的 revision 字段单独当作实际加载树完整性证明。runtime 快照 dirty/格式向前写入导致旧回滚不可读，应另立兼容性与部署产物审计任务。

## 收尾订正与证据索引
- 上段的“格式向前写入”不能解释为 adcda94b 提交本身不兼容：Git blob 中本来就含 maintenance_launch。旧目录当前 run_store.py 的 SHA256 为 130c906c562cc0acdec02eeaa9387b1bfcf6046ef900e3a48baad1c3b0d4d70d，Git blob/干净 recovery 树均为 b816a5153b83c771032ac9839a814a224197c83b0eb086c2843431c601e36ca4。已证实的是启动失败时文件与提交不符；未证明写者、改写时刻，不能回推 19:07 回滚时已脏。
- 启动器没有自动造 recovery 树的逻辑。deploy-ledger 的 21:26 switch/startup 和进程 3095 证明运行树被切换，不证明操作者身份。本诊断窗口没有执行切换。
- PR #844 已建，WIP、未合未部署；代码 ea5df3ea4，首份交接 9475a9b0b。链接：http://127.0.0.1:3300/a77/finance-workspace-private/pulls/844 。
- 本地证据根 `~/.finance-runtime/reviews/rag-probe-diagnostics-20260921/`：targeted.txt/xml、ruff.txt、mutation-drop-timing.txt、mutation-timeout-pass.txt；变异分别打红 3 项与 2 项，已恢复。它们不是独立审核收据。
- sampling-closeout/receipt.json 绑定 24 份原件哈希：10 个 help 计时、12 个 readiness 响应、2 个后续健康/就绪响应。早期 help 为 0.19–0.54 秒，12 响应仅行情红；没有同时绑定执行身份，也未保存这 12 次 HTTP 状态码/耗时，不回填臆测。归档时采集的 KB 身份只代表归档时刻。
- 工具沉淀：故障注入和变异保护已落正式测试；没有新建通用部署器或重复采样脚本。共享 harness 未改；采样与事故证据只作个案，不足升级为自动恢复规则。
