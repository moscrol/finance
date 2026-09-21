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
