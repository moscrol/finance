# RAG 启动恢复与安全诊断

## 这个分支做什么
修复 worker 已自愈而全局启动失败仍阻断 readiness；保留安全的预热/子进程退出原因。

## 当前状态
独立树 `~/fwp-wt-rag-recovery-state-0923`，基线 `gitea/main@bbd53487f`。
代码提交 `6c26041cb6600e43264603e6df8b56e20e44f4f5`；本篇与日期快照为后续文档。
未推送、未开 PR、未合 main、未部署。主脏树和冻结 runtime 均未改。
8792 15:17 附近复核仍为 `3b7e473575b0`，health/readiness 200、无关键缺项、任务为空。

## 决策与被否方案
- 配置/构造错误留启动层；已注册实例独占运行失败，API 不重复记账。否掉任一成功就清全局，防掩盖其他错误。
- 原 selector 同时排空 stdout/stderr，私有尾部限 4096 字节；公开仅阶段/固定原因/退出码/白名单类型，不透出原文。
- 保持混合检索、代际绑定、保活和超时策略；不放宽 readiness、不改索引、不自动修无实例配置。
- 详细背景/方案与命令见 `docs/handoffs/2026-09-23-rag-recovery-state.md`。

## 下一步
独立审查，按最新 main 重验组合及完整合入门禁，用户确认后才合并。
部署须另取固定候选收据及真实探针；不得把本次假 KB 的 HTTP 恢复当生产模型验收。
#874、#858/#867、Engine B answer_status 另案，未收口。

## 未验证 / 已知边界
本候选全量 Python、前端/E2E/完整 registry 未跑；无独立审查、真实 BGE 模型或自然会话验收。
未知异常类型/被截断错误行诊断为 null；普通查询响应合同不变，stderr 仅请求等待时排空。
未部署，不改变此前线上历史失败或金融质量结论。

## 已验证
固定干净 `6c26041cb`：413 passed（新增17），0失败/错误/跳过；全仓 Ruff、提交钩子通过。
收据 `~/.finance-runtime/test-receipts/20260923T071402Z-6c26041c-53033ec65c38.json`。
新增7组、旧管道9组撤保护均红→绿；各基线/还原整套17P、78P。
原件 `~/.finance-runtime/reviews/rag-recovery-state-0923/6c26041cb/{startup,transport}-mutations/`，complete=true。

## 踩过的坑
同时改 module 与 API 的重复失败锁存，否则内部 ready 仍会 HTTP 503。
管道测试替身必须返回 selector 事件结构；循环缩进变化需更新旧变异锚点。
真实 BrokenPipe 测试关闭 stdin 可再抛同类错误，仅测试清理容忍。无本轮残留子进程。
