# 在途交接 · RAG 探针诊断

## 这个分支做什么
为 RagCliProbe 补安全耗时/失败分类；继续定位帮助命令超时，不改变单次 5 秒失败语义。

## 决策与被否方案
- 保留单次 help、无重试/成功缓存、失败 503；否了抬超时和隐去错误。
- 只暴露固定分类/耗时，不输出 stderr、异常全文或环境。
- KB 懒加载只作隔离实验：虽更快，但坏依赖时帮助探针报兼容；否了作为“纯性能修复”合入。不是整个 readiness 报绿的证明。
- 保留 worker 模块导出，否了直接把所有导入搬进 query，避免绕过复用函数替换。
- 理由/收据见 `../2026-09-21-rag-cli-startup-experiment.md`；事故背景见 `../2026-09-21-rag-probe-diagnostics.md`。

## 当前状态
PR #844 保持 WIP，未合未部署。原诊断代码 ea5df3ea4，前次收据绑定 bac1b42a8；本轮仅新增回放脚本及测试，KB 候选未进入 Git/共享树。K3/judge-off 未恢复；本轮未重启、改行情库、改启动器或重发生产题。

## 已验证
金融定向组 178 passed/4 skipped；4 项默认未指定跨仓根。另显式指定新 KB 候选，跨仓+worker 51 passed（含那 4 项），仅证明合成索引路径。旧 KB 基线/候选 253/266 passed，新 KB 308/321 passed。Ruff、diff check 通过。候选启动合同在原基线预期 12 failed/1 passed。
两组各臂 20 次交替 help 采样；临时 hash 索引 CLI/连续 worker 一致。慢导入原探针 timeout；坏导入原探针 nonzero_exit，但懒加载候选 help 仍兼容、query 失败。

## 未验证 / 已知边界
历史超时根因未知；非严格冷启动，未证明生产兼容、真实 BGE 质量、长期稳定、judge-off、fallback 或恢复演练。全仓/前端/独立外审未跑。本轮未新查生产 HTTP；沿用前次记录不能当实时状态。新证据 `tmp/rag-cli-startup/evidence/selected-manifest.json` 及两份 final-*-pair/receipt.json；原件 0600，勿清理。

## 下一步
审诊断 PR 后等授权；若继续懒加载，先设计协议/运行时健康分层，并验证 worker 关闭/失败时仍可拒绝坏依赖，另开 KB 分支。合并后新 tip 需重跑门禁，不借实验收据部署。行情一致性与 runtime 漂移另案。

## 踩过的坑
KB 共享 HEAD 8a413cde 与本地 gitea/main d0caf311 不同，不能混用；副本各 40/45 个 Python 文件已对 Git 核验。help 成功不是检索可用。Git adcda94b 本来支持 maintenance_launch，旧目录是文件漂移；recovery 来源不能归因启动器自动创建。
