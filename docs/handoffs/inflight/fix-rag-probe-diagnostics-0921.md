# 在途交接 · RAG 探针诊断与并发优化

## 这个分支做什么
安全诊断 + 同配置重叠 help 探针去重；保留单次 5 秒、无重试/成功缓存、失败 503。

## 决策与被否方案
- 选同 key single-flight，完成即删除；否了全局锁包慢 IO、成功缓存及延长超时。
- 保留查询依赖导入；否了全懒加载，前轮已证明坏依赖被 help 掩盖。
- key 绑定代码指纹/解释器/环境/预算，返回前复验；变化 code_changed，不输出原始错误或环境。
- API 字段白名单不变；否了额外 shared_inflight 字段。
- 理由/收据见 `../2026-09-21-rag-probe-singleflight.md`；前轮见 `../2026-09-21-rag-cli-startup-experiment.md`。

## 当前状态
实现已提交 3451c1d65，PR #844 仍 WIP，未合未部署。只改金融探针/测试/回放工具/门页；共享 KB 未改。K3/judge-off 未恢复，本轮无生产 HTTP、重启、行情写入、启动器修改或重发题。

## 已验证
提交后干净树定向组 230 passed/4 skipped（默认跨仓根未设），Ruff/diff check/pre-commit 通过。真实子进程故障/超时回收、双 HTTP 入口失败 503、不同配置并行、完成后重验已覆盖。两种内存变异分别被 6/1 项失败抓住。
两轮各条件 n=10：8 并发每轮子进程 8→1；批耗时中位 242→177ms、168→116ms；单请求未加速。慢/坏导入两版仍报 timeout/nonzero_exit。金融哈希匹配提交，KB 40 文件匹配固定 8a413cde。

## 未验证 / 已知边界
生产并发频率、历史超时根因、真实 BGE/自然检索质量、judge-off/fallback/恢复未验；全仓/前端/E2E/外审未跑。非严格冷启动，仅同进程去重；不检测解释器/依赖原地替换，仍需不可变部署。5 秒不是端到端截止时间。
证据 `tmp/rag-probe-singleflight/`，含 compare-v1/v2、postcommit-focused XML/日志及 mutations；postcommit-receipt 与 selected-manifest 核验 110 原件。私有本地归档勿删，前轮也保留。

## 下一步
审 PR 后等合并/部署授权；目标 tip 重跑适用门禁。不得借本轮采样宣称历史 timeout 已修复。行情一致性与 runtime 漂移另案。

## 踩过的坑
并行 pytest 自动收据同秒同 HEAD 会撞名，本轮以独立 XML/日志为准；提交后单独复验收据 20260921T154016Z-3451c1d6。KB HEAD 与 main 不同勿混用；help 成功不等于检索质量。adcda94b 本来支持 maintenance_launch，旧 runtime 为文件漂移，不能归因启动器自动恢复。
