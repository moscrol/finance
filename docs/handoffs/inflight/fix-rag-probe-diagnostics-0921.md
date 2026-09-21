# 在途交接 · RAG 探针诊断

## 这个分支做什么
为 readiness 的 `RagCliProbe` 补安全、结构化的耗时与失败分类，定位间歇超时；不改变 5 秒失败语义。

## 决策与被否方案
- 保留单次 `query --help`、5 秒上限、无重试、无成功缓存；否了抬帽/重试/缓存绿结果，避免把故障掩掉。
- 失败只暴露固定分类和耗时；否了原始 stderr、异常文本、完整命令环境，避免凭证/路径泄漏。
- elapsed 包含启动与清理，不能当端到端检索耗时；手造 probe receipt 的耗时仍可为 null。
- 本分支只做诊断，不自动合并、切 K3、关判官或重发生产两题。

## 当前状态
已提交并推送 `ea5df3ea49f3ee19657aacec73d1889506b8e15a`，分支 `fix/rag-probe-diagnostics-0921`，工作树干净。PR 尚未合并。生产当前仍为回滚版 GLM-5.3-flash，judge-off/K3 未上线。

## 已验证
净化环境定向组：172 passed、4 skipped；跳过项均是未显式提供 `KB_RECEIPT_CODE_ROOT` 的跨仓验收，不能代表生产兼容。ruff、diff check、pre-commit 全过。故障注入覆盖配置/缺脚本/OSError/非零/超时/协议缺项、503 及无成功缓存；超时子进程可被回收。
生产只读复核：health 200；readiness 503 仅 `market_data_consistency`，RAG available、required protocol 兼容、legacy optional warning。期间发现旧 runtime 的 `run_store.py` 不识别 `maintenance_launch`；日志证明该路径启动失败。部署台账随后记录了同 revision 的干净 recovery 树切换/启动，但不能据此断言是启动器自动构造；未改生产数据/启动器。

## 未验证 / 已知边界
历史 RAG 超时根因仍未知，当前采样未复现；未做真实检索成功、长期稳定性、自然 KB 候选 judge-off、fallback 或答案质量验收。4 个跨仓测试仍未跑。恢复成功不等于旧运行目录漂移问题已修复。

## 下一步
先审 PR 与提交文件，再由用户明确授权合并。合并后须为新候选重新做门禁和一次有界部署验收，不能借本分支收据自动切换。另开独立任务审计 launchd/runtime 快照的 Git HEAD、dirty 状态与回滚时的数据格式兼容。

## 踩过的坑
health 的 source revision 不能单独证明实际加载文件无漂移；旧 runtime 目录可与其 Git HEAD 不同。不要把 recovery 树的出现归因给启动器，先以 deploy-ledger 与启动器源码分别核对。readiness 的 RAG legacy warning 与 critical failure 是两层，不要把 optional 缺项写成不可用。
