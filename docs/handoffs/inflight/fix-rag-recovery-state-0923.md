# RAG 启动恢复与生命周期边界

## 这个分支做什么
修复失败状态重复锁存、安全子进程诊断，以及预热错误漏记、退役实例重生、管道注册漏清理。

## 当前状态
独立树 `~/fwp-wt-rag-recovery-state-0923`；已 rebase 到本轮 main `27ca084f9`。
代码候选 `52a9bceb62390212e41d6c31786d660161ad5463`，本交接为后续文档提交。
未推送、开 PR、合 main 或部署；主脏树、冻结 runtime、生产索引未动。
8792 仍指向 `3b7e473575b0`。15:58 左右一次 readiness 15s 超时，复查 health/readiness 200、
关键缺项为空，PID 58014/58612 未变；已记本机告警。超时根因未明，不代表资源有余量。

## 决策与被否方案
- 配置/构造错误归启动层；实例独占整段预热失败，API 不重复锁存。否掉任一成功清全局。
- stderr 与 stdout 共用 selector；私有尾部4096字节，仅公开固定原因/阶段/退出码/白名单类型。
- 保活启动完成才 ready；配方完整转换后替换。关闭在执行锁内复查，拒绝旧实例重生；允许新实例。
- 注册管道也受 finally 清理保护。不放宽混合检索/代际/readiness，不改超时策略或索引。
- 细节见 `docs/handoffs/2026-09-23-rag-recovery-state-followup.md`；初版同日快照保留。

## 下一步
独立审查，固定届时 main 组合候选，跑完整合入门禁；用户确认后才合 main。
部署另取真实模型/会话及 readiness/PID/cwd/账本证据。不要重复旧 cutover 或跑 rag update。
#874、#858/#867、Engine B answer_status 另案。

## 未验证 / 已知边界
作者复核不是独审。全量 Python、前端/E2E、完整 registry 未跑；本机有其他任务全仓门禁。
无新候选真实 BGE、自然会话、部署效果或资源余量验收；本轮未重做生产任务队列验收。
未知/截断异常诊断为 null；stderr 仅等待请求时排空。假 KB 的 HTTP 恢复不能当生产模型验收。

## 已验证
固定干净 `52a9bceb6`：421P，0失败/错误/跳过，本次新增8条；全仓 Ruff、提交钩子通过。
证据根 `~/.finance-runtime/reviews/rag-recovery-state-0923/52a9bceb6/`：
`related-receipt.json` 身份校验通过；startup/transport-mutations 各12/9组红→绿，
基线/还原整套25P/78P，均 complete=true。临时变异树已清理。

## 踩过的坑
测试文件是 `test_rag_worker_generation.py`；误写路径的零执行收据不得计入通过。
竞争测试用事件屏障，不靠 sleep；闭环必须同时验实例和真实 HTTP。
整合前旧 SHA 收据只属历史，不能改签新提交。共享记忆的无关并发改动不纳入本分支。
